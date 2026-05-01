"""Service-Schicht für die Dispatcher-Plan-Ansicht.

Spiegelt `web_api/employees/service.py`, filtert jedoch auf Team-Ebene
(PlanPeriod.team_id) statt auf Person-Ebene (ActorPlanPeriod.person_id).
"""

import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy import select as sa_select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Address,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    AvailDayCombLocLink,
    CastGroup,
    CombinationLocationsPossible,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    LocOfWorkCombLocLink,
    Person,
    Plan,
    PlanPeriod,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
    TimeOfDay,
    TimeOfDayEnum,
)
from database.slot_arithmetic import TimeSlot, slot_gap, slots_overlap
from web_api.availability.service import create_avail_day, find_avail_day, reset_location_prefs_to_normal
from web_api.common import guest_count, interval_minutes, location_display_name
from web_api.email.service import EmailPayload
from web_api.employees.service import CalendarEvent
from web_api.palette import location_color
from web_api.plan_adjustment.service import update_appointment_avail_days


@dataclass
class TeamInfo:
    id: uuid.UUID
    name: str
    project_id: uuid.UUID


def get_teams_for_dispatcher(
    session: Session,
    person_id: uuid.UUID,
) -> list[TeamInfo]:
    """Alle aktiven Teams, für die die Person als Dispatcher eingetragen ist.

    Soft-deletete Teams werden ausgefiltert, damit sie nicht in der Disponenten-
    Sidebar als auswählbares Team auftauchen.
    """
    rows = session.execute(
        sa_select(Team.id, Team.name, Team.project_id)
        .where(Team.dispatcher_id == person_id)
        .where(Team.prep_delete.is_(None))
        .order_by(Team.name)
    ).mappings().all()
    return [
        TeamInfo(id=r["id"], name=r["name"], project_id=r["project_id"])
        for r in rows
    ]


