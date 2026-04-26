"""Service-Schicht für die Verfügbarkeits-Eingabe.

Alle DB-Zugriffe laufen über die injected Request-Session (Depends(get_db_session)).
db_services.* wird bewusst NICHT importiert — Mutations werden als direkte ORM-Calls
auf der übergebenen Session reimplementiert (strategisches Ziel: einheitliche Request-Session).
"""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import exists, func, select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    AvailDayGroup,
    Person,
    PersonTimeOfDayLink,
    Plan,
    PlanPeriod,
    Project,
    Team,
    TimeOfDay,
    TimeOfDayEnum,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ── Dataclasses (Service-Rückgaben) ───────────────────────────────────────────


@dataclass
class TeamInfo:
    team_id: uuid.UUID
    team_name: str


@dataclass
class OpenPlanPeriodInfo:
    actor_plan_period_id: uuid.UUID
    plan_period_id: uuid.UUID
    start: date
    end: date
    deadline: date
    notes_for_employees: str | None
    notes: str | None                    # ActorPlanPeriod.notes
    requested_assignments: int
    closed: bool
    team_id: uuid.UUID
    team_name: str

    @property
    def days_until_deadline(self) -> int | None:
        delta = (self.deadline - date.today()).days
        return delta

    @property
    def label(self) -> str:
        months_de = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                     "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        s = f"{self.start.day}. {months_de[self.start.month - 1]} {self.start.year}"
        e = f"{self.end.day}. {months_de[self.end.month - 1]} {self.end.year}"
        return f"{s} – {e}"

    @property
    def is_locked(self) -> bool:
        return self.closed or date.today() > self.deadline

    @property
    def deadline_severity(self) -> Literal["normal", "warning", "locked"]:
        if self.is_locked:
            return "locked"
        if self.days_until_deadline is not None and self.days_until_deadline <= 3:
            return "warning"
        return "normal"


@dataclass
class AvailDayMarker:
    avail_day_id: uuid.UUID
    day: date
    time_of_day_id: uuid.UUID
    time_of_day_name: str | None
    time_of_day_start: time
    time_of_day_end: time
    time_of_day_enum_id: uuid.UUID
    time_of_day_enum_name: str
    time_of_day_enum_abbreviation: str
    time_of_day_enum_time_index: int
    has_appointment: bool


@dataclass
class PersonTimeOfDayInfo:
    id: uuid.UUID
    name: str | None
    start: time
    end: time
    enum_id: uuid.UUID
    enum_name: str
    enum_abbreviation: str
    enum_time_index: int
    avail_day_count: int


@dataclass
class DayTodOption:
    """Eine TOD-Option für den Day-Panel (pro TimeOfDayEnum)."""
    time_of_day_id: uuid.UUID
    tod_name: str | None
    tod_start: time
    tod_end: time
    avail_day_id: uuid.UUID | None       # None = noch nicht eingetragen
    has_appointment: bool                # True = Termin → read-only


@dataclass
class DayEnumGroup:
    """Alle TOD-Optionen eines Enums für den Day-Panel."""
    enum_id: uuid.UUID
    enum_name: str
    enum_abbreviation: str
    enum_time_index: int
    options: list[DayTodOption]


@dataclass
class DayDetailViewModel:
    day: date
    actor_plan_period_id: uuid.UUID
    is_locked: bool
    enum_groups: list[DayEnumGroup]


@dataclass
class SidebarStats:
    total_entered: int
    total_appointed: int
    requested_assignments: int


@dataclass
class AvailabilityViewModel:
    active_period: OpenPlanPeriodInfo
    markers: list[AvailDayMarker]
    person_time_of_days: list[PersonTimeOfDayInfo]   # alle persönlichen TODs
    initial_date: str                                 # ISO, für FullCalendar initialDate
    sidebar_stats: SidebarStats
    teams: list[TeamInfo]                             # Teams des Users (für Dropdown)
    selected_team_id: uuid.UUID | None               # aktives Team
    is_simple_mode: bool                              # Project.use_simple_time_slots


# ── Simple-Mode-Helfer ────────────────────────────────────────────────────────


def is_simple_mode_for_person(session: Session, person_id: uuid.UUID) -> bool:
    """Liefert das Project.use_simple_time_slots-Flag für die Person."""
    return session.execute(
        sa_select(Project.use_simple_time_slots)
        .join(Person, Person.project_id == Project.id)
        .where(Person.id == person_id)
    ).scalar_one()


def get_project_enums(session: Session, project_id: uuid.UUID) -> list[TimeOfDayEnum]:
    """Alle TimeOfDayEnums des Projekts nach time_index sortiert (für Simple-Mode-Day-Panel)."""
    return list(session.execute(
        sa_select(TimeOfDayEnum)
        .where(TimeOfDayEnum.project_id == project_id)
        .where(TimeOfDayEnum.prep_delete.is_(None))
        .order_by(TimeOfDayEnum.time_index)
    ).scalars().all())


