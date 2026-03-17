import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def create(actor_loc_pref: schemas.ActorLocationPrefCreate) -> schemas.ActorLocationPrefShow:
    log_function_info()
    with get_session() as session:
        obj = models.ActorLocationPref(
            score=actor_loc_pref.score,
            project=session.get(models.Project, actor_loc_pref.person.project.id),
            person=session.get(models.Person, actor_loc_pref.person.id),
            location_of_work=session.get(models.LocationOfWork, actor_loc_pref.location_of_work.id))
        session.add(obj)
        session.flush()
        return schemas.ActorLocationPrefShow.model_validate(obj)


def delete(actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.ActorLocationPref, actor_loc_pref_id)
        obj.prep_delete = _utcnow()
        session.flush()
        return schemas.ActorLocationPrefShow.model_validate(obj)


def undelete(actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.ActorLocationPref, actor_loc_pref_id)
        obj.prep_delete = None
        session.flush()
        return schemas.ActorLocationPrefShow.model_validate(obj)


def delete_unused(project_id: UUID) -> list[UUID]:
    log_function_info()
    with get_session() as session:
        prefs = session.exec(select(models.ActorLocationPref).where(
            models.ActorLocationPref.project_id == project_id)).all()
        deleted_ids = []
        for p in prefs:
            if p.prep_delete:
                continue
            if not p.actor_plan_periods_defaults and not p.avail_days_defaults and not p.person_default:
                p.prep_delete = _utcnow()
                deleted_ids.append(p.id)
        return deleted_ids


def delete_prep_deletes(project_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        prefs = session.exec(select(models.ActorLocationPref).where(
            models.ActorLocationPref.project_id == project_id)).all()
        for p in prefs:
            if p.prep_delete:
                session.delete(p)


def get_loc_pref_ids_per_avail_day_of_actor_plan_period(actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        return {ad.id: [p.id for p in ad.actor_location_prefs_defaults] for ad in app.avail_days}