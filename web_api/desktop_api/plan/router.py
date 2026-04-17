"""Desktop-API: Plan-Endpunkte (/api/v1/plans)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/plans", tags=["desktop-plans"])
teams_router = APIRouter(prefix="/teams", tags=["desktop-plans"])


# ── Request-Bodies ────────────────────────────────────────────────────────────


class PlanCreateBody(BaseModel):
    plan_period_id: uuid.UUID
    name: str
    notes: str = ""


class PlanNameBody(BaseModel):
    name: str


class PlanNotesBody(BaseModel):
    notes: str


class PlanLocationColumnsBody(BaseModel):
    location_columns: str


class PlanExcelSettingsBody(BaseModel):
    excel_settings_id: uuid.UUID


class SetBindingResponse(BaseModel):
    previous_plan_id: uuid.UUID | None


# ── Endpunkte ─────────────────────────────────────────────────────────────────


@router.post("", response_model=schemas.PlanShow, status_code=status.HTTP_201_CREATED)
def create_plan(body: PlanCreateBody, _: DesktopUser):
    return db_services.Plan.create(body.plan_period_id, body.name, body.notes)


@router.patch("/{plan_id}/name", response_model=schemas.PlanShow)
def update_plan_name(plan_id: uuid.UUID, body: PlanNameBody, _: DesktopUser):
    return db_services.Plan.update_name(plan_id, body.name)


@router.patch("/{plan_id}/notes", response_model=schemas.PlanShow)
def update_plan_notes(plan_id: uuid.UUID, body: PlanNotesBody, _: DesktopUser):
    return db_services.Plan.update_notes(plan_id, body.notes)


@router.patch("/{plan_id}/location-columns", status_code=status.HTTP_204_NO_CONTENT)
def update_location_columns(plan_id: uuid.UUID, body: PlanLocationColumnsBody, _: DesktopUser):
    db_services.Plan.update_location_columns(plan_id, body.location_columns)


@router.post("/{plan_id}/binding", response_model=SetBindingResponse)
def set_binding(plan_id: uuid.UUID, _: DesktopUser):
    previous_plan_id = db_services.Plan.set_binding(plan_id)
    return SetBindingResponse(previous_plan_id=previous_plan_id)


@router.delete("/{plan_id}/binding", status_code=status.HTTP_204_NO_CONTENT)
def unset_binding(plan_id: uuid.UUID, _: DesktopUser):
    db_services.Plan.unset_binding(plan_id)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan(plan_id: uuid.UUID, _: DesktopUser):
    db_services.Plan.delete(plan_id)


@router.post("/{plan_id}/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_plan(plan_id: uuid.UUID, _: DesktopUser):
    db_services.Plan.undelete(plan_id)


@router.delete("/{plan_id}/prep-deleted", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep_deleted(plan_id: uuid.UUID, _: DesktopUser):
    db_services.Plan.delete_prep_deleted(plan_id)


@router.put("/{plan_id}/excel-settings", response_model=schemas.PlanShow)
def put_in_excel_settings(plan_id: uuid.UUID, body: PlanExcelSettingsBody, _: DesktopUser):
    return db_services.Plan.put_in_excel_settings(plan_id, body.excel_settings_id)


@teams_router.delete("/{team_id}/plans/prep-deleted", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_prep_deleted_plans(team_id: uuid.UUID, _: DesktopUser):
    db_services.Plan.delete_prep_deletes_from__team(team_id)
