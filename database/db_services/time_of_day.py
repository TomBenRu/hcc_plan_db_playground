import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(time_of_day_id: UUID, reduced: bool = False) -> schemas.TimeOfDayShow | schemas.TimeOfDay:
    with get_session() as session:
        tod = session.get(models.TimeOfDay, time_of_day_id)
        return schemas.TimeOfDay.model_validate(tod) if reduced else schemas.TimeOfDayShow.model_validate(tod)


def get_time_of_days_from__event(event_id: UUID) -> list[schemas.TimeOfDay]:
    with get_session() as session:
        return [schemas.TimeOfDay.model_validate(t) for t in session.get(models.Event, event_id).time_of_days]


def get_all_from_location_plan_period(location_plan_period_id: UUID) -> list[schemas.TimeOfDay]:
    with get_session() as session:
        return [schemas.TimeOfDay.model_validate(t) for t in session.get(models.LocationPlanPeriod, location_plan_period_id).time_of_days]


def create(time_of_day: schemas.TimeOfDayCreate, project_id: UUID) -> schemas.TimeOfDay:
    log_function_info()
    with get_session() as session:
        tod = models.TimeOfDay(name=time_of_day.name,
                               time_of_day_enum=session.get(models.TimeOfDayEnum, time_of_day.time_of_day_enum.id),
                               project=session.get(models.Project, project_id),
                               start=time_of_day.start, end=time_of_day.end)
        session.add(tod)
        session.flush()
        return schemas.TimeOfDay.model_validate(tod)


def update(time_of_day: schemas.TimeOfDay):
    log_function_info()
    with get_session() as session:
        tod = session.get(models.TimeOfDay, time_of_day.id)
        tod.name = time_of_day.name
        tod.start = time_of_day.start
        tod.end = time_of_day.end
        tod.time_of_day_enum = session.get(models.TimeOfDayEnum, time_of_day.time_of_day_enum.id)
        session.flush()
        return schemas.TimeOfDay.model_validate(tod)


def put_to_model(time_of_day: schemas.TimeOfDay, pydantic_model: schemas.ModelWithTimeOfDays, db_model):
    log_function_info()
    if not (isinstance(pydantic_model, schemas.ModelWithTimeOfDays) or isinstance(pydantic_model, schemas.Project)):
        raise ValueError
    with get_session() as session:
        instance_db = session.get(db_model, pydantic_model.id)
        instance_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day.id))
        session.flush()
        return type(pydantic_model).model_validate(instance_db)


def delete(time_of_day_id: UUID) -> schemas.TimeOfDay:
    log_function_info()
    with get_session() as session:
        tod = session.get(models.TimeOfDay, time_of_day_id)
        tod.prep_delete = _utcnow()
        session.flush()
        return schemas.TimeOfDay.model_validate(tod)


def undo_delete(time_of_day_id: UUID) -> schemas.TimeOfDay:
    log_function_info()
    with get_session() as session:
        tod = session.get(models.TimeOfDay, time_of_day_id)
        tod.prep_delete = None
        session.flush()
        return schemas.TimeOfDay.model_validate(tod)


def delete_unused(project_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        tods = session.exec(select(models.TimeOfDay).where(models.TimeOfDay.project_id == project_id)).all()
        for t in tods:
            if t.prep_delete:
                continue
            empty = [t.persons_defaults, t.actor_plan_periods_defaults, t.avail_days_defaults,
                     t.avail_days, t.locations_of_work_defaults, t.location_plan_periods_defaults,
                     t.events_defaults, t.events]
            if not t.project_defaults and all(not c for c in empty):
                t.prep_delete = _utcnow()


def delete_prep_deletes(project_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        tods = session.exec(select(models.TimeOfDay).where(models.TimeOfDay.project_id == project_id)).all()
        for t in tods:
            if t.prep_delete:
                session.delete(t)