def ensure_simple_primary_tod(
    session: Session,
    person: Person,
    enum: TimeOfDayEnum,
) -> TimeOfDay | None:
    """Ermittelt die „primary"-TOD für (Person, Enum) im Simple-Modus.

    Regel (User-Vorgabe):
      1. Project-Default für dieses Enum existiert + ist bereits zur Person gelinkt → diese.
      2. Project-Default existiert, aber nicht gelinkt → Link anlegen, diese zurückgeben.
      3. Kein Project-Default, aber Person hat eine TOD zu diesem Enum → erste nach start.
      4. Keine TOD ermittelbar → None (Enum wird im UI ausgelassen).

    Seiteneffekt nur im Fall 2: `PersonTimeOfDayLink`-Insert.
    """
    # Schritt 1/2: Project-Default zu diesem Enum suchen.
    project_default = session.execute(
        sa_select(TimeOfDay)
        .where(TimeOfDay.project_defaults_id == person.project_id)
        .where(TimeOfDay.time_of_day_enum_id == enum.id)
        .where(TimeOfDay.prep_delete.is_(None))
        .order_by(TimeOfDay.start)
        .limit(1)
    ).scalar_one_or_none()

    if project_default is not None:
        # Link-Existenz prüfen
        link = session.get(PersonTimeOfDayLink, (person.id, project_default.id))
        if link is None:
            session.add(PersonTimeOfDayLink(
                person_id=person.id,
                time_of_day_id=project_default.id,
            ))
            session.flush()
        return project_default

    # Schritt 3: irgendeine Person-TOD zu diesem Enum.
    person_tod = session.execute(
        sa_select(TimeOfDay)
        .join(PersonTimeOfDayLink, PersonTimeOfDayLink.time_of_day_id == TimeOfDay.id)
        .where(PersonTimeOfDayLink.person_id == person.id)
        .where(TimeOfDay.time_of_day_enum_id == enum.id)
        .where(TimeOfDay.prep_delete.is_(None))
        .order_by(TimeOfDay.start)
        .limit(1)
    ).scalar_one_or_none()
    return person_tod


def find_avail_day_by_enum(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    day: date,
    enum_id: uuid.UUID,
) -> AvailDay | None:
    """Simple-Mode-Uniqueness: irgendein aktiver AvailDay für (app, day, enum)."""
    return session.execute(
        sa_select(AvailDay)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.prep_delete.is_(None))
        .where(TimeOfDay.time_of_day_enum_id == enum_id)
        .limit(1)
    ).scalar_one_or_none()


def delete_avail_days_by_enum(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    day: date,
    enum_id: uuid.UUID,
) -> int:
    """Simple-Mode-Delete: löscht ALLE AvailDays für (app, day, enum), inkl. Child-Groups.

    Gibt Anzahl gelöschter AvailDays zurück. Nutzer in der Router-Schicht muss vorher
    `has_appointment` pro betroffenem AvailDay prüfen — hier kein Guard, damit das
    mit dem Intervall-Modus-Delete-Pattern konsistent bleibt.
    """
    rows = session.execute(
        sa_select(AvailDay)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.prep_delete.is_(None))
        .where(TimeOfDay.time_of_day_enum_id == enum_id)
    ).scalars().all()
    count = 0
    for ad in rows:
        delete_avail_day(session, ad.id)
        count += 1
    return count


# ── Queries ───────────────────────────────────────────────────────────────────


def get_open_plan_periods_for_person(
    session: Session,
    person_id: uuid.UUID,
    team_id: uuid.UUID | None = None,
) -> list[OpenPlanPeriodInfo]:
    """Alle offenen PlanPeriods der Person, optional nach Team gefiltert."""
    stmt = (
        sa_select(
            ActorPlanPeriod.id.label("app_id"),
            ActorPlanPeriod.notes.label("app_notes"),
            ActorPlanPeriod.requested_assignments.label("requested_assignments"),
            PlanPeriod.id.label("pp_id"),
            PlanPeriod.start.label("pp_start"),
            PlanPeriod.end.label("pp_end"),
            PlanPeriod.deadline.label("pp_deadline"),
            PlanPeriod.notes_for_employees.label("pp_notes_for_employees"),
            PlanPeriod.closed.label("pp_closed"),
            Team.id.label("team_id"),
            Team.name.label("team_name"),
        )
        .select_from(ActorPlanPeriod)
        .join(PlanPeriod, PlanPeriod.id == ActorPlanPeriod.plan_period_id)
        .join(Team, Team.id == PlanPeriod.team_id)
        .where(ActorPlanPeriod.person_id == person_id)
        .where(PlanPeriod.closed.is_(False))
        .where(PlanPeriod.prep_delete.is_(None))
        .where(Team.prep_delete.is_(None))
    )
    if team_id is not None:
        stmt = stmt.where(PlanPeriod.team_id == team_id)
    stmt = stmt.order_by(PlanPeriod.start.desc())
    rows = session.execute(stmt).mappings().all()
    return [
        OpenPlanPeriodInfo(
            actor_plan_period_id=r["app_id"],
            plan_period_id=r["pp_id"],
            start=r["pp_start"],
            end=r["pp_end"],
            deadline=r["pp_deadline"],
            notes_for_employees=r["pp_notes_for_employees"],
            notes=r["app_notes"],
            requested_assignments=r["requested_assignments"],
            closed=r["pp_closed"],
            team_id=r["team_id"],
            team_name=r["team_name"],
        )
        for r in rows
    ]


