"""Alembic env.py — konfiguriert für SQLModel + SQLite/PostgreSQL.

Die DB-URL wird in folgender Priorität bestimmt:
    1. Env-Var DATABASE_URL (PostgreSQL auf render.com oder lokal)
    2. Anwendungskonfiguration → SQLite unter AppData
    3. Fallback-URL aus alembic.ini

render_as_batch wird nur für SQLite aktiviert (PostgreSQL unterstützt
ALTER TABLE nativ).
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Projekt-Root in sys.path, damit `database.*` importierbar ist
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# SQLModel-Modelle importieren → füllt SQLModel.metadata
from sqlmodel import SQLModel

from database.models import *  # noqa: F401, F403
from web_api.models.web_models import *  # noqa: F401, F403

# ── Alembic Config ───────────────────────────────────────────────────────────

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DB-URL: Priorität DATABASE_URL (PG) → AppData-Pfad (SQLite) → alembic.ini-Fallback
_database_url = os.environ.get("DATABASE_URL")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)
else:
    _current_url = config.get_main_option("sqlalchemy.url")
    if not _current_url or _current_url == "sqlite:///database.sqlite":
        from configuration.project_paths import curr_user_path_handler

        db_folder = curr_user_path_handler.get_config().db_file_path
        db_path = os.path.join(db_folder, "database.sqlite")
        config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

# render_as_batch nur für SQLite (PostgreSQL unterstützt ALTER TABLE nativ)
_url = config.get_main_option("sqlalchemy.url")
_is_sqlite = _url.startswith("sqlite")

# Ziel-Metadata für Autogenerate
target_metadata = SQLModel.metadata

# Tabellen, die Alembic bei autogenerate ignorieren soll
# (werden von externen Bibliotheken selbst verwaltet)
_EXCLUDE_TABLES = {"apscheduler_jobs"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in _EXCLUDE_TABLES:
        return False
    return True


# ── Offline-Modus (generiert SQL ohne DB-Verbindung) ────────────────────────


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online-Modus (mit DB-Verbindung) ────────────────────────────────────────


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_is_sqlite,
            compare_type=True,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