def get_appointments_for_teams(
    session: Session,
    team_ids: list[uuid.UUID],
    start_date: date | None = None,
    end_date: date | None = None,
    only_understaffed: bool = False,
    user_overrides: dict[uuid.UUID, str] | None = None,
) -> list[CalendarEvent]:
    """Alle Appointments der angegebenen Teams als CalendarEvents.

    Mit `only_understaffed=True` wird das Ergebnis nach dem CalendarEvent-
    Build gefiltert (Python-Filter, nicht SQL-HAVING — die is_understaffed-
    Berechnung kombiniert avail-count und JSON-Guests-Länge und lässt sich
    nicht trivial in SQL ausdrücken).
    """
    if not team_ids:
        return []

    # Subquery: AvailDay-Count pro Appointment (= „besetzt durch Mitarbeiter")
    avail_count_subq = (
        sa_select(
            AvailDayAppointmentLink.appointment_id.label("appointment_id"),
            func.count(AvailDayAppointmentLink.avail_day_id).label("avail_count"),
        )
        .group_by(AvailDayAppointmentLink.appointment_id)
        .subquery()
    )

    stmt = (
        sa_select(
            Appointment.id.label("appointment_id"),
            Appointment.notes.label("appointment_notes"),
            Appointment.guests.label("guests"),
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            LocationOfWork.id.label("location_id"),
            Address.city.label("location_city"),
            TimeOfDay.name.label("time_of_day_name"),
            TimeOfDay.start.label("time_start"),
            TimeOfDay.end.label("time_end"),
            PlanPeriod.id.label("plan_period_id"),
            PlanPeriod.start.label("period_start"),
            PlanPeriod.end.label("period_end"),
            PlanPeriod.team_id.label("team_id"),
            CastGroup.nr_actors.label("cast_required"),
            func.coalesce(avail_count_subq.c.avail_count, 0).label("avail_count"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod,
              LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork,
              LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(Address, Address.id == LocationOfWork.address_id, isouter=True)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(CastGroup, CastGroup.id == Event.cast_group_id)
        .outerjoin(avail_count_subq,
                   avail_count_subq.c.appointment_id == Appointment.id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .where(PlanPeriod.team_id.in_(team_ids))
        .where(Appointment.prep_delete.is_(None))
        .where(Event.prep_delete.is_(None))
        .order_by(Event.date, TimeOfDay.start)
    )

    if start_date:
        stmt = stmt.where(Event.date >= start_date)
    if end_date:
        stmt = stmt.where(Event.date <= end_date)

    rows = session.execute(stmt).mappings().all()

    result: list[CalendarEvent] = []
    for r in rows:
        guests_count = guest_count(r["guests"])
        cast_count = int(r["avail_count"]) + guests_count
        cast_required = int(r["cast_required"])
        result.append(CalendarEvent(
            appointment_id=r["appointment_id"],
            event_date=r["event_date"],
            location_name=location_display_name(r["location_name"], r["location_city"]),
            location_name_only=r["location_name"],
            location_id=r["location_id"],
            color=location_color(r["location_id"], user_overrides),
            time_of_day_name=r["time_of_day_name"],
            time_start=r["time_start"],
            time_end=r["time_end"],
            appointment_notes=r["appointment_notes"],
            plan_period_id=r["plan_period_id"],
            period_start=r["period_start"],
            period_end=r["period_end"],
            team_id=r["team_id"],
            cast_count=cast_count,
            cast_required=cast_required,
            is_understaffed=cast_count < cast_required,
        ))

    if only_understaffed:
        result = [ev for ev in result if ev.is_understaffed]
    return result


def get_appointment_detail_for_dispatcher(
    session: Session,
    appointment_id: uuid.UUID,
    allowed_team_ids: list[uuid.UUID],
    user_overrides: dict[uuid.UUID, str] | None = None,
) -> CalendarEvent | None:
    """Einzelner Appointment — nur wenn er zu einem erlaubten Team gehört."""
    events = get_appointments_for_teams(session, allowed_team_ids, user_overrides=user_overrides)
    for ev in events:
        if ev.appointment_id == appointment_id:
            return ev
    return None


def filter_allowed_team_ids(
    requested: list[uuid.UUID],
    allowed: list[uuid.UUID],
) -> list[uuid.UUID]:
    """Schnittmenge: gibt nur Team-IDs zurück, für die der User Dispatcher ist.

    Verhindert, dass ein Dispatcher per Query-Param die Pläne fremder Teams
    sieht. Leerer `requested` bedeutet „alle erlaubten Teams".
    """
    allowed_set = set(allowed)
    if not requested:
        return list(allowed)
    return [tid for tid in requested if tid in allowed_set]


# ── Cast-Change (D2) ──────────────────────────────────────────────────────────


# Gründe, warum ein Team-Mitarbeiter im Cast-Edit-Modal nicht als verfügbar
# markiert wird. `is_available=True` setzt voraus, dass keiner dieser Gründe
# greift. Reihenfolge der Prüfung: no_avail_day → time_overlap → location_combo.
BlockedReason = str  # "no_avail_day" | "time_overlap" | "location_combo"


@dataclass
class CastCandidate:
    person_id: uuid.UUID
    full_name: str
    initials: str
    actor_plan_period_id: uuid.UUID
    is_currently_assigned: bool
    is_available: bool
    avail_day_id: uuid.UUID | None
    blocked_reason: BlockedReason | None = None
    blocking_info: str | None = None


def _compute_initials(f_name: str | None, l_name: str | None) -> str:
    if f_name and l_name:
        return f"{f_name[0]}{l_name[0]}".upper()
    if f_name:
        return f_name[0].upper()
    if l_name:
        return l_name[0].upper()
    return "?"


def get_team_availability_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
) -> list[CastCandidate]:
    """Alle Team-Mitarbeiter der Plan-Periode mit Verfügbarkeits- und
    Zuordnungs-Meta für den Event-Slot dieses Appointments.

    Eine Person gilt als `is_available`, wenn sie am Event-Datum einen
    `AvailDay` hat, dessen Zeit-Intervall das Event-Intervall einschließt
    (`avail.start ≤ event.start` und `avail.end ≥ event.end`). TimeOfDay-
    IDs werden **nicht** direkt verglichen — im Datenmodell werden
    TimeOfDay-Instanzen auf jeder Hierarchie-Ebene neu angelegt
    (Project → Person → ActorPlanPeriod → AvailDay), mit potenziell
    abweichenden start/end-Werten. Der Intervall-Vergleich ist der
    semantisch korrekte Match. Mitternachts-Spannen werden via
    `interval_minutes` normalisiert (end += 24h bei end < start).

    `is_currently_assigned` bleibt unabhängig über die Link-Chain zur
    ActorPlanPeriod ermittelt — auch Solver-Zuordnungen mit vom Slot
    abweichendem time_of_day werden korrekt als zugeordnet gemeldet.
    """
    ctx_row = session.execute(
        sa_select(
            Event.date.label("event_date"),
            TimeOfDay.start.label("event_start"),
            TimeOfDay.end.label("event_end"),
            TimeOfDayEnum.time_index.label("event_time_index"),
            Plan.plan_period_id.label("plan_period_id"),
            PlanPeriod.team_id.label("team_id"),
            Project.use_simple_time_slots.label("use_simple"),
            LocationPlanPeriod.location_of_work_id.label("event_location_id"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(TimeOfDayEnum, TimeOfDayEnum.id == TimeOfDay.time_of_day_enum_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(Team, Team.id == PlanPeriod.team_id)
        .join(Project, Project.id == Team.project_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        return []

    event_date = ctx_row["event_date"]
    plan_period_id = ctx_row["plan_period_id"]
    team_id = ctx_row["team_id"]
    use_simple = bool(ctx_row["use_simple"])
    event_time_index = int(ctx_row["event_time_index"])
    event_start_min, event_end_min = interval_minutes(
        ctx_row["event_start"], ctx_row["event_end"]
    )

    # ActorPlanPeriod-IDs, die aktuell an diesem Appointment zugeordnet sind.
    current_app_ids = set(session.execute(
        sa_select(AvailDay.actor_plan_period_id)
        .join(AvailDayAppointmentLink,
              AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().all())

    # Personen der Plan-Periode, eingeschränkt auf tatsächliche Team-
    # Zugehörigkeit am Event-Datum. `TeamActorAssign.end` ist exklusiv
    # (siehe Modell-Docstring): Intervall gilt, solange start ≤ date
    # und (end IS NULL OR end > date).
    person_rows = session.execute(
        sa_select(
            Person.id.label("person_id"),
            Person.f_name,
            Person.l_name,
            ActorPlanPeriod.id.label("actor_plan_period_id"),
        )
        .select_from(ActorPlanPeriod)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(
            TeamActorAssign,
            and_(
                TeamActorAssign.person_id == Person.id,
                TeamActorAssign.team_id == team_id,
                TeamActorAssign.start <= event_date,
                or_(
                    TeamActorAssign.end.is_(None),
                    TeamActorAssign.end > event_date,
                ),
            ),
        )
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .order_by(Person.l_name, Person.f_name)
    ).mappings().all()

    # Alle AvailDays am Event-Datum für diese Plan-Periode.
    # `avail_time_index` wird für den Simple-Modus verwendet, `avail_start`/
    # `avail_end` für den Intervall-Modus — in einer Query geladen, im
    # Matching-Loop verzweigt.
    avail_rows = session.execute(
        sa_select(
            AvailDay.id.label("avail_day_id"),
            AvailDay.actor_plan_period_id.label("actor_plan_period_id"),
            TimeOfDay.start.label("avail_start"),
            TimeOfDay.end.label("avail_end"),
            TimeOfDayEnum.time_index.label("avail_time_index"),
        )
        .select_from(AvailDay)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .join(TimeOfDayEnum, TimeOfDayEnum.id == TimeOfDay.time_of_day_enum_id)
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .where(AvailDay.date == event_date)
        .where(AvailDay.prep_delete.is_(None))
    ).mappings().all()

    # Gruppiere AvailDays nach ActorPlanPeriod; pro Person den ersten AvailDay
    # finden, der das Match-Kriterium erfüllt. Kriterium ist modus-abhängig:
    # - Simple-Modus: gleicher `time_index`.
    # - Intervall-Modus (Default): `avail.start ≤ event.start AND avail.end ≥ event.end`
    #   (mit Mitternachts-Normalisierung via interval_minutes).
    avails_by_app: dict[uuid.UUID, list[dict]] = {}
    for a in avail_rows:
        avails_by_app.setdefault(a["actor_plan_period_id"], []).append(dict(a))

    def _is_match(a: dict) -> bool:
        if use_simple:
            return int(a["avail_time_index"]) == event_time_index
        a_start_min, a_end_min = interval_minutes(a["avail_start"], a["avail_end"])
        return a_start_min <= event_start_min and a_end_min >= event_end_min

    # Pro Person nur einen CastCandidate, auch wenn im DB-Layer mehrere
    # ActorPlanPeriods für dieselbe Person in derselben Plan-Periode
    # existieren sollten. Im UI ist pro Person genau eine Checkbox
    # semantisch korrekt.
    result: list[CastCandidate] = []
    seen_person_ids: set[uuid.UUID] = set()
    for p in person_rows:
        if p["person_id"] in seen_person_ids:
            continue
        seen_person_ids.add(p["person_id"])
        app_id = p["actor_plan_period_id"]
        matching_avail_id: uuid.UUID | None = None
        for a in avails_by_app.get(app_id, []):
            if _is_match(a):
                matching_avail_id = a["avail_day_id"]
                break
        result.append(CastCandidate(
            person_id=p["person_id"],
            full_name=f"{p['f_name']} {p['l_name']}",
            initials=_compute_initials(p["f_name"], p["l_name"]),
            actor_plan_period_id=app_id,
            is_currently_assigned=app_id in current_app_ids,
            is_available=matching_avail_id is not None,
            avail_day_id=matching_avail_id,
            blocked_reason=None if matching_avail_id is not None else "no_avail_day",
        ))

    # Nachgelagerter Filter: Zeit-Konflikte und unzulässige
    # Location-Kombinationen mit anderen Appointments derselben Person im
    # bindenden Plan dieser Plan-Periode am Event-Datum. Markiert nur
    # Kandidaten, die nicht bereits aktuell zugeordnet sind (eigene
    # Zuordnung darf nicht als Konflikt gewertet werden).
    _apply_conflict_filter(
        session,
        result,
        appointment_id=appointment_id,
        plan_period_id=plan_period_id,
        event_slot=TimeSlot(
            date=event_date,
            start=ctx_row["event_start"],
            end=ctx_row["event_end"],
        ),
        event_location_id=ctx_row["event_location_id"],
    )

    return result


def _apply_conflict_filter(
    session: Session,
    candidates: list[CastCandidate],
    *,
    appointment_id: uuid.UUID,
    plan_period_id: uuid.UUID,
    event_slot: TimeSlot,
    event_location_id: uuid.UUID,
) -> None:
    """Markiert Kandidaten als blockiert, wenn sie im bindenden Plan derselben
    Plan-Periode am Event-Datum bereits einem anderen Appointment zugeordnet
    sind, dessen Slot sich überschneidet ODER dessen Location nicht via
    `CombinationLocationsPossible` (beidseitig, mit `time_span_between`)
    erlaubt ist.

    In-place-Mutation: setzt `blocked_reason`, `blocking_info` und
    `is_available=False` bei Verletzung. Aktuell zugeordnete Kandidaten
    werden übersprungen (eigene Zuordnung darf nicht aus dem Cast geworfen
    werden).
    """
    # Nur Kandidaten mit AvailDay-Match und nicht bereits zugeordnet sind
    # filterrelevant. Personen ohne AvailDay haben bereits
    # blocked_reason="no_avail_day" und brauchen keinen weiteren Check.
    targets_by_ap = {
        c.actor_plan_period_id: c
        for c in candidates
        if c.avail_day_id is not None and not c.is_currently_assigned
    }
    if not targets_by_ap:
        return

    # Andere Appointments der relevanten Personen im bindenden Plan dieser
    # Plan-Periode am Event-Datum. `Plan.is_binding=True` sorgt dafür, dass
    # nicht-bindende Pläne (Solver-Drafts) nicht als Konflikt gelten.
    # `Address` als LEFT OUTER JOIN — `LocationOfWork.address_id` ist
    # nullable (FK SET NULL). Stadt-Name wird via `location_display_name`
    # für den Tooltip verwendet.
    other_rows = session.execute(
        sa_select(
            Appointment.id.label("other_appointment_id"),
            AvailDay.id.label("other_avail_day_id"),
            AvailDay.actor_plan_period_id.label("actor_plan_period_id"),
            TimeOfDay.start.label("other_start"),
            TimeOfDay.end.label("other_end"),
            LocationOfWork.id.label("other_location_id"),
            LocationOfWork.name.label("other_location_name"),
            Address.city.label("other_location_city"),
        )
        .select_from(Appointment)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(Event, Event.id == Appointment.event_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .outerjoin(Address, Address.id == LocationOfWork.address_id)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.appointment_id == Appointment.id)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.plan_period_id == plan_period_id)
        .where(Plan.prep_delete.is_(None))
        .where(Event.date == event_slot.date)
        .where(Event.prep_delete.is_(None))
        .where(Appointment.id != appointment_id)
        .where(Appointment.prep_delete.is_(None))
        .where(AvailDay.prep_delete.is_(None))
        .where(AvailDay.actor_plan_period_id.in_(targets_by_ap.keys()))
    ).mappings().all()

    if not other_rows:
        return

    # Pro ActorPlanPeriod alle "anderen" Slots gruppieren (eine Person kann
    # an einem Tag mehrere weitere Termine haben).
    others_by_ap: dict[uuid.UUID, list[dict]] = {}
    for row in other_rows:
        others_by_ap.setdefault(row["actor_plan_period_id"], []).append(dict(row))

    # CLPs aller relevanten AvailDays in einer Query laden (Self-AvailDay
    # jedes Kandidaten + alle "anderen" AvailDays). Ergebnis: pro AvailDay
    # eine Liste von (clp_id, time_span_between, set[location_ids]).
    relevant_avd_ids = {c.avail_day_id for c in targets_by_ap.values()} | {
        row["other_avail_day_id"] for row in other_rows
    }
    clp_rows = session.execute(
        sa_select(
            AvailDayCombLocLink.avail_day_id.label("avail_day_id"),
            CombinationLocationsPossible.id.label("clp_id"),
            CombinationLocationsPossible.time_span_between.label("tsb"),
            LocOfWorkCombLocLink.location_of_work_id.label("location_of_work_id"),
        )
        .select_from(AvailDayCombLocLink)
        .join(
            CombinationLocationsPossible,
            CombinationLocationsPossible.id == AvailDayCombLocLink.combination_locations_possible_id,
        )
        .join(
            LocOfWorkCombLocLink,
            LocOfWorkCombLocLink.combination_locations_possible_id == CombinationLocationsPossible.id,
        )
        .where(AvailDayCombLocLink.avail_day_id.in_(relevant_avd_ids))
        .where(CombinationLocationsPossible.prep_delete.is_(None))
    ).mappings().all()

    # Aggregation: avail_day_id → list[(clp_id, tsb, locations_set)].
    clps_by_avd: dict[uuid.UUID, dict[uuid.UUID, dict]] = {}
    for row in clp_rows:
        avd_id = row["avail_day_id"]
        clp_id = row["clp_id"]
        bucket = clps_by_avd.setdefault(avd_id, {})
        clp_entry = bucket.setdefault(
            clp_id, {"tsb": row["tsb"], "locations": set()}
        )
        clp_entry["locations"].add(row["location_of_work_id"])

    def _find_clp(avd_id: uuid.UUID, loc_a: uuid.UUID, loc_b: uuid.UUID) -> dict | None:
        """Sucht ein CLP des AvailDay, das beide Locations einschließt."""
        needed = {loc_a, loc_b}
        for clp in clps_by_avd.get(avd_id, {}).values():
            if needed <= clp["locations"]:
                return clp
        return None

    for ap_id, candidate in targets_by_ap.items():
        for other in others_by_ap.get(ap_id, []):
            other_slot = TimeSlot(
                date=event_slot.date,
                start=other["other_start"],
                end=other["other_end"],
            )
            if slots_overlap(event_slot, other_slot):
                candidate.is_available = False
                candidate.blocked_reason = "time_overlap"
                candidate.blocking_info = _format_blocking_info(
                    other["other_location_name"],
                    other["other_location_city"],
                    other_slot,
                )
                break

            # Gleiche Location ist nie ein CLP-Konflikt — die Person macht
            # zwei Slots in derselben Einrichtung, kein Reise-Problem.
            other_loc_id = other["other_location_id"]
            if other_loc_id == event_location_id:
                continue

            clp_self = _find_clp(candidate.avail_day_id, event_location_id, other_loc_id)
            clp_other = _find_clp(other["other_avail_day_id"], event_location_id, other_loc_id)
            if clp_self is None or clp_other is None:
                candidate.is_available = False
                candidate.blocked_reason = "location_combo"
                candidate.blocking_info = _format_blocking_info(
                    other["other_location_name"],
                    other["other_location_city"],
                    other_slot,
                )
                break

            # Mindest-Zeitabstand via slot_gap — korrekt auch fuer
            # Mitternachts-Spannen am gleichen Datum.
            gap = slot_gap(event_slot, other_slot)
            required = max(clp_self["tsb"], clp_other["tsb"])
            if gap < required:
                candidate.is_available = False
                candidate.blocked_reason = "location_combo"
                candidate.blocking_info = _format_blocking_info(
                    other["other_location_name"],
                    other["other_location_city"],
                    other_slot,
                )
                break


def _format_blocking_info(
    location_name: str,
    location_city: str | None,
    slot: TimeSlot,
) -> str:
    """Klartext-Snippet für den Tooltip im Cast-Edit-Modal.

    Format: "LocName Stadt (HH:MM–HH:MM)". Bei Mitternachts-Spannen
    bleibt die natürliche Lesart erhalten ("22:00–02:00"), weil die
    `time`-Werte direkt aus dem Slot stammen — kein Wrap-Aufschlag.
    Stadt fällt weg, wenn die Address nicht gesetzt ist (Convention
    aus `web_api.common.location_display_name`).
    """
    display = location_display_name(location_name, location_city)
    return f"{display} ({slot.start.strftime('%H:%M')}–{slot.end.strftime('%H:%M')})"


def get_cast_status_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
) -> dict:
    """Lädt Besetzungs-Zähler für einen einzelnen Appointment.

    Nutzt dieselbe Definition wie `get_appointments_for_teams`:
    `cast_count = len(avail_days) + len(guests)`. Liefert dict mit
    `cast_count`, `cast_required`, `is_understaffed`.
    """
    avail_count = session.execute(
        sa_select(func.count(AvailDayAppointmentLink.avail_day_id))
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalar_one()

    ctx_row = session.execute(
        sa_select(
            Appointment.guests.label("guests"),
            CastGroup.nr_actors.label("cast_required"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(CastGroup, CastGroup.id == Event.cast_group_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        return {"cast_count": 0, "cast_required": 0, "is_understaffed": False}

    guests_count = guest_count(ctx_row["guests"])
    cast_count = int(avail_count) + guests_count
    cast_required = int(ctx_row["cast_required"])
    return {
        "cast_count": cast_count,
        "cast_required": cast_required,
        "is_understaffed": cast_count < cast_required,
    }


def _normalize_and_validate_guests(raw_guests: list[str]) -> list[str]:
    """Trimmt, entfernt Leereinträge und wirft bei (case-insensitiven) Duplikaten.

    Duplikate werden bewusst hart abgelehnt statt still dedupliziert — der
    User soll merken, dass er einen Namen doppelt eingegeben hat (Tippfehler,
    versehentliches Doppelklicken). Der Vergleich ist case-insensitive, die
    Ausgabe behält aber die ursprüngliche Groß-/Kleinschreibung des ersten
    Vorkommens.
    """
    cleaned: list[str] = []
    seen_lower: set[str] = set()
    for raw in raw_guests:
        stripped = raw.strip()
        if not stripped:
            continue
        key = stripped.lower()
        if key in seen_lower:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Gast »{stripped}« ist mehrfach aufgeführt.",
            )
        seen_lower.add(key)
        cleaned.append(stripped)
    return cleaned


def replace_cast_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
    person_ids: list[uuid.UUID],
    guests: list[str] | None = None,
) -> list[EmailPayload]:
    """Ersetzt die Cast-Zuordnung eines Appointments (Personen + optional Gäste).

    Für jede person_id wird der passende `ActorPlanPeriod` in der Plan-
    Periode gesucht und ein `AvailDay` für den Event-Slot gefunden oder
    angelegt (via `create_avail_day` — erlaubt Zuordnung von aktuell
    nicht-verfügbaren Personen). Ruft dann `update_appointment_avail_days`
    aus `plan_adjustment/service.py`, welches die M:N-Zuordnung ersetzt
    und offene Requests entfernter Personen auf `superseded_by_cast_change`
    flippt + Notification-Payloads erzeugt.

    Parameter `guests`:
        - `None`: Gäste bleiben unverändert (Rückwärtskompatibilität).
        - `list[str]`: Gäste werden komplett ersetzt. Strings werden getrimmt,
          leere entfernt, Duplikate (case-insensitive) werfen 422.

    Gesamt-Cap: `len(person_ids) + len(guests) <= CastGroup.nr_actors` — bei
    Überschreitung 422. Der Check wird **vor** allen Side-Effects ausgeführt.
    """
    ctx_row = session.execute(
        sa_select(
            Event.date.label("event_date"),
            Event.time_of_day_id.label("time_of_day_id"),
            Plan.plan_period_id.label("plan_period_id"),
            CastGroup.nr_actors.label("nr_actors"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(CastGroup, CastGroup.id == Event.cast_group_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")

    event_date = ctx_row["event_date"]
    time_of_day_id = ctx_row["time_of_day_id"]
    plan_period_id = ctx_row["plan_period_id"]
    nr_actors_cap = int(ctx_row["nr_actors"])

    # Gäste normalisieren (falls übergeben) — vor Obergrenze, damit der Cap
    # gegen die finale, deduplizierte Liste geprüft wird.
    clean_guests: list[str] | None = None
    if guests is not None:
        clean_guests = _normalize_and_validate_guests(guests)

    # Obergrenze: aktuelle Gäste-Anzahl einbeziehen, falls guests=None.
    if clean_guests is not None:
        guests_count_for_cap = len(clean_guests)
    else:
        current_row = session.execute(
            sa_select(Appointment.guests).where(Appointment.id == appointment_id)
        ).first()
        guests_count_for_cap = guest_count(current_row[0]) if current_row else 0

    total_cast = len(person_ids) + guests_count_for_cap
    if total_cast > nr_actors_cap:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Die Cast-Größe ({total_cast}) überschreitet die Soll-Besetzung "
                f"({nr_actors_cap}). Erhöhe zuerst die Soll-Größe oder reduziere "
                f"Personen/Gäste."
            ),
        )

    avail_day_ids: list[uuid.UUID] = []
    if person_ids:
        app_rows = session.execute(
            sa_select(ActorPlanPeriod.id, ActorPlanPeriod.person_id)
            .where(ActorPlanPeriod.plan_period_id == plan_period_id)
            .where(ActorPlanPeriod.person_id.in_(person_ids))
        ).mappings().all()
        apps_by_person = {r["person_id"]: r["id"] for r in app_rows}

        missing = set(person_ids) - set(apps_by_person.keys())
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Person nicht in der Plan-Periode planbar",
            )

        for pid in person_ids:
            app_id = apps_by_person[pid]
            avail_day = find_avail_day(session, app_id, event_date, time_of_day_id)
            if avail_day is None:
                avail_day = create_avail_day(session, app_id, event_date, time_of_day_id)
                reset_location_prefs_to_normal(session, avail_day)
            avail_day_ids.append(avail_day.id)

    payloads = update_appointment_avail_days(session, appointment_id, avail_day_ids)

    # Gäste erst nach dem Avail-Day-Update persistieren, damit bei einem
    # Fehler oben die Gäste-Mutation nicht als Ghost-Write zurückbleibt.
    # flag_modified ist nötig, weil die JSON-Spalte ohne MutableList
    # deklariert ist — Reassignment wird von SA sonst nicht zuverlässig
    # als dirty erkannt (silent no-op bei gleicher Python-Ident).
    if clean_guests is not None:
        appointment = session.get(Appointment, appointment_id)
        if appointment is not None:
            appointment.guests = clean_guests
            flag_modified(appointment, "guests")
            session.add(appointment)

    return payloads


_NR_ACTORS_MIN = 0
_NR_ACTORS_MAX = 65535


def set_cast_group_nr_actors(
    session: Session,
    appointment_id: uuid.UUID,
    nr_actors: int,
) -> dict:
    """Setzt `CastGroup.nr_actors` für die CastGroup des Events eines Appointments.

    Wichtig: `nr_actors` lebt auf CastGroup-Ebene, nicht auf Appointment-
    Ebene. Eine Änderung wirkt daher auf **alle** Appointments desselben
    Events (bei mehrfach gespielten Serien).

    Web-API-eigenes UPDATE — ruft bewusst keine Desktop-db_services auf,
    um die Architektur-Grenze zwischen Web-API und Desktop-Client-Services
    sauber zu halten.

    Return-Wert enthält die CastGroup-ID und eine `warnings`-Liste, die
    z. B. einen Hinweis trägt, wenn die neue Soll-Größe unter die aktuelle
    Besetzung fällt — der Aufrufer kann diesen Hinweis dem User zeigen.
    """
    if nr_actors < _NR_ACTORS_MIN or nr_actors > _NR_ACTORS_MAX:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"nr_actors muss zwischen {_NR_ACTORS_MIN} und {_NR_ACTORS_MAX} liegen",
        )

    row = session.execute(
        sa_select(Event.cast_group_id)
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .where(Appointment.id == appointment_id)
    ).first()
    if row is None or row[0] is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="CastGroup nicht gefunden")

    cast_group_id = row[0]
    cast_group = session.get(CastGroup, cast_group_id)
    if cast_group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="CastGroup nicht gefunden")

    cast_group.nr_actors = nr_actors
    session.add(cast_group)

    status_data = get_cast_status_for_appointment(session, appointment_id)
    warnings: list[str] = []
    if status_data["cast_count"] > nr_actors:
        warnings.append(
            f"Aktuelle Besetzung ({status_data['cast_count']}) übersteigt "
            f"die neue Soll-Größe ({nr_actors})."
        )

    return {
        "cast_group_id": cast_group_id,
        "nr_actors": nr_actors,
        "warnings": warnings,
    }


# ── Last-Minute-Appointment-Form (D3) ────────────────────────────────────────
# Domain-Logik für das Anlage-Formular eines Last-Minute-Appointments im
# Disponenten-Plan. Wurde aus dispatcher/router.py hierher migriert (vorher
# als Router-private Helper) — nimmt nur Session und Domain-IDs entgegen,
# liefert Domain-Daten als dict zurück, kein FastAPI-/Template-Spezifisches.

# Warning-Zustände für das Last-Minute-Modal — siehe resolve_appointment_form_state.
# Werte sind Strings, weil sie 1:1 in das Template (_appt_form_period_warning.html)
# eingehen: ein Enum würde dort keinen Mehrwert bringen.
WARNING_OK = "ok"
WARNING_NO_PLAN_PERIOD = "no_plan_period"
WARNING_NO_BINDING_PLAN = "no_binding_plan"
WARNING_NO_LPP = "no_lpp"


def load_locations_for_team(
    session: Session,
    team_id: uuid.UUID,
    *,
    date_filter: date | None = None,
) -> list[dict]:
    """Locations, die dem Team am gewählten Tag zugeordnet sind.

    Quelle: `TeamLocationAssign` mit tagesgenauer Range
    `start <= date < end` (end IS NULL → unbefristete Zuordnung).
    """
    location_query = (
        sa_select(LocationOfWork.id, LocationOfWork.name, Address.city)
        .select_from(LocationOfWork)
        .join(Address, Address.id == LocationOfWork.address_id, isouter=True)
        .join(TeamLocationAssign, TeamLocationAssign.location_of_work_id == LocationOfWork.id)
        .where(TeamLocationAssign.team_id == team_id)
        .where(LocationOfWork.prep_delete.is_(None))
    )
    if date_filter is not None:
        location_query = (
            location_query
            .where(TeamLocationAssign.start <= date_filter)
            .where(
                (TeamLocationAssign.end.is_(None))
                | (TeamLocationAssign.end > date_filter)
            )
        )
    location_query = location_query.distinct().order_by(LocationOfWork.name)

    location_rows = list(session.execute(location_query).mappings().all())
    return [
        {"id": row["id"], "display_name": location_display_name(row["name"], row["city"])}
        for row in location_rows
    ]


def _build_lpp_form_data(lpp: LocationPlanPeriod) -> dict:
    """TODs + nr_actors aus einer geladenen LPP extrahieren.

    TODs werden nach `start` sortiert; jede TOD bekommt ein `is_standard`-Flag.
    Default-TOD ist die zeitlich erste aus `time_of_day_standards`.
    """
    standard_ids = {tod.id for tod in lpp.time_of_day_standards if tod.prep_delete is None}
    active_tods = sorted(
        (t for t in lpp.time_of_days if t.prep_delete is None),
        key=lambda t: t.start,
    )
    time_of_days = [
        {
            "id": t.id,
            "name": t.name,
            "start": t.start,
            "is_standard": t.id in standard_ids,
        }
        for t in active_tods
    ]
    standard_active_sorted = [t for t in active_tods if t.id in standard_ids]
    default_id = standard_active_sorted[0].id if standard_active_sorted else None

    return {
        "time_of_days": time_of_days,
        "default_time_of_day_id": default_id,
        "nr_actors": lpp.nr_actors if lpp.nr_actors is not None else 1,
    }


def resolve_appointment_form_state(
    session: Session,
    *,
    team_id: uuid.UUID,
    date_filter: date | None,
    location_id: uuid.UUID | None,
) -> dict:
    """Auflösung (Team, Datum, Location) → Form-Zustand für das Last-Minute-Modal.

    Liefert ein Dict mit:
    - `time_of_days`: list[dict] mit id/name/start/is_standard, sortiert nach start
    - `default_time_of_day_id`: UUID | None (zeitlich erste aus time_of_day_standards)
    - `nr_actors`: int (Prefill-Wert für Cast-Soll-Größe)
    - `warning_state`: str (siehe WARNING_*-Konstanten)
    - `submit_enabled`: bool (False, wenn kein bindender Plan ODER keine PlanPeriode)

    Logik:
    1. Datum oder Location nicht gesetzt → leer + warning=ok (initial-state, kein Banner)
    2. Keine PlanPeriode für (team, date) → leer + warning=no_plan_period, submit=False
    3. Kein bindender Plan in der Periode → TODs/nr_actors aus LPP laden falls vorhanden,
       warning=no_binding_plan, submit=False (Last-Minute nur auf bindendem Plan erlaubt)
    4. Bindender Plan + LPP fehlt (Location nicht in Periode) → leer + warning=no_lpp,
       submit=False
    5. Alles ok → TODs/nr_actors aus LPP, warning=ok, submit=True
    """
    empty_state = {
        "time_of_days": [],
        "default_time_of_day_id": None,
        "nr_actors": 1,
        "warning_state": WARNING_OK,
        "submit_enabled": False,
    }

    if date_filter is None:
        return empty_state

    plan_period = session.execute(
        sa_select(PlanPeriod)
        .join(Team, Team.id == PlanPeriod.team_id)
        .where(PlanPeriod.team_id == team_id)
        .where(PlanPeriod.start <= date_filter)
        .where(PlanPeriod.end >= date_filter)
        .where(PlanPeriod.prep_delete.is_(None))
        .where(Team.prep_delete.is_(None))
    ).scalars().first()

    if plan_period is None:
        return {**empty_state, "warning_state": WARNING_NO_PLAN_PERIOD}

    has_binding_plan = session.execute(
        sa_select(Plan.id)
        .where(Plan.plan_period_id == plan_period.id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
    ).scalars().first() is not None

    if not has_binding_plan:
        # Banner sofort zeigen — auch ohne Location-Auswahl, sonst sieht der User
        # erst nach Location-Wechsel, dass die ganze Periode noch keinen bindenden
        # Plan hat. Submit bleibt in jedem Fall blockiert.
        if location_id is None:
            return {**empty_state, "warning_state": WARNING_NO_BINDING_PLAN}
        lpp = session.execute(
            sa_select(LocationPlanPeriod)
            .options(
                selectinload(LocationPlanPeriod.time_of_days),
                selectinload(LocationPlanPeriod.time_of_day_standards),
            )
            .where(LocationPlanPeriod.plan_period_id == plan_period.id)
            .where(LocationPlanPeriod.location_of_work_id == location_id)
        ).scalars().first()
        if lpp is None:
            return {**empty_state, "warning_state": WARNING_NO_BINDING_PLAN}
        return {
            **_build_lpp_form_data(lpp),
            "warning_state": WARNING_NO_BINDING_PLAN,
            "submit_enabled": False,
        }

    if location_id is None:
        # PlanPeriode + bindender Plan ok, aber Location noch nicht ausgewählt.
        # Form ist neutral, Submit-Button bleibt aus, bis Location gesetzt ist.
        return empty_state

    lpp = session.execute(
        sa_select(LocationPlanPeriod)
        .options(
            selectinload(LocationPlanPeriod.time_of_days),
            selectinload(LocationPlanPeriod.time_of_day_standards),
        )
        .where(LocationPlanPeriod.plan_period_id == plan_period.id)
        .where(LocationPlanPeriod.location_of_work_id == location_id)
    ).scalars().first()

    if lpp is None:
        return {**empty_state, "warning_state": WARNING_NO_LPP}

    lpp_data = _build_lpp_form_data(lpp)
    return {
        **lpp_data,
        "warning_state": WARNING_OK,
        # Edge-Case: LPP existiert, aber alle TODs sind soft-deleted.
        # Dropdown zeigt seinen Empty-State, Submit-Button bleibt aus.
        "submit_enabled": bool(lpp_data["time_of_days"]),
    }