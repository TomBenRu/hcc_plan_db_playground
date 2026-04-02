"""Datenbank-Engine und Session-Management (SQLModel / SQLAlchemy 2.x).

Ersetzt die bisherige PonyORM-Initialisierung.
Wird beim Import ausgeführt — erzeugt Engine und registriert Event Listeners.

Datenbankauswahl (Priorität):
    1. Env-Var DATABASE_URL → PostgreSQL (render.com oder lokale PG-Instanz)
    2. Fallback → SQLite unter dem plattformspezifischen AppData-Pfad

Verwendung in Services:
    from database.database import get_session

    with get_session() as session:
        session.add(...)
        session.commit()
"""

import os
from contextlib import contextmanager
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import event as _sa_event
from sqlmodel import Session, SQLModel, create_engine

from database.event_listeners import register_listeners

# Alle Modelle importieren, damit SQLModel.metadata vollständig ist
from database.models import *  # noqa: F401, F403

# ── Engine-Konfiguration ─────────────────────────────────────────────────────

# .env laden (nur falls Vars noch nicht gesetzt — explizite Env-Vars haben Vorrang)
load_dotenv()
_database_url = os.environ.get("DATABASE_URL")
_remote = True
if _database_url and _remote:
    # PostgreSQL: render.com setzt DATABASE_URL automatisch
    # pool_pre_ping: Erkennt serverseitig geschlossene Verbindungen (render.com Idle-Timeout)
    # pool_recycle: Verbindungen nach 30 min zwingend erneuern
    engine = create_engine(
        _database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_timeout=30,
        pool_recycle=1800,
    )
else:
    # SQLite-Fallback für lokale Entwicklung (kein DATABASE_URL gesetzt)
    from configuration.project_paths import curr_user_path_handler

    db_folder = curr_user_path_handler.get_config().db_file_path
    db_path = os.path.join(db_folder, "database.sqlite")

    if not os.path.exists(db_folder):
        os.makedirs(db_folder)

    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    # SQLite-Fallback: Tabellen direkt anlegen (kein Alembic-Deployment)
    SQLModel.metadata.create_all(engine)

    # FK-Constraints für SQLite aktivieren (standardmäßig deaktiviert)
    # Nötig damit ON DELETE CASCADE für Bulk-DELETEs wirkt
    @_sa_event.listens_for(engine, "connect")
    def _set_sqlite_fk_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ── Listeners registrieren ───────────────────────────────────────────────────

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
