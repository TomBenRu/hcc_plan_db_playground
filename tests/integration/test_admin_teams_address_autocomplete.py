"""Integration-Tests fuer /admin/teams Adress-Autocomplete (Phase 1.4)."""

from __future__ import annotations

from sqlmodel import Session, select

from database.models import Address, LocationOfWork, Project


def test_address_suggest_returns_matches(
    as_admin, session: Session, project: Project
) -> None:
    addr_a = Address(street="Bahnhofstrasse 12", city="Hamburg", project=project)
    addr_b = Address(street="Marktplatz 1", city="Berlin", project=project)
    session.add_all([addr_a, addr_b])
    session.commit()

    resp = as_admin.get("/admin/teams/addresses/suggest?q=Bahn")
    assert resp.status_code == 200
    assert "Bahnhofstrasse 12" in resp.text
    assert "Marktplatz 1" not in resp.text


def test_address_suggest_empty_query_returns_nothing(
    as_admin, session: Session, project: Project
) -> None:
    addr = Address(street="Hauptstrasse", city="Hamburg", project=project)
    session.add(addr)
    session.commit()
    resp = as_admin.get("/admin/teams/addresses/suggest?q=")
    assert resp.status_code == 200
    assert "Hauptstrasse" not in resp.text


def test_address_suggest_excludes_soft_deleted(
    as_admin, session: Session, project: Project
) -> None:
    import datetime
    addr = Address(
        street="Geloescht 99",
        city="Hamburg",
        project=project,
        prep_delete=datetime.datetime.now(datetime.timezone.utc),
    )
    session.add(addr)
    session.commit()
    resp = as_admin.get("/admin/teams/addresses/suggest?q=Geloescht")
    assert "Geloescht 99" not in resp.text


def test_address_suggest_excludes_other_projects(
    as_admin, session: Session, project: Project
) -> None:
    other_project = Project(name="OtherProject")
    session.add(other_project)
    session.commit()
    addr = Address(street="Fremd 1", city="Hamburg", project=other_project)
    session.add(addr)
    session.commit()

    resp = as_admin.get("/admin/teams/addresses/suggest?q=Fremd")
    assert resp.status_code == 200
    assert "Fremd 1" not in resp.text


def test_save_after_suggestion_click_creates_new_address_row(
    as_admin, session: Session, project: Project
) -> None:
    """Pruefen: Speichern mit Adress-Feldern erzeugt eine NEUE Address-Zeile,
    auch wenn die Felder zufaellig denen einer bestehenden entsprechen.
    Frontend-Konvention: address_id wird beim Suggestion-Click NICHT gesetzt.
    """
    suggestion = Address(street="Suggested 1", city="Hamburg", project=project)
    session.add(suggestion)
    session.commit()
    suggested_id = suggestion.id

    # Standort neu anlegen mit den exakt gleichen Feldern wie die suggestion.
    resp = as_admin.post(
        "/admin/teams/locations",
        data={
            "name": "Loc-AC1",
            "address_street": "Suggested 1",
            "address_city": "Hamburg",
        },
    )
    assert resp.status_code == 200

    session.expire_all()
    loc = session.exec(select(LocationOfWork).where(LocationOfWork.name == "Loc-AC1")).one()
    assert loc.address is not None
    assert loc.address.id != suggested_id, (
        "Suggestion-Click darf nicht auf bestehende Address-Zeile verlinken"
    )
    assert loc.address.street == "Suggested 1"


def test_dispatcher_cannot_query_address_suggest(as_dispatcher) -> None:
    resp = as_dispatcher.get("/admin/teams/addresses/suggest?q=foo")
    assert resp.status_code == 403
