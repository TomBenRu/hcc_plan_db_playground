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


def get_comb_loc_poss_ids_per_avail_day_of_actor_plan_period(actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
    with get_session() as session:
        app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        return {ad.id: [c.id for c in ad.combination_locations_possibles] for ad in app.avail_days}