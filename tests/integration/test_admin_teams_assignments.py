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
    ActorPlanPeriod,
    Gender,
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    PlanPeriod,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)


def _make_person(session: Session, project: Project, first: str = "Anna") -> Person:
    # ``@example.com`` statt ``@test.local`` (RFC 6761 reserviert) +
    # ``gender`` als Enum-Wert — TeamShow-Pydantic-Validation verlangt beides
    # (siehe Memory ``feedback-orm-pass-relations-not-fk``).
    person = Person(
        f_name=first,
        l_name="Mit",
        gender=Gender.female,
        email=f"{first.lower()}-{secrets.token_hex(3)}@example.com",
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


# ═══════════════════════════════════════════════════════════════════════════════
# Standort↔Team-Zuordnung von der Standort-Seite (Phase 1.3b)
# ═══════════════════════════════════════════════════════════════════════════════


def test_add_location_team_default_start_today(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    team = _make_team(session, project)

    resp = as_admin.post(
        f"/admin/teams/locations/{loc.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 200, resp.text
    tla = session.exec(
        select(TeamLocationAssign).where(TeamLocationAssign.location_of_work_id == loc.id)
    ).one()
    assert tla.team_id == team.id
    assert tla.start == date.today()
    assert tla.end is None


def test_add_location_team_with_future_start(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    team = _make_team(session, project)
    future = date.today() + timedelta(days=21)

    resp = as_admin.post(
        f"/admin/teams/locations/{loc.id}/teams",
        data={"team_id": str(team.id), "start": future.isoformat()},
    )
    assert resp.status_code == 200
    tla = session.exec(
        select(TeamLocationAssign).where(TeamLocationAssign.location_of_work_id == loc.id)
    ).one()
    assert tla.start == future


def test_duplicate_open_location_team_returns_conflict_dialog(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    team = _make_team(session, project)
    as_admin.post(
        f"/admin/teams/locations/{loc.id}/teams",
        data={"team_id": str(team.id)},
    )
    resp = as_admin.post(
        f"/admin/teams/locations/{loc.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 409
    assert "bereits zugeordnet" in resp.text
    # Schliessen-Button laedt den Location-Drawer, nicht den Team-Drawer
    assert "location-drawer" in resp.text


def test_end_location_team_with_future_date(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    team = _make_team(session, project)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()
    session.refresh(tla)
    future = date.today() + timedelta(days=14)

    resp = as_admin.patch(
        f"/admin/teams/location-teams/{tla.id}",
        data={"end": future.isoformat()},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(TeamLocationAssign, tla.id)
    assert fresh.end == future


def test_revert_location_team_end(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    team = _make_team(session, project)
    future = date.today() + timedelta(days=10)
    tla = TeamLocationAssign(
        location_of_work=loc, team=team, start=date.today(), end=future
    )
    session.add(tla)
    session.commit()
    session.refresh(tla)

    resp = as_admin.patch(
        f"/admin/teams/location-teams/{tla.id}",
        data={"end": ""},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(TeamLocationAssign, tla.id)
    assert fresh.end is None


def test_delete_future_location_team(
    as_admin, session: Session, project: Project
) -> None:
    """Future-TLA loeschen ist erlaubt (physisch entfernt)."""
    loc = _make_location(session, project)
    team = _make_team(session, project)
    future = date.today() + timedelta(days=30)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=future)
    session.add(tla)
    session.commit()
    tla_id = tla.id

    resp = as_admin.delete(f"/admin/teams/location-teams/{tla_id}")
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(TeamLocationAssign, tla_id) is None


def test_delete_active_location_team_is_blocked(
    as_admin, session: Session, project: Project
) -> None:
    """Aktive TLA (start <= today) darf nicht physisch geloescht werden — 422."""
    loc = _make_location(session, project)
    team = _make_team(session, project)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()
    tla_id = tla.id

    resp = as_admin.delete(f"/admin/teams/location-teams/{tla_id}")
    assert resp.status_code == 422
    session.expire_all()
    assert session.get(TeamLocationAssign, tla_id) is not None


def test_team_search_returns_teams(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    _make_team(session, project, "Hamburg-Search")
    resp = as_admin.get(f"/admin/teams/locations/{loc.id}/team-search?q=Hamburg")
    assert resp.status_code == 200
    assert "Hamburg-Search" in resp.text


def test_dispatcher_cannot_add_location_team(
    as_dispatcher, session: Session, project: Project
) -> None:
    loc = _make_location(session, project)
    team = _make_team(session, project)
    resp = as_dispatcher.post(
        f"/admin/teams/locations/{loc.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 403


def test_drawer_renders_active_team_assigns(
    as_admin, session: Session, project: Project
) -> None:
    """Standort-Drawer zeigt aktive Team-Zuordnungen im Teams-Block."""
    loc = _make_location(session, project)
    team = _make_team(session, project, "TeamInDrawer")
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()

    resp = as_admin.get(f"/admin/teams/locations/{loc.id}/drawer")
    assert resp.status_code == 200
    assert "TeamInDrawer" in resp.text
    assert "Teams (1)" in resp.text


def test_drawer_renders_future_team_assigns_separately(
    as_admin, session: Session, project: Project
) -> None:
    """Future-TLAs erscheinen unter eigener ‚Zukuenftig‘-Headline."""
    loc = _make_location(session, project)
    team = _make_team(session, project, "TeamInFuture")
    future = date.today() + timedelta(days=30)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=future)
    session.add(tla)
    session.commit()

    resp = as_admin.get(f"/admin/teams/locations/{loc.id}/drawer")
    assert resp.status_code == 200
    assert "TeamInFuture" in resp.text
    # Active-Count ist 0, Future-Count ist 1
    assert "Teams (0)" in resp.text
    assert "Zuk" in resp.text  # "Zukünftig (1)" — Umlaut kann je nach Encoding entkommen werden
    assert "(1)" in resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# Team-Drawer Mitglieder + Standorte (Future-DELETE + Drawer-Render)
# ═══════════════════════════════════════════════════════════════════════════════


def test_delete_future_team_member(
    as_admin, session: Session, project: Project
) -> None:
    """Future-TAA loeschen ist erlaubt."""
    team = _make_team(session, project)
    person = _make_person(session, project)
    future = date.today() + timedelta(days=30)
    taa = TeamActorAssign(person=person, team=team, start=future)
    session.add(taa)
    session.commit()
    taa_id = taa.id

    resp = as_admin.delete(f"/admin/teams/members/{taa_id}")
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(TeamActorAssign, taa_id) is None


def test_delete_active_team_member_is_blocked(
    as_admin, session: Session, project: Project
) -> None:
    """Aktive TAA (start <= today) darf nicht physisch geloescht werden — 422."""
    team = _make_team(session, project)
    person = _make_person(session, project)
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()
    taa_id = taa.id

    resp = as_admin.delete(f"/admin/teams/members/{taa_id}")
    assert resp.status_code == 422
    session.expire_all()
    assert session.get(TeamActorAssign, taa_id) is not None


def test_delete_future_team_location_via_team_endpoint(
    as_admin, session: Session, project: Project
) -> None:
    """Future-TLA via Team-seitigem DELETE-Endpoint loeschen."""
    team = _make_team(session, project)
    loc = _make_location(session, project)
    future = date.today() + timedelta(days=30)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=future)
    session.add(tla)
    session.commit()
    tla_id = tla.id

    resp = as_admin.delete(f"/admin/teams/team-locations/{tla_id}")
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(TeamLocationAssign, tla_id) is None


def test_delete_active_team_location_via_team_endpoint_is_blocked(
    as_admin, session: Session, project: Project
) -> None:
    """Aktive TLA via Team-seitigem DELETE — 422."""
    team = _make_team(session, project)
    loc = _make_location(session, project)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()
    tla_id = tla.id

    resp = as_admin.delete(f"/admin/teams/team-locations/{tla_id}")
    assert resp.status_code == 422
    session.expire_all()
    assert session.get(TeamLocationAssign, tla_id) is not None


def test_team_drawer_shows_member_link_with_active_count(
    as_admin, session: Session, project: Project
) -> None:
    """Team-Drawer enthaelt seit 2026-05-15 keine inline-Mitgliederliste mehr,
    sondern zwei Links auf die Tabs (gefiltert auf das Team) mit aktivem Count."""
    team = _make_team(session, project)
    person = _make_person(session, project, "DrawerAnna")
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    # Kein inline-Render mehr der Person
    assert "DrawerAnna" not in resp.text
    # Stattdessen: Link zum Mitglieder-Tab gefiltert auf dieses Team
    assert f"/admin/teams?tab=members&amp;team={team.id}" in resp.text
    # Count-Text "1 aktives Mitglied"
    assert "1</strong>" in resp.text
    assert "aktives Mitglied" in resp.text


def test_team_drawer_shows_location_link_with_active_count(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project)
    loc = _make_location(session, project, "DrawerLoc")
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "DrawerLoc" not in resp.text  # keine inline-Liste mehr
    assert f"/admin/teams?tab=locations&amp;team={team.id}" in resp.text
    assert "aktiver Standort" in resp.text


def test_team_drawer_inactive_team_hides_assignment_links(
    as_admin, session: Session, project: Project
) -> None:
    """Soft-geloeschtes Team blendet die Zuordnungs-Links aus."""
    from datetime import datetime, timezone

    team = Team(
        name="InaktivTeam", project=project,
        prep_delete=datetime.now(timezone.utc),
    )
    session.add(team)
    session.commit()

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "Zuordnungen werden ausgeblendet" in resp.text
    # Keine Tab-Links bei inaktivem Team
    assert "tab=members&amp;team=" not in resp.text
    assert "tab=locations&amp;team=" not in resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# Mitglieder-Tab + Person-Drawer (Phase 1.3c)
# ═══════════════════════════════════════════════════════════════════════════════


def test_members_tab_lists_all_active_persons(
    as_admin, session: Session, project: Project
) -> None:
    """Pool = alle aktiven Personen, auch ohne Team-Zuordnung."""
    _make_person(session, project, "Aaron")  # ohne Team
    _make_person(session, project, "Bea")    # ohne Team
    resp = as_admin.get("/admin/teams?tab=members")
    assert resp.status_code == 200
    assert "Aaron" in resp.text
    assert "Bea" in resp.text


def test_members_tab_team_filter_narrows_list(
    as_admin, session: Session, project: Project
) -> None:
    """team-Filter zeigt nur Personen mit aktiver TAA zum Team."""
    team = _make_team(session, project, "FilterTeam")
    in_team = _make_person(session, project, "InTeam")
    _make_person(session, project, "NotInTeam")
    session.add(TeamActorAssign(person=in_team, team=team, start=date.today()))
    session.commit()

    resp = as_admin.get(f"/admin/teams?tab=members&team={team.id}")
    assert resp.status_code == 200
    assert "InTeam" in resp.text
    assert "NotInTeam" not in resp.text
    # Filter-Banner sichtbar
    assert "FilterTeam" in resp.text
    assert "Filter aufheben" in resp.text


def test_locations_tab_team_filter_narrows_list(
    as_admin, session: Session, project: Project
) -> None:
    """Analog fuer Standorte-Tab mit ?team=<id>."""
    team = _make_team(session, project, "FT-Loc")
    loc_in = _make_location(session, project, "LocInTeam")
    _make_location(session, project, "LocNotInTeam")
    session.add(TeamLocationAssign(location_of_work=loc_in, team=team, start=date.today()))
    session.commit()

    resp = as_admin.get(f"/admin/teams?tab=locations&team={team.id}")
    assert resp.status_code == 200
    assert "LocInTeam" in resp.text
    assert "LocNotInTeam" not in resp.text


def test_member_drawer_renders_with_stammdaten(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "DrawerPerson")
    resp = as_admin.get(f"/admin/teams/persons/{person.id}/drawer")
    assert resp.status_code == 200
    assert "DrawerPerson" in resp.text
    # Stammdaten read-only-Hinweis
    assert "Pflege im Desktop" in resp.text


def test_member_drawer_renders_active_team_memberships(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "WithTeam")
    team = _make_team(session, project, "PersonTeam")
    session.add(TeamActorAssign(person=person, team=team, start=date.today()))
    session.commit()

    resp = as_admin.get(f"/admin/teams/persons/{person.id}/drawer")
    assert resp.status_code == 200
    assert "PersonTeam" in resp.text
    assert "Team-Mitgliedschaften (1)" in resp.text


def test_add_person_team_default_start(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "AddTarget")
    team = _make_team(session, project, "TargetTeam")
    resp = as_admin.post(
        f"/admin/teams/persons/{person.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 200
    taa = session.exec(
        select(TeamActorAssign).where(TeamActorAssign.person_id == person.id)
    ).one()
    assert taa.team_id == team.id
    assert taa.start == date.today()


def test_add_person_team_conflict_returns_dialog(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Conflict")
    team = _make_team(session, project, "ConflictTeam")
    as_admin.post(
        f"/admin/teams/persons/{person.id}/teams",
        data={"team_id": str(team.id)},
    )
    resp = as_admin.post(
        f"/admin/teams/persons/{person.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 409
    assert "bereits zugeordnet" in resp.text
    # Schliessen-Button zeigt auf member-drawer (nicht team-drawer)
    assert "member-drawer" in resp.text


def test_end_person_team(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Ender")
    team = _make_team(session, project, "EndTeam")
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()
    future = date.today() + timedelta(days=14)

    resp = as_admin.patch(
        f"/admin/teams/person-teams/{taa.id}",
        data={"end": future.isoformat()},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(TeamActorAssign, taa.id)
    assert fresh.end == future


def test_delete_future_person_team(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "FutureDel")
    team = _make_team(session, project, "FD-Team")
    future = date.today() + timedelta(days=30)
    taa = TeamActorAssign(person=person, team=team, start=future)
    session.add(taa)
    session.commit()
    taa_id = taa.id

    resp = as_admin.delete(f"/admin/teams/person-teams/{taa_id}")
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(TeamActorAssign, taa_id) is None


def test_person_team_search_returns_teams(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Searcher")
    _make_team(session, project, "FindMe")
    resp = as_admin.get(f"/admin/teams/persons/{person.id}/team-search?q=Find")
    assert resp.status_code == 200
    assert "FindMe" in resp.text


def test_dispatcher_cannot_open_member_drawer(
    as_dispatcher, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Hidden")
    resp = as_dispatcher.get(f"/admin/teams/persons/{person.id}/drawer")
    assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Person-Name editierbar im Mitglieder-Drawer + Team-Chips in Listen
# ═══════════════════════════════════════════════════════════════════════════════


def test_update_person_name_happy_path(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Alt")
    resp = as_admin.patch(
        f"/admin/teams/persons/{person.id}/name",
        data={"f_name": "Neu", "l_name": "Geheissen"},
    )
    assert resp.status_code == 200
    session.expire_all()
    fresh = session.get(Person, person.id)
    assert fresh.f_name == "Neu"
    assert fresh.l_name == "Geheissen"


def test_update_person_name_rejects_empty_f_name(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Stay")
    resp = as_admin.patch(
        f"/admin/teams/persons/{person.id}/name",
        data={"f_name": "   ", "l_name": "Doe"},
    )
    # _render_member_drawer mit error rendert 200 — Validierung sichtbar im Markup
    assert resp.status_code == 200
    assert "Pflichtfeld" in resp.text
    session.expire_all()
    fresh = session.get(Person, person.id)
    assert fresh.f_name == "Stay"  # unveraendert


def test_update_person_name_dispatcher_blocked(
    as_dispatcher, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Protected")
    resp = as_dispatcher.patch(
        f"/admin/teams/persons/{person.id}/name",
        data={"f_name": "X", "l_name": "Y"},
    )
    assert resp.status_code == 403


def test_locations_list_shows_team_name_chips(
    as_admin, session: Session, project: Project
) -> None:
    """Standort-Liste zeigt Team-Namen statt Counts in der Teams-Spalte."""
    loc = _make_location(session, project, "ChipLoc")
    team_a = _make_team(session, project, "Hamburg")
    team_b = _make_team(session, project, "Berlin")
    session.add(TeamLocationAssign(location_of_work=loc, team=team_a, start=date.today()))
    session.add(TeamLocationAssign(location_of_work=loc, team=team_b, start=date.today()))
    session.commit()

    resp = as_admin.get("/admin/teams?tab=locations")
    assert resp.status_code == 200
    assert "ChipLoc" in resp.text
    assert "Hamburg" in resp.text
    assert "Berlin" in resp.text


def test_members_list_shows_team_name_chips(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_person(session, project, "Chipper")
    team = _make_team(session, project, "ChipTeam")
    session.add(TeamActorAssign(person=person, team=team, start=date.today()))
    session.commit()

    resp = as_admin.get("/admin/teams?tab=members")
    assert resp.status_code == 200
    assert "Chipper" in resp.text
    assert "ChipTeam" in resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# Person-Anlage im Mitglieder-Drawer
# ═══════════════════════════════════════════════════════════════════════════════


def test_new_member_drawer_returns_create_form(
    as_admin
) -> None:
    """GET /admin/teams/persons/new liefert ein leeres Mitglieder-Drawer-Form."""
    resp = as_admin.get("/admin/teams/persons/new")
    assert resp.status_code == 200
    assert "Neue Person" in resp.text
    # Form-Felder vorhanden
    assert 'name="f_name"' in resp.text
    assert 'name="l_name"' in resp.text
    assert 'name="email"' in resp.text
    assert 'name="gender"' in resp.text
    # Hinweis auf Auto-Erzeugung der Login-Felder
    assert "automatisch" in resp.text


def test_create_person_happy_path(
    as_admin, session: Session, project: Project
) -> None:
    resp = as_admin.post(
        "/admin/teams/persons",
        data={
            "f_name": "Neu",
            "l_name": "Person",
            "email": "neu@example.com",
            "gender": "female",
        },
    )
    assert resp.status_code == 200, resp.text
    person = session.exec(
        select(Person).where(
            Person.f_name == "Neu", Person.l_name == "Person",
            Person.project_id == project.id,
        )
    ).one()
    assert person.email == "neu@example.com"
    # Auto-Felder gesetzt
    assert person.username.startswith("person.neu-")
    assert len(person.password) >= 16  # token_urlsafe(24)


def test_create_person_gender_optional(
    as_admin, session: Session, project: Project
) -> None:
    resp = as_admin.post(
        "/admin/teams/persons",
        data={"f_name": "NoGender", "l_name": "Person", "email": "ng@example.com"},
    )
    assert resp.status_code == 200
    person = session.exec(
        select(Person).where(Person.f_name == "NoGender")
    ).one()
    assert person.gender is None


def test_create_person_duplicate_name_returns_409(
    as_admin, session: Session, project: Project
) -> None:
    # Erste Person anlegen
    as_admin.post(
        "/admin/teams/persons",
        data={"f_name": "Dup", "l_name": "Test", "email": "dup1@example.com"},
    )
    # Zweite mit gleichem Namen → 409 + Drawer mit Error
    resp = as_admin.post(
        "/admin/teams/persons",
        data={"f_name": "Dup", "l_name": "Test", "email": "dup2@example.com"},
    )
    assert resp.status_code == 409
    assert "existiert bereits" in resp.text
    # Form-Werte wurden vorbelegt (User muss nicht neu tippen)
    assert "dup2@example.com" in resp.text


def test_create_person_rejects_empty_required_field(
    as_admin, project: Project
) -> None:
    resp = as_admin.post(
        "/admin/teams/persons",
        data={"f_name": "  ", "l_name": "Person", "email": "x@example.com"},
    )
    assert resp.status_code == 422
    assert "Pflichtfeld" in resp.text


def test_dispatcher_cannot_create_person(as_dispatcher) -> None:
    resp = as_dispatcher.post(
        "/admin/teams/persons",
        data={"f_name": "X", "l_name": "Y", "email": "xy@example.com"},
    )
    assert resp.status_code == 403


def test_members_list_shows_new_person_button(
    as_admin, project: Project
) -> None:
    resp = as_admin.get("/admin/teams?tab=members")
    assert resp.status_code == 200
    assert "Neue Person" in resp.text
    assert "/admin/teams/persons/new" in resp.text


# ═══════════════════════════════════════════════════════════════════════════════


def test_list_chips_overflow_shows_plus_n(
    as_admin, session: Session, project: Project
) -> None:
    """Ab 4 Teams: erste 3 Chips + '+N' Hinweis."""
    person = _make_person(session, project, "Many")
    for i in range(5):
        team = _make_team(session, project, f"T{i:02d}")
        session.add(TeamActorAssign(person=person, team=team, start=date.today()))
    session.commit()

    resp = as_admin.get("/admin/teams?tab=members")
    assert resp.status_code == 200
    # erste drei Teams sichtbar
    assert "T00" in resp.text
    assert "T01" in resp.text
    assert "T02" in resp.text
    # vierter/fünfter Team-Name nicht direkt als Chip (nur im title-Tooltip)
    # — Plus-N-Hinweis muss erscheinen
    assert "+2" in resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# Add-Member-Folge: APP-Anlage-Dialog bei offenen PPs (Phase 1.3d)
# ═══════════════════════════════════════════════════════════════════════════════


def _open_plan_period(
    session: Session,
    team: Team,
    *,
    start: date | None = None,
    end: date | None = None,
    closed: bool = False,
) -> PlanPeriod:
    pp = PlanPeriod(
        team=team,
        start=start or date.today(),
        end=end or (date.today() + timedelta(days=14)),
        closed=closed,
    )
    session.add(pp)
    session.commit()
    session.refresh(pp)
    return pp


def test_add_member_with_open_overlap_pp_renders_app_dialog(
    as_admin, session: Session, project: Project
) -> None:
    """Wenn ein TAA mit einer offenen PP des Teams ueberschneidet, kommt der
    APP-Anlage-Dialog statt des Team-Drawer-Renders."""
    team = _make_team(session, project, "WithOpenPP")
    person = _make_person(session, project, "Joiner")
    _open_plan_period(session, team)

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" in resp.text
    assert "Joiner" in resp.text
    # Submit-Form-URL zur apply-apps-Route
    taa = session.exec(
        select(TeamActorAssign).where(TeamActorAssign.person_id == person.id)
    ).one()
    assert f"/admin/teams/members/{taa.id}/apply-apps" in resp.text
    # Checkbox vorausgewaehlt
    assert "checked" in resp.text


def test_add_member_without_overlap_renders_drawer_directly(
    as_admin, session: Session, project: Project
) -> None:
    """Kein Dialog, wenn das Team keine offenen PPs hat."""
    team = _make_team(session, project, "NoOpenPP")
    person = _make_person(session, project, "Direct")

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" not in resp.text


def test_add_member_skips_dialog_for_closed_or_softdeleted_pps(
    as_admin, session: Session, project: Project
) -> None:
    """Geschlossene oder soft-deletete PPs zaehlen nicht."""
    team = _make_team(session, project, "ClosedPPs")
    person = _make_person(session, project, "Skipper")
    # Geschlossene PP
    _open_plan_period(session, team, closed=True)
    # Soft-deletete PP
    soft = _open_plan_period(session, team)
    soft.prep_delete = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" not in resp.text


def test_add_member_skips_dialog_when_taa_after_pp_end(
    as_admin, session: Session, project: Project
) -> None:
    """TAA-Start liegt nach PP-Ende → kein Overlap."""
    team = _make_team(session, project, "AfterPP")
    person = _make_person(session, project, "Late")
    yesterday_pp = _open_plan_period(
        session, team,
        start=date.today() - timedelta(days=30),
        end=date.today() - timedelta(days=1),  # PP endete gestern
    )

    future = date.today() + timedelta(days=30)
    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id), "start": future.isoformat()},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" not in resp.text


def test_add_member_skips_dialog_when_app_already_exists(
    as_admin, session: Session, project: Project
) -> None:
    """Person hat bereits ein APP fuer die PP → wird im Dialog nicht aufgefuehrt."""
    team = _make_team(session, project, "AppExists")
    person = _make_person(session, project, "PreExisting")
    pp = _open_plan_period(session, team)
    session.add(ActorPlanPeriod(plan_period=pp, person=person))
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/members",
        data={"person_id": str(person.id)},
    )
    assert resp.status_code == 200
    # APP existiert schon → kein Dialog
    assert "Planperioden anlegen" not in resp.text


def test_apply_apps_creates_actor_plan_periods(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project, "ApplyTeam")
    person = _make_person(session, project, "Applicator")
    pp1 = _open_plan_period(session, team)
    pp2 = _open_plan_period(
        session, team,
        start=date.today() + timedelta(days=20),
        end=date.today() + timedelta(days=40),
    )
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()
    session.refresh(taa)

    resp = as_admin.post(
        f"/admin/teams/members/{taa.id}/apply-apps",
        data={
            "plan_period_ids": [str(pp1.id), str(pp2.id)],
            "return_drawer": "team",
        },
    )
    assert resp.status_code == 200
    session.expire_all()
    apps = session.exec(
        select(ActorPlanPeriod).where(ActorPlanPeriod.person_id == person.id)
    ).all()
    assert len(apps) == 2
    pp_ids = {app.plan_period_id for app in apps}
    assert pp_ids == {pp1.id, pp2.id}


def test_apply_apps_empty_selection_creates_nothing(
    as_admin, session: Session, project: Project
) -> None:
    """User hat alle Checkboxes abgewaehlt → keine APPs erzeugt, aber kein Fehler."""
    team = _make_team(session, project, "EmptyApply")
    person = _make_person(session, project, "NoneSelected")
    _open_plan_period(session, team)
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/members/{taa.id}/apply-apps",
        data={"return_drawer": "team"},
    )
    assert resp.status_code == 200
    session.expire_all()
    apps = session.exec(
        select(ActorPlanPeriod).where(ActorPlanPeriod.person_id == person.id)
    ).all()
    assert apps == []


def test_apply_apps_idempotent_on_existing_app(
    as_admin, session: Session, project: Project
) -> None:
    """Wird der Dialog versehentlich ein zweites Mal submittet, entsteht kein
    Duplikat-APP."""
    team = _make_team(session, project, "Idempotent")
    person = _make_person(session, project, "Twice")
    pp = _open_plan_period(session, team)
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()

    # Erster Submit erzeugt APP
    as_admin.post(
        f"/admin/teams/members/{taa.id}/apply-apps",
        data={"plan_period_ids": [str(pp.id)], "return_drawer": "team"},
    )
    # Zweiter Submit ist no-op
    as_admin.post(
        f"/admin/teams/members/{taa.id}/apply-apps",
        data={"plan_period_ids": [str(pp.id)], "return_drawer": "team"},
    )

    session.expire_all()
    apps = session.exec(
        select(ActorPlanPeriod).where(ActorPlanPeriod.person_id == person.id)
    ).all()
    assert len(apps) == 1


def test_apply_apps_from_person_side_returns_member_drawer(
    as_admin, session: Session, project: Project
) -> None:
    """Wenn der Dialog aus dem Mitglieder-Drawer kam, soll der Submit auch
    den Mitglieder-Drawer rendern (nicht den Team-Drawer)."""
    team = _make_team(session, project, "FromPersonSide")
    person = _make_person(session, project, "MemberCaller")
    pp = _open_plan_period(session, team)
    taa = TeamActorAssign(person=person, team=team, start=date.today())
    session.add(taa)
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/members/{taa.id}/apply-apps",
        data={"plan_period_ids": [str(pp.id)], "return_drawer": "member"},
    )
    assert resp.status_code == 200
    # Member-Drawer rendert „Mitglied" als Header-Label
    assert "Mitglied" in resp.text


def test_add_person_team_with_open_pp_renders_dialog(
    as_admin, session: Session, project: Project
) -> None:
    """Spiegel: aus dem Mitglieder-Drawer ein Team zuweisen → ebenfalls Dialog."""
    team = _make_team(session, project, "PersonSidePP")
    person = _make_person(session, project, "PersonSide")
    _open_plan_period(session, team)

    resp = as_admin.post(
        f"/admin/teams/persons/{person.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" in resp.text
    # Drawer-Target ist Member-Drawer
    assert "member-drawer" in resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# Verlauf-Reiter im Drawer (Phase 1.6 — historische Zuordnungen)
# ═══════════════════════════════════════════════════════════════════════════════


def test_member_drawer_renders_past_team_memberships(
    as_admin, session: Session, project: Project
) -> None:
    """Vergangene TAA (end <= today) erscheint im Verlauf, aktive nicht."""
    person = _make_person(session, project, "Historiker")
    past_team = _make_team(session, project, "PastTeam")
    active_team = _make_team(session, project, "ActiveTeam")
    # Vergangene Mitgliedschaft (vor 30 Tagen beendet)
    session.add(TeamActorAssign(
        person=person, team=past_team,
        start=date.today() - timedelta(days=60),
        end=date.today() - timedelta(days=30),
    ))
    # Aktive Mitgliedschaft
    session.add(TeamActorAssign(
        person=person, team=active_team, start=date.today()
    ))
    session.commit()

    resp = as_admin.get(f"/admin/teams/persons/{person.id}/drawer")
    assert resp.status_code == 200
    # Verlauf-Block mit (1) ist sichtbar
    assert "Verlauf (1)" in resp.text
    assert "PastTeam" in resp.text
    # Aktives Team erscheint in der Mitgliedschaften-Sektion, nicht im Verlauf
    assert "ActiveTeam" in resp.text


def test_member_drawer_no_history_section_when_empty(
    as_admin, session: Session, project: Project
) -> None:
    """Ohne vergangene TAAs wird die Verlauf-Section gar nicht gerendert."""
    person = _make_person(session, project, "Neuling")
    resp = as_admin.get(f"/admin/teams/persons/{person.id}/drawer")
    assert resp.status_code == 200
    assert "Verlauf (" not in resp.text


def test_location_drawer_renders_past_team_assigns(
    as_admin, session: Session, project: Project
) -> None:
    loc = _make_location(session, project, "Historisch")
    past_team = _make_team(session, project, "EhemaligesTeam")
    session.add(TeamLocationAssign(
        location_of_work=loc, team=past_team,
        start=date.today() - timedelta(days=60),
        end=date.today() - timedelta(days=10),
    ))
    session.commit()

    resp = as_admin.get(f"/admin/teams/locations/{loc.id}/drawer")
    assert resp.status_code == 200
    assert "Verlauf (1)" in resp.text
    assert "EhemaligesTeam" in resp.text


def test_team_drawer_renders_past_members_and_locations(
    as_admin, session: Session, project: Project
) -> None:
    """Team-Drawer zeigt beide Historien (Mitglieder + Standorte) im Verlauf."""
    team = _make_team(session, project, "HistTeam")
    person = _make_person(session, project, "AltMitglied")
    loc = _make_location(session, project, "AltStandort")
    session.add(TeamActorAssign(
        person=person, team=team,
        start=date.today() - timedelta(days=90),
        end=date.today() - timedelta(days=5),
    ))
    session.add(TeamLocationAssign(
        location_of_work=loc, team=team,
        start=date.today() - timedelta(days=90),
        end=date.today() - timedelta(days=2),
    ))
    session.commit()

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    # Kombinierter Count im Summary
    assert "Verlauf (2)" in resp.text
    # Beide Sub-Headlines vorhanden
    assert "Mitglieder (1)" in resp.text
    assert "Standorte (1)" in resp.text
    # Die Namen erscheinen
    assert "AltMitglied" in resp.text
    assert "AltStandort" in resp.text


def test_team_drawer_history_excludes_active_assigns(
    as_admin, session: Session, project: Project
) -> None:
    """Aktive TAAs/TLAs werden NICHT im Verlauf gelistet, nur in den primaeren
    Sektionen (die im entschlackten Team-Drawer aber nur als Counts erscheinen)."""
    team = _make_team(session, project, "Lebende")
    active_person = _make_person(session, project, "AktivMitglied")
    session.add(TeamActorAssign(
        person=active_person, team=team, start=date.today()
    ))
    session.commit()

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    # Kein Verlauf-Summary, weil keine past-Eintraege
    assert "Verlauf (" not in resp.text


# ═══════════════════════════════════════════════════════════════════════════════
# LPP-Anlage-Dialog nach Add-Team-Location (Spiegel zum APP-Dialog)
# ═══════════════════════════════════════════════════════════════════════════════


def test_add_team_location_with_open_pp_renders_lpp_dialog(
    as_admin, session: Session, project: Project
) -> None:
    """Symmetrisch zur TAA-Anlage: wenn der TLA-Zeitraum mit einer offenen PP
    ueberlappt und keine LPP fuer den Standort existiert, kommt der Dialog."""
    team = _make_team(session, project, "TLATeam")
    loc = _make_location(session, project, "TLALoc")
    _open_plan_period(session, team)

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" in resp.text
    # Dialog enthaelt Submit-URL zum LPP-apply-Endpoint
    tla = session.exec(
        select(TeamLocationAssign).where(TeamLocationAssign.location_of_work_id == loc.id)
    ).one()
    assert f"/admin/teams/team-locations/{tla.id}/apply-lpps" in resp.text
    # Checkbox vorausgewaehlt
    assert "checked" in resp.text


def test_add_team_location_without_overlap_renders_drawer_directly(
    as_admin, session: Session, project: Project
) -> None:
    """Kein Dialog, wenn das Team keine offenen PPs hat."""
    team = _make_team(session, project, "NoTLAOpenPP")
    loc = _make_location(session, project, "NoTLAOpenPPLoc")
    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" not in resp.text


def test_add_team_location_skips_dialog_for_closed_or_softdeleted_pps(
    as_admin, session: Session, project: Project
) -> None:
    """Geschlossene oder soft-deletete PPs zaehlen nicht."""
    team = _make_team(session, project, "TLAClosed")
    loc = _make_location(session, project, "TLAClosedLoc")
    _open_plan_period(session, team, closed=True)
    soft = _open_plan_period(session, team)
    soft.prep_delete = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" not in resp.text


def test_add_team_location_skips_dialog_when_lpp_already_exists(
    as_admin, session: Session, project: Project
) -> None:
    """Standort hat bereits eine LPP fuer die PP → wird im Dialog nicht aufgefuehrt."""
    team = _make_team(session, project, "TLAExists")
    loc = _make_location(session, project, "TLAExistsLoc")
    pp = _open_plan_period(session, team)
    session.add(LocationPlanPeriod(plan_period=pp, location_of_work=loc))
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/locations",
        data={"location_id": str(loc.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" not in resp.text


def test_apply_lpps_creates_location_plan_periods(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project, "ApplyLPP")
    loc = _make_location(session, project, "ApplyLPPLoc")
    pp1 = _open_plan_period(session, team)
    pp2 = _open_plan_period(
        session, team,
        start=date.today() + timedelta(days=20),
        end=date.today() + timedelta(days=40),
    )
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()
    session.refresh(tla)

    resp = as_admin.post(
        f"/admin/teams/team-locations/{tla.id}/apply-lpps",
        data={
            "plan_period_ids": [str(pp1.id), str(pp2.id)],
            "return_drawer": "team",
        },
    )
    assert resp.status_code == 200
    session.expire_all()
    lpps = session.exec(
        select(LocationPlanPeriod).where(LocationPlanPeriod.location_of_work_id == loc.id)
    ).all()
    assert len(lpps) == 2
    pp_ids = {lpp.plan_period_id for lpp in lpps}
    assert pp_ids == {pp1.id, pp2.id}


def test_apply_lpps_empty_selection_is_no_op(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project, "EmptyLPP")
    loc = _make_location(session, project, "EmptyLPPLoc")
    _open_plan_period(session, team)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/team-locations/{tla.id}/apply-lpps",
        data={"return_drawer": "team"},
    )
    assert resp.status_code == 200
    session.expire_all()
    lpps = session.exec(
        select(LocationPlanPeriod).where(LocationPlanPeriod.location_of_work_id == loc.id)
    ).all()
    assert lpps == []


def test_apply_lpps_idempotent_on_existing_lpp(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project, "IdemLPP")
    loc = _make_location(session, project, "IdemLPPLoc")
    pp = _open_plan_period(session, team)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()

    as_admin.post(
        f"/admin/teams/team-locations/{tla.id}/apply-lpps",
        data={"plan_period_ids": [str(pp.id)], "return_drawer": "team"},
    )
    as_admin.post(
        f"/admin/teams/team-locations/{tla.id}/apply-lpps",
        data={"plan_period_ids": [str(pp.id)], "return_drawer": "team"},
    )

    session.expire_all()
    lpps = session.exec(
        select(LocationPlanPeriod).where(LocationPlanPeriod.location_of_work_id == loc.id)
    ).all()
    assert len(lpps) == 1


def test_apply_lpps_from_location_side_returns_location_drawer(
    as_admin, session: Session, project: Project
) -> None:
    team = _make_team(session, project, "FromLocSide")
    loc = _make_location(session, project, "LocCaller")
    pp = _open_plan_period(session, team)
    tla = TeamLocationAssign(location_of_work=loc, team=team, start=date.today())
    session.add(tla)
    session.commit()

    resp = as_admin.post(
        f"/admin/teams/team-locations/{tla.id}/apply-lpps",
        data={"plan_period_ids": [str(pp.id)], "return_drawer": "location"},
    )
    assert resp.status_code == 200
    # Location-Drawer rendert "Standort" als Header-Label
    assert "Standort" in resp.text
    # Der Location-Name muss sichtbar sein, weil's der Location-Drawer ist
    assert "LocCaller" in resp.text


def test_add_location_team_with_open_pp_renders_dialog(
    as_admin, session: Session, project: Project
) -> None:
    """Spiegel: aus dem Standort-Drawer ein Team zuweisen → ebenfalls Dialog."""
    team = _make_team(session, project, "LocSidePP")
    loc = _make_location(session, project, "LocSide")
    _open_plan_period(session, team)

    resp = as_admin.post(
        f"/admin/teams/locations/{loc.id}/teams",
        data={"team_id": str(team.id)},
    )
    assert resp.status_code == 200
    assert "Planperioden anlegen" in resp.text
    assert "location-drawer" in resp.text