def get_teams_for_person(session: Session, person_id: uuid.UUID) -> list[TeamInfo]:
    """Alle Teams, für die der Mitarbeiter offene ActorPlanPeriods hat — alphabetisch."""
    stmt = (
        sa_select(Team.id.label("team_id"), Team.name.label("team_name"))
        .select_from(ActorPlanPeriod)
        .join(PlanPeriod, PlanPeriod.id == ActorPlanPeriod.plan_period_id)
        .join(Team, Team.id == PlanPeriod.team_id)
        .where(ActorPlanPeriod.person_id == person_id)
        .where(PlanPeriod.closed.is_(False))
        .where(PlanPeriod.prep_delete.is_(None))
        .where(Team.prep_delete.is_(None))
        .distinct()
        .order_by(Team.name)
    )
    rows = session.execute(stmt).mappings().all()
    return [TeamInfo(team_id=r["team_id"], team_name=r["team_name"]) for r in rows]


def get_markers_for_range(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    start: date,
    end: date,
) -> list[AvailDayMarker]:
    """JOIN AvailDay ↔ TimeOfDay ↔ TimeOfDayEnum + has_appointment-Flag."""
    # Subquery: hat dieser AvailDay einen Appointment?
    has_appt_sq = (
        sa_select(AvailDayAppointmentLink.avail_day_id)
        .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .correlate(AvailDay)
        .exists()
        .label("has_appointment")
    )

    stmt = (
        sa_select(
            AvailDay.id.label("ad_id"),
            AvailDay.date.label("ad_date"),
            AvailDay.time_of_day_id.label("tod_id"),
            TimeOfDay.name.label("tod_name"),
            TimeOfDay.start.label("tod_start"),
            TimeOfDay.end.label("tod_end"),
            TimeOfDayEnum.id.label("enum_id"),
            TimeOfDayEnum.name.label("enum_name"),
            TimeOfDayEnum.abbreviation.label("enum_abbr"),
            TimeOfDayEnum.time_index.label("enum_time_index"),
            has_appt_sq,
        )
        .select_from(AvailDay)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .join(TimeOfDayEnum, TimeOfDayEnum.id == TimeOfDay.time_of_day_enum_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.prep_delete.is_(None))
        .where(AvailDay.date >= start)
        .where(AvailDay.date <= end)
        .order_by(AvailDay.date, TimeOfDayEnum.time_index)
    )
    rows = session.execute(stmt).mappings().all()
    return [
        AvailDayMarker(
            avail_day_id=r["ad_id"],
            day=r["ad_date"],
            time_of_day_id=r["tod_id"],
            time_of_day_name=r["tod_name"],
            time_of_day_start=r["tod_start"],
            time_of_day_end=r["tod_end"],
            time_of_day_enum_id=r["enum_id"],
            time_of_day_enum_name=r["enum_name"],
            time_of_day_enum_abbreviation=r["enum_abbr"],
            time_of_day_enum_time_index=r["enum_time_index"],
            has_appointment=bool(r["has_appointment"]),
        )
        for r in rows
    ]


def get_markers_for_range_simple(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    start: date,
    end: date,
) -> list[AvailDayMarker]:
    """Simple-Mode-Variante: dedupliziert Marker pro (date, enum_time_index).

    Altlasten aus dem Intervall-Modus (mehrere AvailDays pro Tag+Enum mit unterschiedlichen
    konkreten TODs) sollen im Kalender nicht als mehrere Dots erscheinen.
    """
    all_markers = get_markers_for_range(session, actor_plan_period_id, start, end)
    seen: set[tuple[date, int]] = set()
    deduped: list[AvailDayMarker] = []
    for m in all_markers:
        key = (m.day, m.time_of_day_enum_time_index)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)
    return deduped


# ── TimeGrid-Layout (Wochenansicht) ───────────────────────────────────────────


@dataclass
class WeekGridSlot:
    """Ein einzelner Verfügbarkeits-Slot im TimeGrid-Layout der Wochenansicht."""
    marker: AvailDayMarker
    top_pct: float       # 0–100 — vertikale Position in % des Sichtfensters
    height_pct: float    # 0–100 — vertikale Größe in % des Sichtfensters
    lane: int            # 0..N-1 innerhalb des überlappenden Clusters
    lane_count: int      # Anzahl Lanes im Cluster (für Breitenberechnung)
    is_overflow: bool    # Mitternachts-Spanne, am view_end abgeschnitten


