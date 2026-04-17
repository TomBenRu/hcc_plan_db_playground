"""Desktop-API: LocationPlanPeriod-Endpunkte (/api/v1/location-plan-periods)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/location-plan-periods", tags=["desktop-location-plan-periods"])


class LocationPlanPeriodCreateBody(BaseModel):
    plan_period_id: uuid.UUID
    location_id: uuid.UUID
    location_plan_period_id: uuid.UUID | None = None


class LppNotesBody(BaseModel):
    notes: str


class LppFixedCastBody(BaseModel):
    fixed_cast: str
    fixed_cast_only_if_available: bool


class LppNumActorsBody(BaseModel):
    num_actors: int


@router.post("", response_model=schemas.LocationPlanPeriodShow, status_code=status.HTTP_201_CREATED)
def create_location_plan_period(body: LocationPlanPeriodCreateBody, _: DesktopUser):
    return db_services.LocationPlanPeriod.create(
        body.plan_period_id, body.location_id, body.location_plan_period_id
    )


@router.delete("/{lpp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_location_plan_period(lpp_id: uuid.UUID, _: DesktopUser):
    db_services.LocationPlanPeriod.delete(lpp_id)


@router.patch("/{lpp_id}/notes", response_model=schemas.LocationPlanPeriodShow)
def update_lpp_notes(lpp_id: uuid.UUID, body: LppNotesBody, _: DesktopUser):
    return db_services.LocationPlanPeriod.update_notes(lpp_id, body.notes)


@router.patch("/{lpp_id}/fixed-cast", response_model=schemas.LocationPlanPeriodShow)
def update_fixed_cast(lpp_id: uuid.UUID, body: LppFixedCastBody, _: DesktopUser):
    return db_services.LocationPlanPeriod.update_fixed_cast(
        lpp_id, body.fixed_cast, body.fixed_cast_only_if_available
    )


@router.patch("/{lpp_id}/num-actors", response_model=schemas.LocationPlanPeriodShow)
def update_num_actors(lpp_id: uuid.UUID, body: LppNumActorsBody, _: DesktopUser):
    return db_services.LocationPlanPeriod.update_num_actors(lpp_id, body.num_actors)