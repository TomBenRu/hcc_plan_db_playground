"""Pytest-Fixtures fuer Web-API-Tests.

Stellt Test-Infrastruktur bereit:
- Eigene SQLite-File-Test-DB im OS-temp-Verzeichnis
- Schema-Reset (`drop_all` + `create_all`) vor jedem Test fuer saubere Isolation
- FastAPI TestClient mit ``get_db_session``-Override
- Vorgefertigte WebUser-Fixtures (admin, dispatcher) inkl. Person-Verknuepfung
- ``as_admin`` / ``as_dispatcher``: Auth-Override fuer geschuetzte Routen

DATABASE_URL wird VOR allen Imports auf die Test-DB gesetzt — Schutz gegen
versehentliche Production-Treffer (vgl. Memory
``feedback_verify_database_url_before_destructive_db_op``).

Warum kein SAVEPOINT-Rollback: die DB-Services in ``database/db_services/``
oeffnen eigene Sessions via ``database.database.get_session()``. Diese sind
von der per ``dependency_overrides`` eingeschleusten Test-Session entkoppelt;
ein SAVEPOINT in der Test-Session wuerde Service-Schreibvorgaenge nicht
abdecken. Schema-Reset pro Test ist auf SQLite < 100 ms — pragmatisch fuer
die initiale Phase.
"""

from __future__ import annotations

import os
import pathlib
import secrets
import tempfile
from collections.abc import Generator
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# Test-DB-URL VOR allen Imports setzen — Sicherheits-Anker gegen Production-Leak
# ═══════════════════════════════════════════════════════════════════════════════

_TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "hcc_plan_test_session.sqlite"
if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
# Production-Indikatoren aus dem Umfeld entfernen (paranoia, kein Effekt auf SQLite)
for _var in ("RENDER", "RENDER_EXTERNAL_URL"):
    os.environ.pop(_var, None)
# Minimal-Settings, sonst wirft pydantic-Settings bei Modul-Import
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event as _sa_event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

# Modul-Imports AB JETZT — DATABASE_URL ist gesetzt, also greift der Server-Pfad
# (PG-/SQLite-Engine) in database.database. Wir patchen unten die Engine, weil
# der dortige `create_engine`-Call SQLite-untypische Pool-Settings nutzt.
import database.database as _database_module
import database.models  # noqa: F401 — Side-Effect: registriert Tabellen in SQLModel.metadata
import web_api.dependencies as _web_dependencies
import web_api.models.web_models  # noqa: F401 — Web-spezifische Tabellen ebenfalls registrieren
from database.event_listeners import register_listeners

from database.models import (
    Gender,
    Person,
    Project,
)
from web_api.auth.dependencies import require_login
from web_api.auth.service import hash_password
from web_api.dependencies import get_db_session
from web_api.main import app
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink


# ═══════════════════════════════════════════════════════════════════════════════
# Engine-Setup: eigene SQLite-Engine mit check_same_thread=False (TestClient) +
# FK-PRAGMA (sonst greift ON DELETE CASCADE auf SQLite nicht).
# ═══════════════════════════════════════════════════════════════════════════════


