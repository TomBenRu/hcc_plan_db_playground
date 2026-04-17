"""Desktop-API-Client: EventGroup-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(location_plan_period_id: uuid.UUID | None = None,
           event_group_id: uuid.UUID | None = None,
           undo_group_id: uuid.UUID | None = None) -> schemas.EventGroupShow:
    data = get_api_client().post("/api/v1/event-groups", json={
        "location_plan_period_id": str(location_plan_period_id) if location_plan_period_id else None,
        "event_group_id": str(event_group_id) if event_group_id else None,
        "undo_group_id": str(undo_group_id) if undo_group_id else None,
    })
    return schemas.EventGroupShow.model_validate(data)


def delete(eg_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/event-groups/{eg_id}")


def update_nr_event_groups(eg_id: uuid.UUID,
                            nr_event_groups: int | None) -> schemas.EventGroupShow:
    data = get_api_client().patch(f"/api/v1/event-groups/{eg_id}/nr-event-groups",
                                  json={"nr_event_groups": nr_event_groups})
    return schemas.EventGroupShow.model_validate(data)


def update_variation_weight(eg_id: uuid.UUID, variation_weight: int) -> schemas.EventGroupShow:
    data = get_api_client().patch(f"/api/v1/event-groups/{eg_id}/variation-weight",
                                  json={"variation_weight": variation_weight})
    return schemas.EventGroupShow.model_validate(data)


def set_new_parent(eg_id: uuid.UUID, new_parent_id: uuid.UUID) -> None:
    get_api_client().patch(f"/api/v1/event-groups/{eg_id}/parent",
                           json={"new_parent_id": str(new_parent_id)})


def set_new_parent_batch(moves: list[tuple[uuid.UUID, uuid.UUID]]
                          ) -> tuple[list[tuple[uuid.UUID | None, int | None]], dict[uuid.UUID, int]]:
    data = get_api_client().post("/api/v1/event-groups/batch/parent", json={
        "moves": [{"child_id": str(c), "new_parent_id": str(p)} for c, p in moves],
    })
    old_infos = [
        (uuid.UUID(i["old_parent_id"]) if i["old_parent_id"] else None, i["old_nr"])
        for i in data["old_parent_infos"]
    ]
    nr_resets = {uuid.UUID(k): v for k, v in data["nr_resets"].items()}
    return old_infos, nr_resets