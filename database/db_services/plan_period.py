import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(plan_period_id: UUID) -> schemas.PlanPeriodShow:
    with get_session() as session:
        return schemas.PlanPeriodShow.model_validate(session.get(models.PlanPeriod, plan_period_id))


def get_all_from__project(project_id: UUID) -> list[schemas.PlanPeriodShow]:
    with get_session() as session:
        pps = session.exec(select(models.PlanPeriod).join(models.Team)
                           .where(models.Team.project_id == project_id)).all()
        return [schemas.PlanPeriodShow.model_validate(p) for p in pps]


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