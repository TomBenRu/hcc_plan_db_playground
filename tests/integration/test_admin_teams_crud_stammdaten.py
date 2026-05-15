"""Integration-Tests fuer /admin/teams Stammdaten-CRUD (Phase 1.1).

Pruefen:
- Admin kann Team + Standort anlegen
- Listener fuer Standort vererbt Default-TimeOfDays vom Project
- Umbenennen aktualisiert den Datensatz
- Duplikat-Name liefert 409 (UniqueConstraint pro Projekt)
- Dispatcher-Auswahl ist auf Personen mit WebUserRole.dispatcher beschraenkt
- Adress-Drei-Faelle-Logik: neue Zeile / in-place / loesen
- Dispatcher-Konto kann KEINE Stammdaten aendern (403)
"""

from __future__ import annotations

import secrets

from sqlmodel import Session, select

from database.models import Address, LocationOfWork, Person, Project, Team
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink


def _make_extra_dispatcher_person(
    session: Session, project: Project, *, first: str = "Eva"
) -> Person:
    """Person + WebUser + Dispatcher-Rolle anlegen. Liefert die Person."""
    person = Person(
        f_name=first,
        l_name="Dispo",
        email=f"{first.lower()}.dispo@test.local",
        username=f"{first.lower()}-{secrets.token_hex(3)}",
        password="dummy",
        project=project,
    )
    session.add(person)
    session.commit()
    web_user = WebUser(
        email=f"{first.lower()}-{secrets.token_hex(3)}@test.local",
        hashed_password="dummy",
        person_id=person.id,
        is_active=True,
    )
    session.add(web_user)
    session.commit()
    session.add(WebUserRoleLink(web_user_id=web_user.id, role=WebUserRole.dispatcher))
    session.commit()
    session.refresh(person)
    return person


def test_create_team_minimal(as_admin, session: Session, project: Project) -> None:
    resp = as_admin.post("/admin/teams/teams", data={"name": "Hamburg"})
    assert resp.status_code == 200, resp.text
    assert "Hamburg" in resp.text
    assert resp.headers.get("HX-Trigger") == "teams-list-changed"
    # DB-Probe
    teams = session.exec(select(Team).where(Team.name == "Hamburg")).all()
    assert len(teams) == 1


def test_create_team_duplicate_name_returns_409(
    as_admin, session: Session, project: Project
) -> None:
    as_admin.post("/admin/teams/teams", data={"name": "Berlin"})
    resp = as_admin.post("/admin/teams/teams", data={"name": "Berlin"})
    assert resp.status_code == 409
    assert "existiert bereits" in resp.text


