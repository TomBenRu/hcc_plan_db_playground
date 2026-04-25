"""Einmalige Datenmigration: SQLite → PostgreSQL.

Liest alle Zeilen aus der lokalen SQLite-DB und schreibt sie in die
PostgreSQL-Datenbank (render.com). Das Schema muss in PostgreSQL bereits
via `alembic upgrade head` angelegt sein.

Verwendung:
    DATABASE_URL="postgresql://..." uv run scripts/migrate_sqlite_to_postgres.py

Übersprungene Tabellen:
    - alembic_version  (von Alembic verwaltet, nicht überschreiben)
    - apscheduler_jobs (von APScheduler verwaltet, noch nicht relevant)

Selbstreferenzielle FKs (z. B. event_group.event_group_id):
    Zwei-Pass-Strategie: erst NULL einfügen, dann per UPDATE korrigieren.
"""

import enum
import os
import sys
from datetime import datetime, timedelta

from sqlalchemy import Interval, MetaData, create_engine, exc, text
from sqlalchemy.schema import sort_tables_and_constraints

# Projekt-Root in sys.path für database.models-Import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel
from database.models import *  # noqa: F401, F403 — füllt SQLModel.metadata

# ── Konfiguration ────────────────────────────────────────────────────────────

SQLITE_PATH = r"C:\Users\tombe\AppData\Local\happy_code_company\hcc_plan_dev\database\database.sqlite"

PG_URL = os.environ.get("DATABASE_URL")
if not PG_URL:
    print("Fehler: Env-Var DATABASE_URL ist nicht gesetzt.")
    sys.exit(1)

SKIP_TABLES = {"alembic_version", "apscheduler_jobs"}

# ── Engines ──────────────────────────────────────────────────────────────────

src_engine = create_engine(f"sqlite:///{SQLITE_PATH}")
dst_engine = create_engine(PG_URL)

# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

_SQLITE_EPOCH = datetime(1970, 1, 1)


def _sqlite_epoch_to_timedelta(value: datetime | timedelta | None) -> timedelta | None:
    """SQLite speichert timedelta als datetime relativ zum Epoch (1970-01-01).
    Konvertiert zurück in ein echtes timedelta für PostgreSQL INTERVAL-Spalten.
    Falls der Wert bereits ein timedelta ist, wird er direkt zurückgegeben."""
    if value is None:
        return None
    if isinstance(value, timedelta):
        return value
    naive = value.replace(tzinfo=None) if value.tzinfo else value
    return naive - _SQLITE_EPOCH


def _find_self_ref_cols(table_name: str) -> set[str]:
    """Gibt Spaltennamen zurück, die auf die eigene Tabelle zeigen (selbstreferenziell)."""
    model_table = SQLModel.metadata.tables.get(table_name)
    if model_table is None:
        return set()
    self_ref = set()
    for col in model_table.columns:
        for fk in col.foreign_keys:
            if fk.column.table.name == table_name:
                self_ref.add(col.name)
    return self_ref


# Interval-Spalten aus SQLModel.metadata (zuverlässiger als DB-Reflection)
INTERVAL_COLS: dict[str, set[str]] = {
    table_name: {col.name for col in table.columns if isinstance(col.type, Interval)}
    for table_name, table in SQLModel.metadata.tables.items()
}

# ── Schema aus SQLite reflektieren ───────────────────────────────────────────

print("Lese Schema aus SQLite ...")
src_meta = MetaData()
src_meta.reflect(bind=src_engine)

all_tables = {name: t for name, t in src_meta.tables.items() if name not in SKIP_TABLES}

# Topologische Sortierung: Eltern-Tabellen vor Kind-Tabellen
# SQLModel.metadata (nicht SQLite-Reflection) verwenden, da SQLite FKs nicht
# zuverlässig speichert und sort_tables_and_constraints sonst blind sortiert.
_model_tables = {
    name: t for name, t in SQLModel.metadata.tables.items()
    if name in all_tables
}
sorted_pairs = sort_tables_and_constraints(_model_tables.values())
sorted_tables = [t for t, _ in sorted_pairs if t is not None]

print(f"  {len(sorted_tables)} Tabellen gefunden (ohne {SKIP_TABLES})\n")

# ── Migration ────────────────────────────────────────────────────────────────

# Sammelt selbstreferenzielle Updates für den zweiten Pass
self_ref_updates: list[tuple[str, str, str, list[dict]]] = []
# Format: (table_name, pk_col, self_ref_col, [{pk: ..., self_ref_col: ...}, ...])

