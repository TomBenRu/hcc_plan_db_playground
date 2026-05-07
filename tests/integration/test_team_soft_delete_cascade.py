"""End-to-End-Test: team.delete/undelete-Cascade auf PlanPeriods.

Validiert Phase B (Soft-Delete-Cascade) gegen eine echte DB:
  - team.delete() soft-loescht alle aktiven PPs des Teams (inkl. closed=True via Bypass)
  - get_all_from__project / get_all_from__team filtern softdeletet aus
  - team.undelete(cascaded_plan_period_ids=...) restored Team + die genannten PPs

Vorgehen: ein neues Test-Team mit einer PlanPeriod anlegen, die Cascade
durchspielen, am Ende hartloeschen.

Voraussetzung: ein vorhandenes Test-Projekt + Login-Credentials.
Umgebungsvariablen: DESKTOP_TEST_EMAIL, DESKTOP_TEST_PASSWORD, DESKTOP_TEST_PROJECT_ID.
"""

import datetime
import os
import sys
from uuid import UUID

from database import db_services, schemas
from gui.api_client import team as api_team, plan_period as api_plan_period
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

    print("2. Test-Team anlegen...")
    team_name = f"_softdelete_cascade_test_{datetime.datetime.utcnow().isoformat(timespec='seconds')}"
    created = api_team.create(team_name, project_id, dispatcher_id=None)
    team_id = created.id
    _ok(f"Team angelegt: {team_id} ({team_name})")

    pp_id: UUID | None = None
    try:
        print("3. PlanPeriod im Team anlegen...")
        today = datetime.date.today()
        pp_create = schemas.PlanPeriodCreate(
            start=today + datetime.timedelta(days=14),
            end=today + datetime.timedelta(days=28),
            deadline=None,
            notes=None, notes_for_employees=None,
            remainder=False,
            team=schemas.Team.model_validate(created.model_dump()),
        )
        pp = api_plan_period.create(pp_create)
        pp_id = pp.id
        _ok(f"PlanPeriod angelegt: {pp_id}")

        print("4. team.delete() — Cascade verifizieren...")
        result = api_team.delete(team_id)
        if not isinstance(result, schemas.TeamDeletionResult):
            _fail(f"delete() returnt {type(result).__name__}, erwartet TeamDeletionResult")
        if pp_id not in result.cascaded_plan_period_ids:
            _fail(f"cascaded_plan_period_ids={result.cascaded_plan_period_ids} enthaelt {pp_id} nicht")
        _ok(f"Cascade-IDs enthalten {pp_id}")

        print("5. get_all_from__project listet softdeleted Team nicht...")
        all_teams = db_services.Team.get_all_from__project(project_id)
        if any(t.id == team_id for t in all_teams):
            _fail("Softdeleted Team taucht weiter in get_all_from__project auf")
        _ok("Team aus Auflistung verschwunden")

        print("6. get_all_from__team listet cascade-soft-deletete PP nicht...")
        all_pps = db_services.PlanPeriod.get_all_from__team(team_id)
        if any(p.id == pp_id for p in all_pps):
            _fail("Cascade-soft-deletete PlanPeriod taucht weiter auf")
        _ok("PlanPeriod aus Auflistung verschwunden")

        print("7. include_deleted=True findet die Records...")
        deleted_team = db_services.Team.get(team_id, include_deleted=True)
        if deleted_team.prep_delete is None:
            _fail("include_deleted=True: prep_delete ist None")
        _ok(f"Team mit prep_delete={deleted_team.prep_delete} gefunden")

        print("8. undelete() mit cascaded_plan_period_ids — Restore verifizieren...")
        api_team.undelete(team_id, cascaded_plan_period_ids=result.cascaded_plan_period_ids)
        restored_team = db_services.Team.get(team_id)
        if restored_team.prep_delete is not None:
            _fail("undelete(): Team hat noch prep_delete")
        restored_pps = db_services.PlanPeriod.get_all_from__team(team_id)
        if not any(p.id == pp_id for p in restored_pps):
            _fail("undelete(): cascade-PP ist nicht zurueck")
        _ok("Team + PlanPeriod erfolgreich restored")

    finally:
        print("9. Cleanup: Test-Team und PlanPeriod hart loeschen...")
        try:
            if pp_id is not None:
                api_plan_period.delete(pp_id)
                api_plan_period.delete_prep_deletes(team_id)
            api_team.delete(team_id)
        except Exception as exc:
            print(f"  [WARN] Cleanup unvollstaendig: {exc}")
        _ok("Cleanup-Versuch abgeschlossen")

    print("\n  team.delete/undelete-Cascade Round-Trip bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())