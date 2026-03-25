"""Service-Funktionen für ActorPlanPeriod (Akteur-Planperiode).

Verknüpft eine Person mit einer PlanPeriod und speichert deren individuelle
Einstellungen wie gewünschte Einsätze, Tageszeiten, Standortpräferenzen und
Standortkombinationen. Enthält auch eine speziell optimierte Abfrage für den
Solver (`get_all_for_solver`).
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import actor_plan_period_show_options, actor_plan_period_mask_options


def get_multiple(actor_plan_period_ids: list[UUID]) -> list[schemas.ActorPlanPeriodShow]:
    """Lädt mehrere ActorPlanPeriodShow-Objekte in einer Batch-Abfrage.

    Effizient für das Vorabladen mehrerer aktiver ActorPlanPeriods — spart
    N einzelne get()-Roundtrips durch einen einzigen IN-Query.
    """
    if not actor_plan_period_ids:
        return []
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id.in_(actor_plan_period_ids))
                .options(*actor_plan_period_show_options()))
        apps = session.exec(stmt).unique().all()
        return [schemas.ActorPlanPeriodShow.model_validate(a) for a in apps]


def get(actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodShow:
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id == actor_plan_period_id)
                .options(*actor_plan_period_show_options()))
        app = session.exec(stmt).unique().one()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def get_multiple_for_mask(actor_plan_period_ids: list[UUID]) -> list[schemas.ActorPlanPeriodForMask]:
    """Lädt mehrere ActorPlanPeriodForMask-Objekte in einer Batch-Abfrage.

    Für Hintergrund-Vorladen aller Akteure einer Planperiode — spart N einzelne
    get_for_mask()-Roundtrips durch einen einzigen IN-Query.
    """
    if not actor_plan_period_ids:
        return []
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id.in_(actor_plan_period_ids))
                .options(*actor_plan_period_mask_options()))
        apps = session.exec(stmt).unique().all()
        return [schemas.ActorPlanPeriodForMask.model_validate(a) for a in apps]


def get_for_mask(actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodForMask:
    """Lädt ActorPlanPeriodForMask für die Masken-Anzeige.

    Verwendet actor_plan_period_mask_options() statt actor_plan_period_show_options().
    Reduziert SQL-Queries von ~20 auf ~10 pro Aktor-Laden.
    """
    with get_session() as session:
        stmt = (select(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.id == actor_plan_period_id)
                .options(*actor_plan_period_mask_options()))
        app = session.exec(stmt).unique().one()
        return schemas.ActorPlanPeriodForMask.model_validate(app)


def get_all_from__plan_period(plan_period_id: UUID, maximal: bool = False) -> list[schemas.ActorPlanPeriod | schemas.ActorPlanPeriodShow]:
    with get_session() as session:
        if maximal:
            stmt = (select(models.ActorPlanPeriod)
                    .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
                    .options(*actor_plan_period_show_options()))
            apps = session.exec(stmt).unique().all()
            return [schemas.ActorPlanPeriodShow.model_validate(a) for a in apps]
        apps = session.exec(select(models.ActorPlanPeriod).where(
            models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
        return [schemas.ActorPlanPeriod.model_validate(a) for a in apps]


def get_all_for_solver(plan_period_id: UUID) -> dict[UUID, schemas.ActorPlanPeriodSolver]:
    with get_session() as session:
        apps = list(session.exec(select(models.ActorPlanPeriod).where(
            models.ActorPlanPeriod.plan_period_id == plan_period_id)).all())
        if not apps:
            return {}
        app_ids = [a.id for a in apps]
        avail_days = session.exec(select(models.AvailDay).where(
            models.AvailDay.actor_plan_period_id.in_(app_ids))).all()
        adg_by_app: dict[UUID, list[UUID]] = {aid: [] for aid in app_ids}
        for ad in avail_days:
            adg_by_app[ad.actor_plan_period_id].append(ad.avail_day_group_id)
        return {
            a.id: schemas.ActorPlanPeriodSolver(
                id=a.id, requested_assignments=a.requested_assignments,
                required_assignments=a.required_assignments,
                person=schemas.PersonSolver(id=a.person.id, f_name=a.person.f_name, l_name=a.person.l_name),
                plan_period=schemas.PlanPeriodSolver(id=a.plan_period.id, start=a.plan_period.start, end=a.plan_period.end),
                avail_day_group_ids=adg_by_app[a.id])
            for a in apps}


def create(plan_period_id: UUID, person_id: UUID,
           actor_plan_period_id: UUID = None) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(plan_period=session.get(models.PlanPeriod, plan_period_id),
                      person=session.get(models.Person, person_id))
        if actor_plan_period_id:
            kwargs['id'] = actor_plan_period_id
        app = models.ActorPlanPeriod(**kwargs)
        session.add(app)
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def delete(actor_plan_period_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.ActorPlanPeriod, actor_plan_period_id))


def update(actor_plan_period: schemas.ActorPlanPeriodShow) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period.id)
        app.time_of_days.clear()
        for t in actor_plan_period.time_of_days:
            app.time_of_days.append(session.get(models.TimeOfDay, t.id))
        for k, v in actor_plan_period.model_dump(include={'notes', 'requested_assignments'}).items():
            setattr(app, k, v)
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def update_notes(actor_plan_period: schemas.ActorPlanPeriodUpdateNotes) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period.id)
        app.notes = actor_plan_period.notes
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def update_requested_assignments(actor_plan_period_id: UUID,
                                 requested_assignments: int, required_assignments: bool) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.requested_assignments = requested_assignments
        app.required_assignments = required_assignments
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def put_in_time_of_day(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_in_time_of_day(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_time_of_day_standard(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def new_time_of_day_standard(actor_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ActorPlanPeriodShow, UUID | None]:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        tod = session.get(models.TimeOfDay, time_of_day_id)
        old_id = None
        for t in list(app.time_of_day_standards):
            if t.time_of_day_enum.id == tod.time_of_day_enum.id:
                app.time_of_day_standards.remove(t)
                old_id = t.id
                break
        app.time_of_day_standards.append(tod)
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app), old_id


def put_in_comb_loc_possible(actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_comb_loc_possible(actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.combination_locations_possibles.remove(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def put_in_location_pref(actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_location_pref(actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def put_in_partner_location_pref(actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)


def remove_partner_location_pref(actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        app.actor_partner_location_prefs_defaults.remove(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
        session.flush()
        return schemas.ActorPlanPeriodShow.model_validate(app)