def _time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def compute_view_window(markers: list[AvailDayMarker]) -> tuple[int, int]:
    """Liefert (view_start_min, view_end_min) für die Time-Axis.

    Dynamisch aus min(start) / max(end) der Marker mit 1h-Padding, geclamped
    auf 0–1440 und auf volle Stunden gerundet. Ohne Marker: 8:00–20:00.
    Mitternachts-Spannen (end <= start) werden im max() als 1440 gewertet.
    """
    if not markers:
        return 8 * 60, 20 * 60

    starts = [_time_to_minutes(m.time_of_day_start) for m in markers]
    ends = []
    for m in markers:
        s = _time_to_minutes(m.time_of_day_start)
        e = _time_to_minutes(m.time_of_day_end)
        ends.append(1440 if e <= s else e)

    view_start = max(0, (min(starts) - 60) // 60 * 60)
    view_end = min(1440, ((max(ends) + 60) + 59) // 60 * 60)
    if view_end <= view_start:
        view_end = min(1440, view_start + 60)
    return view_start, view_end


def layout_week_grid(
    markers: list[AvailDayMarker],
    view_start_min: int,
    view_end_min: int,
) -> dict[date, list[WeekGridSlot]]:
    """Berechnet pro Tag die TimeGrid-Slot-Geometrie inkl. Lane-Zuweisung.

    Greedy-Algorithmus pro Tag: Marker werden nach Start sortiert und in Cluster
    transitiv überlappender Slots gruppiert. Innerhalb eines Clusters bekommt
    jeder Slot die niedrigste Lane, die nicht mit einem vorherigen kollidiert.
    `lane_count` ist Cluster-lokal — disjunkte Slots am selben Tag bleiben
    100% breit.
    """
    view_span = max(1, view_end_min - view_start_min)
    by_day: dict[date, list[AvailDayMarker]] = {}
    for m in markers:
        by_day.setdefault(m.day, []).append(m)

    result: dict[date, list[WeekGridSlot]] = {}
    for day, day_markers in by_day.items():
        normalized: list[tuple[AvailDayMarker, int, int, bool]] = []
        for m in day_markers:
            s = _time_to_minutes(m.time_of_day_start)
            e = _time_to_minutes(m.time_of_day_end)
            is_overflow = e <= s
            if is_overflow:
                e = 1440
            normalized.append((m, s, e, is_overflow))
        normalized.sort(key=lambda x: (x[1], x[2]))

        # Cluster bilden — transitive Überlappung
        clusters: list[list[int]] = []
        current: list[int] = []
        current_max_end = -1
        for idx, (_, s, e, _) in enumerate(normalized):
            if s < current_max_end:
                current.append(idx)
                current_max_end = max(current_max_end, e)
            else:
                if current:
                    clusters.append(current)
                current = [idx]
                current_max_end = e
        if current:
            clusters.append(current)

        slot_lane = [0] * len(normalized)
        slot_lane_count = [1] * len(normalized)
        for cluster in clusters:
            lane_ends: list[int] = []
            for idx in cluster:
                _, s, e, _ = normalized[idx]
                assigned = -1
                for i, lend in enumerate(lane_ends):
                    if lend <= s:
                        lane_ends[i] = e
                        assigned = i
                        break
                if assigned == -1:
                    lane_ends.append(e)
                    assigned = len(lane_ends) - 1
                slot_lane[idx] = assigned
            for idx in cluster:
                slot_lane_count[idx] = len(lane_ends)

        slots: list[WeekGridSlot] = []
        for idx, (m, s, e, is_overflow) in enumerate(normalized):
            top = (s - view_start_min) / view_span * 100.0
            height = (e - s) / view_span * 100.0
            top = max(0.0, min(100.0, top))
            height = max(0.0, min(100.0 - top, height))
            slots.append(WeekGridSlot(
                marker=m,
                top_pct=top,
                height_pct=height,
                lane=slot_lane[idx],
                lane_count=slot_lane_count[idx],
                is_overflow=is_overflow,
            ))
        result[day] = slots

    return result


def get_person_time_of_days(
    session: Session,
    person_id: uuid.UUID,
) -> list[PersonTimeOfDayInfo]:
    """Alle persönlichen TODs (via PersonTimeOfDayLink) mit Enum-Infos und AvailDay-Zähler."""
    avail_count_sq = (
        sa_select(func.count())
        .select_from(AvailDay)
        .where(AvailDay.time_of_day_id == TimeOfDay.id)
        .where(AvailDay.prep_delete.is_(None))
        .correlate(TimeOfDay)
        .scalar_subquery()
    )

    stmt = (
        sa_select(
            TimeOfDay.id.label("tod_id"),
            TimeOfDay.name.label("tod_name"),
            TimeOfDay.start.label("tod_start"),
            TimeOfDay.end.label("tod_end"),
            TimeOfDayEnum.id.label("enum_id"),
            TimeOfDayEnum.name.label("enum_name"),
            TimeOfDayEnum.abbreviation.label("enum_abbr"),
            TimeOfDayEnum.time_index.label("enum_time_index"),
            avail_count_sq.label("avail_day_count"),
        )
        .select_from(PersonTimeOfDayLink)
        .join(TimeOfDay, TimeOfDay.id == PersonTimeOfDayLink.time_of_day_id)
        .join(TimeOfDayEnum, TimeOfDayEnum.id == TimeOfDay.time_of_day_enum_id)
        .where(PersonTimeOfDayLink.person_id == person_id)
        .where(TimeOfDay.prep_delete.is_(None))
        .order_by(TimeOfDayEnum.time_index, TimeOfDay.start)
    )
    rows = session.execute(stmt).mappings().all()
    return [
        PersonTimeOfDayInfo(
            id=r["tod_id"],
            name=r["tod_name"],
            start=r["tod_start"],
            end=r["tod_end"],
            enum_id=r["enum_id"],
            enum_name=r["enum_name"],
            enum_abbreviation=r["enum_abbr"],
            enum_time_index=r["enum_time_index"],
            avail_day_count=r["avail_day_count"],
        )
        for r in rows
    ]


def get_day_detail_simple(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    person_id: uuid.UUID,
    day: date,
    is_locked: bool,
) -> DayDetailViewModel:
    """Simple-Mode-Day-Panel: pro Project-Enum genau eine Option (primary TOD).

    has_appointment prüft ALLE AvailDays des Tages für dieses Enum (nicht nur die
    primary). avail_day_id zeigt auf den ersten gefundenen AvailDay des Enums —
    die konkrete ID ist im Simple-Modus nicht mehr User-sichtbar.
    """
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    enums = get_project_enums(session, person.project_id)

    # Alle AvailDays dieses Tages (inkl. TOD + Enum) in einer Query
    day_rows = session.execute(
        sa_select(
            AvailDay.id.label("ad_id"),
            TimeOfDay.time_of_day_enum_id.label("enum_id"),
        )
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.prep_delete.is_(None))
    ).all()

    ad_by_enum: dict[uuid.UUID, list[uuid.UUID]] = {}
    for r in day_rows:
        ad_by_enum.setdefault(r.enum_id, []).append(r.ad_id)

    # has_appointment für alle existierenden AvailDays ermitteln
    all_ad_ids = [aid for ids in ad_by_enum.values() for aid in ids]
    appointed_ids: set[uuid.UUID] = set()
    if all_ad_ids:
        appt_rows = session.execute(
            sa_select(AvailDayAppointmentLink.avail_day_id)
            .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
            .join(Plan, Plan.id == Appointment.plan_id)
            .where(AvailDayAppointmentLink.avail_day_id.in_(all_ad_ids))
            .where(Plan.is_binding.is_(True))
            .where(Plan.prep_delete.is_(None))
        ).scalars().all()
        appointed_ids = set(appt_rows)

    enum_groups: list[DayEnumGroup] = []
    for enum in enums:
        primary = ensure_simple_primary_tod(session, person, enum)
        if primary is None:
            # User-Entscheidung: Enums ohne ermittelbare TOD ganz weglassen.
            continue
        ad_ids = ad_by_enum.get(enum.id, [])
        has_appt = any(aid in appointed_ids for aid in ad_ids)
        enum_groups.append(DayEnumGroup(
            enum_id=enum.id,
            enum_name=enum.name,
            enum_abbreviation=enum.abbreviation,
            enum_time_index=enum.time_index,
            options=[DayTodOption(
                time_of_day_id=primary.id,
                tod_name=primary.name,
                tod_start=primary.start,
                tod_end=primary.end,
                avail_day_id=ad_ids[0] if ad_ids else None,
                has_appointment=has_appt,
            )],
        ))

    return DayDetailViewModel(
        day=day,
        actor_plan_period_id=actor_plan_period_id,
        is_locked=is_locked,
        enum_groups=enum_groups,
    )


def get_day_detail(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    person_id: uuid.UUID,
    day: date,
    is_locked: bool,
) -> DayDetailViewModel:
    """Day-Panel: alle Person-TODs gruppiert nach Enum, mit AvailDay-Status pro Option."""
    # Alle persönlichen TODs laden
    all_tods = get_person_time_of_days(session, person_id)

    # Existierende AvailDays an diesem Tag laden
    ad_rows = session.execute(
        sa_select(AvailDay.id, AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.prep_delete.is_(None))
    ).all()

    ad_by_tod: dict[uuid.UUID, uuid.UUID] = {r.time_of_day_id: r.id for r in ad_rows}

    # has_appointment für alle aktiven AvailDays
    ad_ids = list(ad_by_tod.values())
    appointed_ids: set[uuid.UUID] = set()
    if ad_ids:
        appt_rows = session.execute(
            sa_select(AvailDayAppointmentLink.avail_day_id)
            .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
            .join(Plan, Plan.id == Appointment.plan_id)
            .where(AvailDayAppointmentLink.avail_day_id.in_(ad_ids))
            .where(Plan.is_binding.is_(True))
            .where(Plan.prep_delete.is_(None))
        ).scalars().all()
        appointed_ids = set(appt_rows)

    # Gruppieren nach Enum
    enum_map: dict[uuid.UUID, DayEnumGroup] = {}
    for tod in all_tods:
        if tod.enum_id not in enum_map:
            enum_map[tod.enum_id] = DayEnumGroup(
                enum_id=tod.enum_id,
                enum_name=tod.enum_name,
                enum_abbreviation=tod.enum_abbreviation,
                enum_time_index=tod.enum_time_index,
                options=[],
            )
        ad_id = ad_by_tod.get(tod.id)
        enum_map[tod.enum_id].options.append(DayTodOption(
            time_of_day_id=tod.id,
            tod_name=tod.name,
            tod_start=tod.start,
            tod_end=tod.end,
            avail_day_id=ad_id,
            has_appointment=ad_id in appointed_ids if ad_id else False,
        ))

    enum_groups = sorted(enum_map.values(), key=lambda g: g.enum_time_index)
    return DayDetailViewModel(
        day=day,
        actor_plan_period_id=actor_plan_period_id,
        is_locked=is_locked,
        enum_groups=enum_groups,
    )


def enum_id_for_tod(session: Session, tod_id: uuid.UUID) -> uuid.UUID | None:
    """Helper: Enum-ID zu einem gegebenen TimeOfDay; None falls nicht vorhanden."""
    return session.execute(
        sa_select(TimeOfDay.time_of_day_enum_id).where(TimeOfDay.id == tod_id)
    ).scalar()


def enum_id_for_avail_day(session: Session, avail_day_id: uuid.UUID) -> uuid.UUID | None:
    """Helper: Enum-ID zu einem gegebenen AvailDay (über sein TimeOfDay)."""
    return session.execute(
        sa_select(TimeOfDay.time_of_day_enum_id)
        .join(AvailDay, AvailDay.time_of_day_id == TimeOfDay.id)
        .where(AvailDay.id == avail_day_id)
    ).scalar()


def get_enum_group_detail(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    person_id: uuid.UUID,
    day: date,
    enum_id: uuid.UUID,
) -> DayEnumGroup | None:
    """Wie `get_day_detail`, aber gibt nur die Enum-Gruppe für `enum_id` zurück.

    Wird von Per-Group-Mutation-Endpoints genutzt: nach einem TOD-Toggle muss nur
    die betroffene Enum-Gruppe neu gerendert werden, nicht das ganze Day-Panel.
    Spart Render-Zeit + macht parallele Klicks unabhängig (kein Race auf #day-panel).
    """
    all_tods = [t for t in get_person_time_of_days(session, person_id) if t.enum_id == enum_id]
    if not all_tods:
        return None
    tod_ids = [t.id for t in all_tods]

    ad_rows = session.execute(
        sa_select(AvailDay.id, AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.time_of_day_id.in_(tod_ids))
        .where(AvailDay.prep_delete.is_(None))
    ).all()
    ad_by_tod: dict[uuid.UUID, uuid.UUID] = {r.time_of_day_id: r.id for r in ad_rows}
    ad_ids = list(ad_by_tod.values())

    appointed_ids: set[uuid.UUID] = set()
    if ad_ids:
        appt_rows = session.execute(
            sa_select(AvailDayAppointmentLink.avail_day_id)
            .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
            .join(Plan, Plan.id == Appointment.plan_id)
            .where(AvailDayAppointmentLink.avail_day_id.in_(ad_ids))
            .where(Plan.is_binding.is_(True))
            .where(Plan.prep_delete.is_(None))
        ).scalars().all()
        appointed_ids = set(appt_rows)

    first = all_tods[0]
    return DayEnumGroup(
        enum_id=first.enum_id,
        enum_name=first.enum_name,
        enum_abbreviation=first.enum_abbreviation,
        enum_time_index=first.enum_time_index,
        options=[
            DayTodOption(
                time_of_day_id=tod.id,
                tod_name=tod.name,
                tod_start=tod.start,
                tod_end=tod.end,
                avail_day_id=ad_by_tod.get(tod.id),
                has_appointment=(ad_by_tod.get(tod.id) in appointed_ids) if ad_by_tod.get(tod.id) else False,
            )
            for tod in all_tods
        ],
    )


def get_enum_group_detail_simple(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    person_id: uuid.UUID,
    day: date,
    enum_id: uuid.UUID,
) -> DayEnumGroup | None:
    """Simple-Mode-Variante: 1 Option (primary TOD) pro Enum, has_appointment
    aggregiert über alle AvailDays des Enums an diesem Tag."""
    person = session.get(Person, person_id)
    if person is None:
        return None
    enum = session.get(TimeOfDayEnum, enum_id)
    if enum is None or enum.project_id != person.project_id:
        return None
    primary = ensure_simple_primary_tod(session, person, enum)
    if primary is None:
        return None

    ad_ids = session.execute(
        sa_select(AvailDay.id)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.prep_delete.is_(None))
        .where(TimeOfDay.time_of_day_enum_id == enum_id)
    ).scalars().all()

    appointed_ids: set[uuid.UUID] = set()
    if ad_ids:
        appt_rows = session.execute(
            sa_select(AvailDayAppointmentLink.avail_day_id)
            .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
            .join(Plan, Plan.id == Appointment.plan_id)
            .where(AvailDayAppointmentLink.avail_day_id.in_(ad_ids))
            .where(Plan.is_binding.is_(True))
            .where(Plan.prep_delete.is_(None))
        ).scalars().all()
        appointed_ids = set(appt_rows)

    has_appt = any(aid in appointed_ids for aid in ad_ids)
    return DayEnumGroup(
        enum_id=enum.id,
        enum_name=enum.name,
        enum_abbreviation=enum.abbreviation,
        enum_time_index=enum.time_index,
        options=[DayTodOption(
            time_of_day_id=primary.id,
            tod_name=primary.name,
            tod_start=primary.start,
            tod_end=primary.end,
            avail_day_id=ad_ids[0] if ad_ids else None,
            has_appointment=has_appt,
        )],
    )


