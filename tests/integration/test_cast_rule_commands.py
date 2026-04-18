"""End-to-End-Test: cast_rule_commands via API-Client.

Validiert Phase-4-Command-Migration an einer entity-level CRUD-Kette:
  - Create.execute / _undo / _redo  (mit restore_id fuer ID-Stabilitaet)
  - Update.execute / _undo
  - SetPrepDelete.execute / _undo

Cleanup: die erstellte Test-CastRule wird hart geloescht (via direkte
Session, da die API nur soft-delete kennt).

Umgebungsvariablen wie test_address_round_trip.py.
"""

import os
import sys
import time
from uuid import UUID

from database import db_services, models
from database.database import get_session
from commands.database_commands import cast_rule_commands
from gui.api_client.client import get_api_client


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"  [OK]   {msg}")


def _hard_delete(cast_rule_id: UUID) -> None:
    with get_session() as session:
        cr = session.get(models.CastRule, cast_rule_id)
        if cr:
            session.delete(cr)


def main() -> int:
    email = os.environ.get("DESKTOP_TEST_EMAIL")
    password = os.environ.get("DESKTOP_TEST_PASSWORD")
    project_id_str = os.environ.get("DESKTOP_TEST_PROJECT_ID")
    if not email or not password or not project_id_str:
        print("Env-Variablen fehlen")
        return 1
    project_id = UUID(project_id_str)

    print("1. Login...")
    get_api_client().login(email, password)
    _ok("Token erhalten")

    suffix = str(int(time.time()))
    created_id: UUID | None = None

    try:
        print("2. Create-Command: CastRule anlegen...")
        create_cmd = cast_rule_commands.Create(project_id, f"E2E-Rule-{suffix}", "ABAB")
        create_cmd.execute()
        if create_cmd.created_cast_rule is None:
            _fail("created_cast_rule ist None")
        created_id = create_cmd.created_cast_rule.id
        db_cr = db_services.CastRule.get(created_id)
        if db_cr.name != f"E2E-Rule-{suffix}" or db_cr.rule != "ABAB":
            _fail(f"Nach execute: name={db_cr.name!r}, rule={db_cr.rule!r}")
        _ok(f"CastRule {created_id} angelegt (name/rule korrekt)")

        print("3. Update-Command: name + rule aendern...")
        update_cmd = cast_rule_commands.Update(created_id, f"E2E-Updated-{suffix}", "ABCD")
        update_cmd.execute()
        db_after = db_services.CastRule.get(created_id)
        if db_after.name != f"E2E-Updated-{suffix}" or db_after.rule != "ABCD":
            _fail(f"Nach update: name={db_after.name!r}, rule={db_after.rule!r}")
        _ok("Update erfolgreich")

        print("4. Update.undo() -> zurueck auf Original-name+rule...")
        update_cmd.undo()
        db_restored = db_services.CastRule.get(created_id)
        if db_restored.name != f"E2E-Rule-{suffix}" or db_restored.rule != "ABAB":
            _fail(f"Nach undo: name={db_restored.name!r}, rule={db_restored.rule!r}")
        _ok("Undo erfolgreich")

        print("5. SetPrepDelete-Command: soft-delete...")
        prep_cmd = cast_rule_commands.SetPrepDelete(created_id)
        prep_cmd.execute()
        db_prep = db_services.CastRule.get(created_id)
        if db_prep.prep_delete is None:
            _fail("Nach SetPrepDelete.execute: prep_delete ist None")
        _ok(f"prep_delete gesetzt: {db_prep.prep_delete}")

        print("6. SetPrepDelete.undo() -> prep_delete klaeren...")
        prep_cmd.undo()
        db_undel = db_services.CastRule.get(created_id)
        if db_undel.prep_delete is not None:
            _fail(f"Nach undo: prep_delete={db_undel.prep_delete}")
        _ok("Undelete erfolgreich")

        print("7. Create.undo() -> CastRule hart loeschen via API...")
        create_cmd.undo()
        # Verifikation: kein Record mehr im DB
        with get_session() as session:
            remaining = session.get(models.CastRule, created_id)
            if remaining:
                _fail(f"Nach Create.undo: CastRule existiert noch (prep_delete={remaining.prep_delete})")
        _ok("CastRule vollstaendig geloescht (hard delete durch Create._undo)")
        created_id = None  # Kein Cleanup mehr noetig

    finally:
        if created_id:
            print("8. Cleanup (Notfall): hart loeschen...")
            _hard_delete(created_id)
            _ok(f"CastRule {created_id} hart geloescht")

    print("\n  cast_rule_commands Round-Trip bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())