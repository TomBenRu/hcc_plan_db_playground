"""Desktop-API: RequiredAvailDayGroups-Endpunkte (/api/v1/required-avail-day-groups)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/required-avail-day-groups",
                   tags=["desktop-required-avail-day-groups"])


class RADGCreateBody(BaseModel):
    num_avail_day_groups: int
    avail_day_group_id: uuid.UUID
    location_of_work_ids: list[uuid.UUID]
    undo_id: uuid.UUID | None = None


class RADGUpdateBody(BaseModel):
    num_avail_day_groups: int
    location_of_work_ids: list[uuid.UUID]


@router.post("", response_model=schemas.RequiredAvailDayGroups,
             status_code=status.HTTP_201_CREATED)
def create_radg(body: RADGCreateBody, _: DesktopUser):
    return db_services.RequiredAvailDayGroups.create(
        body.num_avail_day_groups, body.avail_day_group_id,
        body.location_of_work_ids, body.undo_id,
    )


@router.put("/{radg_id}", response_model=schemas.RequiredAvailDayGroups)
def update_radg(radg_id: uuid.UUID, body: RADGUpdateBody, _: DesktopUser):
    return db_services.RequiredAvailDayGroups.update(
        radg_id, body.num_avail_day_groups, body.location_of_work_ids,
    )


@router.delete("/{radg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_radg(radg_id: uuid.UUID, _: DesktopUser):
    db_services.RequiredAvailDayGroups.delete(radg_id)