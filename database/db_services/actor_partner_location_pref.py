import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
    with get_session() as session:
        return schemas.ActorPartnerLocationPrefShow.model_validate(
            session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))


def get_all_from__avail_day(avail_day_id: UUID) -> list[schemas.ActorPartnerLocationPrefShow]:
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        return [schemas.ActorPartnerLocationPrefShow.model_validate(p) for p in ad.actor_partner_location_prefs_defaults]


def get_ids_per_avail_day_of_actor_plan_period(actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        return {ad.id: [p.id for p in ad.actor_partner_location_prefs_defaults] for ad in app.avail_days}


def create(actor_partner_loc_pref: schemas.ActorPartnerLocationPrefCreate) -> schemas.ActorPartnerLocationPrefShow:
    log_function_info()
    with get_session() as session:
        obj = models.ActorPartnerLocationPref(
            score=actor_partner_loc_pref.score,
            person=session.get(models.Person, actor_partner_loc_pref.person.id),
            partner=session.get(models.Person, actor_partner_loc_pref.partner.id),
            location_of_work=session.get(models.LocationOfWork, actor_partner_loc_pref.location_of_work.id))
        session.add(obj)
        session.flush()
        return schemas.ActorPartnerLocationPrefShow.model_validate(obj)


def modify(actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow) -> schemas.ActorPartnerLocationPrefShow:
    with get_session() as session:
        obj = session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref.id)
        obj.person_default = (session.get(models.Person, actor_partner_loc_pref.person_default.id)
                              if actor_partner_loc_pref.person_default else None)
        obj.actor_plan_periods_defaults.clear()
        for app in actor_partner_loc_pref.actor_plan_periods_defaults:
            obj.actor_plan_periods_defaults.append(session.get(models.ActorPlanPeriod, app.id))
        obj.avail_days_defaults.clear()
        for ad in actor_partner_loc_pref.avail_days_defaults:
            obj.avail_days_defaults.append(session.get(models.AvailDay, ad.id))
        session.flush()
        return schemas.ActorPartnerLocationPrefShow.model_validate(obj)


def delete(actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id)
        obj.prep_delete = _utcnow()
        session.flush()
        return schemas.ActorPartnerLocationPrefShow.model_validate(obj)


def undelete(actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id)
        obj.prep_delete = None
        session.flush()
        return schemas.ActorPartnerLocationPrefShow.model_validate(obj)


def delete_unused(person_id: UUID) -> list[UUID]:
    log_function_info()
    with get_session() as session:
        prefs = session.exec(select(models.ActorPartnerLocationPref).where(
            models.ActorPartnerLocationPref.person_id == person_id)).all()
        deleted_ids = []
        for p in prefs:
            if p.prep_delete:
                continue
            if not p.actor_plan_periods_defaults and not p.avail_days_defaults and not p.person_default:
                p.prep_delete = _utcnow()
                deleted_ids.append(p.id)
        return deleted_ids


def delete_prep_deletes(person_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        prefs = session.exec(select(models.ActorPartnerLocationPref).where(
            models.ActorPartnerLocationPref.person_id == person_id)).all()
        for p in prefs:
            if p.prep_delete:
                session.delete(p)