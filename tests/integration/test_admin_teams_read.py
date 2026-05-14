"""Integration-Tests fuer /admin/teams Read-Routes (Phase 1.0).

Pruefen:
- Admin und Dispatcher erreichen die Seite + beide Tabs
- Liste enthaelt angelegte Teams / Standorte
- Drawer-Endpoints liefern Detail-Markup
- Aktiv/Inaktiv-Filter wirkt
- HTMX-Header ausgeschaltet → Vollseiten-Render; eingeschaltet → Partial
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from database.models import LocationOfWork, Project, Team


def _add_team(session: Session, project: Project, name: str, prep_delete: datetime | None = None) -> Team:
    team = Team(name=name, project=project, prep_delete=prep_delete)
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


def _add_location(
    session: Session, project: Project, name: str, prep_delete: datetime | None = None
) -> LocationOfWork:
    loc = LocationOfWork(name=name, project=project, prep_delete=prep_delete)
    session.add(loc)
    session.commit()
    session.refresh(loc)
    return loc


def test_admin_sees_teams_tab_by_default(as_admin, session: Session, project: Project) -> None:
    _add_team(session, project, "Hamburg")
    resp = as_admin.get("/admin/teams")
    assert resp.status_code == 200
    assert "Hamburg" in resp.text
    assert "Teams &amp; Standorte" in resp.text


def test_admin_can_switch_to_locations_tab(as_admin, session: Session, project: Project) -> None:
    _add_location(session, project, "Spielstaette A")
    resp = as_admin.get("/admin/teams?tab=locations")
    assert resp.status_code == 200
    assert "Spielstaette A" in resp.text


def test_dispatcher_sees_same_page(as_dispatcher, session: Session, project: Project) -> None:
    _add_team(session, project, "Hamburg-D")
    resp = as_dispatcher.get("/admin/teams")
    assert resp.status_code == 200
    assert "Hamburg-D" in resp.text


def test_inactive_filter_shows_only_soft_deleted_teams(
    as_admin, session: Session, project: Project
) -> None:
    _add_team(session, project, "Active-Team")
    _add_team(session, project, "Soft-Deleted-Team", prep_delete=datetime.now(timezone.utc))

    active = as_admin.get("/admin/teams?status=active")
    assert "Active-Team" in active.text
    assert "Soft-Deleted-Team" not in active.text

    inactive = as_admin.get("/admin/teams?status=inactive")
    assert "Active-Team" not in inactive.text
    assert "Soft-Deleted-Team" in inactive.text


def test_team_drawer_returns_partial(as_admin, session: Session, project: Project) -> None:
    team = _add_team(session, project, "DrawerTestTeam")
    resp = as_admin.get(f"/admin/teams/teams/{team.id}/drawer")
    assert resp.status_code == 200
    assert "DrawerTestTeam" in resp.text
    assert "Stammdaten" in resp.text
    # Drawer-Partial darf KEIN <html>-Wrapper haben — wird in #team-drawer geswappt
    assert "<html" not in resp.text.lower()


def test_location_drawer_returns_partial(
    as_admin, session: Session, project: Project
) -> None:
    loc = _add_location(session, project, "DrawerTestStandort")
    resp = as_admin.get(f"/admin/teams/locations/{loc.id}/drawer")
    assert resp.status_code == 200
    assert "DrawerTestStandort" in resp.text
    assert "Plan-Konfiguration" in resp.text


def test_htmx_request_returns_oob_partial(as_admin, session: Session, project: Project) -> None:
    _add_team(session, project, "HTMX-Team")
    resp = as_admin.get("/admin/teams", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "HTMX-Team" in resp.text
    # OOB-Wrapper: sidebar-filters mit hx-swap-oob soll im Response stehen
    assert 'hx-swap-oob="outerHTML"' in resp.text
    # Vollseiten-Layout (<html>) darf nicht drin sein
    assert "<html" not in resp.text.lower()


def test_search_filter_narrows_teams(as_admin, session: Session, project: Project) -> None:
    _add_team(session, project, "Berlin")
    _add_team(session, project, "Muenchen")
    resp = as_admin.get("/admin/teams?search=ber")
    assert "Berlin" in resp.text
    assert "Muenchen" not in resp.text


def test_dispatcher_dashboard_shows_standorte_tile(as_dispatcher) -> None:
    """Phase 1.0: neue Tile 'Standorte' im Dispatcher-Block muss sichtbar sein."""
    resp = as_dispatcher.get("/dashboard")
    assert resp.status_code == 200
    assert "Standorte" in resp.text
    assert "/admin/teams?tab=locations" in resp.text
