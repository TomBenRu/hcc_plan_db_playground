"""Service-Funktionen für PlanPeriod (Planungszeitraum).

Eine PlanPeriod definiert den Zeitraum (Start, Ende, Deadline), für den ein
Team geplant wird. Bei einer Datumsänderung (`update`) werden automatisch alle
AvailDays und Events außerhalb des neuen Zeitraums soft-gelöscht.
`delete_prep_deletes` entfernt endgültig alle als gelöscht markierten Perioden
eines Teams.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import joinedload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import plan_period_show_options, plan_period_actor_tab_options


def get(plan_period_id: UUID, minimal: bool = False) -> schemas.PlanPeriodShow | schemas.PlanPeriod:
    """Lädt eine PlanPeriod.

    minimal=True gibt schemas.PlanPeriod (id, start, end, team) zurück ohne
    actor_plan_periods, location_plan_periods und cast_groups — für Aufrufer,
    die nur Datum und ID benötigen (~120ms statt ~490ms).
    """
    with get_session() as session:
        if minimal:
            stmt = (select(models.PlanPeriod)
                    .where(models.PlanPeriod.id == plan_period_id)
                    .options(
                        joinedload(models.PlanPeriod.team).joinedload(models.Team.project),
                        joinedload(models.PlanPeriod.team).joinedload(models.Team.dispatcher),
                        joinedload(models.PlanPeriod.team).joinedload(models.Team.excel_export_settings),
                    ))
            pp = session.exec(stmt).unique().one()
            return schemas.PlanPeriod.model_validate(pp)
        stmt = (select(models.PlanPeriod)
                .where(models.PlanPeriod.id == plan_period_id)
                .options(*plan_period_show_options()))
        pp = session.exec(stmt).unique().one()
        return schemas.PlanPeriodShow.model_validate(pp)


def get_for_actor_tab(plan_period_id: UUID) -> schemas.PlanPeriodForActorTab:
    """Lädt PlanPeriod für FrmTabActorPlanPeriods — ohne location_plan_periods, cast_groups, project.

    Spart ~600ms gegenüber get() mit vollem PlanPeriodShow, da die schweren
    location_plan_periods- und cast_groups-Chains nicht geladen werden.
    """
    with get_session() as session:
        stmt = (select(models.PlanPeriod)
                .where(models.PlanPeriod.id == plan_period_id)
                .options(*plan_period_actor_tab_options()))
        pp = session.exec(stmt).unique().one()
        return schemas.PlanPeriodForActorTab.model_validate(pp)


def get_lpp_and_app_ids(plan_period_id: UUID) -> tuple[list[UUID], list[UUID]]:
    """Lädt ausschließlich die LocationPlanPeriod- und ActorPlanPeriod-ID-Listen.

    Ersetzt 2× PlanPeriod.get() (je ~700ms mit vollem Eager-Loading) durch
    2 einfache SELECT-Queries (~10ms gesamt). Verwendet kein model_validate.
    Für den Solver-Tree-Aufbau, der nur die IDs benötigt.

    Returns:
        (lpp_ids, app_ids)
    """
    with get_session() as session:
        lpp_ids = session.exec(
            select(models.LocationPlanPeriod.id)
            .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)
        ).all()
        app_ids = session.exec(
            select(models.ActorPlanPeriod.id)
            .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
        ).all()
    return list(lpp_ids), list(app_ids)


def exists_any_from__project(project_id: UUID) -> bool:
    """Gibt True zurück, wenn das Projekt mindestens einen Planungszeitraum hat (kein model_validate)."""
    with get_session() as session:
        stmt = (select(models.PlanPeriod)
                .join(models.Team)
                .where(models.Team.project_id == project_id)
                .limit(1))
        return session.exec(stmt).first() is not None


def get_all_from__project(project_id: UUID) -> list[schemas.PlanPeriod]:
    """Gibt alle PlanPeriod-Basis-Objekte eines Projekts zurück.

    Verwendet bewusst das Basis-Schema (nicht PlanPeriodShow), da Aufrufer
    nur id, start, end, prep_delete und team benötigen — kein Deep-Loading
    von actor_plan_periods, location_plan_periods oder cast_groups.
    """
    with get_session() as session:
        stmt = (select(models.PlanPeriod)
                .join(models.Team)
                .where(models.Team.project_id == project_id)
                .options(
                    joinedload(models.PlanPeriod.team).joinedload(models.Team.project),
                    joinedload(models.PlanPeriod.team).joinedload(models.Team.dispatcher),
                    joinedload(models.PlanPeriod.team).joinedload(models.Team.excel_export_settings),
                ))
        pps = session.exec(stmt).unique().all()
        return [schemas.PlanPeriod.model_validate(p) for p in pps]


def get_all_from__team(team_id: UUID) -> list[schemas.PlanPeriodShow]:
    with get_session() as session:
        pps = session.exec(select(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)).all()
        return [schemas.PlanPeriodShow.model_validate(p) for p in pps]


def get_all_from__team_minimal(team_id: UUID) -> list[schemas.PlanPeriodMinimal]:
    with get_session() as session:
        pps = session.exec(select(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)).all()
        return [schemas.PlanPeriodMinimal.model_validate(p) for p in pps]


def create(plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
    log_function_info()
    with get_session() as session:
        pp = models.PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                               notes=plan_period.notes, notes_for_employees=plan_period.notes_for_employees,
                               team=session.get(models.Team, plan_period.team.id))
        session.add(pp)
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def update(plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period.id)
        pp.start = plan_period.start
        pp.end = plan_period.end
        pp.deadline = plan_period.deadline
        pp.notes = plan_period.notes
        pp.notes_for_employees = plan_period.notes_for_employees
        pp.remainder = plan_period.remainder
        for app in pp.actor_plan_periods:
            for ad in app.avail_days:
                if not (plan_period.start <= ad.date <= plan_period.end) and not ad.prep_delete:
                    ad.prep_delete = _utcnow()
        for lpp in pp.location_plan_periods:
            for event in lpp.events:
                if not (plan_period.start <= event.date <= plan_period.end) and not event.prep_delete:
                    event.prep_delete = _utcnow()
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def update_notes(plan_period_id: UUID, notes: str) -> schemas.PlanPeriodShow:
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        pp.notes = notes
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def delete(plan_period_id: UUID) -> schemas.PlanPeriodShow:
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        pp.prep_delete = _utcnow()
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def undelete(plan_period_id: UUID):
    log_function_info()
    with get_session() as session:
        pp = session.get(models.PlanPeriod, plan_period_id)
        pp.prep_delete = None
        session.flush()
        return schemas.PlanPeriodShow.model_validate(pp)


def delete_prep_deletes(team_id: UUID):
    with get_session() as session:
        pps = session.exec(select(models.PlanPeriod).where(
            models.PlanPeriod.team_id == team_id, models.PlanPeriod.prep_delete.isnot(None))).all()
        for pp in pps:
            session.delete(pp)