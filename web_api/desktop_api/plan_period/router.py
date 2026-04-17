"""Desktop-API: PlanPeriod-Endpunkte (/api/v1/plan-periods)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/plan-periods", tags=["desktop-plan-periods"])
teams_router = APIRouter(prefix="/teams", tags=["desktop-plan-periods"])


class PlanPeriodCreateBody(BaseModel):
    start: datetime.date
    end: datetime.date
    deadline: datetime.date
    notes: str | None = None
    notes_for_employees: str | None = None
    remainder: bool
    team_id: uuid.UUID


class PlanPeriodNotesBody(BaseModel):
    notes: str


@router.post("", response_model=schemas.PlanPeriodShow, status_code=status.HTTP_201_CREATED)
def create_plan_period(body: PlanPeriodCreateBody, _: DesktopUser):
    team = db_services.Team.get(body.team_id)
    pp_create = schemas.PlanPeriodCreate(
        start=body.start, end=body.end, deadline=body.deadline,
        notes=body.notes, notes_for_employees=body.notes_for_employees,
        remainder=body.remainder, team=team,
    )
    return db_services.PlanPeriod.create(pp_create)


@router.put("/{plan_period_id}", response_model=schemas.PlanPeriodShow)
def update_plan_period(plan_period_id: uuid.UUID, body: schemas.PlanPeriod, _: DesktopUser):
    return db_services.PlanPeriod.update(body)


@router.patch("/{plan_period_id}/notes", response_model=schemas.PlanPeriodShow)
def update_plan_period_notes(plan_period_id: uuid.UUID, body: PlanPeriodNotesBody, _: DesktopUser):
    return db_services.PlanPeriod.update_notes(plan_period_id, body.notes)


@router.delete("/{plan_period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan_period(plan_period_id: uuid.UUID, _: DesktopUser):
    db_services.PlanPeriod.delete(plan_period_id)


@router.post("/{plan_period_id}/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_plan_period(plan_period_id: uuid.UUID, _: DesktopUser):
    db_services.PlanPeriod.undelete(plan_period_id)


@teams_router.delete("/{team_id}/plan-periods/prep-deleted", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_prep_deleted_plan_periods(team_id: uuid.UUID, _: DesktopUser):
    db_services.PlanPeriod.delete_prep_deletes(team_id)