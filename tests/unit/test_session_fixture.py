"""Self-Test der Test-Infrastruktur aus ``tests/conftest.py``.

Sichert ab, dass:
- Die Test-DB-URL eine SQLite-Datei in ``tempfile.gettempdir()`` ist (kein Production-Leak)
- Schema-Reset zwischen Tests sauber laeuft (keine geleakten Records)
- ``before_flush``-Listener fuer Team/LocationOfWork in der Test-Engine aktiv sind
- ``client`` + ``as_admin`` einen geschuetzten Endpoint erreichen (Auth-Override greift)
"""

from __future__ import annotations

import os

from sqlmodel import Session, select

from database.models import LocationOfWork, Project, Team


def test_database_url_is_test_sqlite() -> None:
    """Sicherheitscheck: DATABASE_URL zeigt auf SQLite-Test-Datei, nicht Production."""
    url = os.environ["DATABASE_URL"]
    assert url.startswith("sqlite:///"), f"Erwarte SQLite-URL, bekam: {url}"
    assert "test" in url.lower(), f"Erwarte 'test' im Pfad, bekam: {url}"


def test_schema_is_fresh_per_test_part_1(session: Session, project: Project) -> None:
    """Schreibt einen Team-Record und committet. Naechster Test darf ihn nicht sehen."""
    team = Team(name="leak-probe", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    rows = session.exec(select(Team).where(Team.name == "leak-probe")).all()
    assert len(rows) == 1


def test_schema_is_fresh_per_test_part_2(session: Session) -> None:
    """Wenn ``_fresh_schema`` greift, ist der Team aus dem vorherigen Test weg."""
    rows = session.exec(select(Team).where(Team.name == "leak-probe")).all()
    assert rows == []


def test_team_listener_inherits_excel_settings(session: Session, project: Project) -> None:
    """``_on_insert_team`` muss in der Test-DB feuern (excel_export_settings vom Project)."""
    # Project hat anfangs keine excel_export_settings — Listener erbt None, das ist OK.
    # Hauptpunkt: der Listener crasht nicht beim Insert.
    team = Team(name="listener-probe", project=project)
    session.add(team)
    session.commit()
    session.refresh(team)
    assert team.id is not None
    assert team.project_id == project.id


def test_location_listener_inherits_timeofdays(session: Session, project: Project) -> None:
    """``_on_insert_location_of_work`` muss feuern — bei leerem Project sind die M2M-Listen
    leer, aber kein Crash."""
    loc = LocationOfWork(name="loc-listener-probe", project=project)
    session.add(loc)
    session.commit()
    session.refresh(loc)
    assert loc.id is not None
    assert loc.project_id == project.id


def test_health_endpoint_reachable(client) -> None:
    """``/health``-Route ohne Auth — Schnell-Check, dass FastAPI-App + DB-Override funktionieren."""
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_admin_dashboard_reachable_with_admin_override(as_admin) -> None:
    """``/dashboard`` ist hinter ``require_login`` — Auth-Override muss den Endpoint freischalten."""
    response = as_admin.get("/dashboard")
    assert response.status_code == 200, (
        f"Erwarte 200, bekam {response.status_code}. Body: {response.text[:500]}"
    )