def _make_test_engine() -> Engine:
    engine = create_engine(
        f"sqlite:///{_TEST_DB_PATH.as_posix()}",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    @_sa_event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


_test_engine = _make_test_engine()

# Modul-globale Engine-Referenzen patchen — sowohl `database.database.engine`
# als auch `web_api.dependencies.engine` (Letzteres ist beim Import bereits
# als reference gezogen worden, muss daher separat aktualisiert werden).
_database_module.engine = _test_engine
_web_dependencies.engine = _test_engine

# `register_listeners()` registriert auf `sqlalchemy.orm.Session` global —
# gilt fuer alle Engines. Dennoch einmal aufrufen, falls es noch nicht passiert
# ist (Modul-Import-Reihenfolge ist hier idempotent).
register_listeners()


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _fresh_schema() -> Generator[None, None, None]:
    """Schema vor jedem Test komplett neu — saubere Isolation ohne Rollback-Komplexitaet."""
    SQLModel.metadata.drop_all(_test_engine)
    SQLModel.metadata.create_all(_test_engine)
    yield


@pytest.fixture
def session() -> Generator[Session, None, None]:
    """Reguläre Session — committet/rollbackt wie Production, kein SAVEPOINT.

    Aufrufer commiten explizit, wenn Daten persistiert werden sollen. Schema-Reset
    durch ``_fresh_schema`` raeumt zwischen Tests auf.
    """
    sess = Session(_test_engine)
    try:
        yield sess
    finally:
        sess.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient mit eigener Session pro Request.

    Bewusst ohne ``with``-Block instanziiert, damit der lifespan-Context von
    ``web_api/main.py`` (PG-Advisory-Lock) nicht laeuft — der wuerde gegen
    SQLite crashen.

    Endpoints holen sich ihre Session via ``Depends(get_db_session)`` — die
    Engine ist unsere Test-Engine, also landen alle Schreibvorgaenge in der
    Test-DB.
    """
    return TestClient(app)


@pytest.fixture
def project(session: Session) -> Project:
    """Frisches Test-Projekt — wird via ``_fresh_schema`` automatisch beim
    naechsten Test wieder weggewischt."""
    proj = Project(name=f"TestProject-{secrets.token_hex(4)}", active=True)
    session.add(proj)
    session.commit()
    session.refresh(proj)
    return proj


def _make_person(
    session: Session,
    *,
    project: Project,
    f_name: str,
    l_name: str,
    admin_of: Project | None = None,
) -> Person:
    # @example.com statt @test.local: Pydantic-EmailStr lehnt .local-TLDs ab
    # (RFC 6761 "special-use"). gender='f' weil das Show-Schema einen Enum-Wert
    # erfordert (None waere Validation-Error bei transitiver Hydration).
    person = Person(
        f_name=f_name,
        l_name=l_name,
        gender=Gender.female,
        email=f"{f_name.lower()}.{l_name.lower()}-{secrets.token_hex(3)}@example.com",
        username=f"{f_name.lower()}-{l_name.lower()}-{secrets.token_hex(3)}",
        password="dummy-hash-not-used",
        project=project,
        admin_of_project_id=admin_of.id if admin_of else None,
    )
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


def _make_web_user(
    session: Session,
    *,
    email: str,
    roles: list[WebUserRole],
    person: Person | None = None,
) -> WebUser:
    user = WebUser(
        email=email,
        hashed_password=hash_password("test-password"),
        is_active=True,
        person_id=person.id if person else None,
    )
    session.add(user)
    session.commit()
    for role in roles:
        session.add(WebUserRoleLink(web_user_id=user.id, role=role))
    session.commit()
    session.refresh(user, attribute_names=["role_links"])
    return user


@pytest.fixture
def admin_user(session: Session, project: Project) -> WebUser:
    """WebUser mit Admin-Rolle + Person mit ``admin_of_project_id`` auf das Test-Projekt."""
    person = _make_person(
        session,
        project=project,
        f_name="Admin",
        l_name="Test",
        admin_of=project,
    )
    return _make_web_user(
        session,
        email=f"admin-{secrets.token_hex(3)}@test.local",
        roles=[WebUserRole.admin],
        person=person,
    )


@pytest.fixture
def dispatcher_user(session: Session, project: Project) -> WebUser:
    """WebUser mit Dispatcher-Rolle + Person dem Test-Projekt zugeordnet (``project_id``)."""
    person = _make_person(
        session,
        project=project,
        f_name="Disp",
        l_name="Test",
    )
    return _make_web_user(
        session,
        email=f"dispatcher-{secrets.token_hex(3)}@test.local",
        roles=[WebUserRole.dispatcher],
        person=person,
    )


@pytest.fixture
def as_admin(client: TestClient, admin_user: WebUser) -> Generator[TestClient, None, None]:
    """Auth-Override: ``require_login`` und ``get_current_user`` liefern den admin_user
    direkt zurueck — JWT-Token-Flow wird umgangen."""
    app.dependency_overrides[require_login] = lambda: admin_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(require_login, None)


@pytest.fixture
def as_dispatcher(
    client: TestClient, dispatcher_user: WebUser
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[require_login] = lambda: dispatcher_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(require_login, None)


