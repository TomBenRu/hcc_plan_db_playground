#!/usr/bin/env python3
"""
Daten-Migrationsskript: PonyORM SQLite → SQLModel SQLite

Liest alle Daten aus der alten PonyORM-Datenbank und überträgt sie
in die neue SQLModel/SQLAlchemy-Datenbankstruktur.

Aufruf:
    cd <worktree-root>
    .venv/bin/python migrate_ponyorm_to_sqlmodel.py [OLD_DB] [NEW_DB]

Standardwerte:
    OLD_DB = C:/Users/tombe/AppData/Local/happy_code_company/hcc_plan_dev/database/database.sqlite
    NEW_DB = C:/Users/tombe/AppData/Local/happy_code_company/hcc_plan_dev/database/database_sqlmodel.sqlite

Die neue Datei wird neu erstellt. Falls sie bereits existiert, wird sie ÜBERSCHRIEBEN.
"""

import logging
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)-8s  %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger(__name__)

EPOCH = datetime(1970, 1, 1)

# ════════════════════════════════════════════════════════════════════════════
# 1. HELPER-FUNKTIONEN
# ════════════════════════════════════════════════════════════════════════════


def h(val) -> str | None:
    """PonyORM Binary-UUID (16 Bytes) → SQLModel 32-Zeichen Hex-String."""
    if val is None:
        return None
    if isinstance(val, bytes):
        return uuid.UUID(bytes=val).hex
    # Fallback: bereits als String (z. B. im Testbetrieb)
    return str(val).replace('-', '')


def dt(val) -> str | None:
    """Naiver datetime-String → UTC datetime-String ('+00:00' anhängen)."""
    if val is None:
        return None
    s = str(val)
    if '+' not in s and 'Z' not in s:
        return s + '+00:00'
    return s


def interval_to_dt(days_float) -> str | None:
    """
    PonyORM INTERVAL (als Tage-Float) → SQLAlchemy INTERVAL auf SQLite.

    SQLAlchemy speichert timedelta auf SQLite als: epoch + timedelta (datetime-String).
    Beispiel: 0.041666... Tage (= 1 Stunde) → '1970-01-01 01:00:00.000000'
    """
    if days_float is None:
        return None
    td = timedelta(days=float(days_float))
    return (EPOCH + td).isoformat(sep=' ')


def rows_as_dicts(cursor: sqlite3.Cursor) -> list[dict]:
    """Alle Zeilen eines SELECT-Ergebnisses als Liste von Dicts zurückgeben."""
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def ins(conn: sqlite3.Connection, table: str, row: dict) -> None:
    """Generisches INSERT mit named columns."""
    cols = ', '.join(row.keys())
    placeholders = ', '.join(['?'] * len(row))
    conn.execute(f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})', list(row.values()))


# ════════════════════════════════════════════════════════════════════════════
# 2. SCHEMA ANLEGEN
# ════════════════════════════════════════════════════════════════════════════


def create_new_schema(new_db_path: str) -> None:
    """Neue SQLite-Datenbank mit dem SQLModel-Schema anlegen."""
    log.info(f'Erstelle neues Schema in: {new_db_path}')
    from sqlalchemy import create_engine
    from database.models import SQLModel  # importiert alle Tabellenklassen

    engine = create_engine(f'sqlite:///{new_db_path}')
    SQLModel.metadata.create_all(engine)
    engine.dispose()
    log.info('Schema erfolgreich erstellt.')


# ════════════════════════════════════════════════════════════════════════════
# 3. ENTITY-TABELLEN (in FK-Abhängigkeitsreihenfolge)
# ════════════════════════════════════════════════════════════════════════════


