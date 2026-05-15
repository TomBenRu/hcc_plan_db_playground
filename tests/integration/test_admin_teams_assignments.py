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
    Gender,
    LocationOfWork,
    Person,
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
