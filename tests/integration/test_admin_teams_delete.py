"""Integration-Tests fuer /admin/teams Soft-/Hard-Delete (Phase 1.5).

Pruefen:
- Team ohne aktive PP soft-deleten + restore
- Soft-Delete blockiert bei aktiver PlanPeriod (409)
- Hard-Delete erfordert Name-Confirm
- Hard-Delete blockiert sobald JEDE PP existiert (auch historische)
- TAA/TLA-Cleanup: offene Eintraege werden end=today, Future-Eintraege geloescht
- Standort-Pendants analog
- Dispatcher darf NICHT loeschen (403)
"""

from __future__ import annotations

import datetime
from datetime import date, timedelta

from sqlmodel import Session, select

from database.models import (
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    PlanPeriod,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)


def test_soft_delete_team_without_plan_periods(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="SoftDel-1", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(Team, team.id)
    assert fresh.prep_delete is not None


def test_soft_delete_team_blocked_by_active_plan_period(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="SoftDel-2", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    pp = PlanPeriod(
        team=team,
        start=date.today(),
        end=date.today() + timedelta(days=14),
    )
    session.add(pp)
    session.commit()

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 200  # Drawer mit Error gerendert
    assert "kann nicht entfernt werden" in resp.text
    session.expire_all()
    fresh = session.get(Team, team.id)
    assert fresh.prep_delete is None, "Team darf NICHT soft-deleted sein"


def test_restore_team(as_admin, session: Session, project: Project) -> None:
    team = Team(
        name="Restoreable",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/restore")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(Team, team.id)
    assert fresh.prep_delete is None


def test_hard_delete_team_requires_correct_name(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(
        name="HardDel-1",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    team_id = team.id

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/teams/{team_id}",
        data={"name_confirmation": "FalscherName"},
    )
    assert resp.status_code == 422
    session.expire_all()
    assert session.get(Team, team_id) is not None, "Team darf NICHT geloescht sein"

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/teams/{team_id}",
        data={"name_confirmation": "HardDel-1"},
    )
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(Team, team_id) is None


def test_hard_delete_team_blocked_by_any_plan_period(
    as_admin, session: Session, project: Project
) -> None:
    """Selbst eine historische, soft-deletete PlanPeriod blockiert Hard-Delete —
    Schutz vor Cascade-Verlust."""
    team = Team(
        name="ProtectedTeam",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    pp = PlanPeriod(
        team=team,
        start=date.today() - timedelta(days=180),
        end=date.today() - timedelta(days=150),
        prep_delete=datetime.datetime.now(datetime.timezone.utc),  # historisch
    )
    session.add(pp)
    session.commit()
    session.refresh(team)
    team_id = team.id

    resp = as_admin.request(
        "DELETE",
        f"/admin/teams/teams/{team_id}",
        data={"name_confirmation": "ProtectedTeam"},
    )
    assert resp.status_code == 422
    assert "Endgültiges Löschen nicht möglich" in resp.text
    session.expire_all()
    assert session.get(Team, team_id) is not None, "Team mit PP-Historie darf NICHT weg"


def test_soft_delete_cleans_open_assigns(
    as_admin, session: Session, project: Project
) -> None:
    """Beim Team-Soft-Delete:
    - Offene TAA mit start<=heute → end=heute
    - Future-Start-TAA → DELETE
    """
    team = Team(name="CleanupTest", project=project)
    session.add(team)
    session.commit()
    person_a = Person(
        f_name="Active", l_name="Mit", email="a@test.local", username="a", password="x",
        project=project,
    )
    person_b = Person(
        f_name="Future", l_name="Mit", email="b@test.local", username="b", password="x",
        project=project,
    )
    session.add_all([person_a, person_b])
    session.commit()

    today = date.today()
    open_taa = TeamActorAssign(person=person_a, team=team, start=today - timedelta(days=10))
    future_taa = TeamActorAssign(person=person_b, team=team, start=today + timedelta(days=30))
    session.add_all([open_taa, future_taa])
    session.commit()
    session.refresh(open_taa)
    session.refresh(future_taa)
    open_id = open_taa.id
    future_id = future_taa.id

    resp = as_admin.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 200

    session.expire_all()
    open_after = session.get(TeamActorAssign, open_id)
    assert open_after is not None
    assert open_after.end == today, "Offene Mitgliedschaft sollte end=today bekommen"

    future_after = session.get(TeamActorAssign, future_id)
    assert future_after is None, "Future-Mitgliedschaft sollte geloescht sein"


def test_soft_delete_location_blocked_by_lpp(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="TeamForLPP", project=project)
    loc = LocationOfWork(name="ProtectedLoc", project=project)
    session.add_all([team, loc])
    session.commit()
    pp = PlanPeriod(team=team, start=date.today(), end=date.today() + timedelta(days=7))
    session.add(pp)
    session.commit()
    lpp = LocationPlanPeriod(plan_period=pp, location_of_work=loc)
    session.add(lpp)
    session.commit()
    session.refresh(loc)

    resp = as_admin.post(f"/admin/teams/locations/{loc.id}/soft-delete")
    assert "kann nicht entfernt werden" in resp.text
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.prep_delete is None


def test_soft_delete_location_without_lpp(
    as_admin, session: Session, project: Project
) -> None:
    loc = LocationOfWork(name="DelLoc-1", project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)

    resp = as_admin.post(f"/admin/teams/locations/{loc.id}/soft-delete")
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(LocationOfWork, loc.id)
    assert fresh.prep_delete is not None


def test_dispatcher_cannot_soft_delete(
    as_dispatcher, session: Session, project: Project
) -> None:
    team = Team(name="Lock", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    resp = as_dispatcher.post(f"/admin/teams/teams/{team.id}/soft-delete")
    assert resp.status_code == 403


def test_admin_drawer_shows_soft_delete_button_for_active_team(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(name="UIActionsAktiv", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "In Inaktiv verschieben" in resp.text
    assert "Wiederherstellen" not in resp.text
    assert "Endgültig löschen" not in resp.text


def test_admin_drawer_shows_restore_and_delete_for_inactive_team(
    as_admin, session: Session, project: Project
) -> None:
    team = Team(
        name="UIActionsInaktiv",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "Wiederherstellen" in resp.text
    assert "Endgültig löschen" in resp.text
    assert "name_confirmation" in resp.text
    assert "In Inaktiv verschieben" not in resp.text


def test_dispatcher_drawer_blocked(
    as_dispatcher, session: Session, project: Project
) -> None:
    """/admin/teams ist seit 2026-05-15 strikt admin-only — Dispatcher bekommt
    403 auf jeden Drawer-Endpoint."""
    team = Team(name="NoAccessForDisp", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    resp = as_dispatcher.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 403


def test_admin_drawer_shows_location_actions(
    as_admin, session: Session, project: Project
) -> None:
    loc_active = LocationOfWork(name="LocAktiv", project=project)
    loc_inactive = LocationOfWork(
        name="LocInaktiv",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add_all([loc_active, loc_inactive])
    session.commit()
    session.refresh(loc_active)
    session.refresh(loc_inactive)

    resp_active = as_admin.get(f"/admin/teams/locations/{loc_active.id}/drawer")
    assert "In Inaktiv verschieben" in resp_active.text
    assert "Endgültig löschen" not in resp_active.text

    resp_inactive = as_admin.get(f"/admin/teams/locations/{loc_inactive.id}/drawer")
    assert "Wiederherstellen" in resp_inactive.text
    assert "Endgültig löschen" in resp_inactive.text
    assert "name_confirmation" in resp_inactive.text
