"""Integration-Tests fuer /admin/teams Zuordnungen (Phase 1.3).

Pruefen:
- Person zuweisen (Default start=heute)
- Person mit Future-Start zuweisen
- Konflikt bei zweiter offener Mitgliedschaft → 409 + Dialog
- Mitgliedschaft mit Future-End beenden
- End revertieren (auf NULL setzen)
- Standort↔Team analog
- Dispatcher-Konto darf NICHT zuweisen (403)
"""

from __future__ import annotations

import secrets
from datetime import date, timedelta

from sqlmodel import Session, select

from database.models import (
    LocationOfWork,
    Person,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)


def _make_person(session: Session, project: Project, first: str = "Anna") -> Person:
    person = Person(
        f_name=first,
        l_name="Mit",
        email=f"{first.lower()}@test.local",
        username=f"{first.lower()}-{secrets.token_hex(3)}",
        password="dummy",
        project=project,
    )
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


def _make_team(session: Session, project: Project, name: str = "Team1") -> Team:
    team = Team(name=name, project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def _make_location(session: Session, project: Project, name: str = "Loc1") -> LocationOfWork:
    loc = LocationOfWork(name=name, project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)
    return loc


def test_add_team_member_default_start_today(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 200, resp.text
    taa = session.exec(
        select(TeamActorAssign).where(TeamActorAssign.person_id == person.id)
    ).one()
    assert taa.start == date.today()
    assert taa.end is None


def test_add_team_member_with_future_start(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)
    future = date.today() + timedelta(days=30)

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id), "start": future.isoformat()},
    )
    assert resp.status_code == 200
    taa = session.exec(select(TeamActorAssign).where(TeamActorAssign.person_id == person.id)).one()
    assert taa.start == future


def test_duplicate_open_member_returns_conflict_dialog(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)
    as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 409
    assert "bereits eine offene Mitgliedschaft" in resp.text


def test_end_team_member_with_future_date(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)
    as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    taa = session.exec(
        select(TeamActorAssign).where(TeamActorAssign.person_id == person.id)
    ).one()
    future = date.today() + timedelta(days=14)

    resp = as_admin.patch(
        f"/admin/teams/members/{taa.id}",
        data={"end": future.isoformat()},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(TeamActorAssign, taa.id)
    assert fresh.end == future


def test_revert_team_member_end(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)
    future = date.today() + timedelta(days=14)
    taa = TeamActorAssign(person=person, team=team, start=date.today(), end=future)
    session.add(taa)
    session.commit()
    session.refresh(taa)

    resp = as_admin.patch(
        f"/admin/teams/members/{taa.id}",
        data={"end": ""},  # leeres String → revert
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(TeamActorAssign, taa.id)
    assert fresh.end is None


def test_add_team_location(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    loc = _make_location(session, project)

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    assert resp.status_code == 200
    tla = session.exec(
        select(TeamLocationAssign).where(TeamLocationAssign.location_of_work_id == loc.id)
    ).one()
    assert tla.start == date.today()
    assert tla.end is None


def test_duplicate_open_location_returns_conflict(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    loc = _make_location(session, project)
    as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    assert resp.status_code == 409


def test_end_team_location_with_future_date(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    loc = _make_location(session, project)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()
    session.refresh(tla)
    future = date.today() + timedelta(days=21)

    resp = as_admin.patch(
        f"/admin/teams/team-locations/{tla.id}",
        data={"end": future.isoformat()},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(TeamLocationAssign, tla.id)
    assert fresh.end == future


def test_dispatcher_cannot_add_member(
    as_dispatcher, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)
    resp = as_dispatcher.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 403


def test_member_search_returns_persons(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project, "SearchTarget")
    resp = as_admin.get(f"/admin/teams/teams/{team.id}/member-search?q=Search")
    assert resp.status_code == 200
    assert "SearchTarget" in resp.text


def test_set_end_validates_end_must_be_after_start(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    person = _make_person(session, project)
    today = date.today()
    taa = TeamActorAssign(person=person, team=team, start=today + timedelta(days=10))
    session.add(taa)
    session.commit()
    session.refresh(taa)

    # End vor Start → 422
    resp = as_admin.patch(
        f"/admin/teams/members/{taa.id}",
        data={"end": (today + timedelta(days=5)).isoformat()},
    )
    assert resp.status_code == 422
