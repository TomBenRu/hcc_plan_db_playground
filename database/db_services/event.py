"""Service-Funktionen für Event (Veranstaltungstermin).

Ein Event repräsentiert einen konkreten Termin an einem Datum und zu einer
Tageszeit an einem Standort (LocationPlanPeriod). Das Erstellen legt automatisch
eine EventGroup (Baumknoten) und eine CastGroup (Besetzungsvorgabe) an — beides
wird beim Löschen wieder bereinigt. Unterstützt Flags und SkillGroups als
Metadaten-Verknüpfungen.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload, joinedload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import event_button_update_options, event_for_button_options


def get(event_id: UUID) -> schemas.EventShow:
    with get_session() as session:
        return schemas.EventShow.model_validate(session.get(models.Event, event_id))


def get_flat(event_id: UUID) -> schemas.Event | None:
    """Lädt Event mit flachem Schema — kein event_group/cast_group/skill_groups."""
    with get_session() as session:
        event = session.get(models.Event, event_id)
        return schemas.Event.model_validate(event) if event else None


def get_time_of_day_and_nr_actors(event_id: UUID) -> tuple[schemas.TimeOfDay, int] | None:
    """Lädt time_of_day + cast_group.nr_actors via JOINs — für ButtonEvent.on_appointment_moved."""
    with get_session() as session:
        stmt = (
            select(models.Event)
            .options(*event_button_update_options())
            .where(models.Event.id == event_id)
        )
        event = session.exec(stmt).unique().first()
        if not event:
            return None
        return schemas.TimeOfDay.model_validate(event.time_of_day), event.cast_group.nr_actors


def get_batch_for_solver(event_ids: list[UUID]) -> dict[UUID, schemas.EventForSolver]:
    """Lädt mehrere Events als EventForSolver für den Solver.

    Benötigte Felder durch Solver-Constraints:
    - time_of_day → time_of_day_enum  (check_time_span_avail_day_fits_event)
    - location_plan_period → location_of_work  (check_actor_location_prefs_fits_event, cast_rules)
    - location_plan_period → plan_period → team  (LocationPlanPeriod-Schema-Pflichtfeld)
    - flags  (EventCreate-Pflichtfeld)
    - skill_groups  (skills.py)
    - cast_group.nr_actors  (skills.py, partner_location_prefs.py, unsigned_shifts.py)
    - event_group.id  (cast_rules.py — lookup via entities.event_groups)

    EventForSolver vermeidet die rekursive event_group-Eltern-Kette (EventShow-Problem:
    4014ms für 55 Events durch Pydantic-Traversierung bis Root-EventGroup).
    """
    if not event_ids:
        return {}
    with get_session() as session:
        stmt = (select(models.Event)
                .where(models.Event.id.in_(event_ids))
                .options(
                    # ── Basis-Chains ─────────────────────────────────────────
                    joinedload(models.Event.time_of_day)
                    .joinedload(models.TimeOfDay.time_of_day_enum),
                    joinedload(models.Event.location_plan_period)
                    .joinedload(models.LocationPlanPeriod.location_of_work),
                    joinedload(models.Event.location_plan_period)
                    .joinedload(models.LocationPlanPeriod.plan_period)
                    .joinedload(models.PlanPeriod.team),
                    selectinload(models.Event.flags),
                    # ── Solver-spezifische Chains ─────────────────────────────
                    selectinload(models.Event.skill_groups),
                    joinedload(models.Event.cast_group),  # nur id + nr_actors benötigt
                    joinedload(models.Event.event_group),  # nur id benötigt
                ))
        events = session.exec(stmt).unique().all()
        return {e.id: schemas.EventForSolver.model_validate(e) for e in events}


def get_all_from__plan_period(plan_period_id: UUID) -> list[schemas.EventShow]:
    with get_session() as session:
        events = session.exec(select(models.Event).join(models.LocationPlanPeriod)
                              .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)).all()
        return [schemas.EventShow.model_validate(e) for e in events]


def get_all_from__plan_period_date_time_of_day(plan_period_id: UUID,
                                               date: datetime.date, time_index: int) -> list[schemas.EventShow]:
    with get_session() as session:
        events = session.exec(
            select(models.Event).join(models.LocationPlanPeriod)
            .join(models.TimeOfDay, models.Event.time_of_day_id == models.TimeOfDay.id)
            .join(models.TimeOfDayEnum)
            .where(models.LocationPlanPeriod.plan_period_id == plan_period_id,
                   models.Event.date == date, models.TimeOfDayEnum.time_index == time_index)
        ).all()
        return [schemas.EventShow.model_validate(e) for e in events]


def get_all_from__location_plan_period(location_plan_period_id) -> list[schemas.EventShow]:
    with get_session() as session:
        events = session.exec(select(models.Event).where(
            models.Event.location_plan_period_id == location_plan_period_id)).all()
        return [schemas.EventShow.model_validate(e) for e in events]


def get_events_for_buttons__plan_period(plan_period_id: UUID) -> dict[UUID, list[schemas.EventForButton]]:
    """Lädt Events aller LocationPlanPeriods einer PlanPeriode mit SkillGroups in einem Batch-Query.

    Ersetzt N einzelne get_all_from__location_plan_period()-Calls durch einen einzigen
    JOIN-Query mit selectinload für skill_groups.skill.
    Rückgabe: dict[location_plan_period_id → list[EventForButton]]
    """
    with get_session() as session:
        stmt = (select(models.Event)
                .join(models.LocationPlanPeriod)
                .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)
                .options(selectinload(models.Event.skill_groups)
                         .joinedload(models.SkillGroup.skill)))
        events = session.exec(stmt).all()
        result: dict[UUID, list[schemas.EventForButton]] = {}
        for e in events:
            result.setdefault(e.location_plan_period_id, []).append(
                schemas.EventForButton.model_validate(e))
        return result


def get_from__event_group(event_group_id) -> schemas.EventShow | None:
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        return schemas.EventShow.model_validate(eg.event) if eg.event else None


def get_from__location_pp_date_tod(location_plan_period_id: UUID, date: datetime.date,
                                   time_of_day_id) -> schemas.EventShow | None:
    with get_session() as session:
        event = session.exec(select(models.Event).where(
            models.Event.location_plan_period_id == location_plan_period_id,
            models.Event.date == date, models.Event.time_of_day_id == time_of_day_id,
            models.Event.prep_delete.is_(None))).first()
        return schemas.EventShow.model_validate(event) if event else None


def get_from__location_pp_date_time_index(location_plan_period_id: UUID, date: datetime.date,
                                          time_index: int) -> schemas.Event | None:
    with get_session() as session:
        event = session.exec(
            select(models.Event)
            .join(models.TimeOfDay, models.Event.time_of_day_id == models.TimeOfDay.id)
            .join(models.TimeOfDayEnum)
            .where(models.Event.location_plan_period_id == location_plan_period_id,
                   models.Event.date == date, models.TimeOfDayEnum.time_index == time_index)
        ).first()
        return schemas.Event.model_validate(event) if event else None


def get_from__location_pp_date(location_plan_period_id: UUID, date: datetime.date) -> list[schemas.EventForButton]:
    """Lädt Events eines Datums als EventForButton — für ButtonNotes/ButtonSkillGroups-Prefetch."""
    with get_session() as session:
        stmt = (select(models.Event)
                .where(models.Event.location_plan_period_id == location_plan_period_id,
                       models.Event.date == date)
                .options(*event_for_button_options()))
        events = session.exec(stmt).unique().all()
        return [schemas.EventForButton.model_validate(e) for e in events]


def create(event: schemas.EventCreate) -> schemas.EventShow:
    """Erstellt Event mit zugehöriger EventGroup und CastGroup (inlined)."""
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, event.location_plan_period.id)
        master_eg = lpp.event_group
        # EventGroup erstellen (inlined)
        eg = models.EventGroup(event_group=master_eg)
        session.add(eg)
        # CastGroup erstellen (inlined)
        cg = models.CastGroup(nr_actors=lpp.nr_actors, plan_period=lpp.plan_period,
                              fixed_cast=lpp.fixed_cast, fixed_cast_only_if_available=lpp.fixed_cast_only_if_available)
        session.add(cg)
        session.flush()
        event_db = models.Event(date=event.date,
                                time_of_day=session.get(models.TimeOfDay, event.time_of_day.id),
                                event_group=eg, cast_group=cg, location_plan_period=lpp)
        session.add(event_db)
        session.flush()
        return schemas.EventShow.model_validate(event_db)


def update_time_of_day_and_date(event_id: UUID, new_time_of_day_id: UUID,
                                new_date: datetime.date = None) -> None:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.time_of_day = session.get(models.TimeOfDay, new_time_of_day_id)
        if new_date:
            event.date = new_date
        session.flush()


def update_time_of_days(event_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        for t in time_of_days:
            event.time_of_days.append(session.get(models.TimeOfDay, t.id))
        session.flush()
        return schemas.EventShow.model_validate(event)


def update_notes(event_id: UUID, notes: str) -> None:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.notes = notes
        session.flush()


def delete(event_id: UUID) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        deleted = schemas.EventShow.model_validate(event)
        eg = event.event_group
        cg = event.cast_group
        session.delete(event)
        session.flush()
        session.delete(eg)
        session.delete(cg)
        return deleted


def put_in_flag(event_id: UUID, flag_id: UUID) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.flags.append(session.get(models.Flag, flag_id))
        session.flush()
        return schemas.EventShow.model_validate(event)


def remove_flag(event_id: UUID, flag_id: UUID) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.flags.remove(session.get(models.Flag, flag_id))
        session.flush()
        return schemas.EventShow.model_validate(event)


def add_skill_group(event_id: UUID, skill_group_id: UUID) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.skill_groups.append(session.get(models.SkillGroup, skill_group_id))
        session.flush()
        return schemas.EventShow.model_validate(event)


def remove_skill_group(event_id: UUID, skill_group_id: UUID) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.skill_groups.remove(session.get(models.SkillGroup, skill_group_id))
        session.flush()
        return schemas.EventShow.model_validate(event)