def get_sidebar_stats(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    requested_assignments: int,
) -> SidebarStats:
    total_entered = session.execute(
        sa_select(func.count())
        .select_from(AvailDay)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.prep_delete.is_(None))
    ).scalar_one()

    # Appointments: AvailDays die mind. einen AppointmentLink haben
    total_appointed = session.execute(
        sa_select(func.count(AvailDay.id.distinct()))
        .select_from(AvailDay)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.prep_delete.is_(None))
    ).scalar_one()

    return SidebarStats(
        total_entered=total_entered,
        total_appointed=total_appointed,
        requested_assignments=requested_assignments,
    )


def build_availability_view(
    session: Session,
    person_id: uuid.UUID,
    active_period: OpenPlanPeriodInfo,
    teams: list[TeamInfo],
    selected_team_id: uuid.UUID | None,
) -> AvailabilityViewModel:
    """Zentrale Aggregation für die index.html-Seite."""
    is_simple = is_simple_mode_for_person(session, person_id)
    if is_simple:
        markers = get_markers_for_range_simple(
            session,
            active_period.actor_plan_period_id,
            active_period.start,
            active_period.end,
        )
    else:
        markers = get_markers_for_range(
            session,
            active_period.actor_plan_period_id,
            active_period.start,
            active_period.end,
        )
    person_tods = get_person_time_of_days(session, person_id)
    stats = get_sidebar_stats(
        session,
        active_period.actor_plan_period_id,
        active_period.requested_assignments,
    )
    # Initial-Datum: innerhalb der Periode bleiben
    today = date.today()
    if today < active_period.start:
        initial_date = active_period.start.isoformat()
    elif today > active_period.end:
        initial_date = active_period.end.isoformat()
    else:
        initial_date = today.isoformat()

    return AvailabilityViewModel(
        active_period=active_period,
        markers=markers,
        person_time_of_days=person_tods,
        initial_date=initial_date,
        sidebar_stats=stats,
        teams=teams,
        selected_team_id=selected_team_id,
        is_simple_mode=is_simple,
    )


