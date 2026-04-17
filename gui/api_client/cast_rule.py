"""Desktop-API-Client: CastRule-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(project_id: uuid.UUID, name: str, rule: str,
           restore_id: uuid.UUID | None = None) -> schemas.CastRuleShow:
    data = get_api_client().post("/api/v1/cast-rules", json={
        "project_id": str(project_id),
        "name": name,
        "rule": rule,
        "restore_id": str(restore_id) if restore_id else None,
    })
    return schemas.CastRuleShow.model_validate(data)


def update(cast_rule_id: uuid.UUID, name: str, rule: str) -> schemas.CastRuleShow:
    data = get_api_client().patch(f"/api/v1/cast-rules/{cast_rule_id}",
                                  json={"name": name, "rule": rule})
    return schemas.CastRuleShow.model_validate(data)


def delete(cast_rule_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/cast-rules/{cast_rule_id}")


def set_prep_delete(cast_rule_id: uuid.UUID) -> schemas.CastRuleShow:
    data = get_api_client().post(f"/api/v1/cast-rules/{cast_rule_id}/prep-delete")
    return schemas.CastRuleShow.model_validate(data)


def undelete(cast_rule_id: uuid.UUID) -> schemas.CastRuleShow:
    data = get_api_client().post(f"/api/v1/cast-rules/{cast_rule_id}/undelete")
    return schemas.CastRuleShow.model_validate(data)