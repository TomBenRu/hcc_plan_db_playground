import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(avail_day_group_id: UUID) -> schemas.AvailDayGroupShow:
    with get_session() as session:
        return schemas.AvailDayGroupShow.model_validate(session.get(models.AvailDayGroup, avail_day_group_id))


def get_master_from__actor_plan_period(actor_plan_period_id: UUID) -> schemas.AvailDayGroupShow:
    with get_session() as session:
        return schemas.AvailDayGroupShow.model_validate(
            session.get(models.ActorPlanPeriod, actor_plan_period_id).avail_day_group)


def get_child_groups_from__parent_group(avail_day_group_id) -> list[schemas.AvailDayGroupShow]:
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        return [schemas.AvailDayGroupShow.model_validate(c) for c in adg.avail_day_groups]


def get_all_for_tree(actor_plan_period_id: UUID) -> dict[UUID, schemas.AvailDayGroupTreeNode]:
    with get_session() as session:
        result: dict[UUID, schemas.AvailDayGroupTreeNode] = {}
        def collect(adg):
            node = schemas.AvailDayGroupTreeNode(
                id=adg.id, variation_weight=adg.variation_weight or 1,
                nr_avail_day_groups=adg.nr_avail_day_groups,
                child_ids=[c.id for c in adg.avail_day_groups],
                avail_day_id=adg.avail_day.id if adg.avail_day else None)
            result[adg.id] = node
            for child in adg.avail_day_groups:
                collect(child)
        master = session.get(models.ActorPlanPeriod, actor_plan_period_id).avail_day_group
        collect(master)
        return result


def create(*, actor_plan_period_id: Optional[UUID] = None,
           avail_day_group_id: Optional[UUID] = None, undo_id: UUID = None) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        kwargs = {}
        if actor_plan_period_id:
            kwargs['actor_plan_period'] = session.get(models.ActorPlanPeriod, actor_plan_period_id)
        if avail_day_group_id:
            kwargs['avail_day_group'] = session.get(models.AvailDayGroup, avail_day_group_id)
        if undo_id:
            kwargs['id'] = undo_id
        adg = models.AvailDayGroup(**kwargs)
        session.add(adg)
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def update_nr_avail_day_groups(avail_day_group_id: UUID, nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.nr_avail_day_groups = nr_avail_day_groups
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def update_variation_weight(avail_day_group_id: UUID, variation_weight: int) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.variation_weight = variation_weight
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def update_mandatory_nr_avail_day_groups(avail_day_group_id: UUID, mandatory_nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.mandatory_nr_avail_day_groups = mandatory_nr_avail_day_groups
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def set_new_parent(avail_day_group_id: UUID, new_parent_id: UUID) -> schemas.AvailDayGroupShow:
    log_function_info()
    with get_session() as session:
        adg = session.get(models.AvailDayGroup, avail_day_group_id)
        adg.avail_day_group = session.get(models.AvailDayGroup, new_parent_id)
        session.flush()
        return schemas.AvailDayGroupShow.model_validate(adg)


def delete(avail_day_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.AvailDayGroup, avail_day_group_id))