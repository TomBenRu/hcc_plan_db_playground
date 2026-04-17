"""Desktop-API: ActorPlanPeriod-Endpunkte (/api/v1/actor-plan-periods)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/actor-plan-periods", tags=["desktop-actor-plan-periods"])


class ActorPlanPeriodCreateBody(BaseModel):
    plan_period_id: uuid.UUID
    person_id: uuid.UUID
    actor_plan_period_id: uuid.UUID | None = None


class AppNotesBody(BaseModel):
    notes: str | None = None


class AppRequestedAssignmentsBody(BaseModel):
    requested_assignments: int
    required_assignments: bool


@router.post("", response_model=schemas.ActorPlanPeriodShow, status_code=status.HTTP_201_CREATED)
def create_actor_plan_period(body: ActorPlanPeriodCreateBody, _: DesktopUser):
    return db_services.ActorPlanPeriod.create(
        body.plan_period_id, body.person_id, body.actor_plan_period_id
    )


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_actor_plan_period(app_id: uuid.UUID, _: DesktopUser):
    db_services.ActorPlanPeriod.delete(app_id)


@router.put("/{app_id}", response_model=schemas.ActorPlanPeriodShow)
def update_actor_plan_period(app_id: uuid.UUID, body: schemas.ActorPlanPeriodShow, _: DesktopUser):
    return db_services.ActorPlanPeriod.update(body)


@router.patch("/{app_id}/notes", response_model=schemas.ActorPlanPeriodShow)
def update_app_notes(app_id: uuid.UUID, body: AppNotesBody, _: DesktopUser):
    update_data = schemas.ActorPlanPeriodUpdateNotes(id=app_id, notes=body.notes)
    return db_services.ActorPlanPeriod.update_notes(update_data)


@router.patch("/{app_id}/requested-assignments", response_model=schemas.ActorPlanPeriodShow)
def update_requested_assignments(app_id: uuid.UUID, body: AppRequestedAssignmentsBody, _: DesktopUser):
    return db_services.ActorPlanPeriod.update_requested_assignments(
        app_id, body.requested_assignments, body.required_assignments
    )