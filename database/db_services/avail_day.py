"""Service-Funktionen für AvailDay (Verfügbarkeitstag eines Akteurs).

Speichert, an welchem Datum und zu welcher Tageszeit ein Akteur verfügbar ist.
Enthält umfangreiche Hilfsfunktionen zum Verwalten von Standortpräferenzen,
Partner-Präferenzen, Standortkombinationen und Skills auf Tagesbasis.
Das Löschen eines AvailDay löscht automatisch auch die zugehörige AvailDayGroup.
Bietet außerdem batch-optimierte Abfragen für den Solver.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import avail_day_show_options


def get(avail_day_id: UUID) -> schemas.AvailDayShow:
    with get_session() as session:
        return schemas.AvailDayShow.model_validate(session.get(models.AvailDay, avail_day_id))


def get_batch(avail_day_ids: list[UUID]) -> dict[UUID, schemas.AvailDayShow]:
    if not avail_day_ids:
        return {}
    with get_session() as session:
        ads = session.exec(select(models.AvailDay).where(models.AvailDay.id.in_(avail_day_ids))).all()
        return {ad.id: schemas.AvailDayShow.model_validate(ad) for ad in ads}


def get_batch_minimal(avail_day_ids: list[UUID]) -> dict[UUID, schemas.AvailDaySolverMinimal]:
    if not avail_day_ids:
        return {}
    with get_session() as session:
        ads = session.exec(select(models.AvailDay).where(models.AvailDay.id.in_(avail_day_ids))).all()
        return {ad.id: schemas.AvailDaySolverMinimal.model_validate(ad) for ad in ads}


def get_from__actor_pp_date_tod(actor_plan_period_id: UUID, date: datetime.date,
                                time_of_day_id) -> schemas.AvailDayShow | None:
    with get_session() as session:
        ad = session.exec(select(models.AvailDay).where(
            models.AvailDay.actor_plan_period_id == actor_plan_period_id,
            models.AvailDay.date == date, models.AvailDay.time_of_day_id == time_of_day_id,
            models.AvailDay.prep_delete.is_(None))).first()
        return schemas.AvailDayShow.model_validate(ad) if ad else None


def get_from__actor_pp_date(actor_plan_period_id: UUID, date: datetime.date) -> list[schemas.AvailDayShow]:
    with get_session() as session:
        ads = session.exec(select(models.AvailDay).where(
            models.AvailDay.actor_plan_period_id == actor_plan_period_id,
            models.AvailDay.date == date)).all()
        return [schemas.AvailDayShow.model_validate(ad) for ad in ads]


def get_all_from__plan_period(plan_period_id: UUID) -> list[schemas.AvailDayShow]:
    with get_session() as session:
        ads = session.exec(select(models.AvailDay).join(models.ActorPlanPeriod)
                           .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
        return [schemas.AvailDayShow.model_validate(ad) for ad in ads]


def get_all_from__actor_plan_period(actor_plan_period_id: UUID) -> list[schemas.AvailDayShow]:
    with get_session() as session:
        stmt = (select(models.AvailDay)
                .where(models.AvailDay.actor_plan_period_id == actor_plan_period_id)
                .options(*avail_day_show_options()))
        ads = session.exec(stmt).unique().all()
        return [schemas.AvailDayShow.model_validate(ad) for ad in ads]


def get_with_skills__actor_pp_date(actor_plan_period_id: UUID, date: datetime.date) -> list[schemas.AvailDayWithSkills]:
    """Lädt AvailDays eines ActorPlanPeriods an einem bestimmten Datum – nur mit Skills.

    Fallback-Variante für ButtonSkills ohne Prefetch (z.B. nach Reload einzelner Buttons).
    """
    with get_session() as session:
        stmt = (select(models.AvailDay)
                .where(models.AvailDay.actor_plan_period_id == actor_plan_period_id,
                       models.AvailDay.date == date)
                .options(selectinload(models.AvailDay.skills)))
        ads = session.exec(stmt).all()
        return [schemas.AvailDayWithSkills.model_validate(ad) for ad in ads]


def get_all_with_skills__actor_plan_period(actor_plan_period_id: UUID) -> list[schemas.AvailDayWithSkills]:
    """Lädt alle AvailDays eines ActorPlanPeriods mit nur Skills-Daten.

    Verwendet das schlanke AvailDayWithSkills-Schema statt AvailDayShow,
    um Pydantic-Validierungsoverhead für unbenötigte Nested-Schemas zu vermeiden.
    Geeignet für ButtonSkills, das ausschließlich .skills benötigt.
    """
    with get_session() as session:
        stmt = (select(models.AvailDay)
                .where(models.AvailDay.actor_plan_period_id == actor_plan_period_id)
                .options(selectinload(models.AvailDay.skills)))
        ads = session.exec(stmt).all()
        return [schemas.AvailDayWithSkills.model_validate(ad) for ad in ads]


def get_all_from__plan_period_date(plan_period_id: UUID, date: datetime.date) -> list[schemas.AvailDayShow]:
    with get_session() as session:
        ads = session.exec(select(models.AvailDay).join(models.ActorPlanPeriod)
                           .where(models.ActorPlanPeriod.plan_period_id == plan_period_id,
                                  models.AvailDay.date == date)).all()
        return [schemas.AvailDayShow.model_validate(ad) for ad in ads]


def get_all_from__plan_period__date__time_of_day__location_prefs(
        plan_period_id: UUID, date: datetime.date, time_of_day_index: int,
        location_of_work_ids: set[UUID]) -> list[schemas.AvailDayShow]:
    with get_session() as session:
        ads = session.exec(
            select(models.AvailDay).join(models.ActorPlanPeriod)
            .join(models.TimeOfDay, models.AvailDay.time_of_day_id == models.TimeOfDay.id)
            .join(models.TimeOfDayEnum)
            .where(models.ActorPlanPeriod.plan_period_id == plan_period_id,
                   models.AvailDay.date == date,
                   models.TimeOfDayEnum.time_index == time_of_day_index)
        ).all()
        filtered = []
        for ad in ads:
            dominated = True
            for loc_id in location_of_work_ids:
                blocked = any(p.location_of_work_id == loc_id and p.score == 0
                              for p in ad.actor_location_prefs_defaults)
                if not blocked:
                    dominated = False
                    break
            if not dominated:
                filtered.append(schemas.AvailDayShow.model_validate(ad))
        return filtered


def get_from__avail_day_group(avail_day_group_id) -> schemas.AvailDayShow | None:
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        return schemas.AvailDayShow.model_validate(adg.avail_day) if adg.avail_day else None


def create(avail_day: schemas.AvailDayCreate) -> schemas.AvailDayShow:
    """Erstellt AvailDay mit zugehöriger AvailDayGroup (inlined)."""
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, avail_day.actor_plan_period.id)
        master_adg = app.avail_day_group
        # AvailDayGroup erstellen (inlined)
        adg = models.AvailDayGroup(avail_day_group=master_adg)
        session.add(adg)
        session.flush()
        ad = models.AvailDay(date=avail_day.date,
                             time_of_day=session.get(models.TimeOfDay, avail_day.time_of_day.id),
                             avail_day_group=adg, actor_plan_period=app)
        session.add(ad)
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def update_time_of_day(avail_day_id: UUID, new_time_of_day_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.time_of_day = session.get(models.TimeOfDay, new_time_of_day_id)
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def update_time_of_days(avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.time_of_days.clear()
        for t in time_of_days:
            ad.time_of_days.append(session.get(models.TimeOfDay, t.id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def delete(avail_day_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        deleted = schemas.AvailDayShow.model_validate(ad)
        adg = ad.avail_day_group
        session.delete(ad)
        session.flush()
        session.delete(adg)
        return deleted


def put_in_comb_loc_possible(avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def put_in_comb_loc_possibles(avail_day_id: UUID, comb_loc_possible_ids: list[UUID]) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        for cid in comb_loc_possible_ids:
            ad.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, cid))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def remove_comb_loc_possible(avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.combination_locations_possibles.remove(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def clear_comb_loc_possibles(avail_day_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.combination_locations_possibles.clear()
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def put_in_location_pref(avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def put_in_location_prefs(avail_day_id: UUID, actor_loc_pref_ids: list[UUID]) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        for pid in actor_loc_pref_ids:
            ad.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, pid))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def remove_location_pref(avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def clear_location_prefs(avail_day_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.actor_location_prefs_defaults.clear()
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def put_in_partner_location_pref(avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def put_in_partner_location_prefs(avail_day_id: UUID, actor_partner_loc_pref_ids: list[UUID]) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        for pid in actor_partner_loc_pref_ids:
            ad.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, pid))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def remove_partner_location_pref(avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.actor_partner_location_prefs_defaults.remove(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def clear_partner_location_prefs(avail_day_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.actor_partner_location_prefs_defaults.clear()
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(actor_plan_period_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        defaults = list(app.actor_partner_location_prefs_defaults)
        for ad in app.avail_days:
            ad.actor_partner_location_prefs_defaults.clear()
            ad.actor_partner_location_prefs_defaults.extend(defaults)


def reset_all_avail_days_location_prefs_of_actor_plan_period_to_defaults(actor_plan_period_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        defaults = list(app.actor_location_prefs_defaults)
        for ad in app.avail_days:
            ad.actor_location_prefs_defaults.clear()
            ad.actor_location_prefs_defaults.extend(defaults)


def reset_all_avail_days_comb_loc_possibles_of_actor_plan_period_to_defaults(actor_plan_period_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        defaults = list(app.combination_locations_possibles)
        for ad in app.avail_days:
            ad.combination_locations_possibles.clear()
            ad.combination_locations_possibles.extend(defaults)


def add_skill(avail_day_id: UUID, skill_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.skills.append(session.get(models.Skill, skill_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def remove_skill(avail_day_id: UUID, skill_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.skills.remove(session.get(models.Skill, skill_id))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def clear_skills(avail_day_id: UUID) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        ad.skills.clear()
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def put_in_skills(avail_day_id: UUID, skill_ids: list[UUID]) -> schemas.AvailDayShow:
    log_function_info()
    with get_session() as session:
        ad = session.get(models.AvailDay, avail_day_id)
        for sid in skill_ids:
            ad.skills.append(session.get(models.Skill, sid))
        session.flush()
        return schemas.AvailDayShow.model_validate(ad)


def clear_all_skills_of_actor_plan_period(actor_plan_period_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        for ad in app.avail_days:
            ad.skills.clear()


def reset_all_skills_of_actor_plan_period_to_person_defaults(actor_plan_period_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        person_skills = list(app.person.skills)
        for ad in app.avail_days:
            ad.skills.clear()
            ad.skills.extend(person_skills)


def get_skill_ids_per_avail_day_of_actor_plan_period(actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        return {ad.id: [s.id for s in ad.skills] for ad in app.avail_days}