def test_rename_team_updates_db(as_admin, session: Session, project: Project) -> None:
    team = Team(name="Alt", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.patch(
        f"/admin/teams/teams/{team.id}",
        data={"name": "Neu", "notes": "Notiz"},
    )
    assert resp.status_code == 200
    session.refresh(team)
    assert team.name == "Neu"
    assert team.notes == "Notiz"


def test_create_location_inherits_timeofdays(
    as_admin, session: Session, project: Project
) -> None:
    """Listener ``_on_insert_location_of_work`` muss feuern — auf leerem Project
    sind die M2M-Listen leer, aber die Anlage darf nicht crashen."""
    resp = as_admin.post(
        "/admin/teams/locations",
        data={
            "name": "Spielstaette-X",
            "nr_actors": 3,
            "address_street": "Hauptstrasse 1",
            "address_city": "Hamburg",
        },
    )
    assert resp.status_code == 200, resp.text
    loc = session.exec(
        select(LocationOfWork).where(LocationOfWork.name == "Spielstaette-X")
    ).one()
    assert loc.nr_actors == 3
    assert loc.project_id == project.id
    # M2M-Listen sind eager-loaded via Listener; bei leerem Project leer, aber kein Crash
    assert loc.time_of_days is not None
    # Adresse wurde angelegt
    assert loc.address is not None
    assert loc.address.street == "Hauptstrasse 1"
    assert loc.address.city == "Hamburg"


def test_location_address_inplace_update(
    as_admin, session: Session, project: Project
) -> None:
    """Bestehende Adresse + geaenderte Felder → in-place-Update, kein neuer
    Address-Record."""
    address = Address(street="Original 1", city="Berlin", project=project)
    session.add(address)
    session.commit()
    location = LocationOfWork(name="Loc-A", project=project, address=address)
    session.add(location)
    session.commit()
    session.refresh(location)
    original_addr_id = location.address.id

    resp = as_admin.patch(
        f"/admin/teams/locations/{location.id}/stammdaten",
        data={
            "name": "Loc-A",
            "address_street": "Geaendert 99",
            "address_city": "Berlin",
        },
    )
    assert resp.status_code == 200

    # Endpoint nutzt eigene Session — wir muessen die Test-Session-Identity-Map
    # invalidieren, sonst sehen wir noch den Cache-Wert.
    session.expire_all()
    fresh_addr = session.get(Address, original_addr_id)
    assert fresh_addr is not None
    assert fresh_addr.street == "Geaendert 99"
    fresh_loc = session.get(LocationOfWork, location.id)
    assert fresh_loc.address_id == original_addr_id, "Adresse soll in-place geaendert sein"


def test_location_address_new_when_was_empty(
    as_admin, session: Session, project: Project
) -> None:
    """Standort ohne Adresse + neue Felder → neue Address-Zeile, verlinkt."""
    location = LocationOfWork(name="Loc-B", project=project)
    session.add(location)
    session.commit()
    session.refresh(location)
    assert location.address is None

    as_admin.patch(
        f"/admin/teams/locations/{location.id}/stammdaten",
        data={
            "name": "Loc-B",
            "address_street": "Frisch 1",
        },
    )
    session.refresh(location)
    assert location.address is not None
    assert location.address.street == "Frisch 1"


def test_location_address_unlink_when_emptied(
    as_admin, session: Session, project: Project
) -> None:
    """Felder geleert → Verknuepfung loesen, alte Address-Zeile bleibt stehen."""
    address = Address(street="Alt 1", city="Bremen", project=project)
    session.add(address)
    session.commit()
    location = LocationOfWork(name="Loc-C", project=project, address=address)
    session.add(location)
    session.commit()
    session.refresh(location)
    addr_id = location.address.id

    as_admin.patch(
        f"/admin/teams/locations/{location.id}/stammdaten",
        data={"name": "Loc-C"},  # alle Adress-Felder leer
    )
    session.refresh(location)
    assert location.address is None, "Verknuepfung sollte geloest sein"
    # Address-Zeile bleibt stehen (verwaister Eintrag fuer spaeteren Cleanup)
    leftover = session.exec(select(Address).where(Address.id == addr_id)).one()
    assert leftover.street == "Alt 1"


def test_assign_dispatcher_to_team(
    as_admin, session: Session, project: Project
) -> None:
    person = _make_extra_dispatcher_person(session, project)
    team = Team(name="DispoTeam", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.post(
        f"/admin/teams/teams/{team.id}/dispatcher",
        data={"dispatcher_id": str(person.id)},
    )
    assert resp.status_code == 200
    session.refresh(team)
    assert team.dispatcher_id == person.id


def test_dispatcher_search_only_returns_dispatcher_role(
    as_admin, session: Session, project: Project, admin_user: WebUser, dispatcher_user: WebUser
) -> None:
    """Pool ist auf Personen mit WebUserRole.dispatcher beschraenkt — Admin-only-Konten
    duerfen nicht auftauchen."""
    team = Team(name="SearchTeam", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_admin.get(f"/admin/teams/teams/{team.id}/dispatcher-search?q=")
    assert resp.status_code == 200
    # Dispatcher-Person (Disp Test) muss enthalten sein
    assert "Disp" in resp.text
    # Admin-Person (Admin Test) darf NICHT enthalten sein
    assert "Admin" not in resp.text


def test_dispatcher_cannot_change_stammdaten(
    as_dispatcher, session: Session, project: Project
) -> None:
    """Dispatcher hat keinen Schreibzugriff auf Admin-Felder."""
    team = Team(name="Locked", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)

    resp = as_dispatcher.patch(
        f"/admin/teams/teams/{team.id}",
        data={"name": "Geklaut"},
    )
    assert resp.status_code == 403


def test_get_new_team_drawer_renders_anlegen_form(as_admin) -> None:
    """Leerer Team-Drawer mit Anlegen-Form via GET /teams/new."""
    resp = as_admin.get("/admin/teams/teams/new")
    assert resp.status_code == 200
    assert "Neues Team" in resp.text
    assert 'hx-post="/admin/teams/teams"' in resp.text
    # Aktions-Footer darf NICHT erscheinen (kein bestehendes Team)
    assert "In Inaktiv verschieben" not in resp.text


def test_get_new_location_drawer_renders_anlegen_form(as_admin) -> None:
    resp = as_admin.get("/admin/teams/locations/new")
    assert resp.status_code == 200
    assert "Neuer Standort" in resp.text
    assert 'hx-post="/admin/teams/locations"' in resp.text
    # nr_actors-Eingabe nur beim Anlegen sichtbar
    assert 'name="nr_actors"' in resp.text


def test_dispatcher_cannot_get_new_team_drawer(as_dispatcher) -> None:
    resp = as_dispatcher.get("/admin/teams/teams/new")
    assert resp.status_code == 403


def test_dispatcher_cannot_get_new_location_drawer(as_dispatcher) -> None:
    resp = as_dispatcher.get("/admin/teams/locations/new")
    assert resp.status_code == 403


def test_teams_list_shows_neues_team_button_for_admin(
    as_admin, session: Session, project: Project
) -> None:
    resp = as_admin.get("/admin/teams")
    assert resp.status_code == 200
    assert "Neues Team" in resp.text
    assert 'hx-get="/admin/teams/teams/new"' in resp.text


def test_locations_list_shows_neuer_standort_button_for_admin(
    as_admin, session: Session, project: Project
) -> None:
    resp = as_admin.get("/admin/teams?tab=locations")
    assert resp.status_code == 200
    assert "Neuer Standort" in resp.text
    assert 'hx-get="/admin/teams/locations/new"' in resp.text


def test_dispatcher_blocked_from_list(as_dispatcher) -> None:
    """/admin/teams ist seit 2026-05-15 strikt admin-only — reiner Dispatcher
    bekommt 403."""
    resp = as_dispatcher.get("/admin/teams")
    assert resp.status_code == 403


def test_new_team_drawer_via_get_with_random_uuid_returns_404(as_admin) -> None:
    """Sanity-Check: GET auf eine random UUID auf dem Detail-Endpoint liefert 404
    (im Gegensatz zu /teams/new, der ein leeres Drawer rendert)."""
    import uuid

    resp = as_admin.get(f"/admin/teams/teams/{uuid.uuid4()}/drawer")
    assert resp.status_code == 404
