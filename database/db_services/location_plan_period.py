"""Service-Funktionen für LocationPlanPeriod (Standort-Planperiode).

Verknüpft einen Arbeitsort mit einer PlanPeriod und übernimmt standortspezifische
Konfigurationen wie Tageszeiten, Tageszeit-Standards, Besetzungsvorgaben
(fixed_cast) und die Anzahl benötigter Akteure. Hartes Löschen ohne Soft-Delete,
da LocationPlanPeriod den Lebenszyklus ihrer Events bestimmt.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(location_plan_period_id: UUID) -> schemas.LocationPlanPeriodShow:
    with get_session() as session:
        return schemas.LocationPlanPeriodShow.model_validate(session.get(models.LocationPlanPeriod, location_plan_period_id))


def create(plan_period_id: UUID, location_id: UUID, location_plan_period_id: UUID = None) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(plan_period=session.get(models.PlanPeriod, plan_period_id),
                      location_of_work=session.get(models.LocationOfWork, location_id))
        if location_plan_period_id:
            kwargs['id'] = location_plan_period_id
        lpp = models.LocationPlanPeriod(**kwargs)
        session.add(lpp)
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def delete(location_plan_period_id: UUID):
    with get_session() as session:
        session.delete(session.get(models.LocationPlanPeriod, location_plan_period_id))


def update_notes(location_plan_period_id: UUID, notes: str) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        lpp.notes = notes
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def put_in_time_of_day(location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        lpp.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def remove_in_time_of_day(location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        lpp.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def remove_time_of_day_standard(location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        lpp.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def new_time_of_day_standard(location_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationPlanPeriodShow, UUID | None]:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        tod = session.get(models.TimeOfDay, time_of_day_id)
        old_id = None
        for t in list(lpp.time_of_day_standards):
            if t.time_of_day_enum.id == tod.time_of_day_enum.id:
                lpp.time_of_day_standards.remove(t)
                old_id = t.id
                break
        lpp.time_of_day_standards.append(tod)
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp), old_id


def update_fixed_cast(location_plan_period_id: UUID, fixed_cast: str,
                      fixed_cast_only_if_available: bool) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        lpp.fixed_cast = fixed_cast
        lpp.fixed_cast_only_if_available = fixed_cast_only_if_available
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def update_num_actors(location_plan_period_id: UUID, num_actors: int) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        lpp.nr_actors = num_actors
        session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)