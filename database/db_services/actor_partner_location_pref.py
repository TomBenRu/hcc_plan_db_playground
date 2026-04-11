"""Service-Funktionen für ActorPartnerLocationPref (Partner-Standortpräferenz).

Verwaltet Präferenz-Scores für die Kombination aus Akteur, Partner-Person und
Arbeitsort. Unterstützt Soft-Delete, Abfragen per AvailDay sowie das Bereinigen
ungenutzter Einträge ohne Bezug zu ActorPlanPeriod, AvailDay oder Person-Default.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import joinedload, selectinload
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

        app_ids = [app.id for app in actor_partner_loc_pref.actor_plan_periods_defaults]
        apps_by_id = {
            a.id: a for a in session.exec(
                select(models.ActorPlanPeriod).where(models.ActorPlanPeriod.id.in_(app_ids))
            ).all()
        } if app_ids else {}
        obj.actor_plan_periods_defaults.clear()
        obj.actor_plan_periods_defaults.extend(apps_by_id[a_id] for a_id in app_ids)

        ad_ids = [ad.id for ad in actor_partner_loc_pref.avail_days_defaults]
        avds_by_id = {
            ad.id: ad for ad in session.exec(
                select(models.AvailDay).where(models.AvailDay.id.in_(ad_ids))
            ).all()
        } if ad_ids else {}
        obj.avail_days_defaults.clear()
        obj.avail_days_defaults.extend(avds_by_id[ad_id] for ad_id in ad_ids)

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
        prefs = session.exec(
            select(models.ActorPartnerLocationPref)
            .where(models.ActorPartnerLocationPref.person_id == person_id)
            .options(selectinload(models.ActorPartnerLocationPref.actor_plan_periods_defaults),
                     selectinload(models.ActorPartnerLocationPref.avail_days_defaults),
                     joinedload(models.ActorPartnerLocationPref.person_default))
        ).all()
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

        existing_person_prefs = session.exec(
            select(models.ActorPartnerLocationPref)
            .where(models.ActorPartnerLocationPref.person_id == person_id)
            .where(models.ActorPartnerLocationPref.prep_delete == None)
        ).all()
        pref_index: dict[tuple[UUID, UUID, float], models.ActorPartnerLocationPref] = {
            (p.partner_id, p.location_of_work_id, p.score): p for p in existing_person_prefs
        }

        old_apls = [a for a in model_obj.actor_partner_location_prefs_defaults if a.prep_delete is None]
        old_apl_ids = [a.id for a in old_apls]

        model_obj.actor_partner_location_prefs_defaults.clear()
        session.flush()

        new_pref_keys = {(partner_id, location_id, score) for partner_id, location_id, score in new_prefs}
        now = _utcnow()
        for apl in old_apls:
            key = (apl.partner_id, apl.location_of_work_id, apl.score)
            if key in new_pref_keys:
                continue  # wird gleich wiederverwendet — nicht soft-löschen
            if (apl.person_default is None
                    and not apl.actor_plan_periods_defaults
                    and not apl.avail_days_defaults):
                apl.prep_delete = now

        new_ids: list[UUID] = []
        for partner_id, location_id, score in new_prefs:
            key = (partner_id, location_id, score)
            if key in pref_index:
                apl = pref_index[key]
                apl.prep_delete = None  # ggf. reaktivieren
                model_obj.actor_partner_location_prefs_defaults.append(apl)
            else:
                new_apl = models.ActorPartnerLocationPref(
                    score=score,
                    person=session.get(models.Person, person_id),
                    partner=session.get(models.Person, partner_id),
                    location_of_work=session.get(models.LocationOfWork, location_id))
                session.add(new_apl)
                session.flush()
                new_ids.append(new_apl.id)
                model_obj.actor_partner_location_prefs_defaults.append(new_apl)

        session.flush()
        return new_ids, old_apl_ids


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


def replace_all_for_avail_days(
    avail_day_ids: list[UUID],
    person_id: UUID,
    new_prefs: list[tuple[UUID, UUID, float]],
) -> tuple[list[UUID], dict[UUID, list[UUID]]]:
    """Ersetzt alle APL-Verknüpfungen für mehrere AvailDays in einer einzigen Session.

    Analog zu replace_all_for_model, aber für mehrere AvailDays gleichzeitig.
    Wiederverwendungslogik: Existiert bereits eine nicht-gelöschte APL der Person
    mit identischem (partner, location, score)-Tripel, wird sie übernommen.

    Returns: (created_ids, old_pref_ids_per_avail_day) — für Undo-Support.
    """
    log_function_info()
    with get_session() as session:
        existing_person_prefs = session.exec(
            select(models.ActorPartnerLocationPref)
            .where(models.ActorPartnerLocationPref.person_id == person_id)
            .where(models.ActorPartnerLocationPref.prep_delete == None)
        ).all()
        pref_index: dict[tuple[UUID, UUID, float], models.ActorPartnerLocationPref] = {
            (p.partner_id, p.location_of_work_id, p.score): p for p in existing_person_prefs
        }

        # Alten Zustand sichern, AvailDays leeren
        old_pref_ids_per_avail_day: dict[UUID, list[UUID]] = {}
        all_old_apls: list[models.ActorPartnerLocationPref] = []
        avail_day_objs: list[models.AvailDay] = []
        for avd_id in avail_day_ids:
            avd = session.get(models.AvailDay, avd_id)
            old_pref_ids_per_avail_day[avd_id] = [
                a.id for a in avd.actor_partner_location_prefs_defaults if a.prep_delete is None]
            all_old_apls.extend(
                a for a in avd.actor_partner_location_prefs_defaults if a.prep_delete is None)
            avd.actor_partner_location_prefs_defaults.clear()
            avail_day_objs.append(avd)
        session.flush()

        # Verwaiste APLs soft-löschen
        new_pref_keys = {(partner_id, location_id, score) for partner_id, location_id, score in new_prefs}
        now = _utcnow()
        for apl in all_old_apls:
            key = (apl.partner_id, apl.location_of_work_id, apl.score)
            if key not in new_pref_keys:
                if (apl.person_default is None
                        and not apl.actor_plan_periods_defaults
                        and not apl.avail_days_defaults):
                    apl.prep_delete = now

        # Neue Prefs erstellen/wiederverwenden
        new_apl_objects: list[models.ActorPartnerLocationPref] = []
        new_ids: list[UUID] = []
        for partner_id, location_id, score in new_prefs:
            key = (partner_id, location_id, score)
            if key in pref_index:
                apl = pref_index[key]
                apl.prep_delete = None
                new_apl_objects.append(apl)
            else:
                new_apl = models.ActorPartnerLocationPref(
                    score=score,
                    person=session.get(models.Person, person_id),
                    partner=session.get(models.Person, partner_id),
                    location_of_work=session.get(models.LocationOfWork, location_id))
                session.add(new_apl)
                session.flush()
                new_ids.append(new_apl.id)
                new_apl_objects.append(new_apl)

        # Alle AvailDays auf neue Prefs setzen
        for avd in avail_day_objs:
            avd.actor_partner_location_prefs_defaults = list(new_apl_objects)
        session.flush()

        return new_ids, old_pref_ids_per_avail_day


def undo_replace_all_for_avail_days(
    avail_day_ids: list[UUID],
    created_ids: list[UUID],
    old_pref_ids_per_avail_day: dict[UUID, list[UUID]],
) -> None:
    """Undo-Gegenstück zu replace_all_for_avail_days in einer einzigen Session."""
    log_function_info()
    with get_session() as session:
        # Neu angelegte APLs soft-löschen
        now = _utcnow()
        for created_id in created_ids:
            apl = session.get(models.ActorPartnerLocationPref, created_id)
            if apl:
                apl.prep_delete = now

        # Pro AvailDay alten Zustand wiederherstellen
        for avd_id in avail_day_ids:
            avd = session.get(models.AvailDay, avd_id)
            if not avd:
                continue
            avd.actor_partner_location_prefs_defaults.clear()
            old_ids = old_pref_ids_per_avail_day.get(avd_id, [])
            for old_id in old_ids:
                apl = session.get(models.ActorPartnerLocationPref, old_id)
                if apl:
                    apl.prep_delete = None
                    avd.actor_partner_location_prefs_defaults.append(apl)
        session.flush()


def delete_prep_deletes(person_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        prefs = session.exec(select(models.ActorPartnerLocationPref).where(
            models.ActorPartnerLocationPref.person_id == person_id)).all()
        for p in prefs:
            if p.prep_delete:
                session.delete(p)