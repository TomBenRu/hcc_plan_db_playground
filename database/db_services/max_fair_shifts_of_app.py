"""Service-Funktionen für MaxFairShiftsOfApp (Max./faire Einsätze je ActorPlanPeriod).

Speichert für jede ActorPlanPeriod die Obergrenzen für maximale (`max_shifts`)
und faire (`fair_shifts`) Schichtzuteilungen, die der Solver zur Fairness-
Optimierung verwendet. Die minimale Abfrage (`get_all_from__plan_period_minimal`)
liefert ein kompaktes Dict für den Solver-Zugriff ohne Schema-Overhead.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get_all_from__plan_period(plan_period_id: UUID) -> list[schemas.MaxFairShiftsOfAppShow]:
    with get_session() as session:
        mfs_list = session.exec(select(models.MaxFairShiftsOfApp).join(models.ActorPlanPeriod)
                                .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
        return [schemas.MaxFairShiftsOfAppShow.model_validate(m) for m in mfs_list]


def get_all_from__plan_period_minimal(plan_period_id: UUID) -> dict[UUID, tuple[int, int]]:
    with get_session() as session:
        mfs_list = session.exec(select(models.MaxFairShiftsOfApp).join(models.ActorPlanPeriod)
                                .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
        return {m.actor_plan_period_id: (m.max_shifts, m.fair_shifts) for m in mfs_list}


def get_by_actor_plan_period_ids(actor_plan_period_ids: list[UUID]) -> dict[UUID, tuple[int, int]]:
    """Lädt MaxFairShifts direkt per ID-Liste — kein JOIN, keine Pydantic-Validierung.

    Schneller als get_all_from__plan_period_minimal() wenn die actor_plan_period_ids
    bereits bekannt sind (kein JOIN über ActorPlanPeriod nötig).
    """
    if not actor_plan_period_ids:
        return {}
    with get_session() as session:
        mfs_list = session.exec(
            select(models.MaxFairShiftsOfApp)
            .where(models.MaxFairShiftsOfApp.actor_plan_period_id.in_(actor_plan_period_ids))
        ).all()
        return {m.actor_plan_period_id: (m.max_shifts, m.fair_shifts) for m in mfs_list}


def create(max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppCreate) -> schemas.MaxFairShiftsOfAppShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(max_shifts=max_fair_shifts_per_app.max_shifts,
                      fair_shifts=max_fair_shifts_per_app.fair_shifts,
                      actor_plan_period=session.get(models.ActorPlanPeriod, max_fair_shifts_per_app.actor_plan_period_id))
        if max_fair_shifts_per_app.id:
            kwargs['id'] = max_fair_shifts_per_app.id
        mfs = models.MaxFairShiftsOfApp(**kwargs)
        session.add(mfs)
        session.flush()
        return schemas.MaxFairShiftsOfAppShow.model_validate(mfs)


def delete(max_fair_shifts_per_app_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.MaxFairShiftsOfApp, max_fair_shifts_per_app_id))