# ── Autorisierungs-Helfer ─────────────────────────────────────────────────────


def authorize_actor_plan_period(
    session: Session,
    person_id: uuid.UUID,
    actor_plan_period_id: uuid.UUID,
) -> ActorPlanPeriod:
    """HTTP 403 wenn APP nicht zur Person gehört."""
    app = session.get(ActorPlanPeriod, actor_plan_period_id)
    if app is None or app.person_id != person_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf diese Planperiode")
    return app


def authorize_avail_day(
    session: Session,
    person_id: uuid.UUID,
    avail_day_id: uuid.UUID,
) -> AvailDay:
    """HTTP 403/404 wenn AvailDay nicht zu einer APP dieser Person gehört."""
    ad = session.get(AvailDay, avail_day_id)
    if ad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Verfügbarkeitstag nicht gefunden")
    app = session.get(ActorPlanPeriod, ad.actor_plan_period_id)
    if app is None or app.person_id != person_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf diesen Verfügbarkeitstag")
    return ad


def authorize_person_time_of_day(
    session: Session,
    person_id: uuid.UUID,
    tod_id: uuid.UUID,
) -> TimeOfDay:
    """HTTP 403/404 wenn TOD nicht via PersonTimeOfDayLink zur Person gehört."""
    tod = session.get(TimeOfDay, tod_id)
    if tod is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tageszeit nicht gefunden")
    link = session.get(PersonTimeOfDayLink, (person_id, tod_id))
    if link is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf diese Tageszeit")
    return tod