def migrate_excel_export_settings(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    Keine FK-Abhängigkeiten. Wird zuerst eingefügt.
    FK-Umkehrung: PonyORM hat ExcelSettings.project → SQLModel hat project.excel_export_settings_id.
    Die project-Spalte wird hier WEGGELASSEN (nicht in SQLModel-Schema).
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, color_head_weekdays_1, color_head_weekdays_2, '
        'color_head_locations_1, color_head_locations_2, '
        'color_day_nrs_1, color_day_nrs_2, '
        'color_column_kw_1, color_column_kw_2, created_at, last_modified '
        'FROM ExcelExportSettings'
    ))
    for r in rows:
        ins(new, 'excel_export_settings', {
            'id': h(r['id']),
            'color_head_weekdays_1': r['color_head_weekdays_1'],
            'color_head_weekdays_2': r['color_head_weekdays_2'],
            'color_head_locations_1': r['color_head_locations_1'],
            'color_head_locations_2': r['color_head_locations_2'],
            'color_day_nrs_1': r['color_day_nrs_1'],
            'color_day_nrs_2': r['color_day_nrs_2'],
            'color_column_kw_1': r['color_column_kw_1'],
            'color_column_kw_2': r['color_column_kw_2'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
        })
    log.info(f'  excel_export_settings: {len(rows):5d} Einträge')


def migrate_project(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    FK-Umkehrung: PonyORM ExcelSettings.project → SQLModel Project.excel_export_settings_id.
    Wir suchen für jedes Projekt das zugehörige ExcelSettings über den alten project-FK.
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, active, created_at, last_modified FROM Project'
    ))
    for r in rows:
        es = old.execute(
            'SELECT id FROM ExcelExportSettings WHERE project=?', (r['id'],)
        ).fetchone()
        ins(new, 'project', {
            'id': h(r['id']),
            'name': r['name'],
            'active': r['active'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'excel_export_settings_id': h(es[0]) if es else None,
        })
    log.info(f'  project: {len(rows):5d} Einträge')


def migrate_address(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    location_of_work-FK wird weggelassen (FK-Richtung umgekehrt →
    jetzt auf location_of_work.address_id).
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, street, postal_code, city, created_at, last_modified, '
        'prep_delete, project '
        'FROM Address'
    ))
    for r in rows:
        ins(new, 'address', {
            'id': h(r['id']),
            'name': r['name'],
            'street': r['street'],
            'postal_code': r['postal_code'],
            'city': r['city'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
        })
    log.info(f'  address: {len(rows):5d} Einträge')


def migrate_team(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """FK excel_export_settings bleibt auf Team-Seite (gleiche Richtung)."""
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, created_at, last_modified, prep_delete, notes, '
        'project, dispatcher, excel_export_settings '
        'FROM Team'
    ))
    for r in rows:
        ins(new, 'team', {
            'id': h(r['id']),
            'name': r['name'],
            'notes': r['notes'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'dispatcher_id': h(r['dispatcher']),
            'excel_export_settings_id': h(r['excel_export_settings']),
        })
    log.info(f'  team: {len(rows):5d} Einträge')


def migrate_cast_rule(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, rule, created_at, last_modified, prep_delete, project FROM CastRule'
    ))
    for r in rows:
        ins(new, 'cast_rule', {
            'id': h(r['id']),
            'name': r['name'],
            'rule': r['rule'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
        })
    log.info(f'  cast_rule: {len(rows):5d} Einträge')


def migrate_flag(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, category, name, created_at, last_modified, prep_delete, project FROM Flag'
    ))
    for r in rows:
        ins(new, 'flag', {
            'id': h(r['id']),
            'category': r['category'],
            'name': r['name'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
        })
    log.info(f'  flag: {len(rows):5d} Einträge')


def migrate_skill(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, notes, created_at, last_modified, prep_delete, project FROM Skill'
    ))
    for r in rows:
        ins(new, 'skill', {
            'id': h(r['id']),
            'name': r['name'],
            'notes': r['notes'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
        })
    log.info(f'  skill: {len(rows):5d} Einträge')


def migrate_time_of_day_enum(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, abbreviation, time_index, created_at, last_modified, '
        'prep_delete, project, project_standard '
        'FROM TimeOfDayEnum'
    ))
    for r in rows:
        ins(new, 'time_of_day_enum', {
            'id': h(r['id']),
            'name': r['name'],
            'abbreviation': r['abbreviation'],
            'time_index': r['time_index'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'project_standard_id': h(r['project_standard']),
        })
    log.info(f'  time_of_day_enum: {len(rows):5d} Einträge')


def migrate_time_of_day(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, start, end, time_of_day_enum, created_at, last_modified, '
        'prep_delete, project, project_standard, project_defaults '
        'FROM TimeOfDay'
    ))
    for r in rows:
        ins(new, 'time_of_day', {
            'id': h(r['id']),
            'name': r['name'],
            'start': r['start'],
            'end': r['end'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'project_defaults_id': h(r['project_defaults']),
            'project_standard_id': h(r['project_standard']),
            'time_of_day_enum_id': h(r['time_of_day_enum']),
        })
    log.info(f'  time_of_day: {len(rows):5d} Einträge')


def migrate_person(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    Umbenennungen: project_of_admin → admin_of_project_id.
    Spalte address bleibt als address_id.
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, f_name, l_name, gender, role, email, phone_nr, username, password, '
        'requested_assignments, notes, created_at, last_modified, prep_delete, '
        'project, project_of_admin, address '
        'FROM Person'
    ))
    for r in rows:
        ins(new, 'person', {
            'id': h(r['id']),
            'f_name': r['f_name'],
            'l_name': r['l_name'],
            'gender': r['gender'],
            'role': r['role'],
            'email': r['email'],
            'phone_nr': r['phone_nr'],
            'username': r['username'],
            'password': r['password'],
            'requested_assignments': r['requested_assignments'],
            'notes': r['notes'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'admin_of_project_id': h(r['project_of_admin']),
            'address_id': h(r['address']),
        })
    log.info(f'  person: {len(rows):5d} Einträge')


def migrate_location_of_work(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    FK-Umkehrung: PonyORM Address.location_of_work → SQLModel LocationOfWork.address_id.
    Wir suchen für jede Location deren Adresse über den alten Address.location_of_work-FK.
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, notes, nr_actors, fixed_cast, fixed_cast_only_if_available, '
        'created_at, last_modified, prep_delete, project '
        'FROM LocationOfWork'
    ))
    for r in rows:
        addr = old.execute(
            'SELECT id FROM Address WHERE location_of_work=?', (r['id'],)
        ).fetchone()
        ins(new, 'location_of_work', {
            'id': h(r['id']),
            'name': r['name'],
            'notes': r['notes'],
            'nr_actors': r['nr_actors'],
            'fixed_cast': r['fixed_cast'],
            'fixed_cast_only_if_available': r['fixed_cast_only_if_available'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'address_id': h(addr[0]) if addr else None,
        })
    log.info(f'  location_of_work: {len(rows):5d} Einträge')


def migrate_combination_locations_possible(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    time_span_between: PonyORM INTERVAL (Tage-Float) →
    SQLAlchemy SQLite-INTERVAL (epoch + timedelta als datetime-String).
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, time_span_between, created_at, last_modified, prep_delete, project, team '
        'FROM CombinationLocationsPossible'
    ))
    for r in rows:
        ins(new, 'combination_locations_possible', {
            'id': h(r['id']),
            'time_span_between': interval_to_dt(r['time_span_between']),
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'team_id': h(r['team']),
        })
    log.info(f'  combination_locations_possible: {len(rows):5d} Einträge')


