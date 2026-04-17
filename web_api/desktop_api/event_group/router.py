"""Desktop-API: EventGroup-Endpunkte (/api/v1/event-groups)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/event-groups", tags=["desktop-event-groups"])


class EventGroupCreateBody(BaseModel):
    location_plan_period_id: uuid.UUID | None = None
    event_group_id: uuid.UUID | None = None
    undo_group_id: uuid.UUID | None = None


class NrEventGroupsBody(BaseModel):
    nr_event_groups: int | None = None


class VariationWeightBody(BaseModel):
    variation_weight: int


class NewParentBody(BaseModel):
    new_parent_id: uuid.UUID


class BatchParentMove(BaseModel):
    child_id: uuid.UUID
    new_parent_id: uuid.UUID


class BatchParentRequest(BaseModel):
    moves: list[BatchParentMove]


class OldParentInfo(BaseModel):
    old_parent_id: uuid.UUID | None
    old_nr: int | None


class BatchParentResponse(BaseModel):
    old_parent_infos: list[OldParentInfo]
    nr_resets: dict[uuid.UUID, int]


@router.post("", response_model=schemas.EventGroupShow, status_code=status.HTTP_201_CREATED)
def create_event_group(body: EventGroupCreateBody, _: DesktopUser):
    return db_services.EventGroup.create(
        location_plan_period_id=body.location_plan_period_id,
        event_group_id=body.event_group_id,
        undo_group_id=body.undo_group_id,
    )


@router.delete("/{eg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event_group(eg_id: uuid.UUID, _: DesktopUser):
    db_services.EventGroup.delete(eg_id)


@router.patch("/{eg_id}/nr-event-groups", response_model=schemas.EventGroupShow)
def update_nr_event_groups(eg_id: uuid.UUID, body: NrEventGroupsBody, _: DesktopUser):
    return db_services.EventGroup.update_nr_event_groups(eg_id, body.nr_event_groups)


@router.patch("/{eg_id}/variation-weight", response_model=schemas.EventGroupShow)
def update_variation_weight(eg_id: uuid.UUID, body: VariationWeightBody, _: DesktopUser):
    return db_services.EventGroup.update_variation_weight(eg_id, body.variation_weight)


@router.patch("/{eg_id}/parent", status_code=status.HTTP_204_NO_CONTENT)
def set_new_parent(eg_id: uuid.UUID, body: NewParentBody, _: DesktopUser):
    db_services.EventGroup.set_new_parent(eg_id, body.new_parent_id)


@router.post("/batch/parent", response_model=BatchParentResponse)
def set_new_parent_batch(body: BatchParentRequest, _: DesktopUser):
    moves = [(m.child_id, m.new_parent_id) for m in body.moves]
    old_infos, nr_resets = db_services.EventGroup.set_new_parent_batch(moves)
    return BatchParentResponse(
        old_parent_infos=[OldParentInfo(old_parent_id=p, old_nr=n) for p, n in old_infos],
        nr_resets=nr_resets,
    )