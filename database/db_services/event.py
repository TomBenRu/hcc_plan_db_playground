"""Service-Funktionen für Event (Veranstaltungstermin).

Ein Event repräsentiert einen konkreten Termin an einem Datum und zu einer
Tageszeit an einem Standort (LocationPlanPeriod). Das Erstellen legt automatisch
eine EventGroup (Baumknoten) und eine CastGroup (Besetzungsvorgabe) an — beides
wird beim Löschen wieder bereinigt. Unterstützt Flags und SkillGroups als
Metadaten-Verknüpfungen.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(event_id: UUID) -> schemas.EventShow:
    with get_session() as session:
        return schemas.EventShow.model_validate(session.get(models.Event, event_id))


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


def get_from__location_pp_date(location_plan_period_id: UUID, date: datetime.date) -> list[schemas.EventShow]:
    with get_session() as session:
        events = session.exec(select(models.Event).where(
            models.Event.location_plan_period_id == location_plan_period_id,
            models.Event.date == date)).all()
        return [schemas.EventShow.model_validate(e) for e in events]


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
                                new_date: datetime.date = None) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.time_of_day = session.get(models.TimeOfDay, new_time_of_day_id)
        if new_date:
            event.date = new_date
        session.flush()
        return schemas.EventShow.model_validate(event)


def update_time_of_days(event_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        for t in time_of_days:
            event.time_of_days.append(session.get(models.TimeOfDay, t.id))
        session.flush()
        return schemas.EventShow.model_validate(event)


def update_notes(event_id: UUID, notes: str) -> schemas.EventShow:
    log_function_info()
    with get_session() as session:
        event = session.get(models.Event, event_id)
        event.notes = notes
        session.flush()
        return schemas.EventShow.model_validate(event)


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