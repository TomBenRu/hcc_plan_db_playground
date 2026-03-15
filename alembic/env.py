"""Alembic env.py — konfiguriert für SQLModel + SQLite (Batch-Mode).

Die DB-URL wird dynamisch aus der Anwendungskonfiguration gelesen,
nicht aus alembic.ini (dort steht nur ein Fallback).
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

# ── Alembic Config ───────────────────────────────────────────────────────────

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DB-URL: Falls nicht schon programmatisch gesetzt (z.B. via Tests),
# dynamisch aus der Anwendungskonfiguration lesen.
_current_url = config.get_main_option("sqlalchemy.url")
if not _current_url or _current_url == "sqlite:///database.sqlite":
    from configuration.project_paths import curr_user_path_handler

    db_folder = curr_user_path_handler.get_config().db_file_path
    db_path = os.path.join(db_folder, "database.sqlite")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

# Ziel-Metadata für Autogenerate
target_metadata = SQLModel.metadata


# ── Offline-Modus (generiert SQL ohne DB-Verbindung) ────────────────────────


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite: ALTER TABLE über Batch-Modus
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
            render_as_batch=True,  # SQLite: ALTER TABLE über Batch-Modus
            compare_type=True,     # Typänderungen erkennen
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
