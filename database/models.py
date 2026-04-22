"""SQLModel-Entity-Definitionen — PonyORM → SQLModel Migration

Migrationsergebnis von database/models.py (PonyORM) zu SQLModel/SQLAlchemy 2.x.
Alle Entities, Link-Tabellen und Beziehungen sind hier definiert.

Struktur:
  1. Imports & Helpers
  2. M:N-Link-Tabellen (29 Tabellen, vor Entities da link_model= keine Forward-Refs unterstützt)
  3. Entity-Modelle (in Abhängigkeitsreihenfolge, Leaf-Entities zuerst)
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SAEnum,
    Index,
    Interval,
    JSON,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlmodel import Field, Relationship, SQLModel

from database.enums import Gender, Role


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _created_at_col() -> Column:
    """Factory: created_at – gesetzt beim INSERT, danach unveränderlich."""
    return Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def _last_modified_col() -> Column:
    """Factory: last_modified – gesetzt beim INSERT, auto-aktualisiert bei UPDATE."""
    return Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def _optional_dt_col() -> Column:
    """Factory: optionales DateTime-Feld (z.B. prep_delete)."""
    return Column(DateTime(timezone=True), nullable=True)


# ═══════════════════════════════════════════════════════════════════════════════
# M:N-LINK-TABELLEN
# ═══════════════════════════════════════════════════════════════════════════════
# Alle Link-Tabellen VOR den Entity-Klassen definiert, da link_model= eine
# aufgelöste Klasse benötigt (String-Forward-References funktionieren nicht).
# FK-ondelete ist immer CASCADE: wenn eine Seite gelöscht wird, wird der Link entfernt.


# ── Person ↔ TimeOfDay ───────────────────────────────────────────────────────

class PersonTimeOfDayLink(SQLModel, table=True):
    """Person.time_of_days ↔ TimeOfDay.persons_defaults"""
    __tablename__ = "person_time_of_day"
    person_id: uuid.UUID = Field(foreign_key="person.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class PersonTimeOfDayStandardLink(SQLModel, table=True):
    """Person.time_of_day_standards ↔ TimeOfDay.persons_standard"""
    __tablename__ = "person_time_of_day_standard"
    person_id: uuid.UUID = Field(foreign_key="person.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


# ── Person ↔ Skill / Flag / CombLoc ─────────────────────────────────────────

class PersonSkillLink(SQLModel, table=True):
    __tablename__ = "person_skill"
    person_id: uuid.UUID = Field(foreign_key="person.id", primary_key=True, ondelete="CASCADE")
    skill_id: uuid.UUID = Field(foreign_key="skill.id", primary_key=True, ondelete="CASCADE")


class PersonFlagLink(SQLModel, table=True):
    __tablename__ = "person_flag"
    person_id: uuid.UUID = Field(foreign_key="person.id", primary_key=True, ondelete="CASCADE")
    flag_id: uuid.UUID = Field(foreign_key="flag.id", primary_key=True, ondelete="CASCADE")


class PersonCombLocLink(SQLModel, table=True):
    """Person ↔ CombinationLocationsPossible"""
    __tablename__ = "person_combination_loc"
    person_id: uuid.UUID = Field(foreign_key="person.id", primary_key=True, ondelete="CASCADE")
    combination_locations_possible_id: uuid.UUID = Field(
        foreign_key="combination_locations_possible.id", primary_key=True, ondelete="CASCADE"
    )


# ── Person / Team ↔ EmployeeEvent ───────────────────────────────────────────

class PersonEmployeeEventLink(SQLModel, table=True):
    """EmployeeEvent.participants ↔ Person.employee_events"""
    __tablename__ = "person_employee_event"
    person_id: uuid.UUID = Field(foreign_key="person.id", primary_key=True, ondelete="CASCADE")
    employee_event_id: uuid.UUID = Field(foreign_key="employee_event.id", primary_key=True, ondelete="CASCADE")


class TeamEmployeeEventLink(SQLModel, table=True):
    __tablename__ = "team_employee_event"
    team_id: uuid.UUID = Field(foreign_key="team.id", primary_key=True, ondelete="CASCADE")
    employee_event_id: uuid.UUID = Field(foreign_key="employee_event.id", primary_key=True, ondelete="CASCADE")


# ── ActorPlanPeriod ↔ TimeOfDay / CombLoc / Prefs ───────────────────────────

class ActorPlanPeriodTimeOfDayLink(SQLModel, table=True):
    """ActorPlanPeriod.time_of_days ↔ TimeOfDay.actor_plan_periods_defaults"""
    __tablename__ = "actor_plan_period_time_of_day"
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class ActorPlanPeriodTimeOfDayStdLink(SQLModel, table=True):
    """ActorPlanPeriod.time_of_day_standards ↔ TimeOfDay.actor_plan_periods_standard"""
    __tablename__ = "actor_plan_period_time_of_day_std"
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class ActorPlanPeriodCombLocLink(SQLModel, table=True):
    __tablename__ = "actor_plan_period_combination_loc"
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", primary_key=True, ondelete="CASCADE")
    combination_locations_possible_id: uuid.UUID = Field(
        foreign_key="combination_locations_possible.id", primary_key=True, ondelete="CASCADE"
    )


class ActorPlanPeriodPartnerPrefLink(SQLModel, table=True):
    """ActorPlanPeriod.actor_partner_location_prefs_defaults"""
    __tablename__ = "actor_plan_period_partner_pref"
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", primary_key=True, ondelete="CASCADE")
    actor_partner_location_pref_id: uuid.UUID = Field(
        foreign_key="actor_partner_location_pref.id", primary_key=True, ondelete="CASCADE"
    )


class ActorPlanPeriodLocPrefLink(SQLModel, table=True):
    """ActorPlanPeriod.actor_location_prefs_defaults"""
    __tablename__ = "actor_plan_period_loc_pref"
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", primary_key=True, ondelete="CASCADE")
    actor_location_pref_id: uuid.UUID = Field(
        foreign_key="actor_location_pref.id", primary_key=True, ondelete="CASCADE"
    )


# ── AvailDay ↔ TimeOfDay / Skill / Appointment / CombLoc / Prefs ────────────

class AvailDayTimeOfDayLink(SQLModel, table=True):
    """AvailDay.time_of_days ↔ TimeOfDay.avail_days_defaults"""
    __tablename__ = "avail_day_time_of_day"
    avail_day_id: uuid.UUID = Field(foreign_key="avail_day.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class AvailDaySkillLink(SQLModel, table=True):
    __tablename__ = "avail_day_skill"
    avail_day_id: uuid.UUID = Field(foreign_key="avail_day.id", primary_key=True, ondelete="CASCADE")
    skill_id: uuid.UUID = Field(foreign_key="skill.id", primary_key=True, ondelete="CASCADE")


class AvailDayAppointmentLink(SQLModel, table=True):
    __tablename__ = "avail_day_appointment"
    avail_day_id: uuid.UUID = Field(foreign_key="avail_day.id", primary_key=True, ondelete="CASCADE")
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id", primary_key=True, ondelete="CASCADE")


class AvailDayCombLocLink(SQLModel, table=True):
    __tablename__ = "avail_day_combination_loc"
    avail_day_id: uuid.UUID = Field(foreign_key="avail_day.id", primary_key=True, ondelete="CASCADE")
    combination_locations_possible_id: uuid.UUID = Field(
        foreign_key="combination_locations_possible.id", primary_key=True, ondelete="CASCADE"
    )


class AvailDayPartnerPrefLink(SQLModel, table=True):
    __tablename__ = "avail_day_partner_pref"
    avail_day_id: uuid.UUID = Field(foreign_key="avail_day.id", primary_key=True, ondelete="CASCADE")
    actor_partner_location_pref_id: uuid.UUID = Field(
        foreign_key="actor_partner_location_pref.id", primary_key=True, ondelete="CASCADE"
    )


class AvailDayLocPrefLink(SQLModel, table=True):
    __tablename__ = "avail_day_loc_pref"
    avail_day_id: uuid.UUID = Field(foreign_key="avail_day.id", primary_key=True, ondelete="CASCADE")
    actor_location_pref_id: uuid.UUID = Field(
        foreign_key="actor_location_pref.id", primary_key=True, ondelete="CASCADE"
    )


# ── LocationOfWork ↔ TimeOfDay / CombLoc / RequiredAvailDayGroups ────────────

class LocOfWorkTimeOfDayLink(SQLModel, table=True):
    """LocationOfWork.time_of_days ↔ TimeOfDay.locations_of_work_defaults"""
    __tablename__ = "location_of_work_time_of_day"
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class LocOfWorkTimeOfDayStdLink(SQLModel, table=True):
    """LocationOfWork.time_of_day_standards ↔ TimeOfDay.locations_of_work_standard"""
    __tablename__ = "location_of_work_time_of_day_std"
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class LocOfWorkCombLocLink(SQLModel, table=True):
    __tablename__ = "location_of_work_combination_loc"
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", primary_key=True, ondelete="CASCADE")
    combination_locations_possible_id: uuid.UUID = Field(
        foreign_key="combination_locations_possible.id", primary_key=True, ondelete="CASCADE"
    )


class LocOfWorkReqAvailDayGroupsLink(SQLModel, table=True):
    """LocationOfWork ↔ RequiredAvailDayGroups"""
    __tablename__ = "location_of_work_req_avail_day_groups"
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", primary_key=True, ondelete="CASCADE")
    required_avail_day_groups_id: uuid.UUID = Field(
        foreign_key="required_avail_day_groups.id", primary_key=True, ondelete="CASCADE"
    )


# ── LocationPlanPeriod ↔ TimeOfDay ──────────────────────────────────────────

class LocPlanPeriodTimeOfDayLink(SQLModel, table=True):
    """LocationPlanPeriod.time_of_days ↔ TimeOfDay.location_plan_periods_defaults"""
    __tablename__ = "location_plan_period_time_of_day"
    location_plan_period_id: uuid.UUID = Field(foreign_key="location_plan_period.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class LocPlanPeriodTimeOfDayStdLink(SQLModel, table=True):
    """LocationPlanPeriod.time_of_day_standards ↔ TimeOfDay.location_plan_periods_standard"""
    __tablename__ = "location_plan_period_time_of_day_std"
    location_plan_period_id: uuid.UUID = Field(foreign_key="location_plan_period.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


# ── Event ↔ TimeOfDay / Flag / SkillGroup ───────────────────────────────────

class EventTimeOfDayLink(SQLModel, table=True):
    """Event.time_of_days ↔ TimeOfDay.events_defaults"""
    __tablename__ = "event_time_of_day"
    event_id: uuid.UUID = Field(foreign_key="event.id", primary_key=True, ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id", primary_key=True, ondelete="CASCADE")


class EventFlagLink(SQLModel, table=True):
    __tablename__ = "event_flag"
    event_id: uuid.UUID = Field(foreign_key="event.id", primary_key=True, ondelete="CASCADE")
    flag_id: uuid.UUID = Field(foreign_key="flag.id", primary_key=True, ondelete="CASCADE")


class EventSkillGroupLink(SQLModel, table=True):
    __tablename__ = "event_skill_group"
    event_id: uuid.UUID = Field(foreign_key="event.id", primary_key=True, ondelete="CASCADE")
    skill_group_id: uuid.UUID = Field(foreign_key="skill_group.id", primary_key=True, ondelete="CASCADE")


# ── CastGroup ↔ CastGroup (self-ref M:N) ────────────────────────────────────

class CastGroupLink(SQLModel, table=True):
    """Self-referential M:N: CastGroup.parent_groups ↔ CastGroup.child_groups"""
    __tablename__ = "cast_group_link"
    parent_id: uuid.UUID = Field(foreign_key="cast_group.id", primary_key=True, ondelete="CASCADE")
    child_id: uuid.UUID = Field(foreign_key="cast_group.id", primary_key=True, ondelete="CASCADE")


# ── EmployeeEvent ↔ EmployeeEventCategory ───────────────────────────────────

class EmployeeEventCategoryLink(SQLModel, table=True):
    __tablename__ = "employee_event_category_link"
    employee_event_id: uuid.UUID = Field(foreign_key="employee_event.id", primary_key=True, ondelete="CASCADE")
    employee_event_category_id: uuid.UUID = Field(
        foreign_key="employee_event_category.id", primary_key=True, ondelete="CASCADE"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENTITY-MODELLE
# ═══════════════════════════════════════════════════════════════════════════════


# ── Leaf-Entities (keine/minimale FK-Abhängigkeiten) ─────────────────────────


class ExcelExportSettings(SQLModel, table=True):
    __tablename__ = "excel_export_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    color_head_weekdays_1: str = Field(default="#FFFFFF", max_length=15)
    color_head_weekdays_2: str = Field(default="#FFFFFF", max_length=15)
    color_head_locations_1: str = Field(default="#FFFFFF", max_length=15)
    color_head_locations_2: str = Field(default="#FFFFFF", max_length=15)
    color_day_nrs_1: str = Field(default="#FFFFFF", max_length=15)
    color_day_nrs_2: str = Field(default="#FFFFFF", max_length=15)
    color_column_kw_1: str = Field(default="#FFFFFF", max_length=15)
    color_column_kw_2: str = Field(default="#FFFFFF", max_length=15)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # Reverse relationships
    project: Optional["Project"] = Relationship(
        back_populates="excel_export_settings",
        sa_relationship_kwargs={"foreign_keys": "[Project.excel_export_settings_id]"},
    )
    teams: list["Team"] = Relationship(back_populates="excel_export_settings")
    plans: list["Plan"] = Relationship(back_populates="excel_export_settings")


class Address(SQLModel, table=True):
    __tablename__ = "address"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str | None = Field(default=None, max_length=50)
    street: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    city: str | None = Field(default=None, max_length=40)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")

    # Relationships
    project: "Project" = Relationship(back_populates="addresses")
    persons: list["Person"] = Relationship(back_populates="address")
    location_of_work: Optional["LocationOfWork"] = Relationship(back_populates="address")
    employee_events: list["EmployeeEvent"] = Relationship(back_populates="address")


class TimeOfDayEnum(SQLModel, table=True):
    """Zeigt durch time_index die Position im Tagesablauf an."""
    __tablename__ = "time_of_day_enum"
    __table_args__ = (
        UniqueConstraint("name", "project_id"),
        UniqueConstraint("abbreviation", "project_id"),
        UniqueConstraint("time_index", "project_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50)
    abbreviation: str = Field(max_length=10)
    time_index: int = Field(ge=0, le=255)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK (2x Project – Disambiguierung nötig)
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    project_standard_id: uuid.UUID | None = Field(default=None, foreign_key="project.id", ondelete="SET NULL")

    # Relationships
    project: "Project" = Relationship(
        back_populates="time_of_day_enums",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDayEnum.project_id]"},
    )
    project_standard: Optional["Project"] = Relationship(
        back_populates="time_of_day_enum_standards",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDayEnum.project_standard_id]"},
    )
    time_of_days: list["TimeOfDay"] = Relationship(back_populates="time_of_day_enum")


class CastRule(SQLModel, table=True):
    __tablename__ = "cast_rule"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    rule: str
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")

    # Relationships
    project: "Project" = Relationship(back_populates="cast_rules")
    cast_groups: list["CastGroup"] = Relationship(back_populates="cast_rule")


# ── Zweite Ebene (einfache FKs) ─────────────────────────────────────────────


class Project(SQLModel, table=True):
    __tablename__ = "project"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50, unique=True)
    active: bool = Field(default=False)
    use_simple_time_slots: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    excel_export_settings_id: uuid.UUID | None = Field(
        default=None, foreign_key="excel_export_settings.id", ondelete="SET NULL"
    )

    # Relationships (eigene FKs)
    excel_export_settings: Optional[ExcelExportSettings] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"foreign_keys": "[Project.excel_export_settings_id]"},
    )

    # Reverse relationships (1:N – FK liegt auf der anderen Seite)
    teams: list["Team"] = Relationship(back_populates="project", cascade_delete=True)
    persons: list["Person"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"foreign_keys": "[Person.project_id]"},
        cascade_delete=True,
    )
    admin: Optional["Person"] = Relationship(
        back_populates="project_of_admin",
        sa_relationship_kwargs={"foreign_keys": "[Person.admin_of_project_id]"},
    )
    addresses: list["Address"] = Relationship(back_populates="project", cascade_delete=True)
    locations_of_work: list["LocationOfWork"] = Relationship(back_populates="project", cascade_delete=True)
    time_of_days_all: list["TimeOfDay"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDay.project_id]"},
        cascade_delete=True,
    )
    time_of_days: list["TimeOfDay"] = Relationship(
        back_populates="project_defaults",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDay.project_defaults_id]"},
    )
    time_of_day_standards: list["TimeOfDay"] = Relationship(
        back_populates="project_standard",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDay.project_standard_id]"},
    )
    time_of_day_enums: list["TimeOfDayEnum"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDayEnum.project_id]"},
        cascade_delete=True,
    )
    time_of_day_enum_standards: list["TimeOfDayEnum"] = Relationship(
        back_populates="project_standard",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDayEnum.project_standard_id]"},
    )
    combination_locations_possibles: list["CombinationLocationsPossible"] = Relationship(
        back_populates="project", cascade_delete=True
    )
    actor_location_prefs: list["ActorLocationPref"] = Relationship(
        back_populates="project",
        sa_relationship_kwargs={"foreign_keys": "[ActorLocationPref.project_id]"},
        cascade_delete=True,
    )
    skills: list["Skill"] = Relationship(back_populates="project", cascade_delete=True)
    flags: list["Flag"] = Relationship(back_populates="project", cascade_delete=True)
    cast_rules: list["CastRule"] = Relationship(back_populates="project", cascade_delete=True)
    employee_events: list["EmployeeEvent"] = Relationship(back_populates="project", cascade_delete=True)
    employee_event_categories: list["EmployeeEventCategory"] = Relationship(
        back_populates="project", cascade_delete=True
    )


class TimeOfDay(SQLModel, table=True):
    """TimeOfDays werden beim Anlegen vererbt: Project → Person → ActorPlanPeriod → AvailDay."""
    __tablename__ = "time_of_day"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str | None = Field(default=None, max_length=50)
    start: time = Field(sa_column=Column(Time(), nullable=False))
    end: time = Field(sa_column=Column(Time(), nullable=False))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK (3x Project + 1x TimeOfDayEnum – Disambiguierung nötig)
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    project_defaults_id: uuid.UUID | None = Field(default=None, foreign_key="project.id", ondelete="SET NULL")
    project_standard_id: uuid.UUID | None = Field(default=None, foreign_key="project.id", ondelete="SET NULL")
    time_of_day_enum_id: uuid.UUID = Field(foreign_key="time_of_day_enum.id", ondelete="CASCADE")

    # Relationships (eigene FKs)
    project: "Project" = Relationship(
        back_populates="time_of_days_all",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDay.project_id]"},
    )
    project_defaults: Optional["Project"] = Relationship(
        back_populates="time_of_days",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDay.project_defaults_id]"},
    )
    project_standard: Optional["Project"] = Relationship(
        back_populates="time_of_day_standards",
        sa_relationship_kwargs={"foreign_keys": "[TimeOfDay.project_standard_id]"},
    )
    time_of_day_enum: "TimeOfDayEnum" = Relationship(back_populates="time_of_days")

    # 1:N reverse (FK auf der anderen Seite)
    avail_days: list["AvailDay"] = Relationship(
        back_populates="time_of_day",
        sa_relationship_kwargs={"foreign_keys": "[AvailDay.time_of_day_id]"},
    )
    events: list["Event"] = Relationship(
        back_populates="time_of_day",
        sa_relationship_kwargs={"foreign_keys": "[Event.time_of_day_id]"},
    )

    # M:N reverse
    persons_defaults: list["Person"] = Relationship(
        back_populates="time_of_days", link_model=PersonTimeOfDayLink
    )
    persons_standard: list["Person"] = Relationship(
        back_populates="time_of_day_standards", link_model=PersonTimeOfDayStandardLink
    )
    actor_plan_periods_defaults: list["ActorPlanPeriod"] = Relationship(
        back_populates="time_of_days", link_model=ActorPlanPeriodTimeOfDayLink
    )
    actor_plan_periods_standard: list["ActorPlanPeriod"] = Relationship(
        back_populates="time_of_day_standards", link_model=ActorPlanPeriodTimeOfDayStdLink
    )
    avail_days_defaults: list["AvailDay"] = Relationship(
        back_populates="time_of_days", link_model=AvailDayTimeOfDayLink
    )
    locations_of_work_defaults: list["LocationOfWork"] = Relationship(
        back_populates="time_of_days", link_model=LocOfWorkTimeOfDayLink
    )
    locations_of_work_standard: list["LocationOfWork"] = Relationship(
        back_populates="time_of_day_standards", link_model=LocOfWorkTimeOfDayStdLink
    )
    location_plan_periods_defaults: list["LocationPlanPeriod"] = Relationship(
        back_populates="time_of_days", link_model=LocPlanPeriodTimeOfDayLink
    )
    location_plan_periods_standard: list["LocationPlanPeriod"] = Relationship(
        back_populates="time_of_day_standards", link_model=LocPlanPeriodTimeOfDayStdLink
    )
    events_defaults: list["Event"] = Relationship(
        back_populates="time_of_days", link_model=EventTimeOfDayLink
    )


class LocationOfWork(SQLModel, table=True):
    """Einsatzort des Mitarbeiters. Soft-Delete über prep_delete."""
    __tablename__ = "location_of_work"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50)
    notes: str | None = Field(default=None)
    nr_actors: int = Field(default=2, ge=0, le=255)
    fixed_cast: str | None = Field(default=None)
    fixed_cast_only_if_available: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    address_id: uuid.UUID | None = Field(default=None, foreign_key="address.id", ondelete="SET NULL")

    # Relationships
    project: "Project" = Relationship(back_populates="locations_of_work")
    address: Optional["Address"] = Relationship(back_populates="location_of_work")
    team_location_assigns: list["TeamLocationAssign"] = Relationship(
        back_populates="location_of_work", cascade_delete=True
    )
    skill_groups: list["SkillGroup"] = Relationship(back_populates="location_of_work")
    location_plan_periods: list["LocationPlanPeriod"] = Relationship(
        back_populates="location_of_work", cascade_delete=True
    )
    actor_partner_location_prefs: list["ActorPartnerLocationPref"] = Relationship(
        back_populates="location_of_work"
    )
    actor_location_prefs: list["ActorLocationPref"] = Relationship(back_populates="location_of_work")

    # M:N
    time_of_days: list["TimeOfDay"] = Relationship(
        back_populates="locations_of_work_defaults", link_model=LocOfWorkTimeOfDayLink
    )
    time_of_day_standards: list["TimeOfDay"] = Relationship(
        back_populates="locations_of_work_standard", link_model=LocOfWorkTimeOfDayStdLink
    )
    combination_locations_possibles: list["CombinationLocationsPossible"] = Relationship(
        back_populates="locations_of_work", link_model=LocOfWorkCombLocLink
    )
    required_avail_day_groups: list["RequiredAvailDayGroups"] = Relationship(
        back_populates="locations_of_work", link_model=LocOfWorkReqAvailDayGroupsLink
    )


class Flag(SQLModel, table=True):
    """category bestimmt, welcher Klasse die Flag zugehört (person/event)."""
    __tablename__ = "flag"
    __table_args__ = (UniqueConstraint("name", "project_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    category: str | None = Field(default=None)
    name: str = Field(max_length=30)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")

    # Relationships
    project: "Project" = Relationship(back_populates="flags")

    # M:N
    persons: list["Person"] = Relationship(back_populates="flags", link_model=PersonFlagLink)
    events: list["Event"] = Relationship(back_populates="flags", link_model=EventFlagLink)


class Skill(SQLModel, table=True):
    __tablename__ = "skill"
    __table_args__ = (UniqueConstraint("name", "project_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field()
    notes: str = Field(default="")
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")

    # Relationships
    project: "Project" = Relationship(back_populates="skills")
    skill_groups: list["SkillGroup"] = Relationship(back_populates="skill")

    # M:N
    persons: list["Person"] = Relationship(back_populates="skills", link_model=PersonSkillLink)
    avail_days: list["AvailDay"] = Relationship(back_populates="skills", link_model=AvailDaySkillLink)


# ── Dritte Ebene (mittlere Abhängigkeit) ─────────────────────────────────────


class Person(SQLModel, table=True):
    """Soft-Delete über prep_delete. Nicht aus DB löschen für Konsistenz zurückliegender Pläne."""
    __tablename__ = "person"
    __table_args__ = (UniqueConstraint("f_name", "l_name", "project_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    f_name: str = Field(max_length=50)
    l_name: str = Field(max_length=50)
    gender: Gender | None = Field(default=None, sa_column=Column(SAEnum(Gender), nullable=True))
    role: Role | None = Field(default=None, sa_column=Column(SAEnum(Role), nullable=True))
    email: str = Field(max_length=50)
    phone_nr: str | None = Field(default=None, max_length=50)
    username: str = Field(max_length=50, unique=True)
    password: str
    requested_assignments: int = Field(default=8, ge=0, le=65535)
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK (2x Project + 1x Address – Disambiguierung nötig für Project)
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    admin_of_project_id: uuid.UUID | None = Field(default=None, foreign_key="project.id", ondelete="SET NULL")
    address_id: uuid.UUID | None = Field(default=None, foreign_key="address.id", ondelete="SET NULL")

    # Relationships (eigene FKs)
    project: "Project" = Relationship(
        back_populates="persons",
        sa_relationship_kwargs={"foreign_keys": "[Person.project_id]"},
    )
    project_of_admin: Optional["Project"] = Relationship(
        back_populates="admin",
        sa_relationship_kwargs={"foreign_keys": "[Person.admin_of_project_id]"},
    )
    address: Optional["Address"] = Relationship(back_populates="persons")

    # 1:N reverse
    team_actor_assigns: list["TeamActorAssign"] = Relationship(back_populates="person", cascade_delete=True)
    teams_of_dispatcher: list["Team"] = Relationship(
        back_populates="dispatcher", passive_deletes="all"
    )
    actor_plan_periods: list["ActorPlanPeriod"] = Relationship(back_populates="person", cascade_delete=True)
    actor_partner_location_prefs: list["ActorPartnerLocationPref"] = Relationship(
        back_populates="person",
        sa_relationship_kwargs={"foreign_keys": "[ActorPartnerLocationPref.person_id]"},
    )
    actor_partner_location_prefs_as_partner: list["ActorPartnerLocationPref"] = Relationship(
        back_populates="partner",
        sa_relationship_kwargs={"foreign_keys": "[ActorPartnerLocationPref.partner_id]"},
    )
    actor_partner_location_prefs_defaults: list["ActorPartnerLocationPref"] = Relationship(
        back_populates="person_default",
        sa_relationship_kwargs={"foreign_keys": "[ActorPartnerLocationPref.person_default_id]"},
    )
    actor_location_prefs: list["ActorLocationPref"] = Relationship(
        back_populates="person",
        sa_relationship_kwargs={"foreign_keys": "[ActorLocationPref.person_id]"},
    )
    actor_location_prefs_defaults: list["ActorLocationPref"] = Relationship(
        back_populates="person_default",
        sa_relationship_kwargs={"foreign_keys": "[ActorLocationPref.person_default_id]"},
    )

    # M:N
    time_of_days: list["TimeOfDay"] = Relationship(
        back_populates="persons_defaults", link_model=PersonTimeOfDayLink
    )
    time_of_day_standards: list["TimeOfDay"] = Relationship(
        back_populates="persons_standard", link_model=PersonTimeOfDayStandardLink
    )
    skills: list["Skill"] = Relationship(back_populates="persons", link_model=PersonSkillLink)
    flags: list["Flag"] = Relationship(back_populates="persons", link_model=PersonFlagLink)
    combination_locations_possibles: list["CombinationLocationsPossible"] = Relationship(
        back_populates="persons", link_model=PersonCombLocLink
    )
    employee_events: list["EmployeeEvent"] = Relationship(
        back_populates="participants", link_model=PersonEmployeeEventLink
    )

    @property
    def full_name(self) -> str:
        return f"{self.f_name} {self.l_name}"


class Team(SQLModel, table=True):
    __tablename__ = "team"
    __table_args__ = (UniqueConstraint("project_id", "name"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50)
    notes: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    dispatcher_id: uuid.UUID | None = Field(default=None, foreign_key="person.id", ondelete="SET NULL")
    excel_export_settings_id: uuid.UUID | None = Field(
        default=None, foreign_key="excel_export_settings.id", ondelete="SET NULL"
    )

    # Relationships
    project: "Project" = Relationship(back_populates="teams")
    dispatcher: Optional["Person"] = Relationship(back_populates="teams_of_dispatcher")
    excel_export_settings: Optional[ExcelExportSettings] = Relationship(back_populates="teams")

    # 1:N reverse
    team_actor_assigns: list["TeamActorAssign"] = Relationship(back_populates="team", cascade_delete=True)
    team_location_assigns: list["TeamLocationAssign"] = Relationship(back_populates="team", cascade_delete=True)
    plan_periods: list["PlanPeriod"] = Relationship(back_populates="team", cascade_delete=True)
    combination_locations_possibles: list["CombinationLocationsPossible"] = Relationship(
        back_populates="team"
    )

    # M:N
    employee_events: list["EmployeeEvent"] = Relationship(
        back_populates="teams", link_model=TeamEmployeeEventLink
    )


class PlanPeriod(SQLModel, table=True):
    __tablename__ = "plan_period"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    start: date
    end: date
    deadline: date
    notes: str | None = Field(default=None)
    notes_for_employees: str | None = Field(default=None)
    closed: bool = Field(default=False)
    remainder: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    team_id: uuid.UUID = Field(foreign_key="team.id", ondelete="CASCADE")

    # Relationships
    team: Team = Relationship(back_populates="plan_periods")

    @property
    def project(self) -> "Project":
        """Kompatibilitäts-Property für PlanPeriodShow.project (war @property in PonyORM)."""
        return self.team.project

    # 1:N reverse
    actor_plan_periods: list["ActorPlanPeriod"] = Relationship(back_populates="plan_period", cascade_delete=True)
    location_plan_periods: list["LocationPlanPeriod"] = Relationship(
        back_populates="plan_period", cascade_delete=True
    )
    cast_groups: list["CastGroup"] = Relationship(back_populates="plan_period", cascade_delete=True)
    plans: list["Plan"] = Relationship(back_populates="plan_period", cascade_delete=True)


class TeamActorAssign(SQLModel, table=True):
    """Zeitabschnitt der Team-Zuordnung einer Person. start inklusiv, end exklusiv."""
    __tablename__ = "team_actor_assign"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    start: date = Field(default_factory=date.today)
    end: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    person_id: uuid.UUID = Field(foreign_key="person.id", ondelete="CASCADE")
    team_id: uuid.UUID = Field(foreign_key="team.id", ondelete="CASCADE")

    # Relationships
    person: Person = Relationship(back_populates="team_actor_assigns")
    team: Team = Relationship(back_populates="team_actor_assigns")


class TeamLocationAssign(SQLModel, table=True):
    """Zeitabschnitt der Team-Zuordnung einer Location. start inklusiv, end exklusiv."""
    __tablename__ = "team_location_assign"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    start: date = Field(default_factory=date.today)
    end: date | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", ondelete="CASCADE")
    team_id: uuid.UUID = Field(foreign_key="team.id", ondelete="CASCADE")

    # Relationships
    location_of_work: LocationOfWork = Relationship(back_populates="team_location_assigns")
    team: Team = Relationship(back_populates="team_location_assigns")


# ── Vierte Ebene (tiefe Abhängigkeit) ────────────────────────────────────────


class ActorPlanPeriod(SQLModel, table=True):
    __tablename__ = "actor_plan_period"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    notes: str | None = Field(default=None)
    requested_assignments: int = Field(default=8, ge=0, le=65535)
    required_assignments: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    plan_period_id: uuid.UUID = Field(foreign_key="plan_period.id", ondelete="CASCADE")
    person_id: uuid.UUID = Field(foreign_key="person.id", ondelete="CASCADE")

    # Relationships
    plan_period: PlanPeriod = Relationship(back_populates="actor_plan_periods")
    person: Person = Relationship(back_populates="actor_plan_periods")

    @property
    def team(self) -> "Team":
        """Kompatibilitäts-Property für ActorPlanPeriodShow.team (war @property in PonyORM)."""
        return self.plan_period.team

    @property
    def project(self) -> "Project":
        """Kompatibilitäts-Property für ActorPlanPeriodShow.project (war @property in PonyORM)."""
        return self.plan_period.team.project

    # 1:1 / 1:N reverse
    avail_day_group: Optional["AvailDayGroup"] = Relationship(
        back_populates="actor_plan_period",
        sa_relationship_kwargs={"foreign_keys": "[AvailDayGroup.actor_plan_period_id]"},
        cascade_delete=True,
        passive_deletes=True,
    )
    avail_days: list["AvailDay"] = Relationship(back_populates="actor_plan_period", cascade_delete=True)
    max_fair_shifts_of_apps: list["MaxFairShiftsOfApp"] = Relationship(
        back_populates="actor_plan_period", cascade_delete=True
    )

    # M:N
    time_of_days: list["TimeOfDay"] = Relationship(
        back_populates="actor_plan_periods_defaults", link_model=ActorPlanPeriodTimeOfDayLink
    )
    time_of_day_standards: list["TimeOfDay"] = Relationship(
        back_populates="actor_plan_periods_standard", link_model=ActorPlanPeriodTimeOfDayStdLink
    )
    combination_locations_possibles: list["CombinationLocationsPossible"] = Relationship(
        back_populates="actor_plan_periods", link_model=ActorPlanPeriodCombLocLink
    )
    actor_partner_location_prefs_defaults: list["ActorPartnerLocationPref"] = Relationship(
        back_populates="actor_plan_periods_defaults", link_model=ActorPlanPeriodPartnerPrefLink
    )
    actor_location_prefs_defaults: list["ActorLocationPref"] = Relationship(
        back_populates="actor_plan_periods_defaults", link_model=ActorPlanPeriodLocPrefLink
    )


class LocationPlanPeriod(SQLModel, table=True):
    """Jede LocationPlanPeriod enthält genau 1 EventGroup (Root)."""
    __tablename__ = "location_plan_period"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    notes: str | None = Field(default=None)
    nr_actors: int | None = Field(default=2, ge=0, le=255)
    fixed_cast: str | None = Field(default=None)
    fixed_cast_only_if_available: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    plan_period_id: uuid.UUID = Field(foreign_key="plan_period.id", ondelete="CASCADE")
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", ondelete="CASCADE")

    # Relationships
    plan_period: PlanPeriod = Relationship(back_populates="location_plan_periods")
    location_of_work: LocationOfWork = Relationship(back_populates="location_plan_periods")

    @property
    def team(self) -> "Team":
        """Kompatibilitäts-Property für LocationPlanPeriodShow.team (war @property in PonyORM)."""
        return self.plan_period.team

    @property
    def project(self) -> "Project":
        """Kompatibilitäts-Property für LocationPlanPeriodShow.project (war @property in PonyORM)."""
        return self.plan_period.team.project

    # 1:N reverse
    event_group: Optional["EventGroup"] = Relationship(
        back_populates="location_plan_period",
        sa_relationship_kwargs={"foreign_keys": "[EventGroup.location_plan_period_id]"},
        cascade_delete=True,
    )
    events: list["Event"] = Relationship(back_populates="location_plan_period", cascade_delete=True)

    # M:N
    time_of_days: list["TimeOfDay"] = Relationship(
        back_populates="location_plan_periods_defaults", link_model=LocPlanPeriodTimeOfDayLink
    )
    time_of_day_standards: list["TimeOfDay"] = Relationship(
        back_populates="location_plan_periods_standard", link_model=LocPlanPeriodTimeOfDayStdLink
    )


class AvailDayGroup(SQLModel, table=True):
    """Hierarchische Baumstruktur. Root-Knoten zeigen auf ActorPlanPeriod,
    Kind-Knoten zeigen auf ihren Parent-AvailDayGroup."""
    __tablename__ = "avail_day_group"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nr_avail_day_groups: int | None = Field(default=None, ge=0)
    variation_weight: int = Field(default=1, ge=0, le=255)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK (Optional: entweder actor_plan_period ODER parent avail_day_group)
    actor_plan_period_id: uuid.UUID | None = Field(
        default=None, foreign_key="actor_plan_period.id", ondelete="CASCADE"
    )
    avail_day_group_id: uuid.UUID | None = Field(
        default=None, foreign_key="avail_day_group.id", ondelete="CASCADE"
    )

    # Relationships
    actor_plan_period: Optional[ActorPlanPeriod] = Relationship(
        back_populates="avail_day_group",
        sa_relationship_kwargs={"foreign_keys": "[AvailDayGroup.actor_plan_period_id]"},
    )

    # Self-referential 1:N (Adjacency List)
    avail_day_group: Optional["AvailDayGroup"] = Relationship(
        back_populates="avail_day_groups",
        sa_relationship_kwargs={"remote_side": "AvailDayGroup.id"},
    )
    avail_day_groups: list["AvailDayGroup"] = Relationship(
        back_populates="avail_day_group",
        cascade_delete=True,
        passive_deletes=True,
    )

    # 1:1 reverse
    avail_day: Optional["AvailDay"] = Relationship(
        back_populates="avail_day_group",
        sa_relationship_kwargs={"foreign_keys": "[AvailDay.avail_day_group_id]"},
    )
    required_avail_day_groups: Optional["RequiredAvailDayGroups"] = Relationship(
        back_populates="avail_day_group", cascade_delete=True
    )


class RequiredAvailDayGroups(SQLModel, table=True):
    __tablename__ = "required_avail_day_groups"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    num_avail_day_groups: int | None = Field(default=None, ge=0, le=255)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    avail_day_group_id: uuid.UUID = Field(foreign_key="avail_day_group.id", ondelete="CASCADE")

    # Relationships
    avail_day_group: AvailDayGroup = Relationship(back_populates="required_avail_day_groups")

    # M:N
    locations_of_work: list[LocationOfWork] = Relationship(
        back_populates="required_avail_day_groups", link_model=LocOfWorkReqAvailDayGroupsLink
    )


class CastGroup(SQLModel, table=True):
    """Besetzungsgruppen mit self-referential M:N (parent ↔ child)."""
    __tablename__ = "cast_group"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    fixed_cast: str | None = Field(default=None)
    fixed_cast_only_if_available: bool = Field(default=False)
    prefer_fixed_cast_events: bool = Field(default=False)
    nr_actors: int = Field(ge=0, le=65535)
    custom_rule: str | None = Field(default=None)
    strict_cast_pref: int = Field(default=2, ge=0, le=255)

    # FK
    plan_period_id: uuid.UUID = Field(foreign_key="plan_period.id", ondelete="CASCADE")
    cast_rule_id: uuid.UUID | None = Field(default=None, foreign_key="cast_rule.id", ondelete="SET NULL")

    # Relationships
    plan_period: PlanPeriod = Relationship(back_populates="cast_groups")
    cast_rule: Optional[CastRule] = Relationship(back_populates="cast_groups")

    # 1:1 reverse (Event zeigt auf CastGroup)
    event: Optional["Event"] = Relationship(back_populates="cast_group")

    # Self-referential M:N
    parent_groups: list["CastGroup"] = Relationship(
        back_populates="child_groups",
        link_model=CastGroupLink,
        sa_relationship_kwargs={
            "primaryjoin": "CastGroup.id == CastGroupLink.child_id",
            "secondaryjoin": "CastGroup.id == CastGroupLink.parent_id",
        },
    )
    child_groups: list["CastGroup"] = Relationship(
        back_populates="parent_groups",
        link_model=CastGroupLink,
        sa_relationship_kwargs={
            "primaryjoin": "CastGroup.id == CastGroupLink.parent_id",
            "secondaryjoin": "CastGroup.id == CastGroupLink.child_id",
        },
    )


class EventGroup(SQLModel, table=True):
    """Hierarchische Baumstruktur. Root-Knoten zeigen auf LocationPlanPeriod,
    Kind-Knoten zeigen auf ihren Parent-EventGroup."""
    __tablename__ = "event_group"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nr_event_groups: int | None = Field(default=None, ge=0)
    variation_weight: int = Field(default=1, ge=0, le=255)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK (Optional: entweder location_plan_period ODER parent event_group)
    location_plan_period_id: uuid.UUID | None = Field(
        default=None, foreign_key="location_plan_period.id", ondelete="CASCADE"
    )
    event_group_id: uuid.UUID | None = Field(
        default=None, foreign_key="event_group.id", ondelete="CASCADE"
    )

    # Relationships
    location_plan_period: Optional[LocationPlanPeriod] = Relationship(
        back_populates="event_group",
        sa_relationship_kwargs={"foreign_keys": "[EventGroup.location_plan_period_id]"},
    )

    # Self-referential 1:N
    event_group: Optional["EventGroup"] = Relationship(
        back_populates="event_groups",
        sa_relationship_kwargs={"remote_side": "EventGroup.id"},
    )
    event_groups: list["EventGroup"] = Relationship(
        back_populates="event_group",
        cascade_delete=True,
    )

    # 1:1 reverse
    event: Optional["Event"] = Relationship(back_populates="event_group")


# ── Fünfte Ebene ─────────────────────────────────────────────────────────────


class AvailDay(SQLModel, table=True):
    """Verfügbarkeit eines Mitarbeiters an einem Tag. Kann mehreren Appointments zugeordnet werden."""
    __tablename__ = "avail_day"
    __table_args__ = (UniqueConstraint("actor_plan_period_id", "date", "time_of_day_id"),)

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    date: date
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", ondelete="CASCADE")
    avail_day_group_id: uuid.UUID = Field(foreign_key="avail_day_group.id", ondelete="CASCADE")
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id")  # kein CASCADE – TimeOfDay ist Referenz

    # Relationships
    actor_plan_period: ActorPlanPeriod = Relationship(back_populates="avail_days")

    @property
    def project(self) -> "Project":
        """Kompatibilitäts-Property für AvailDayShow.project (war @property in PonyORM)."""
        return self.actor_plan_period.plan_period.team.project

    avail_day_group: AvailDayGroup = Relationship(
        back_populates="avail_day",
        sa_relationship_kwargs={"foreign_keys": "[AvailDay.avail_day_group_id]"},
    )
    time_of_day: TimeOfDay = Relationship(
        back_populates="avail_days",
        sa_relationship_kwargs={"foreign_keys": "[AvailDay.time_of_day_id]"},
    )

    # M:N
    time_of_days: list[TimeOfDay] = Relationship(
        back_populates="avail_days_defaults", link_model=AvailDayTimeOfDayLink
    )
    skills: list[Skill] = Relationship(back_populates="avail_days", link_model=AvailDaySkillLink)
    appointments: list["Appointment"] = Relationship(
        back_populates="avail_days", link_model=AvailDayAppointmentLink
    )
    combination_locations_possibles: list["CombinationLocationsPossible"] = Relationship(
        back_populates="avail_days", link_model=AvailDayCombLocLink
    )
    actor_partner_location_prefs_defaults: list["ActorPartnerLocationPref"] = Relationship(
        back_populates="avail_days_defaults", link_model=AvailDayPartnerPrefLink
    )
    actor_location_prefs_defaults: list["ActorLocationPref"] = Relationship(
        back_populates="avail_days_defaults", link_model=AvailDayLocPrefLink
    )


class Event(SQLModel, table=True):
    """Veranstaltung, Arbeitsschicht o.Ä. Immer genau einer EventGroup zugeordnet."""
    __tablename__ = "event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None)
    date: date
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    time_of_day_id: uuid.UUID = Field(foreign_key="time_of_day.id")  # kein CASCADE – Referenz
    event_group_id: uuid.UUID = Field(foreign_key="event_group.id", ondelete="CASCADE")
    cast_group_id: uuid.UUID = Field(foreign_key="cast_group.id", ondelete="CASCADE")
    location_plan_period_id: uuid.UUID = Field(foreign_key="location_plan_period.id", ondelete="CASCADE")

    # Relationships
    time_of_day: TimeOfDay = Relationship(
        back_populates="events",
        sa_relationship_kwargs={"foreign_keys": "[Event.time_of_day_id]"},
    )
    event_group: EventGroup = Relationship(back_populates="event")
    cast_group: CastGroup = Relationship(back_populates="event")
    location_plan_period: LocationPlanPeriod = Relationship(back_populates="events")

    # 1:N reverse
    appointments: list["Appointment"] = Relationship(back_populates="event", cascade_delete=True)

    # M:N
    time_of_days: list[TimeOfDay] = Relationship(
        back_populates="events_defaults", link_model=EventTimeOfDayLink
    )
    skill_groups: list["SkillGroup"] = Relationship(
        back_populates="events", link_model=EventSkillGroupLink
    )
    flags: list[Flag] = Relationship(back_populates="events", link_model=EventFlagLink)


# ── Sechste Ebene ────────────────────────────────────────────────────────────


class Plan(SQLModel, table=True):
    __tablename__ = "plan"
    __table_args__ = (
        UniqueConstraint("name", "plan_period_id"),
        Index(
            "uq_plan_one_binding_per_period",
            "plan_period_id",
            unique=True,
            postgresql_where=text("is_binding = TRUE"),
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=50)
    notes: str | None = Field(default=None)
    location_columns: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False, server_default="{}"))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())
    is_binding: bool = Field(default=False)

    # FK
    plan_period_id: uuid.UUID = Field(foreign_key="plan_period.id", ondelete="CASCADE")
    excel_export_settings_id: uuid.UUID | None = Field(
        default=None, foreign_key="excel_export_settings.id", ondelete="SET NULL"
    )

    # Relationships
    plan_period: PlanPeriod = Relationship(back_populates="plans")
    excel_export_settings: Optional[ExcelExportSettings] = Relationship(back_populates="plans")

    # 1:N reverse
    appointments: list["Appointment"] = Relationship(back_populates="plan", cascade_delete=True)


class Appointment(SQLModel, table=True):
    __tablename__ = "appointment"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    notes: str | None = Field(default=None)
    guests: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False, server_default="[]"))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    event_id: uuid.UUID = Field(foreign_key="event.id", ondelete="CASCADE")
    plan_id: uuid.UUID = Field(foreign_key="plan.id", ondelete="CASCADE")

    # Relationships
    event: Event = Relationship(back_populates="appointments")
    plan: Plan = Relationship(back_populates="appointments")

    # M:N
    avail_days: list[AvailDay] = Relationship(
        back_populates="appointments", link_model=AvailDayAppointmentLink
    )


class SkillGroup(SQLModel, table=True):
    """Legt fest, wie viele Personen den Skill beherrschen müssen."""
    __tablename__ = "skill_group"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    nr_actors: int | None = Field(default=None)  # None = alle müssen den Skill haben
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    skill_id: uuid.UUID = Field(foreign_key="skill.id", ondelete="CASCADE")
    location_of_work_id: uuid.UUID | None = Field(
        default=None, foreign_key="location_of_work.id", ondelete="SET NULL"
    )

    # Relationships
    skill: Skill = Relationship(back_populates="skill_groups")
    location_of_work: Optional[LocationOfWork] = Relationship(back_populates="skill_groups")

    # M:N
    events: list[Event] = Relationship(back_populates="skill_groups", link_model=EventSkillGroupLink)


class MaxFairShiftsOfApp(SQLModel, table=True):
    __tablename__ = "max_fair_shifts_of_app"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    max_shifts: int = Field(default=0, ge=0, le=65535)
    fair_shifts: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())

    # FK
    actor_plan_period_id: uuid.UUID = Field(foreign_key="actor_plan_period.id", ondelete="CASCADE")

    # Relationships
    actor_plan_period: ActorPlanPeriod = Relationship(back_populates="max_fair_shifts_of_apps")


# ── Präferenz-Entities ───────────────────────────────────────────────────────


class ActorPartnerLocationPref(SQLModel, table=True):
    """Präferenz für Partnerzuordnung an einem Einsatzort.
    3 FKs zu Person (person, partner, person_default) – Disambiguierung erforderlich."""
    __tablename__ = "actor_partner_location_pref"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    score: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK (3x Person + 1x LocationOfWork)
    person_id: uuid.UUID = Field(foreign_key="person.id", ondelete="CASCADE")
    partner_id: uuid.UUID = Field(foreign_key="person.id", ondelete="CASCADE")
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", ondelete="CASCADE")
    person_default_id: uuid.UUID | None = Field(default=None, foreign_key="person.id", ondelete="SET NULL")

    # Relationships (alle 3 Person-FKs disambiguiert)
    person: Person = Relationship(
        back_populates="actor_partner_location_prefs",
        sa_relationship_kwargs={"foreign_keys": "[ActorPartnerLocationPref.person_id]"},
    )
    partner: Person = Relationship(
        back_populates="actor_partner_location_prefs_as_partner",
        sa_relationship_kwargs={"foreign_keys": "[ActorPartnerLocationPref.partner_id]"},
    )
    person_default: Optional[Person] = Relationship(
        back_populates="actor_partner_location_prefs_defaults",
        sa_relationship_kwargs={"foreign_keys": "[ActorPartnerLocationPref.person_default_id]"},
    )
    location_of_work: LocationOfWork = Relationship(back_populates="actor_partner_location_prefs")

    # M:N reverse
    actor_plan_periods_defaults: list[ActorPlanPeriod] = Relationship(
        back_populates="actor_partner_location_prefs_defaults",
        link_model=ActorPlanPeriodPartnerPrefLink,
    )
    avail_days_defaults: list[AvailDay] = Relationship(
        back_populates="actor_partner_location_prefs_defaults",
        link_model=AvailDayPartnerPrefLink,
    )


class ActorLocationPref(SQLModel, table=True):
    """Präferenz einer Person für einen Einsatzort.
    2 FKs zu Person (person, person_default) – Disambiguierung erforderlich."""
    __tablename__ = "actor_location_pref"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    score: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK (2x Person + Project + LocationOfWork)
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    person_id: uuid.UUID = Field(foreign_key="person.id", ondelete="CASCADE")
    location_of_work_id: uuid.UUID = Field(foreign_key="location_of_work.id", ondelete="CASCADE")
    person_default_id: uuid.UUID | None = Field(default=None, foreign_key="person.id", ondelete="SET NULL")

    # Relationships
    project: Project = Relationship(
        back_populates="actor_location_prefs",
        sa_relationship_kwargs={"foreign_keys": "[ActorLocationPref.project_id]"},
    )
    person: Person = Relationship(
        back_populates="actor_location_prefs",
        sa_relationship_kwargs={"foreign_keys": "[ActorLocationPref.person_id]"},
    )
    person_default: Optional[Person] = Relationship(
        back_populates="actor_location_prefs_defaults",
        sa_relationship_kwargs={"foreign_keys": "[ActorLocationPref.person_default_id]"},
    )
    location_of_work: LocationOfWork = Relationship(back_populates="actor_location_prefs")

    # M:N reverse
    actor_plan_periods_defaults: list[ActorPlanPeriod] = Relationship(
        back_populates="actor_location_prefs_defaults",
        link_model=ActorPlanPeriodLocPrefLink,
    )
    avail_days_defaults: list[AvailDay] = Relationship(
        back_populates="actor_location_prefs_defaults",
        link_model=AvailDayLocPrefLink,
    )


class CombinationLocationsPossible(SQLModel, table=True):
    """Mögliche Location-Kombinationen an einem Tag. Wird von Project → Person → ActorPlanPeriod → AvailDay vererbt."""
    __tablename__ = "combination_locations_possible"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    time_span_between: timedelta = Field(sa_column=Column(Interval(), nullable=False))
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    team_id: uuid.UUID | None = Field(default=None, foreign_key="team.id", ondelete="SET NULL")

    # Relationships
    project: Project = Relationship(back_populates="combination_locations_possibles")
    team: Optional[Team] = Relationship(back_populates="combination_locations_possibles")

    # M:N
    locations_of_work: list[LocationOfWork] = Relationship(
        back_populates="combination_locations_possibles", link_model=LocOfWorkCombLocLink
    )
    persons: list[Person] = Relationship(
        back_populates="combination_locations_possibles", link_model=PersonCombLocLink
    )
    actor_plan_periods: list[ActorPlanPeriod] = Relationship(
        back_populates="combination_locations_possibles", link_model=ActorPlanPeriodCombLocLink
    )
    avail_days: list[AvailDay] = Relationship(
        back_populates="combination_locations_possibles", link_model=AvailDayCombLocLink
    )


# ── Employee-Events ──────────────────────────────────────────────────────────


class EmployeeEventCategory(SQLModel, table=True):
    __tablename__ = "employee_event_category"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=40, unique=True)
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")

    # Relationships
    project: Project = Relationship(back_populates="employee_event_categories")

    # M:N
    employee_events: list["EmployeeEvent"] = Relationship(
        back_populates="employee_event_categories", link_model=EmployeeEventCategoryLink
    )


class EmployeeEvent(SQLModel, table=True):
    __tablename__ = "employee_event"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str = Field(max_length=40)
    description: str
    start: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    end: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    google_calendar_event_id: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=_utcnow, sa_column=_created_at_col())
    last_modified: datetime = Field(default_factory=_utcnow, sa_column=_last_modified_col())
    prep_delete: datetime | None = Field(default=None, sa_column=_optional_dt_col())

    # FK
    project_id: uuid.UUID = Field(foreign_key="project.id", ondelete="CASCADE")
    address_id: uuid.UUID | None = Field(default=None, foreign_key="address.id", ondelete="SET NULL")

    # Relationships
    project: Project = Relationship(back_populates="employee_events")
    address: Optional[Address] = Relationship(back_populates="employee_events")

    # M:N
    teams: list[Team] = Relationship(back_populates="employee_events", link_model=TeamEmployeeEventLink)
    participants: list[Person] = Relationship(
        back_populates="employee_events", link_model=PersonEmployeeEventLink
    )
    employee_event_categories: list[EmployeeEventCategory] = Relationship(
        back_populates="employee_events", link_model=EmployeeEventCategoryLink
    )
