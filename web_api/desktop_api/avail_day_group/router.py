"""Desktop-API: AvailDayGroup-Endpunkte (/api/v1/avail-day-groups)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/avail-day-groups", tags=["desktop-avail-day-groups"])


class AvailDayGroupCreateBody(BaseModel):
    actor_plan_period_id: uuid.UUID | None = None
    avail_day_group_id: uuid.UUID | None = None
    undo_id: uuid.UUID | None = None


class NrAvailDayGroupsBody(BaseModel):
    nr_avail_day_groups: int | None = None


class MandatoryNrAvailDayGroupsBody(BaseModel):
    mandatory_nr_avail_day_groups: int | None = None


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


@router.post("", response_model=schemas.AvailDayGroupShow, status_code=status.HTTP_201_CREATED)
def create_avail_day_group(body: AvailDayGroupCreateBody, _: DesktopUser):
    return db_services.AvailDayGroup.create(
        actor_plan_period_id=body.actor_plan_period_id,
        avail_day_group_id=body.avail_day_group_id,
        undo_id=body.undo_id,
    )


@router.delete("/{adg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_avail_day_group(adg_id: uuid.UUID, _: DesktopUser):
    db_services.AvailDayGroup.delete(adg_id)


@router.patch("/{adg_id}/nr-avail-day-groups", response_model=schemas.AvailDayGroupShow)
def update_nr_avail_day_groups(adg_id: uuid.UUID, body: NrAvailDayGroupsBody, _: DesktopUser):
    return db_services.AvailDayGroup.update_nr_avail_day_groups(adg_id, body.nr_avail_day_groups)


@router.patch("/{adg_id}/variation-weight", response_model=schemas.AvailDayGroupShow)
def update_variation_weight(adg_id: uuid.UUID, body: VariationWeightBody, _: DesktopUser):
    return db_services.AvailDayGroup.update_variation_weight(adg_id, body.variation_weight)


@router.patch("/{adg_id}/mandatory-nr-avail-day-groups", response_model=schemas.AvailDayGroupShow)
def update_mandatory_nr_avail_day_groups(adg_id: uuid.UUID,
                                          body: MandatoryNrAvailDayGroupsBody, _: DesktopUser):
    return db_services.AvailDayGroup.update_mandatory_nr_avail_day_groups(
        adg_id, body.mandatory_nr_avail_day_groups
    )


# Statische /batch/... vor dynamischen /{adg_id}/... Routen.
@router.post("/batch/parent", response_model=BatchParentResponse)
def set_new_parent_batch(body: BatchParentRequest, _: DesktopUser):
    moves = [(m.child_id, m.new_parent_id) for m in body.moves]
    old_infos, nr_resets = db_services.AvailDayGroup.set_new_parent_batch(moves)
    return BatchParentResponse(
        old_parent_infos=[OldParentInfo(old_parent_id=p, old_nr=n) for p, n in old_infos],
        nr_resets=nr_resets,
    )


@router.patch("/{adg_id}/parent", status_code=status.HTTP_204_NO_CONTENT)
def set_new_parent(adg_id: uuid.UUID, body: NewParentBody, _: DesktopUser):
    db_services.AvailDayGroup.set_new_parent(adg_id, body.new_parent_id)