def migrate_plan_period(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, start, end, deadline, created_at, last_modified, prep_delete, '
        'notes, notes_for_employees, closed, remainder, team '
        'FROM PlanPeriod'
    ))
    for r in rows:
        ins(new, 'plan_period', {
            'id': h(r['id']),
            'start': r['start'],
            'end': r['end'],
            'deadline': r['deadline'],
            'notes': r['notes'],
            'notes_for_employees': r['notes_for_employees'],
            'closed': r['closed'],
            'remainder': r['remainder'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'team_id': h(r['team']),
        })
    log.info(f'  plan_period: {len(rows):5d} Einträge')


def migrate_actor_location_pref(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, score, created_at, last_modified, prep_delete, '
        'project, person, location_of_work, person_default '
        'FROM ActorLocationPref'
    ))
    for r in rows:
        ins(new, 'actor_location_pref', {
            'id': h(r['id']),
            'score': r['score'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'person_id': h(r['person']),
            'location_of_work_id': h(r['location_of_work']),
            'person_default_id': h(r['person_default']),
        })
    log.info(f'  actor_location_pref: {len(rows):5d} Einträge')


def migrate_actor_partner_location_pref(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, score, created_at, last_modified, prep_delete, '
        'person, partner, location_of_work, person_default '
        'FROM ActorPartnerLocationPref'
    ))
    for r in rows:
        ins(new, 'actor_partner_location_pref', {
            'id': h(r['id']),
            'score': r['score'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'person_id': h(r['person']),
            'partner_id': h(r['partner']),
            'location_of_work_id': h(r['location_of_work']),
            'person_default_id': h(r['person_default']),
        })
    log.info(f'  actor_partner_location_pref: {len(rows):5d} Einträge')


def migrate_actor_plan_period(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    Spalte avail_day_group wird WEGGELASSEN — in SQLModel ist der FK
    auf avail_day_group.actor_plan_period_id (gleiche semantische Richtung,
    PonyORM speicherte beide Seiten redundant).
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, notes, requested_assignments, required_assignments, '
        'created_at, last_modified, plan_period, person '
        'FROM ActorPlanPeriod'
    ))
    for r in rows:
        ins(new, 'actor_plan_period', {
            'id': h(r['id']),
            'notes': r['notes'],
            'requested_assignments': r['requested_assignments'],
            'required_assignments': r['required_assignments'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'plan_period_id': h(r['plan_period']),
            'person_id': h(r['person']),
        })
    log.info(f'  actor_plan_period: {len(rows):5d} Einträge')


def migrate_avail_day_group(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    FK-Umkehrung: PonyORM ActorPlanPeriod.avail_day_group → SQLModel AvailDayGroup.actor_plan_period_id.
    Der FK liegt im alten Schema auf ActorPlanPeriod-Seite — wir suchen ihn per Rückwärtssuche.
    Self-referential (avail_day_group → avail_day_group): Da FK-Constraints deaktiviert,
    können alle Zeilen direkt eingefügt werden.
    """
    rows = rows_as_dicts(old.execute(
        'SELECT id, nr_avail_day_groups, variation_weight, created_at, last_modified, avail_day_group '
        'FROM AvailDayGroup'
    ))
    for r in rows:
        # FK-Umkehrung: welche ActorPlanPeriod verweist auf diese AvailDayGroup?
        app = old.execute(
            'SELECT id FROM ActorPlanPeriod WHERE avail_day_group=?', (r['id'],)
        ).fetchone()
        ins(new, 'avail_day_group', {
            'id': h(r['id']),
            'nr_avail_day_groups': r['nr_avail_day_groups'],
            'variation_weight': r['variation_weight'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'actor_plan_period_id': h(app[0]) if app else None,
            'avail_day_group_id': h(r['avail_day_group']),
        })
    log.info(f'  avail_day_group: {len(rows):5d} Einträge')


def migrate_required_avail_day_groups(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, num_avail_day_groups, created_at, last_modified, avail_day_group '
        'FROM RequiredAvailDayGroups'
    ))
    for r in rows:
        ins(new, 'required_avail_day_groups', {
            'id': h(r['id']),
            'num_avail_day_groups': r['num_avail_day_groups'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'avail_day_group_id': h(r['avail_day_group']),
        })
    log.info(f'  required_avail_day_groups: {len(rows):5d} Einträge')


def migrate_avail_day(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, date, created_at, last_modified, prep_delete, '
        'actor_plan_period, avail_day_group, time_of_day '
        'FROM AvailDay'
    ))
    for r in rows:
        ins(new, 'avail_day', {
            'id': h(r['id']),
            'date': r['date'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'actor_plan_period_id': h(r['actor_plan_period']),
            'avail_day_group_id': h(r['avail_day_group']),
            'time_of_day_id': h(r['time_of_day']),
        })
    log.info(f'  avail_day: {len(rows):5d} Einträge')


def migrate_max_fair_shifts_of_app(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, max_shifts, fair_shifts, created_at, last_modified, actor_plan_period '
        'FROM MaxFairShiftsOfApp'
    ))
    for r in rows:
        ins(new, 'max_fair_shifts_of_app', {
            'id': h(r['id']),
            'max_shifts': r['max_shifts'],
            'fair_shifts': r['fair_shifts'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'actor_plan_period_id': h(r['actor_plan_period']),
        })
    log.info(f'  max_fair_shifts_of_app: {len(rows):5d} Einträge')


def migrate_cast_group(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, fixed_cast, fixed_cast_only_if_available, prefer_fixed_cast_events, '
        'nr_actors, custom_rule, strict_cast_pref, plan_period, cast_rule '
        'FROM CastGroup'
    ))
    for r in rows:
        ins(new, 'cast_group', {
            'id': h(r['id']),
            'fixed_cast': r['fixed_cast'],
            'fixed_cast_only_if_available': r['fixed_cast_only_if_available'],
            'prefer_fixed_cast_events': r['prefer_fixed_cast_events'],
            'nr_actors': r['nr_actors'],
            'custom_rule': r['custom_rule'],
            'strict_cast_pref': r['strict_cast_pref'],
            'plan_period_id': h(r['plan_period']),
            'cast_rule_id': h(r['cast_rule']),
        })
    log.info(f'  cast_group: {len(rows):5d} Einträge')


def migrate_location_plan_period(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, notes, nr_actors, fixed_cast, fixed_cast_only_if_available, '
        'created_at, last_modified, plan_period, location_of_work '
        'FROM LocationPlanPeriod'
    ))
    for r in rows:
        ins(new, 'location_plan_period', {
            'id': h(r['id']),
            'notes': r['notes'],
            'nr_actors': r['nr_actors'],
            'fixed_cast': r['fixed_cast'],
            'fixed_cast_only_if_available': r['fixed_cast_only_if_available'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'plan_period_id': h(r['plan_period']),
            'location_of_work_id': h(r['location_of_work']),
        })
    log.info(f'  location_plan_period: {len(rows):5d} Einträge')


def migrate_event_group(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """Self-referential (event_group → event_group). FK-Constraints deaktiviert."""
    rows = rows_as_dicts(old.execute(
        'SELECT id, nr_event_groups, variation_weight, created_at, last_modified, '
        'location_plan_period, event_group '
        'FROM EventGroup'
    ))
    for r in rows:
        ins(new, 'event_group', {
            'id': h(r['id']),
            'nr_event_groups': r['nr_event_groups'],
            'variation_weight': r['variation_weight'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'location_plan_period_id': h(r['location_plan_period']),
            'event_group_id': h(r['event_group']),
        })
    log.info(f'  event_group: {len(rows):5d} Einträge')


def migrate_event(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, notes, date, created_at, last_modified, prep_delete, '
        'time_of_day, event_group, cast_group, location_plan_period '
        'FROM Event'
    ))
    for r in rows:
        ins(new, 'event', {
            'id': h(r['id']),
            'name': r['name'],
            'notes': r['notes'],
            'date': r['date'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'time_of_day_id': h(r['time_of_day']),
            'event_group_id': h(r['event_group']),
            'cast_group_id': h(r['cast_group']),
            'location_plan_period_id': h(r['location_plan_period']),
        })
    log.info(f'  event: {len(rows):5d} Einträge')


def migrate_skill_group(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, nr_actors, created_at, last_modified, prep_delete, skill, location_of_work '
        'FROM SkillGroup'
    ))
    for r in rows:
        ins(new, 'skill_group', {
            'id': h(r['id']),
            'nr_actors': r['nr_actors'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'skill_id': h(r['skill']),
            'location_of_work_id': h(r['location_of_work']),
        })
    log.info(f'  skill_group: {len(rows):5d} Einträge')


def migrate_plan(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, notes, location_columns, created_at, last_modified, prep_delete, '
        'plan_period, excel_export_settings '
        'FROM Plan'
    ))
    for r in rows:
        ins(new, 'plan', {
            'id': h(r['id']),
            'name': r['name'],
            'notes': r['notes'],
            'location_columns': r['location_columns'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'plan_period_id': h(r['plan_period']),
            'excel_export_settings_id': h(r['excel_export_settings']),
        })
    log.info(f'  plan: {len(rows):5d} Einträge')


def migrate_appointment(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, notes, guests, created_at, last_modified, prep_delete, event, plan '
        'FROM Appointment'
    ))
    for r in rows:
        ins(new, 'appointment', {
            'id': h(r['id']),
            'notes': r['notes'],
            'guests': r['guests'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'event_id': h(r['event']),
            'plan_id': h(r['plan']),
        })
    log.info(f'  appointment: {len(rows):5d} Einträge')


def migrate_employee_event_category(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, name, description, created_at, last_modified, prep_delete, project '
        'FROM EmployeeEventCategory'
    ))
    for r in rows:
        ins(new, 'employee_event_category', {
            'id': h(r['id']),
            'name': r['name'],
            'description': r['description'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
        })
    log.info(f'  employee_event_category: {len(rows):5d} Einträge')


def migrate_employee_event(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, title, description, start, end, google_calendar_event_id, '
        'created_at, last_modified, prep_delete, project, address '
        'FROM EmployeeEvent'
    ))
    for r in rows:
        ins(new, 'employee_event', {
            'id': h(r['id']),
            'title': r['title'],
            'description': r['description'],
            'start': dt(r['start']),
            'end': dt(r['end']),
            'google_calendar_event_id': r['google_calendar_event_id'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'prep_delete': dt(r['prep_delete']),
            'project_id': h(r['project']),
            'address_id': h(r['address']),
        })
    log.info(f'  employee_event: {len(rows):5d} Einträge')


def migrate_team_actor_assign(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, start, end, created_at, last_modified, person, team FROM TeamActorAssign'
    ))
    for r in rows:
        ins(new, 'team_actor_assign', {
            'id': h(r['id']),
            'start': r['start'],
            'end': r['end'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'person_id': h(r['person']),
            'team_id': h(r['team']),
        })
    log.info(f'  team_actor_assign: {len(rows):5d} Einträge')


def migrate_team_location_assign(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    rows = rows_as_dicts(old.execute(
        'SELECT id, start, end, created_at, last_modified, location_of_work, team '
        'FROM TeamLocationAssign'
    ))
    for r in rows:
        ins(new, 'team_location_assign', {
            'id': h(r['id']),
            'start': r['start'],
            'end': r['end'],
            'created_at': dt(r['created_at']),
            'last_modified': dt(r['last_modified']),
            'location_of_work_id': h(r['location_of_work']),
            'team_id': h(r['team']),
        })
    log.info(f'  team_location_assign: {len(rows):5d} Einträge')


# ════════════════════════════════════════════════════════════════════════════
# 4. M:N LINK-TABELLEN
# ════════════════════════════════════════════════════════════════════════════


def migrate_link(
    old: sqlite3.Connection,
    new: sqlite3.Connection,
    old_table: str,
    new_table: str,
    old_cols: tuple[str, str],
    new_cols: tuple[str, str],
) -> None:
    """Generische Funktion für M:N Link-Tabellen (je 2 UUID-Spalten)."""
    rows = old.execute(
        f'SELECT "{old_cols[0]}", "{old_cols[1]}" FROM "{old_table}"'
    ).fetchall()
    for r in rows:
        ins(new, new_table, {new_cols[0]: h(r[0]), new_cols[1]: h(r[1])})
    log.info(f'  {new_table}: {len(rows):5d} Einträge  (aus {old_table})')


def migrate_all_link_tables(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """
    Mapping aller M:N-Tabellen:
    PonyORM-Tabellenname → SQLModel-Tabellenname, (alte Spalten) → (neue Spalten)
    """
    link_map = [
        # (PonyORM-Tabelle, SQLModel-Tabelle, (old_col1, old_col2), (new_col1, new_col2))
        ('ActorLocationPref_ActorPlanPeriod', 'actor_plan_period_loc_pref',
         ('actorlocationpref', 'actorplanperiod'),
         ('actor_location_pref_id', 'actor_plan_period_id')),

        ('ActorLocationPref_AvailDay', 'avail_day_loc_pref',
         ('actorlocationpref', 'availday'),
         ('actor_location_pref_id', 'avail_day_id')),

        ('ActorPartnerLocationPref_ActorPlanPeriod', 'actor_plan_period_partner_pref',
         ('actorpartnerlocationpref', 'actorplanperiod'),
         ('actor_partner_location_pref_id', 'actor_plan_period_id')),

        ('ActorPartnerLocationPref_AvailDay', 'avail_day_partner_pref',
         ('actorpartnerlocationpref', 'availday'),
         ('actor_partner_location_pref_id', 'avail_day_id')),

        ('ActorPlanPeriod_CombinationLocationsPossible', 'actor_plan_period_combination_loc',
         ('actorplanperiod', 'combinationlocationspossible'),
         ('actor_plan_period_id', 'combination_locations_possible_id')),

        ('ActorPlanPeriod_TimeOfDay', 'actor_plan_period_time_of_day',
         ('actorplanperiod', 'timeofday'),
         ('actor_plan_period_id', 'time_of_day_id')),

        ('ActorPlanPeriod_TimeOfDay_2', 'actor_plan_period_time_of_day_std',
         ('actorplanperiod', 'timeofday'),
         ('actor_plan_period_id', 'time_of_day_id')),

        ('Appointment_AvailDay', 'avail_day_appointment',
         ('appointment', 'availday'),
         ('appointment_id', 'avail_day_id')),

        ('AvailDay_CombinationLocationsPossible', 'avail_day_combination_loc',
         ('availday', 'combinationlocationspossible'),
         ('avail_day_id', 'combination_locations_possible_id')),

        ('AvailDay_Skill', 'avail_day_skill',
         ('availday', 'skill'),
         ('avail_day_id', 'skill_id')),

        ('AvailDay_TimeOfDay', 'avail_day_time_of_day',
         ('availday', 'timeofday'),
         ('avail_day_id', 'time_of_day_id')),

        ('CastGroup_CastGroup', 'cast_group_link',
         ('castgroup', 'castgroup_2'),
         ('child_id', 'parent_id')),

        ('CombinationLocationsPossible_LocationOfWork', 'location_of_work_combination_loc',
         ('combinationlocationspossible', 'locationofwork'),
         ('combination_locations_possible_id', 'location_of_work_id')),

        ('CombinationLocationsPossible_Person', 'person_combination_loc',
         ('combinationlocationspossible', 'person'),
         ('combination_locations_possible_id', 'person_id')),

        ('EmployeeEvent_EmployeeEventCategory', 'employee_event_category_link',
         ('employeeevent', 'employeeeventcategory'),
         ('employee_event_id', 'employee_event_category_id')),

        ('EmployeeEvent_Person', 'person_employee_event',
         ('employeeevent', 'person'),
         ('employee_event_id', 'person_id')),

        ('EmployeeEvent_Team', 'team_employee_event',
         ('employeeevent', 'team'),
         ('employee_event_id', 'team_id')),

        ('Event_Flag', 'event_flag',
         ('event', 'flag'),
         ('event_id', 'flag_id')),

        ('Event_SkillGroup', 'event_skill_group',
         ('event', 'skillgroup'),
         ('event_id', 'skill_group_id')),

        ('Event_TimeOfDay', 'event_time_of_day',
         ('event', 'timeofday'),
         ('event_id', 'time_of_day_id')),

        ('Flag_Person', 'person_flag',
         ('flag', 'person'),
         ('flag_id', 'person_id')),

        ('LocationOfWork_RequiredAvailDayGroups', 'location_of_work_req_avail_day_groups',
         ('locationofwork', 'requiredavaildaygroups'),
         ('location_of_work_id', 'required_avail_day_groups_id')),

        ('LocationOfWork_TimeOfDay', 'location_of_work_time_of_day',
         ('locationofwork', 'timeofday'),
         ('location_of_work_id', 'time_of_day_id')),

        ('LocationOfWork_TimeOfDay_2', 'location_of_work_time_of_day_std',
         ('locationofwork', 'timeofday'),
         ('location_of_work_id', 'time_of_day_id')),

        ('LocationPlanPeriod_TimeOfDay', 'location_plan_period_time_of_day',
         ('locationplanperiod', 'timeofday'),
         ('location_plan_period_id', 'time_of_day_id')),

        ('LocationPlanPeriod_TimeOfDay_2', 'location_plan_period_time_of_day_std',
         ('locationplanperiod', 'timeofday'),
         ('location_plan_period_id', 'time_of_day_id')),

        ('Person_Skill', 'person_skill',
         ('person', 'skill'),
         ('person_id', 'skill_id')),

        ('Person_TimeOfDay', 'person_time_of_day',
         ('person', 'timeofday'),
         ('person_id', 'time_of_day_id')),

        ('Person_TimeOfDay_2', 'person_time_of_day_standard',
         ('person', 'timeofday'),
         ('person_id', 'time_of_day_id')),
    ]

    for old_table, new_table, old_cols, new_cols in link_map:
        migrate_link(old, new, old_table, new_table, old_cols, new_cols)


# ════════════════════════════════════════════════════════════════════════════
# 5. VERIFIKATION
# ════════════════════════════════════════════════════════════════════════════


def verify(old: sqlite3.Connection, new: sqlite3.Connection) -> None:
    """Vergleicht Zeilenanzahl pro Tabelle zwischen alt und neu."""
    log.info('\n--- Verifikation (Zeilenanzahl-Vergleich) ---')
    checks = [
        # (PonyORM-Tabelle, SQLModel-Tabelle)
        ('ExcelExportSettings', 'excel_export_settings'),
        ('Project', 'project'),
        ('Address', 'address'),
        ('Team', 'team'),
        ('Person', 'person'),
        ('CastRule', 'cast_rule'),
        ('Flag', 'flag'),
        ('Skill', 'skill'),
        ('TimeOfDayEnum', 'time_of_day_enum'),
        ('TimeOfDay', 'time_of_day'),
        ('LocationOfWork', 'location_of_work'),
        ('CombinationLocationsPossible', 'combination_locations_possible'),
        ('PlanPeriod', 'plan_period'),
        ('ActorLocationPref', 'actor_location_pref'),
        ('ActorPartnerLocationPref', 'actor_partner_location_pref'),
        ('ActorPlanPeriod', 'actor_plan_period'),
        ('AvailDayGroup', 'avail_day_group'),
        ('RequiredAvailDayGroups', 'required_avail_day_groups'),
        ('AvailDay', 'avail_day'),
        ('MaxFairShiftsOfApp', 'max_fair_shifts_of_app'),
        ('CastGroup', 'cast_group'),
        ('LocationPlanPeriod', 'location_plan_period'),
        ('EventGroup', 'event_group'),
        ('Event', 'event'),
        ('SkillGroup', 'skill_group'),
        ('Plan', 'plan'),
        ('Appointment', 'appointment'),
        ('EmployeeEventCategory', 'employee_event_category'),
        ('EmployeeEvent', 'employee_event'),
        ('TeamActorAssign', 'team_actor_assign'),
        ('TeamLocationAssign', 'team_location_assign'),
    ]
    ok = True
    for old_table, new_table in checks:
        n_old = count(old, old_table)
        n_new = count(new, new_table)
        status = '✓' if n_old == n_new else '✗ FEHLER'
        log.info(f'  {status}  {old_table:40s} {n_old:5d} → {n_new:5d}')
        if n_old != n_new:
            ok = False
    if ok:
        log.info('Alle Tabellen stimmen überein.')
    else:
        log.error('FEHLER: Einige Tabellen haben abweichende Zeilenzahlen!')


# ════════════════════════════════════════════════════════════════════════════
# 6. HAUPTPROGRAMM
# ════════════════════════════════════════════════════════════════════════════


def main() -> None:
    default_old = (
        'C:/Users/tombe/AppData/Local/happy_code_company/hcc_plan_dev/'
        'database/database.sqlite'
    )
    default_new = (
        'C:/Users/tombe/AppData/Local/happy_code_company/hcc_plan_dev/'
        'database/database_sqlmodel.sqlite'
    )

    old_path = sys.argv[1] if len(sys.argv) > 1 else default_old
    new_path = sys.argv[2] if len(sys.argv) > 2 else default_new

    # Unter WSL: Windows-Pfade umwandeln (nur wenn unter Linux/WSL)
    if sys.platform != 'win32':
        if old_path.startswith('C:/') or old_path.startswith('C:\\'):
            old_path = '/mnt/c/' + old_path[3:].replace('\\', '/')
        if new_path.startswith('C:/') or new_path.startswith('C:\\'):
            new_path = '/mnt/c/' + new_path[3:].replace('\\', '/')

    log.info(f'Alte DB: {old_path}')
    log.info(f'Neue DB: {new_path}')

    # Neue DB löschen falls vorhanden, dann Schema anlegen
    Path(new_path).unlink(missing_ok=True)
    create_new_schema(new_path)

    old = sqlite3.connect(old_path)
    new = sqlite3.connect(new_path)

    try:
        new.execute('PRAGMA foreign_keys = OFF')
        new.execute('PRAGMA journal_mode = WAL')

        log.info('\n--- Entity-Tabellen ---')
        migrate_excel_export_settings(old, new)
        migrate_project(old, new)
        migrate_address(old, new)
        migrate_team(old, new)
        migrate_cast_rule(old, new)
        migrate_flag(old, new)
        migrate_skill(old, new)
        migrate_time_of_day_enum(old, new)
        migrate_time_of_day(old, new)
        migrate_person(old, new)
        migrate_location_of_work(old, new)
        migrate_combination_locations_possible(old, new)
        migrate_plan_period(old, new)
        migrate_actor_location_pref(old, new)
        migrate_actor_partner_location_pref(old, new)
        migrate_actor_plan_period(old, new)
        migrate_avail_day_group(old, new)
        migrate_required_avail_day_groups(old, new)
        migrate_avail_day(old, new)
        migrate_max_fair_shifts_of_app(old, new)
        migrate_cast_group(old, new)
        migrate_location_plan_period(old, new)
        migrate_event_group(old, new)
        migrate_event(old, new)
        migrate_skill_group(old, new)
        migrate_plan(old, new)
        migrate_appointment(old, new)
        migrate_employee_event_category(old, new)
        migrate_employee_event(old, new)
        migrate_team_actor_assign(old, new)
        migrate_team_location_assign(old, new)

        log.info('\n--- M:N Link-Tabellen ---')
        migrate_all_link_tables(old, new)

        new.commit()
        log.info('\nDaten committed.')

        verify(old, new)

    except Exception as exc:
        new.rollback()
        log.exception(f'Migration fehlgeschlagen: {exc}')
        sys.exit(1)
    finally:
        old.close()
        new.close()


if __name__ == '__main__':
    main()
