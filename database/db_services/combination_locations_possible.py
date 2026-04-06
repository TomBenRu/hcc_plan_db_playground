"""Service-Funktionen für CombinationLocationsPossible (mögliche Standortkombination).

Definiert, welche Kombination aus mehreren Arbeitsorten an einem Tag für einen
Akteur zulässig ist und welche Zeitspanne zwischen den Einsätzen eingehalten
werden muss. Unterstützt Soft-Delete. Abfrage aller Kombinations-IDs je
AvailDay für eine ActorPlanPeriod per Hilfsfunktion.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def create(comb_loc_poss: schemas.CombinationLocationsPossibleCreate) -> schemas.CombinationLocationsPossibleShow:
    log_function_info()
    with get_session() as session:
        obj = models.CombinationLocationsPossible(
            project=session.get(models.Project, comb_loc_poss.project.id),
            time_span_between=comb_loc_poss.time_span_between)
        session.add(obj)
        session.flush()
        for loc in comb_loc_poss.locations_of_work:
            obj.locations_of_work.append(session.get(models.LocationOfWork, loc.id))
        session.flush()
        return schemas.CombinationLocationsPossibleShow.model_validate(obj)


def delete(comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.CombinationLocationsPossible, comb_loc_poss_id)
        obj.prep_delete = _utcnow()
        session.flush()
        return schemas.CombinationLocationsPossibleShow.model_validate(obj)


def undelete(comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.CombinationLocationsPossible, comb_loc_poss_id)
        obj.prep_delete = None
        session.flush()
        return schemas.CombinationLocationsPossibleShow.model_validate(obj)


def is_comb_loc_orphaned(session, clp_id: UUID) -> bool:
    """Gibt True zurück wenn keine Person, kein ActorPlanPeriod, kein AvailDay und kein Team
    die CombinationLocationsPossible noch referenziert.
    Muss innerhalb einer offenen Session aufgerufen werden."""
    if session.exec(
        select(models.PersonCombLocLink.person_id)
        .where(models.PersonCombLocLink.combination_locations_possible_id == clp_id)
        .limit(1)
    ).first():
        return False
    if session.exec(
        select(models.ActorPlanPeriodCombLocLink.actor_plan_period_id)
        .where(models.ActorPlanPeriodCombLocLink.combination_locations_possible_id == clp_id)
        .limit(1)
    ).first():
        return False
    if session.exec(
        select(models.AvailDayCombLocLink.avail_day_id)
        .where(models.AvailDayCombLocLink.combination_locations_possible_id == clp_id)
        .limit(1)
    ).first():
        return False
    clp = session.get(models.CombinationLocationsPossible, clp_id)
    return clp is not None and clp.team_id is None


def get_comb_loc_poss_ids_per_avail_day_of_actor_plan_period(actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        return {ad.id: [c.id for c in ad.combination_locations_possibles] for ad in app.avail_days}