"""End-to-End-Test: plan_period_commands.UpdateNotes via API-Client.

Validiert Phase-3-Commands-Migration:
  - UpdateNotes.execute() -> PATCH /plan-periods/{id}/notes
  - undo/redo schreiben ebenfalls via API
  - Daten bleiben nach Test unveraendert (zweites undo am Ende)

Voraussetzung: mindestens 1 aktive PlanPeriod im Test-Projekt.

Umgebungsvariablen wie test_address_round_trip.py.
"""

import os
import sys
from uuid import UUID

from database import db_services
from commands.database_commands import plan_period_commands
from gui.api_client.client import get_api_client


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
    get_api_client().login(email, password)
    _ok("Token erhalten")

    print("2. Aktive PlanPeriod im Test-Projekt suchen (read-only)...")
    # Alle Teams im Projekt durchgehen, erste aktive PlanPeriod nehmen
    teams = db_services.Team.get_all_from__project(project_id)
    plan_period = None
    for team in teams:
        for pp in db_services.PlanPeriod.get_all_from__team(team.id):
            if pp.prep_delete is None:
                plan_period = pp
                break
        if plan_period:
            break
    if plan_period is None:
        _fail("Keine aktive PlanPeriod im Test-Projekt gefunden")
    original_notes = plan_period.notes
    _ok(f"PlanPeriod: {plan_period.id} (notes={original_notes!r})")

    test_notes = f"E2E-Test — aktive Notiz"

    try:
        print(f"3. UpdateNotes.execute() — setze notes={test_notes!r}...")
        cmd = plan_period_commands.UpdateNotes(plan_period.id, test_notes)
        cmd.execute()
        after_execute = db_services.PlanPeriod.get(plan_period.id)
        if after_execute.notes != test_notes:
            _fail(f"execute(): notes ist {after_execute.notes!r}, erwartet {test_notes!r}")
        _ok("DB zeigt neue notes")

        print("4. undo() — zurueck auf Original-notes...")
        cmd.undo()
        after_undo = db_services.PlanPeriod.get(plan_period.id)
        if after_undo.notes != original_notes:
            _fail(f"undo(): notes ist {after_undo.notes!r}, erwartet {original_notes!r}")
        _ok("DB zeigt Original-notes")

        print("5. redo() — wieder auf neue notes...")
        cmd.redo()
        after_redo = db_services.PlanPeriod.get(plan_period.id)
        if after_redo.notes != test_notes:
            _fail(f"redo(): notes ist {after_redo.notes!r}, erwartet {test_notes!r}")
        _ok("DB zeigt neue notes")

    finally:
        print("6. Cleanup: Notes final auf Original zuruecksetzen...")
        if plan_period is not None:
            cmd_cleanup = plan_period_commands.UpdateNotes(plan_period.id, original_notes or "")
            cmd_cleanup.execute()
            final = db_services.PlanPeriod.get(plan_period.id)
            if final.notes != (original_notes or ""):
                _fail(f"Cleanup: notes ist {final.notes!r}, erwartet {original_notes!r}")
            _ok("Original-Zustand wiederhergestellt")

    print("\n  PlanPeriod.UpdateNotes-Command Round-Trip bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())