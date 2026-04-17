"""End-to-End-Test: address_commands.Update via Desktop-API-Client.

Validiert den kompletten Stack:
  - DesktopApiClient.login() gegen /auth/login (JWT-Token)
  - api_address.update() gegen PUT /api/v1/addresses/{id}
  - Pydantic-Schema-Round-Trip (Address mit nested Project) über HTTP/JSON
  - Command-Pattern execute/undo/redo nach Migration auf api_client

Voraussetzung:
  - web_api läuft lokal (uvicorn web_api.main:app --reload)
  - Test-User (dispatcher-Rolle) existiert
  - Test-Projekt existiert

Umgebungsvariablen:
  DESKTOP_API_URL           (optional, Standard: http://localhost:8000)
  DESKTOP_TEST_EMAIL        Email des Test-Dispatchers
  DESKTOP_TEST_PASSWORD     Passwort
  DESKTOP_TEST_PROJECT_ID   UUID eines bestehenden Projekts

Aufruf:
  python -m tests.integration.test_address_round_trip
"""

import os
import sys
from uuid import UUID

from database import db_services, schemas
from gui.api_client.client import get_api_client
from commands.database_commands import address_commands


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def main() -> int:
    email = os.environ.get("DESKTOP_TEST_EMAIL")
    password = os.environ.get("DESKTOP_TEST_PASSWORD")
    project_id_str = os.environ.get("DESKTOP_TEST_PROJECT_ID")
    if not email or not password or not project_id_str:
        print("Env-Variablen fehlen: DESKTOP_TEST_EMAIL, DESKTOP_TEST_PASSWORD, DESKTOP_TEST_PROJECT_ID")
        return 1
    project_id = UUID(project_id_str)

    print("1. Login gegen Web-API...")
    client = get_api_client()
    try:
        client.login(email, password)
    except Exception as e:
        _fail(f"Login fehlgeschlagen: {e}")
    if not client.is_authenticated:
        _fail("Kein Token nach Login")
    _ok(f"Token erhalten (Base: {client._base_url})")

    print("2. Test-Adresse via DB anlegen...")
    create_payload = schemas.AddressCreate(
        name="E2E-Test", project_id=project_id,
        street="Teststr. 1", postal_code="12345", city="Teststadt",
    )
    created = db_services.Address.create(create_payload)
    _ok(f"Adresse angelegt: {created.id}")

    try:
        print("3. Update-Command execute() (schreibt via API)...")
        current = db_services.Address.get(created.id)
        modified = current.model_copy(update={"street": "Neue Str. 42", "city": "Neustadt"})
        cmd = address_commands.Update(modified)
        cmd.execute()
        after_execute = db_services.Address.get(created.id)
        if after_execute.street != "Neue Str. 42" or after_execute.city != "Neustadt":
            _fail(f"execute(): street={after_execute.street!r}, city={after_execute.city!r}")
        _ok("Update erfolgreich (street + city aktualisiert)")

        print("4. Update-Command undo() (schreibt via API)...")
        cmd.undo()
        after_undo = db_services.Address.get(created.id)
        if after_undo.street != current.street or after_undo.city != current.city:
            _fail(f"undo(): street={after_undo.street!r}, city={after_undo.city!r}")
        _ok("Undo erfolgreich")

        print("5. Update-Command redo() (schreibt via API)...")
        cmd.redo()
        after_redo = db_services.Address.get(created.id)
        if after_redo.street != "Neue Str. 42" or after_redo.city != "Neustadt":
            _fail(f"redo(): street={after_redo.street!r}, city={after_redo.city!r}")
        _ok("Redo erfolgreich")

    finally:
        print("6. Cleanup...")
        db_services.Address.delete(created.id, soft_delete=False)
        _ok("Test-Adresse hart gelöscht")

    print("\n  Alle Tests bestanden. Der Stack funktioniert end-to-end.")
    return 0


if __name__ == "__main__":
    sys.exit(main())