"""Service-Funktionen für LocationPlanPeriod (Standort-Planperiode).

Verknüpft einen Arbeitsort mit einer PlanPeriod und übernimmt standortspezifische
Konfigurationen wie Tageszeiten, Tageszeit-Standards, Besetzungsvorgaben
(fixed_cast) und die Anzahl benötigter Akteure. Hartes Löschen ohne Soft-Delete,
da LocationPlanPeriod den Lebenszyklus ihrer Events bestimmt.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import joinedload, selectinload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import (location_plan_period_show_options, location_mask_lpp_options,
                             location_plan_period_for_dialog_options)


def get(location_plan_period_id: UUID) -> schemas.LocationPlanPeriodShow:
    with get_session() as session:
        stmt = (select(models.LocationPlanPeriod)
                .where(models.LocationPlanPeriod.id == location_plan_period_id)
                .options(*location_plan_period_show_options()))
        lpp = session.exec(stmt).unique().one()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def get_for_dialog(location_plan_period_id: UUID) -> schemas.LocationPlanPeriodForDialog:
    """Minimaler LPP-Load für reload_object_with_groups im EventGroup-Dialog.

    Lädt nur id + team.id (via plan_period → team) — kein events, time_of_days,
    location_of_work, project. Ersetzt get() in reload_object_with_groups.
    """
    with get_session() as session:
        stmt = (select(models.LocationPlanPeriod)
                .where(models.LocationPlanPeriod.id == location_plan_period_id)
                .options(*location_plan_period_for_dialog_options()))
        lpp = session.exec(stmt).unique().one()
        return schemas.LocationPlanPeriodForDialog.model_validate(lpp)


def get_multiple(location_plan_period_ids: list[UUID]) -> list[schemas.LocationPlanPeriodShow]:
    """Lädt mehrere LocationPlanPeriodShow-Objekte in einer Batch-Abfrage.

    Ersetzt N einzelne get()-Roundtrips durch einen einzigen IN-Query mit
    vollständigem Eager Loading — für das Startup-Vorladen aller aktiven Standorte.
    """
    if not location_plan_period_ids:
        return []
    with get_session() as session:
        stmt = (select(models.LocationPlanPeriod)
                .where(models.LocationPlanPeriod.id.in_(location_plan_period_ids))
                .options(*location_plan_period_show_options()))
        lpps = session.exec(stmt).unique().all()
        return [schemas.LocationPlanPeriodShow.model_validate(lpp) for lpp in lpps]


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
        tod = session.get(models.TimeOfDay, time_of_day_id)
        if tod in lpp.time_of_days:
            lpp.time_of_days.remove(tod)
            session.flush()
        return schemas.LocationPlanPeriodShow.model_validate(lpp)


def remove_time_of_day_standard(location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
    log_function_info()
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        tod = session.get(models.TimeOfDay, time_of_day_id)
        if tod in lpp.time_of_day_standards:
            lpp.time_of_day_standards.remove(tod)
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


def get_location_mask_data(plan_period_id: UUID) -> schemas.LocationMaskData:
    """Lädt alle Anzeigedaten der Standort-Maske in einer einzigen Session mit 7 Queries.

    Query-Struktur:
      Q3  (1+3): LPPs + team + TLAs (selectinload) + time_of_days + tod_standards
      Q4  (1):   CastGroups mit joinedload(event)
      Q5  (1):   Events mit joinedload(skill_groups → skill)
      Q6  (1):   LocationOfWork mit joinedload(skill_groups → skill)
    Q1 (PlanPeriod) und Q2 (TeamLocationAssigns separat) sind eliminiert:
      - pp_start/pp_end aus lpps[0].plan_period (Q3 lädt plan_period via joinedload)
      - TLAs aus lpps[0].plan_period.team.team_location_assigns (Q3 selectinload-Kette)
    """
    with get_session() as session:
        # Q3 (1 Haupt-Query + 3 selectinloads): LPPs + team + TLAs + time_of_days + tod_standards
        lpps = session.exec(
            select(models.LocationPlanPeriod)
            .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)
            .options(*location_mask_lpp_options())
        ).unique().all()

        # PlanPeriod-Daten aus Q3-Ergebnissen ableiten (kein separater Q1-Query)
        if lpps:
            pp_start = lpps[0].plan_period.start
            pp_end = lpps[0].plan_period.end
            tla_models = lpps[0].plan_period.team.team_location_assigns
        else:
            # Fallback für leere PlanPeriods (sehr ungewöhnlich)
            pp = session.get(models.PlanPeriod, plan_period_id)
            pp_start = pp.start
            pp_end = pp.end
            tla_models = []

        # Q4: CastGroups für Buttons (joinedload event — 1:1-Beziehung)
        cast_groups = session.exec(
            select(models.CastGroup)
            .where(models.CastGroup.plan_period_id == plan_period_id)
            .options(joinedload(models.CastGroup.event))
        ).all()

        # Q5: Events mit time_of_day + skill_groups — kein separater Round-Trip
        events = session.exec(
            select(models.Event)
            .join(models.LocationPlanPeriod)
            .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)
            .options(
                joinedload(models.Event.time_of_day)
                .joinedload(models.TimeOfDay.time_of_day_enum),
                joinedload(models.Event.skill_groups)
                .joinedload(models.SkillGroup.skill),
            )
        ).unique().all()

        # Q6: LocationOfWork-SkillGroups mit joinedload — kein separater selectinload-Roundtrip
        lows = session.exec(
            select(models.LocationOfWork)
            .join(models.LocationPlanPeriod,
                  models.LocationPlanPeriod.location_of_work_id == models.LocationOfWork.id)
            .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)
            .options(
                joinedload(models.LocationOfWork.skill_groups)
                .joinedload(models.SkillGroup.skill)
            )
        ).unique().all()

        # Events nach LPP gruppieren
        lpp_id__events: dict[UUID, list[schemas.EventForButton]] = {}
        for e in events:
            lpp_id__events.setdefault(e.location_plan_period_id, []).append(
                schemas.EventForButton.model_validate(e))

        return schemas.LocationMaskData(
            plan_period_id=plan_period_id,
            plan_period_start=pp_start,
            plan_period_end=pp_end,
            location_plan_periods=[schemas.LocationPlanPeriod.model_validate(lpp) for lpp in lpps],
            loc_id__location_pp_for_mask={
                str(lpp.location_of_work.id): schemas.LocationPlanPeriodForMask.model_validate(lpp)
                for lpp in lpps
            },
            team_location_assigns=[schemas.TeamLocationAssignForMask.model_validate(tla) for tla in tla_models],
            cast_groups_of_pp=[schemas.CastGroupForButton.model_validate(cg) for cg in cast_groups],
            lpp_id__events_for_buttons=lpp_id__events,
            location_id__skill_groups={
                low.id: [schemas.SkillGroup.model_validate(sg) for sg in low.skill_groups]
                for low in lows
            },
        )