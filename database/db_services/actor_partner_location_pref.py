"""Service-Funktionen für ActorPartnerLocationPref (Partner-Standortpräferenz).

Verwaltet Präferenz-Scores für die Kombination aus Akteur, Partner-Person und
Arbeitsort. Unterstützt Soft-Delete, Abfragen per AvailDay sowie das Bereinigen
ungenutzter Einträge ohne Bezug zu ActorPlanPeriod, AvailDay oder Person-Default.
"""
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


def replace_all_for_model(
    model_class_name: str,
    model_id: UUID,
    person_id: UUID,
    new_prefs: list[tuple[UUID, UUID, float]],
) -> tuple[list[UUID], list[UUID]]:
    """Ersetzt alle APL-Verknüpfungen eines Modells in einer einzigen Transaktion.

    Entspricht dem Ablauf: alle alten Links leeren → verwaiste APLs soft-löschen
    → neue APLs erstellen und verknüpfen.

    Returns:
        (created_ids, old_apl_ids) — für Undo-Support in ReplaceAll-Command
    """
    log_function_info()
    with get_session() as session:
        if model_class_name == 'PersonShow':
            model_obj = session.get(models.Person, model_id)
        elif model_class_name == 'ActorPlanPeriodForMask':
            model_obj = session.get(models.ActorPlanPeriod, model_id)
        else:  # AvailDay, AvailDayShow
            model_obj = session.get(models.AvailDay, model_id)

        old_apls = [a for a in model_obj.actor_partner_location_prefs_defaults if a.prep_delete is None]
        old_apl_ids = [a.id for a in old_apls]

        model_obj.actor_partner_location_prefs_defaults.clear()
        session.flush()

        now = _utcnow()
        for apl in old_apls:
            if (apl.person_default is None
                    and not apl.actor_plan_periods_defaults
                    and not apl.avail_days_defaults):
                apl.prep_delete = now

        person_obj = session.get(models.Person, person_id)
        for partner_id, location_id, score in new_prefs:
            new_apl = models.ActorPartnerLocationPref(
                score=score,
                person=person_obj,
                partner=session.get(models.Person, partner_id),
                location_of_work=session.get(models.LocationOfWork, location_id))
            session.add(new_apl)
            model_obj.actor_partner_location_prefs_defaults.append(new_apl)

        session.flush()
        created_ids = [a.id for a in model_obj.actor_partner_location_prefs_defaults]
        return created_ids, old_apl_ids


def undo_replace_all_for_model(
    model_class_name: str,
    model_id: UUID,
    created_ids: list[UUID],
    old_apl_ids: list[UUID],
) -> None:
    """Macht replace_all_for_model rückgängig in einer einzigen Transaktion."""
    log_function_info()
    with get_session() as session:
        if model_class_name == 'PersonShow':
            model_obj = session.get(models.Person, model_id)
        elif model_class_name == 'ActorPlanPeriodForMask':
            model_obj = session.get(models.ActorPlanPeriod, model_id)
        else:  # AvailDay, AvailDayShow
            model_obj = session.get(models.AvailDay, model_id)

        model_obj.actor_partner_location_prefs_defaults.clear()
        session.flush()

        now = _utcnow()
        for created_id in created_ids:
            apl = session.get(models.ActorPartnerLocationPref, created_id)
            if apl:
                apl.prep_delete = now

        for old_id in old_apl_ids:
            apl = session.get(models.ActorPartnerLocationPref, old_id)
            if apl:
                apl.prep_delete = None
                model_obj.actor_partner_location_prefs_defaults.append(apl)

        session.flush()


def delete_prep_deletes(person_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        prefs = session.exec(select(models.ActorPartnerLocationPref).where(
            models.ActorPartnerLocationPref.person_id == person_id)).all()
        for p in prefs:
            if p.prep_delete:
                session.delete(p)