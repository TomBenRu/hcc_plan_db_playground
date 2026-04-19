"""Desktop-API: CastGroup-Endpunkte (/api/v1/cast-groups)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/cast-groups", tags=["desktop-cast-groups"])


class CastGroupCreateBody(BaseModel):
    plan_period_id: uuid.UUID
    restore_cast_group: schemas.CastGroupShow | None = None


class NrActorsBody(BaseModel):
    nr_actors: int


class NewParentBody(BaseModel):
    new_parent_id: uuid.UUID


class RemoveParentBody(BaseModel):
    parent_group_id: uuid.UUID


class FixedCastBody(BaseModel):
    # None erlaubt — User kann Fixed-Cast komplett leeren.
    fixed_cast: str | None = None
    fixed_cast_only_if_available: bool


class StrictCastPrefBody(BaseModel):
    strict_cast_pref: int


class PreferFixedCastEventsBody(BaseModel):
    prefer_fixed_cast_events: bool


class CustomRuleBody(BaseModel):
    custom_rule: str


class CastRuleLinkBody(BaseModel):
    cast_rule_id: uuid.UUID | None = None


@router.post("", response_model=schemas.CastGroupShow, status_code=status.HTTP_201_CREATED)
def create_cast_group(body: CastGroupCreateBody, _: DesktopUser):
    return db_services.CastGroup.create(
        plan_period_id=body.plan_period_id,
        restore_cast_group=body.restore_cast_group,
    )


@router.delete("/{cg_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cast_group(cg_id: uuid.UUID, _: DesktopUser):
    db_services.CastGroup.delete(cg_id)


@router.patch("/{cg_id}/nr-actors", response_model=schemas.CastGroupShow)
def update_nr_actors(cg_id: uuid.UUID, body: NrActorsBody, _: DesktopUser):
    return db_services.CastGroup.update_nr_actors(cg_id, body.nr_actors)


@router.patch("/{cg_id}/parent", response_model=schemas.CastGroupShow)
def set_new_parent(cg_id: uuid.UUID, body: NewParentBody, _: DesktopUser):
    return db_services.CastGroup.set_new_parent(cg_id, body.new_parent_id)


@router.patch("/{cg_id}/remove-parent", response_model=schemas.CastGroupShow)
def remove_from_parent(cg_id: uuid.UUID, body: RemoveParentBody, _: DesktopUser):
    return db_services.CastGroup.remove_from_parent(cg_id, body.parent_group_id)


@router.patch("/{cg_id}/fixed-cast", response_model=schemas.CastGroupShow)
def update_fixed_cast(cg_id: uuid.UUID, body: FixedCastBody, _: DesktopUser):
    return db_services.CastGroup.update_fixed_cast(cg_id, body.fixed_cast, body.fixed_cast_only_if_available)


@router.patch("/{cg_id}/strict-cast-pref", response_model=schemas.CastGroupShow)
def update_strict_cast_pref(cg_id: uuid.UUID, body: StrictCastPrefBody, _: DesktopUser):
    return db_services.CastGroup.update_strict_cast_pref(cg_id, body.strict_cast_pref)


@router.patch("/{cg_id}/prefer-fixed-cast-events", response_model=schemas.CastGroupShow)
def update_prefer_fixed_cast_events(cg_id: uuid.UUID, body: PreferFixedCastEventsBody, _: DesktopUser):
    return db_services.CastGroup.update_prefer_fixed_cast_events(cg_id, body.prefer_fixed_cast_events)


@router.patch("/{cg_id}/custom-rule", response_model=schemas.CastGroupShow)
def update_custom_rule(cg_id: uuid.UUID, body: CustomRuleBody, _: DesktopUser):
    return db_services.CastGroup.update_custom_rule(cg_id, body.custom_rule)


@router.patch("/{cg_id}/cast-rule", response_model=schemas.CastGroupShow)
def update_cast_rule(cg_id: uuid.UUID, body: CastRuleLinkBody, _: DesktopUser):
    return db_services.CastGroup.update_cast_rule(cg_id, body.cast_rule_id)