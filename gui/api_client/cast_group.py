"""Desktop-API-Client: CastGroup-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(plan_period_id: uuid.UUID,
           restore_cast_group: schemas.CastGroupShow | None = None) -> schemas.CastGroupShow:
    data = get_api_client().post("/api/v1/cast-groups", json={
        "plan_period_id": str(plan_period_id),
        "restore_cast_group": restore_cast_group.model_dump(mode="json") if restore_cast_group else None,
    })
    return schemas.CastGroupShow.model_validate(data)


def delete(cg_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/cast-groups/{cg_id}")


def update_nr_actors(cg_id: uuid.UUID, nr_actors: int) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/nr-actors",
                                  json={"nr_actors": nr_actors})
    return schemas.CastGroupShow.model_validate(data)


def set_new_parent(cg_id: uuid.UUID, new_parent_id: uuid.UUID) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/parent",
                                  json={"new_parent_id": str(new_parent_id)})
    return schemas.CastGroupShow.model_validate(data)


def remove_from_parent(cg_id: uuid.UUID, parent_group_id: uuid.UUID) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/remove-parent",
                                  json={"parent_group_id": str(parent_group_id)})
    return schemas.CastGroupShow.model_validate(data)


def update_fixed_cast(cg_id: uuid.UUID, fixed_cast: str,
                       fixed_cast_only_if_available: bool) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/fixed-cast", json={
        "fixed_cast": fixed_cast,
        "fixed_cast_only_if_available": fixed_cast_only_if_available,
    })
    return schemas.CastGroupShow.model_validate(data)


def update_strict_cast_pref(cg_id: uuid.UUID, strict_cast_pref: int) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/strict-cast-pref",
                                  json={"strict_cast_pref": strict_cast_pref})
    return schemas.CastGroupShow.model_validate(data)


def update_prefer_fixed_cast_events(cg_id: uuid.UUID,
                                      prefer_fixed_cast_events: bool) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/prefer-fixed-cast-events",
                                  json={"prefer_fixed_cast_events": prefer_fixed_cast_events})
    return schemas.CastGroupShow.model_validate(data)


def update_custom_rule(cg_id: uuid.UUID, custom_rule: str) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/custom-rule",
                                  json={"custom_rule": custom_rule})
    return schemas.CastGroupShow.model_validate(data)


def update_cast_rule(cg_id: uuid.UUID, cast_rule_id: uuid.UUID | None) -> schemas.CastGroupShow:
    data = get_api_client().patch(f"/api/v1/cast-groups/{cg_id}/cast-rule",
                                  json={"cast_rule_id": str(cast_rule_id) if cast_rule_id else None})
    return schemas.CastGroupShow.model_validate(data)