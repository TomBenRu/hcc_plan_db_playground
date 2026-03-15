"""Datenbank-Engine und Session-Management (SQLModel / SQLAlchemy 2.x).

Ersetzt die bisherige PonyORM-Initialisierung.
Wird beim Import ausgeführt — erzeugt Engine, erstellt Tabellen und registriert Event Listeners.

Verwendung in Services:
    from database.database import get_session

    with get_session() as session:
        session.add(...)
        session.commit()
"""

import os
from contextlib import contextmanager
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from configuration.project_paths import curr_user_path_handler
from database.event_listeners import register_listeners

# Alle Modelle importieren, damit SQLModel.metadata vollständig ist
from database.models import *  # noqa: F401, F403

# ── Engine-Konfiguration ─────────────────────────────────────────────────────

db_folder = curr_user_path_handler.get_config().db_file_path
db_path = os.path.join(db_folder, "database.sqlite")

if not os.path.exists(db_folder):
    os.makedirs(db_folder)

engine = create_engine(
    f"sqlite:///{db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)

# ── Tabellen erstellen & Listeners registrieren ──────────────────────────────

SQLModel.metadata.create_all(engine)
register_listeners()


# ── Session-Factory ──────────────────────────────────────────────────────────


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context-Manager für eine DB-Session mit Auto-Commit.

    Bildet PonyORM's @db_session nach:
    - Automatisches commit() bei fehlerfreiem Verlassen
    - Automatisches rollback() bei Exception

    Verwendung:
        with get_session() as session:
            obj = Model(name="test")
            session.add(obj)
            # commit() passiert automatisch am Ende
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