def check_deadline_or_403(plan_period: PlanPeriod) -> None:
    """HTTP 403 wenn PlanPeriod geschlossen oder Deadline überschritten."""
    if plan_period.closed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Planperiode ist geschlossen")
    if date.today() > plan_period.deadline:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Abgabefrist ist abgelaufen")


# ── Mutations (ORM auf injected Session) ─────────────────────────────────────


def find_avail_day(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    day: date,
    time_of_day_id: uuid.UUID,
) -> AvailDay | None:
    """Uniqueness-Vorcheck. Spiegelt db_services/avail_day.py:75-82."""
    return session.execute(
        sa_select(AvailDay)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.time_of_day_id == time_of_day_id)
        .where(AvailDay.prep_delete.is_(None))
    ).scalar_one_or_none()


def has_appointment(session: Session, avail_day_id: uuid.UUID) -> bool:
    """Prüft ob ein AvailDay einem Appointment aus einem verbindlichen Plan zugeordnet ist."""
    return session.execute(
        sa_select(
            exists()
            .where(AvailDayAppointmentLink.avail_day_id == avail_day_id)
            .where(AvailDayAppointmentLink.appointment_id == Appointment.id)
            .where(Appointment.plan_id == Plan.id)
            .where(Plan.is_binding.is_(True))
            .where(Plan.prep_delete.is_(None))
        )
    ).scalar_one()


def create_avail_day(
    session: Session,
    actor_plan_period_id: uuid.UUID,
    day: date,
    time_of_day_id: uuid.UUID,
) -> AvailDay:
    """Child-AvailDayGroup + AvailDay anlegen. Spiegelt db_services/avail_day.py:241-256.

    Wichtig: `actor_plan_period` und `avail_day_group` werden als Objekte
    übergeben (nicht nur FK), damit der `before_flush`-Listener
    `_on_insert_avail_day` (database/event_listeners.py:191) die Defaults
    (CombLoc, TimeOfDays, Location-/Partner-Prefs, Skills) von der APP
    übernehmen kann. Bei FK-only sind die Relationen zur Listener-Zeit
    nicht zuverlässig verfügbar.
    """
    app = session.get(ActorPlanPeriod, actor_plan_period_id)
    if app is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    master = app.avail_day_group
    if master is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Root-AvailDayGroup fehlt (Datenbestand-Anomalie)")
    child = AvailDayGroup(avail_day_group=master)
    session.add(child)
    session.flush()
    ad = AvailDay(
        date=day,
        time_of_day_id=time_of_day_id,
        avail_day_group=child,
        actor_plan_period=app,
    )
    session.add(ad)
    session.flush()
    return ad


