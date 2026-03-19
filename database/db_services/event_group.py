"""Service-Funktionen für EventGroup (Veranstaltungsgruppen-Baum).

EventGroups bilden wie AvailDayGroups eine Baumstruktur. Jeder Blattknoten
referenziert ein einzelnes Event; interne Knoten steuern über `nr_event_groups`
und `variation_weight`, wie viele Events aus der Gruppe geplant werden müssen.
Der Master-Knoten gehört zur LocationPlanPeriod.
"""
import datetime
from typing import Optional
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(event_group_id: UUID) -> schemas.EventGroupShow:
    with get_session() as session:
        return schemas.EventGroupShow.model_validate(session.get(models.EventGroup, event_group_id))


def get_master_from__location_plan_period(location_plan_period_id: UUID) -> schemas.EventGroupShow:
    with get_session() as session:
        lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
        return schemas.EventGroupShow.model_validate(lpp.event_group)


def get_child_groups_from__parent_group(event_group_id) -> list[schemas.EventGroupShow]:
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        return [schemas.EventGroupShow.model_validate(e) for e in eg.event_groups]


def get_grand_parent_event_group_id_from_event(event_id: UUID) -> UUID | None:
    with get_session() as session:
        event = session.get(models.Event, event_id)
        return event.event_group.event_group.id if event.event_group.event_group else None


def create(*, location_plan_period_id: Optional[UUID] = None,
           event_group_id: Optional[UUID] = None, undo_group_id: UUID = None) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        kwargs = {}
        if location_plan_period_id:
            kwargs['location_plan_period'] = session.get(models.LocationPlanPeriod, location_plan_period_id)
        if event_group_id:
            kwargs['event_group'] = session.get(models.EventGroup, event_group_id)
        if undo_group_id:
            kwargs['id'] = undo_group_id
        eg = models.EventGroup(**kwargs)
        session.add(eg)
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def update_nr_event_groups(event_group_id: UUID, nr_event_groups: int | None) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        eg.nr_event_groups = nr_event_groups
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def update_variation_weight(event_group_id: UUID, variation_weight: int) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        eg.variation_weight = variation_weight
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def set_new_parent(event_group_id: UUID, new_parent_id: UUID) -> schemas.EventGroupShow:
    log_function_info()
    with get_session() as session:
        eg = session.get(models.EventGroup, event_group_id)
        eg.event_group = session.get(models.EventGroup, new_parent_id)
        session.flush()
        return schemas.EventGroupShow.model_validate(eg)


def delete(event_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.EventGroup, event_group_id))