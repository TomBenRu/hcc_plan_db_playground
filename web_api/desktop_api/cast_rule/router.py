"""Desktop-API: CastRule-Endpunkte (/api/v1/cast-rules)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/cast-rules", tags=["desktop-cast-rules"])


class CastRuleCreateBody(BaseModel):
    project_id: uuid.UUID
    name: str
    rule: str
    restore_id: uuid.UUID | None = None


class CastRuleUpdateBody(BaseModel):
    name: str
    rule: str


@router.post("", response_model=schemas.CastRuleShow, status_code=status.HTTP_201_CREATED)
def create_cast_rule(body: CastRuleCreateBody, _: DesktopUser):
    return db_services.CastRule.create(body.project_id, body.name, body.rule, body.restore_id)


@router.patch("/{cast_rule_id}", response_model=schemas.CastRuleShow)
def update_cast_rule(cast_rule_id: uuid.UUID, body: CastRuleUpdateBody, _: DesktopUser):
    return db_services.CastRule.update(cast_rule_id, body.name, body.rule)


@router.delete("/{cast_rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cast_rule(cast_rule_id: uuid.UUID, _: DesktopUser):
    db_services.CastRule.delete(cast_rule_id)


@router.post("/{cast_rule_id}/prep-delete", response_model=schemas.CastRuleShow)
def set_prep_delete(cast_rule_id: uuid.UUID, _: DesktopUser):
    return db_services.CastRule.set_prep_delete(cast_rule_id)


@router.post("/{cast_rule_id}/undelete", response_model=schemas.CastRuleShow)
def undelete_cast_rule(cast_rule_id: uuid.UUID, _: DesktopUser):
    return db_services.CastRule.undelete(cast_rule_id)