def reset_location_prefs_to_normal(session: Session, avail_day: AvailDay) -> None:
    """Setzt Location-/Partner-Location-Prefs des AvailDays auf 'normal' (leere M:N-Links).

    Der `_on_insert_avail_day` Event-Listener kopiert beim Insert automatisch die
    ActorPlanPeriod-Defaults — bei Cast-Zuwendung per Dispatcher/Planer sollen
    individuelle Mitarbeiter-Präferenzen das Matching aber nicht verzerren.
    Konvention der Codebase: score=1.0 wird nicht als Link abgelegt
    (vgl. db_services.avail_day.replace_location_prefs_for_avail_days).
    """
    avail_day.actor_location_prefs_defaults.clear()
    avail_day.actor_partner_location_prefs_defaults.clear()
    session.flush()


def delete_avail_day(session: Session, avail_day_id: uuid.UUID) -> None:
    """AvailDay + seine Child-Group löschen. Spiegelt db_services/avail_day.py:279-288."""
    ad = session.get(AvailDay, avail_day_id)
    if ad is None:
        return
    adg_id = ad.avail_day_group_id
    session.delete(ad)
    session.flush()
    adg = session.get(AvailDayGroup, adg_id)
    if adg is not None:
        session.delete(adg)
        session.flush()


def update_notes(session: Session, app: ActorPlanPeriod, notes: str) -> None:
    """Spiegelt db_services/actor_plan_period.py:172-177."""
    app.notes = notes or None
    session.flush()


def update_requested_assignments(session: Session, app: ActorPlanPeriod, requested: int) -> None:
    """Spiegelt db_services/actor_plan_period.py:181-187."""
    app.requested_assignments = max(0, requested)
    session.flush()


def _is_tod_referenced_anywhere(session: Session, tod: TimeOfDay) -> bool:
    """Prüft alle 9 Referenz-Relations analog db_services/time_of_day.py:97-101."""
    # Direktfeld-Prüfung: TOD ist Projekt-Default
    if tod.project_defaults_id is not None:
        return True

    from database.models import (
        ActorPlanPeriodTimeOfDayLink,
        AvailDay,
        AvailDayTimeOfDayLink,
        Event,
        EventTimeOfDayLink,
        LocOfWorkTimeOfDayLink,
        LocPlanPeriodTimeOfDayLink,
    )
    checks = [
        sa_select(exists().where(PersonTimeOfDayLink.time_of_day_id == tod.id)),
        sa_select(exists().where(ActorPlanPeriodTimeOfDayLink.time_of_day_id == tod.id)),
        sa_select(exists().where(AvailDayTimeOfDayLink.time_of_day_id == tod.id)),
        sa_select(exists().where(AvailDay.time_of_day_id == tod.id).where(AvailDay.prep_delete.is_(None))),
        sa_select(exists().where(LocOfWorkTimeOfDayLink.time_of_day_id == tod.id)),
        sa_select(exists().where(LocPlanPeriodTimeOfDayLink.time_of_day_id == tod.id)),
        sa_select(exists().where(EventTimeOfDayLink.time_of_day_id == tod.id)),
        sa_select(exists().where(Event.time_of_day_id == tod.id).where(Event.prep_delete.is_(None))),
    ]
    return any(session.execute(q).scalar_one() for q in checks)


def count_avail_days_for_tod(session: Session, tod_id: uuid.UUID) -> int:
    """Anzahl aktiver AvailDays für diese TimeOfDay."""
    return session.execute(
        sa_select(func.count())
        .select_from(AvailDay)
        .where(AvailDay.time_of_day_id == tod_id)
        .where(AvailDay.prep_delete.is_(None))
    ).scalar_one()


def create_person_time_of_day(
    session: Session,
    person_id: uuid.UUID,
    time_of_day_enum_id: uuid.UUID,
    start: time,
    end: time,
    name: str = "",
) -> TimeOfDay:
    """Neuer TOD + PersonTimeOfDayLink. Spiegelt db_services/time_of_day.py:37-46 + person.py:241-257."""
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    tod = TimeOfDay(
        name=name or None,
        start=start,
        end=end,
        time_of_day_enum_id=time_of_day_enum_id,
        project_id=person.project_id,
    )
    session.add(tod)
    session.flush()
    person.time_of_days.append(tod)
    session.flush()
    return tod


def remove_person_time_of_day(
    session: Session,
    person_id: uuid.UUID,
    tod: TimeOfDay,
) -> None:
    """Link entfernen + ggf. Soft-Delete. Spiegelt db_services/time_of_day.py:72-78 + person.py."""
    person = session.get(Person, person_id)
    if person and tod in person.time_of_days:
        person.time_of_days.remove(tod)
        session.flush()
    if not _is_tod_referenced_anywhere(session, tod):
        tod.prep_delete = _utcnow()
        session.flush()


def replace_person_time_of_day(
    session: Session,
    person_id: uuid.UUID,
    old: TimeOfDay,
    start: time,
    end: time,
) -> TimeOfDay:
    """Remove+Create-Pattern (§2.5 des Plans). Historische AvailDays bleiben unverändert."""
    enum_id = old.time_of_day_enum_id
    name = old.name
    remove_person_time_of_day(session, person_id, old)
    return create_person_time_of_day(session, person_id, enum_id, start, end, name or "")
