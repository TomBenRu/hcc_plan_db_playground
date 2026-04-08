"""Service-Funktionen für AvailDay (Verfügbarkeitstag eines Akteurs).

Speichert, an welchem Datum und zu welcher Tageszeit ein Akteur verfügbar ist.
Enthält umfangreiche Hilfsfunktionen zum Verwalten von Standortpräferenzen,
Partner-Präferenzen, Standortkombinationen und Skills auf Tagesbasis.
Das Löschen eines AvailDay löscht automatisch auch die zugehörige AvailDayGroup.
Bietet außerdem batch-optimierte Abfragen für den Solver.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import avail_day_show_options
from .combination_locations_possible import is_comb_loc_orphaned


def get(avail_day_id: UUID) -> schemas.AvailDayShow:
    with get_session() as session:
        return schemas.AvailDayShow.model_validate(session.get(models.AvailDay, avail_day_id))


def get_batch(avail_day_ids: list[UUID]) -> dict[UUID, schemas.AvailDayShow]:
    if not avail_day_ids:
        return {}
    with get_session() as session:
        stmt = (select(models.AvailDay)
                .where(models.AvailDay.id.in_(avail_day_ids))
                .options(*avail_day_show_options()))
        ads = session.exec(stmt).unique().all()
        return {ad.id: schemas.AvailDayShow.model_validate(ad) for ad in ads}


def get_batch_minimal(avail_day_ids: list[UUID]) -> dict[UUID, schemas.AvailDaySolverMinimal]:
    """Lädt AvailDays als AvailDaySolverMinimal in einer Batch-Abfrage mit Eager-Loading.

    Eager-Loading deckt alle Chains ab, die AvailDaySolverMinimal.model_validate() traversiert:
    - time_of_day → time_of_day_enum
    - actor_plan_period → person
    - skills
    - actor_location_prefs_defaults → location_of_work
    - actor_partner_location_prefs_defaults → partner (person) + location_of_work
    - combination_locations_possibles → locations_of_work
    """
    if not avail_day_ids:
        return {}
    from sqlalchemy.orm import joinedload
    with get_session() as session:
        stmt = (select(models.AvailDay)
                .where(models.AvailDay.id.in_(avail_day_ids))
                .options(
                    joinedload(models.AvailDay.time_of_day)
                    .joinedload(models.TimeOfDay.time_of_day_enum),
                    joinedload(models.AvailDay.actor_plan_period)
                    .joinedload(models.ActorPlanPeriod.person),
                    selectinload(models.AvailDay.skills),
                    selectinload(models.AvailDay.actor_location_prefs_defaults)
                    .joinedload(models.ActorLocationPref.location_of_work),
                    selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
                    .joinedload(models.ActorPartnerLocationPref.partner),
                    selectinload(models.AvailDay.actor_partner_location_prefs_defaults)
                    .joinedload(models.ActorPartnerLocationPref.location_of_work),
                    selectinload(models.AvailDay.combination_locations_possibles)
                    .selectinload(models.CombinationLocationsPossible.locations_of_work),
                ))
        ads = session.exec(stmt).unique().all()
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


def get_avail_days_skills__plan_period(plan_period_id: UUID) -> dict[UUID, list[schemas.AvailDayWithSkills]]:
    """Lädt Skills aller AvailDays einer gesamten PlanPeriode in einem Batch-Query.

    Ersetzt N einzelne get_all_with_skills__actor_plan_period()-Calls (je ~161ms) durch
    zwei Queries: einen IN-Query für ActorPlanPeriod-IDs und einen für AvailDays+Skills.
    Rückgabe: dict[actor_plan_period_id → list[AvailDayWithSkills]]
    """
    with get_session() as session:
        app_ids = session.exec(
            select(models.ActorPlanPeriod.id).where(
                models.ActorPlanPeriod.plan_period_id == plan_period_id
            )
        ).all()
        if not app_ids:
            return {}
        stmt = (select(models.AvailDay)
                .where(models.AvailDay.actor_plan_period_id.in_(app_ids))
                .options(selectinload(models.AvailDay.skills)))
        avail_days = session.exec(stmt).all()
        result: dict[UUID, list[schemas.AvailDayWithSkills]] = {aid: [] for aid in app_ids}
        for ad in avail_days:
            result[ad.actor_plan_period_id].append(schemas.AvailDayWithSkills.model_validate(ad))
        return result


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
            .options(*avail_day_show_options())
        ).unique().all()
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


def get_for_edit_appointment_combo(
        plan_period_id: UUID, date: datetime.date, time_of_day_index: int,
        location_of_work_ids: set[UUID]) -> list[schemas.AvailDayForEditCombo]:
    """Schlanke Variante für DlgEditAppointment: lädt nur id + Personname.

    Gleiche Filterlogik wie get_all_from__plan_period__date__time_of_day__location_prefs,
    aber mit minimalem Eager-Loading (nur actor_plan_period → person + loc_prefs für Filter).
    Spart ~95 % gegenüber AvailDayShow.model_validate().
    """
    with get_session() as session:
        ads = session.exec(
            select(models.AvailDay).join(models.ActorPlanPeriod)
            .join(models.TimeOfDay, models.AvailDay.time_of_day_id == models.TimeOfDay.id)
            .join(models.TimeOfDayEnum)
            .where(models.ActorPlanPeriod.plan_period_id == plan_period_id,
                   models.AvailDay.date == date,
                   models.TimeOfDayEnum.time_index == time_of_day_index)
            .options(
                selectinload(models.AvailDay.actor_location_prefs_defaults),
                joinedload(models.AvailDay.actor_plan_period)
                .joinedload(models.ActorPlanPeriod.person),
            )
        ).unique().all()
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
                filtered.append(schemas.AvailDayForEditCombo.model_validate(ad))
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


def replace_comb_loc_possibles_for_avail_days(
        avail_day_ids: list[UUID],
        person_id: UUID,
        original_ids: set[UUID],
        pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict:
    """Ersetzt CombLocPossibles für alle AvailDays an einem Tag in einer einzigen Session.

    avail_day_ids[0] ist der primäre AvailDay (aus dem Dialog).
    Alle AvailDays erhalten danach dieselben CLPs.
    Wiederverwendungslogik: Existiert in der Person bereits eine CombLocPossible mit
    gleichem locations_of_work-ID-Set und time_span_between, wird sie übernommen.
    Verwaiste CLPs werden soft-deleted.

    Returns: {'old_comb_ids_per_avail_day': {avd_id: [...]}, 'new_comb_ids': [...]}
    """
    log_function_info()
    with get_session() as session:
        # Person-CLPs laden für Wiederverwendungs-Check
        person_clps = session.exec(
            select(models.CombinationLocationsPossible)
            .join(models.PersonCombLocLink,
                  models.PersonCombLocLink.combination_locations_possible_id
                  == models.CombinationLocationsPossible.id)
            .where(models.PersonCombLocLink.person_id == person_id)
            .where(models.CombinationLocationsPossible.prep_delete.is_(None))
            .options(selectinload(models.CombinationLocationsPossible.locations_of_work))
        ).all()
        person_clp_index: dict[tuple, models.CombinationLocationsPossible] = {
            (frozenset(loc.id for loc in clp.locations_of_work), clp.time_span_between): clp
            for clp in person_clps
        }

        # Temp-UUID → echte UUID auflösen
        temp_to_real: dict[UUID, UUID] = {}
        for temp_id, create_schema in pending_creates:
            loc_ids = frozenset(loc.id for loc in create_schema.locations_of_work)
            key = (loc_ids, create_schema.time_span_between)
            if key in person_clp_index:
                temp_to_real[temp_id] = person_clp_index[key].id
            else:
                new_clp = models.CombinationLocationsPossible(
                    project=session.get(models.Project, create_schema.project.id),
                    time_span_between=create_schema.time_span_between)
                session.add(new_clp)
                session.flush()
                for loc in create_schema.locations_of_work:
                    new_clp.locations_of_work.append(session.get(models.LocationOfWork, loc.id))
                session.flush()
                temp_to_real[temp_id] = new_clp.id

        # Finale echte CLPs ermitteln
        final_ids = list({temp_to_real.get(c.id, c.id) for c in current_combs})
        final_clps = [session.get(models.CombinationLocationsPossible, clp_id) for clp_id in final_ids]

        # Alten Zustand pro AvailDay speichern, neuen Zustand setzen
        old_comb_ids_per_avail_day: dict[UUID, list[UUID]] = {}
        all_old_ids: set[UUID] = set()
        for avd_id in avail_day_ids:
            avd = session.get(models.AvailDay, avd_id)
            old_comb_ids_per_avail_day[avd_id] = [c.id for c in avd.combination_locations_possibles]
            all_old_ids.update(c.id for c in avd.combination_locations_possibles)
            avd.combination_locations_possibles = list(final_clps)
        session.flush()

        # Verwaiste CLPs soft-deleten
        now = _utcnow()
        final_ids_set = set(final_ids)
        for removed_id in all_old_ids - final_ids_set:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()

        return {
            'old_comb_ids_per_avail_day': old_comb_ids_per_avail_day,
            'new_comb_ids': final_ids,
        }


def restore_comb_loc_possibles_for_avail_days(
        target_ids_per_avail_day: dict[UUID, list[UUID]],
) -> None:
    """Undo/Redo-Gegenstück zu replace_comb_loc_possibles_for_avail_days.

    Stellt pro AvailDay den übergebenen Zielzustand wieder her.
    Reaktiviert soft-gelöschte CLPs und bereinigt neu entstandene Waisen.
    """
    log_function_info()
    with get_session() as session:
        # Aktuellen Zustand erfassen (für Orphan-Cleanup)
        current_ids: set[UUID] = set()
        for avd_id in target_ids_per_avail_day:
            avd = session.get(models.AvailDay, avd_id)
            if avd:
                current_ids.update(c.id for c in avd.combination_locations_possibles)

        # Zielzustand herstellen
        all_target_ids: set[UUID] = set()
        for avd_id, comb_ids in target_ids_per_avail_day.items():
            avd = session.get(models.AvailDay, avd_id)
            if avd:
                restore_clps = []
                for clp_id in comb_ids:
                    clp = session.get(models.CombinationLocationsPossible, clp_id)
                    if clp:
                        clp.prep_delete = None
                        restore_clps.append(clp)
                        all_target_ids.add(clp_id)
                avd.combination_locations_possibles = restore_clps
        session.flush()

        # Verwaiste CLPs soft-deleten
        now = _utcnow()
        for removed_id in current_ids - all_target_ids:
            clp = session.get(models.CombinationLocationsPossible, removed_id)
            if clp and not clp.prep_delete and is_comb_loc_orphaned(session, removed_id):
                clp.prep_delete = now
        session.flush()


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


def replace_location_prefs_for_avail_days(
        avail_day_ids: list[UUID],
        person_id: UUID,
        project_id: UUID,
        location_id_to_score: dict[UUID, float],
) -> dict:
    """Ersetzt Location-Prefs für alle AvailDays an einem Tag in einer einzigen Session.

    Analog zu ActorPlanPeriod.update_location_prefs_bulk, aber für mehrere AvailDays.
    avail_day_ids[0] ist der primäre AvailDay (aus dem Dialog), alle anderen werden synchronisiert.
    Wiederverwendungslogik: Existiert eine Person-Pref mit gleicher Location und
    gleichem Score, wird sie verknüpft statt neu angelegt.
    Verwaiste Prefs werden am Ende bereinigt.

    Returns: {'old_pref_ids_per_avail_day': {avd_id: [...]}, 'new_pref_ids': [...]}
    """
    log_function_info()
    with get_session() as session:
        existing_person_prefs = session.exec(
            select(models.ActorLocationPref)
            .where(models.ActorLocationPref.person_id == person_id)
            .where(models.ActorLocationPref.prep_delete == None)
        ).all()
        person_pref_index: dict[tuple[UUID, float], models.ActorLocationPref] = {
            (p.location_of_work_id, p.score): p for p in existing_person_prefs
        }

        new_prefs: list[models.ActorLocationPref] = []
        for loc_id, score in location_id_to_score.items():
            if score == 1.0:
                continue
            key = (loc_id, score)
            if key in person_pref_index:
                new_prefs.append(person_pref_index[key])
            else:
                new_pref = models.ActorLocationPref(
                    score=score,
                    project_id=project_id,
                    person_id=person_id,
                    location_of_work_id=loc_id,
                )
                session.add(new_pref)
                session.flush()
                new_prefs.append(new_pref)

        new_pref_ids = [p.id for p in new_prefs]

        old_pref_ids_per_avail_day: dict[UUID, list[UUID]] = {}
        all_old_ids: set[UUID] = set()
        for avd_id in avail_day_ids:
            avd = session.get(models.AvailDay, avd_id)
            old_pref_ids_per_avail_day[avd_id] = [p.id for p in avd.actor_location_prefs_defaults]
            all_old_ids.update(p.id for p in avd.actor_location_prefs_defaults)
            avd.actor_location_prefs_defaults = list(new_prefs)
        session.flush()

        now = _utcnow()
        new_pref_ids_set = set(new_pref_ids)
        for removed_id in all_old_ids - new_pref_ids_set:
            pref = session.get(models.ActorLocationPref, removed_id)
            if (pref and not pref.prep_delete
                    and not pref.actor_plan_periods_defaults
                    and not pref.avail_days_defaults
                    and not pref.person_default):
                pref.prep_delete = now
        session.flush()

        return {
            'old_pref_ids_per_avail_day': old_pref_ids_per_avail_day,
            'new_pref_ids': new_pref_ids,
        }


def restore_location_prefs_for_avail_days(
        target_ids_per_avail_day: dict[UUID, list[UUID]],
) -> None:
    """Undo/Redo-Gegenstück zu replace_location_prefs_for_avail_days.

    Stellt pro AvailDay den übergebenen Zielzustand wieder her.
    Reaktiviert soft-gelöschte Prefs und bereinigt neu entstandene Waisen.
    """
    log_function_info()
    with get_session() as session:
        current_ids: set[UUID] = set()
        for avd_id in target_ids_per_avail_day:
            avd = session.get(models.AvailDay, avd_id)
            if avd:
                current_ids.update(p.id for p in avd.actor_location_prefs_defaults)

        all_target_ids: set[UUID] = set()
        for avd_id, pref_ids in target_ids_per_avail_day.items():
            avd = session.get(models.AvailDay, avd_id)
            if avd:
                restore_prefs = []
                for pref_id in pref_ids:
                    pref = session.get(models.ActorLocationPref, pref_id)
                    if pref:
                        pref.prep_delete = None
                        restore_prefs.append(pref)
                        all_target_ids.add(pref_id)
                avd.actor_location_prefs_defaults = restore_prefs
        session.flush()

        now = _utcnow()
        for removed_id in current_ids - all_target_ids:
            pref = session.get(models.ActorLocationPref, removed_id)
            if (pref and not pref.prep_delete
                    and not pref.actor_plan_periods_defaults
                    and not pref.avail_days_defaults
                    and not pref.person_default):
                pref.prep_delete = now
        session.flush()


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