with src_engine.connect() as src_conn, dst_engine.connect() as dst_conn:

    # Tabellen in umgekehrter Reihenfolge leeren (Kind vor Eltern → keine FK-Violation)
    print("Leere Tabellen in PostgreSQL ...")
    for table in reversed(sorted_tables):
        dst_conn.execute(text(f'DELETE FROM "{table.name}"'))
        print(f"  Geleert: {table.name}", flush=True)
    dst_conn.commit()
    print("Alle Tabellen geleert.\n", flush=True)

    # Daten tabellenweise übertragen
    total_rows = 0
    for table in sorted_tables:
        # SQLite-reflektiertes Table für SELECT verwenden, nicht das Modell-Table:
        # Falls das lokale Schema älter ist als SQLModel.metadata, würde das Modell-Table
        # Spalten referenzieren, die in SQLite fehlen (z. B. plan.is_binding).
        src_table = src_meta.tables[table.name]
        rows = src_conn.execute(src_table.select()).fetchall()
        if not rows:
            print(f"  {table.name}: leer")
            continue

        columns = list(rows[0]._mapping.keys())
        interval_cols = INTERVAL_COLS.get(table.name, set())
        self_ref_cols = _find_self_ref_cols(table.name)

        def _convert_row(row, null_self_ref: bool = False) -> dict:
            d = dict(row._mapping)
            for col in interval_cols:
                if col in d:
                    d[col] = _sqlite_epoch_to_timedelta(d[col])
            for key, val in d.items():
                if isinstance(val, enum.Enum):
                    d[key] = val.name
            if null_self_ref:
                for col in self_ref_cols:
                    d[col] = None
            return d

        converted = [_convert_row(row, null_self_ref=bool(self_ref_cols)) for row in rows]
        col_list = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(f":{c}" for c in columns)
        sql = text(f'INSERT INTO "{table.name}" ({col_list}) VALUES ({placeholders})')

        try:
            dst_conn.execute(sql, converted)
            dst_conn.commit()
            print(f"  {table.name}: {len(rows)} Zeilen")
            total_rows += len(rows)
        except exc.IntegrityError:
            # Batch fehlgeschlagen → zeilenweise mit Skip bei FK-Violation
            dst_conn.rollback()
            inserted = skipped = 0
            skipped_errors: list[str] = []
            for row_dict in converted:
                try:
                    dst_conn.execute(sql, [row_dict])
                    dst_conn.commit()
                    inserted += 1
                except exc.IntegrityError as e:
                    dst_conn.rollback()
                    skipped += 1
                    skipped_errors.append(str(e.orig).split("\n")[0])
            if skipped_errors:
                # Nur ersten und letzten Fehler ausgeben um Log-Flut zu vermeiden
                print(f"    Erster Skip: {skipped_errors[0]}")
                if len(skipped_errors) > 1:
                    print(f"    Letzter Skip: {skipped_errors[-1]}")
            print(f"  {table.name}: {inserted} Zeilen ({skipped} übersprungen)")
            total_rows += inserted

        # Selbstreferenzielle Updates für zweiten Pass merken
        if self_ref_cols:
            # Primärschlüssel der Tabelle ermitteln
            model_table = SQLModel.metadata.tables[table.name]
            pk_cols = [c.name for c in model_table.primary_key.columns]
            for sr_col in self_ref_cols:
                updates = [
                    {**{pk: dict(row._mapping)[pk] for pk in pk_cols}, sr_col: dict(row._mapping).get(sr_col)}
                    for row in rows
                    if dict(row._mapping).get(sr_col) is not None
                ]
                if updates:
                    self_ref_updates.append((table.name, pk_cols, sr_col, updates))

    # ── Zweiter Pass: selbstreferenzielle FKs nachtragen ─────────────────────
    if self_ref_updates:
        print("\nZweiter Pass: selbstreferenzielle FKs korrigieren ...")
        for table_name, pk_cols, sr_col, updates in self_ref_updates:
            where_clause = " AND ".join(f'"{pk}" = :{pk}' for pk in pk_cols)
            sql_update = text(
                f'UPDATE "{table_name}" SET "{sr_col}" = :{sr_col} WHERE {where_clause}'
            )
            updated = failed = 0
            for upd in updates:
                try:
                    dst_conn.execute(sql_update, upd)
                    dst_conn.commit()
                    updated += 1
                except exc.IntegrityError as e:
                    dst_conn.rollback()
                    failed += 1
            print(f"  {table_name}.{sr_col}: {updated} aktualisiert ({failed} fehlgeschlagen)")

print(f"\nMigration abgeschlossen — {total_rows} Zeilen gesamt.")
