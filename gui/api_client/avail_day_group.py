"""Desktop-API-Client: AvailDayGroup-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(actor_plan_period_id: uuid.UUID | None = None,
           avail_day_group_id: uuid.UUID | None = None,
           undo_id: uuid.UUID | None = None) -> schemas.AvailDayGroupShow:
    data = get_api_client().post("/api/v1/avail-day-groups", json={
        "actor_plan_period_id": str(actor_plan_period_id) if actor_plan_period_id else None,
        "avail_day_group_id": str(avail_day_group_id) if avail_day_group_id else None,
        "undo_id": str(undo_id) if undo_id else None,
    })
    return schemas.AvailDayGroupShow.model_validate(data)


def delete(adg_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/avail-day-groups/{adg_id}")


def update_nr_avail_day_groups(adg_id: uuid.UUID,
                                nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
    data = get_api_client().patch(f"/api/v1/avail-day-groups/{adg_id}/nr-avail-day-groups",
                                  json={"nr_avail_day_groups": nr_avail_day_groups})
    return schemas.AvailDayGroupShow.model_validate(data)


def update_variation_weight(adg_id: uuid.UUID, variation_weight: int) -> schemas.AvailDayGroupShow:
    data = get_api_client().patch(f"/api/v1/avail-day-groups/{adg_id}/variation-weight",
                                  json={"variation_weight": variation_weight})
    return schemas.AvailDayGroupShow.model_validate(data)


def update_mandatory_nr_avail_day_groups(adg_id: uuid.UUID,
                                           mandatory_nr_avail_day_groups: int | None
                                           ) -> schemas.AvailDayGroupShow:
    data = get_api_client().patch(
        f"/api/v1/avail-day-groups/{adg_id}/mandatory-nr-avail-day-groups",
        json={"mandatory_nr_avail_day_groups": mandatory_nr_avail_day_groups})
    return schemas.AvailDayGroupShow.model_validate(data)


def set_new_parent(adg_id: uuid.UUID, new_parent_id: uuid.UUID) -> None:
    get_api_client().patch(f"/api/v1/avail-day-groups/{adg_id}/parent",
                           json={"new_parent_id": str(new_parent_id)})


def set_new_parent_batch(moves: list[tuple[uuid.UUID, uuid.UUID]]
                          ) -> tuple[list[tuple[uuid.UUID | None, int | None]], dict[uuid.UUID, int]]:
    data = get_api_client().post("/api/v1/avail-day-groups/batch/parent", json={
        "moves": [{"child_id": str(c), "new_parent_id": str(p)} for c, p in moves],
    })
    old_infos = [
        (uuid.UUID(i["old_parent_id"]) if i["old_parent_id"] else None, i["old_nr"])
        for i in data["old_parent_infos"]
    ]
    nr_resets = {uuid.UUID(k): v for k, v in data["nr_resets"].items()}
    return old_infos, nr_resets