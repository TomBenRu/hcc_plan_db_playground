"""Desktop-API-Client: RequiredAvailDayGroups-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(num_avail_day_groups: int, avail_day_group_id: uuid.UUID,
           location_of_work_ids: list[uuid.UUID],
           undo_id: uuid.UUID | None = None) -> schemas.RequiredAvailDayGroups:
    data = get_api_client().post("/api/v1/required-avail-day-groups", json={
        "num_avail_day_groups": num_avail_day_groups,
        "avail_day_group_id": str(avail_day_group_id),
        "location_of_work_ids": [str(i) for i in location_of_work_ids],
        "undo_id": str(undo_id) if undo_id else None,
    })
    return schemas.RequiredAvailDayGroups.model_validate(data)


def update(radg_id: uuid.UUID, num_avail_day_groups: int,
           location_of_work_ids: list[uuid.UUID]) -> schemas.RequiredAvailDayGroups:
    data = get_api_client().put(f"/api/v1/required-avail-day-groups/{radg_id}", json={
        "num_avail_day_groups": num_avail_day_groups,
        "location_of_work_ids": [str(i) for i in location_of_work_ids],
    })
    return schemas.RequiredAvailDayGroups.model_validate(data)


def delete(radg_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/required-avail-day-groups/{radg_id}")