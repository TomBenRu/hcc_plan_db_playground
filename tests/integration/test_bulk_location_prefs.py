"""End-to-End-Test: Person.update_location_prefs_bulk via API-Client.

Validiert komplexe Bulk-Op-Serialisierung:
  - dict[UUID, float] Request-Body (via list[LocationPrefEntry])
  - dict[str, list[UUID]] Response-Round-Trip
  - restore_location_prefs_bulk als Undo-Pfad

Service-Contract (aus person.update_location_prefs_bulk):
  - Rueckgabe: {'old_pref_ids': [...], 'new_pref_ids': [...]}
  - Score 1.0 wird als neutral ignoriert

Voraussetzung:
  - web_api laeuft (uvicorn web_api.main:app --reload)
  - Test-User existiert
  - DESKTOP_TEST_PROJECT_ID enthaelt mindestens 1 aktive LocationOfWork

Umgebungsvariablen wie test_address_round_trip.py.
Aufruf: python -m tests.integration.test_bulk_location_prefs
"""

import os
import sys
import time
from uuid import UUID

from database import db_services, schemas
from database.enums import Gender
from gui.api_client.client import get_api_client
from gui.api_client import person as api_person


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
    client.login(email, password)
    _ok("Token erhalten")

    print("2. LocationOfWork aus Project lesen (read-only)...")
    locations = db_services.LocationOfWork.get_all_from__project(project_id)
    active = [loc for loc in locations if not loc.prep_delete]
    if not active:
        _fail("Keine aktive LocationOfWork im Projekt")
    location = active[0]
    _ok(f"Location: {location.name} ({location.id})")

    print("3. Test-Person anlegen...")
    suffix = str(int(time.time()))
    test_person_create = schemas.PersonCreate(
        f_name="E2E",
        l_name=f"BulkTest{suffix}",
        email=f"e2e-bulk-{suffix}@example.com",
        gender=Gender.divers,
        phone_nr=None,
        username=f"e2e-bulk-{suffix}",
        password="testpass123",
        address=None,
    )
    created_person = db_services.Person.create(test_person_create, project_id)
    _ok(f"Test-Person: {created_person.id}")

    try:
        print("4. update_location_prefs_bulk: {location_id: 0.5} via API...")
        result = api_person.update_location_prefs_bulk(
            created_person.id, project_id, {location.id: 0.5},
        )
        if not isinstance(result, dict):
            _fail(f"Response ist kein dict: {type(result)}")
        if set(result.keys()) != {"old_pref_ids", "new_pref_ids"}:
            _fail(f"Unerwartete Keys: {sorted(result.keys())}")
        for k, v in result.items():
            if not isinstance(v, list):
                _fail(f"Key '{k}' ist keine Liste")
            for i in v:
                if not isinstance(i, UUID):
                    _fail(f"Key '{k}' enthaelt Nicht-UUID: {i!r}")
        _ok(f"Response: old_pref_ids={len(result['old_pref_ids'])}, "
            f"new_pref_ids={len(result['new_pref_ids'])} (alle UUIDs)")

        new_ids = result["new_pref_ids"]
        if len(new_ids) != 1:
            _fail(f"Erwartete 1 neue pref, bekam {len(new_ids)}")

        print("5. Verifikation via direktem DB-Read...")
        reloaded = db_services.Person.get(created_person.id)
        active_prefs = [p for p in reloaded.actor_location_prefs_defaults if not p.prep_delete]
        matching = [p for p in active_prefs if p.location_of_work.id == location.id]
        if not matching:
            _fail("DB zeigt keine aktive pref fuer Test-Location")
        if abs(matching[0].score - 0.5) > 0.001:
            _fail(f"Score ist {matching[0].score}, erwartet 0.5")
        if matching[0].id != new_ids[0]:
            _fail(f"Pref-ID Mismatch: DB={matching[0].id}, API-Response={new_ids[0]}")
        _ok(f"DB-pref {matching[0].id} mit score=0.5 passt zu API-Response")

        print("6. restore_location_prefs_bulk (Undo auf leere prefs)...")
        api_person.restore_location_prefs_bulk(created_person.id, result["old_pref_ids"])
        reloaded2 = db_services.Person.get(created_person.id)
        active_after_restore = [p for p in reloaded2.actor_location_prefs_defaults
                                 if not p.prep_delete]
        if len(active_after_restore) != 0:
            _fail(f"Nach restore zu leer: {len(active_after_restore)} prefs statt 0")
        _ok("Nach restore: 0 aktive prefs (leerer Original-Zustand wiederhergestellt)")

    finally:
        print("7. Cleanup: Test-Person hart loeschen...")
        db_services.Person.delete(created_person.id)
        _ok(f"Test-Person {created_person.id} soft-deleted")

    print("\n  Bulk-Op-Round-Trip bestanden: dict[UUID,float]-Request, "
          "dict[str,list[UUID]]-Response korrekt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())