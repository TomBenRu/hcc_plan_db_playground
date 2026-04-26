"""Desktop-API: PlanPeriod-Endpunkte (/api/v1/plan-periods).

Routen:
  - GET     /plan-periods/{id}                          → Detail
  - GET     /teams/{team_id}/plan-periods               → Listing pro Team
  - POST    /plan-periods                               → Legacy: Anlage ohne Kinder
  - POST    /plan-periods/with-children                 → Atomar mit LPP/APP/Master-Groups
  - PUT     /plan-periods/{id}                          → Update (closed-Lock)
  - PATCH   /plan-periods/{id}/notes                    → Notes-only (auch bei closed)
  - DELETE  /plan-periods/{id}                          → Soft-Delete (closed-Lock)
  - POST    /plan-periods/{id}/undelete                 → Restore
  - POST    /plan-periods/{id}/close                    → Manuelles Schließen
  - POST    /plan-periods/{id}/reopen                   → Re-Open (admin only)
  - GET     /plan-periods/{id}/takeover-candidates      → Vorschau
  - POST    /plan-periods/{id}/takeover                 → Übernahme ausführen
  - DELETE  /teams/{team_id}/plan-periods/prep-deleted  → Final-Delete soft-deleted PPs
"""

import datetime
import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from database import db_services, schemas
from database.db_services.plan_period import (
    PlanPeriodClosedError,
    PlanPeriodPermissionError,
)
from web_api.desktop_api.auth import DesktopUser
from web_api.models.web_models import WebUserRole

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


def _to_create_schema(body: PlanPeriodCreateBody) -> schemas.PlanPeriodCreate:
    team = db_services.Team.get(body.team_id)
    return schemas.PlanPeriodCreate(
        start=body.start, end=body.end, deadline=body.deadline,
        notes=body.notes, notes_for_employees=body.notes_for_employees,
        remainder=body.remainder, team=team,
    )


@router.get("/{plan_period_id}", response_model=schemas.PlanPeriodShow)
def get_plan_period(plan_period_id: uuid.UUID, _: DesktopUser):
    return db_services.PlanPeriod.get(plan_period_id)


@teams_router.get("/{team_id}/plan-periods", response_model=list[schemas.PlanPeriodShow])
def list_team_plan_periods(team_id: uuid.UUID, _: DesktopUser):
    return db_services.PlanPeriod.get_all_from__team(team_id)


@router.post("", response_model=schemas.PlanPeriodShow, status_code=status.HTTP_201_CREATED)
def create_plan_period(body: PlanPeriodCreateBody, _: DesktopUser):
    """Legacy: Anlage ohne automatische LPP/APP-Anlage. Neue Aufrufer
    sollten /with-children verwenden."""
    return db_services.PlanPeriod.create(_to_create_schema(body))


@router.post("/with-children", response_model=schemas.PlanPeriodShow,
             status_code=status.HTTP_201_CREATED)
def create_plan_period_with_children(body: PlanPeriodCreateBody, _: DesktopUser):
    """Atomar: PlanPeriod + LPP+EventGroup-Master + APP+AvailDayGroup-Master
    in einer Transaktion. Personen/Locations werden über alle Tage in
    [start, end] aufgelöst."""
    return db_services.PlanPeriod.create_with_children(_to_create_schema(body))


@router.put("/{plan_period_id}", response_model=schemas.PlanPeriodShow)
def update_plan_period(plan_period_id: uuid.UUID, body: schemas.PlanPeriod, _: DesktopUser):
    try:
        return db_services.PlanPeriod.update(body)
    except PlanPeriodClosedError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.patch("/{plan_period_id}/notes", response_model=schemas.PlanPeriodShow)
def update_plan_period_notes(plan_period_id: uuid.UUID, body: PlanPeriodNotesBody, _: DesktopUser):
    return db_services.PlanPeriod.update_notes(plan_period_id, body.notes)


@router.delete("/{plan_period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_plan_period(plan_period_id: uuid.UUID, _: DesktopUser):
    try:
        db_services.PlanPeriod.delete(plan_period_id)
    except PlanPeriodClosedError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/{plan_period_id}/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_plan_period(plan_period_id: uuid.UUID, _: DesktopUser):
    db_services.PlanPeriod.undelete(plan_period_id)


@router.post("/{plan_period_id}/close", response_model=schemas.PlanPeriodMinimal)
def close_plan_period(plan_period_id: uuid.UUID, user: DesktopUser):
    """Manueller Close. Disponent oder Admin (DesktopUser-Auth deckt das ab).

    Antwortet mit PlanPeriodMinimal — kein PlanPeriodShow, weil sonst bei
    großen Perioden hunderte Lazy-Queries getriggert würden (30 s-Bloat).
    """
    return db_services.PlanPeriod.set_closed(
        plan_period_id, True, is_admin=user.has_any_role(WebUserRole.admin)
    )


@router.post("/{plan_period_id}/reopen", response_model=schemas.PlanPeriodMinimal)
def reopen_plan_period(plan_period_id: uuid.UUID, user: DesktopUser):
    """Re-Open einer geschlossenen Periode. Admin-only."""
    if not user.has_any_role(WebUserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Re-Open requires admin role")
    try:
        return db_services.PlanPeriod.set_closed(
            plan_period_id, False, is_admin=True
        )
    except PlanPeriodPermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{plan_period_id}/takeover-candidates",
            response_model=schemas.TakeoverPreview)
def get_takeover_candidates(plan_period_id: uuid.UUID, _: DesktopUser):
    """Vorschau der Take-Over-Kandidaten (soft-deleted AvailDays/Events anderer
    PPs des gleichen Teams, deren Datum in der Range der neuen PP liegt)."""
    return db_services.PlanPeriod.find_takeover_candidates(plan_period_id)


@router.post("/{plan_period_id}/takeover", response_model=schemas.TakeoverReport)
def execute_takeover(plan_period_id: uuid.UUID, _: DesktopUser):
    """Übernimmt soft-deleted AvailDays in die neue PP-Tree-Struktur und löscht
    die Originale hart. Events werden in dieser Phase noch NICHT kopiert."""
    return db_services.PlanPeriod.execute_takeover(plan_period_id)


@teams_router.delete("/{team_id}/plan-periods/prep-deleted", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_prep_deleted_plan_periods(team_id: uuid.UUID, _: DesktopUser):
    db_services.PlanPeriod.delete_prep_deletes(team_id)