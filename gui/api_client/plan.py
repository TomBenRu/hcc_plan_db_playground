"""Desktop-API-Client: Plan-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(plan_period_id: uuid.UUID, name: str, notes: str = "") -> schemas.PlanShow:
    data = get_api_client().post("/api/v1/plans", json={
        "plan_period_id": str(plan_period_id),
        "name": name,
        "notes": notes,
    })
    return schemas.PlanShow.model_validate(data)


def update_name(plan_id: uuid.UUID, new_name: str) -> schemas.PlanShow:
    data = get_api_client().patch(f"/api/v1/plans/{plan_id}/name", json={"name": new_name})
    return schemas.PlanShow.model_validate(data)


def update_notes(plan_id: uuid.UUID, notes: str) -> schemas.PlanShow:
    data = get_api_client().patch(f"/api/v1/plans/{plan_id}/notes", json={"notes": notes})
    return schemas.PlanShow.model_validate(data)


def update_location_columns(plan_id: uuid.UUID, location_columns: str) -> None:
    get_api_client().patch(f"/api/v1/plans/{plan_id}/location-columns",
                           json={"location_columns": location_columns})


def set_binding(plan_id: uuid.UUID) -> uuid.UUID | None:
    data = get_api_client().post(f"/api/v1/plans/{plan_id}/binding")
    prev = data.get("previous_plan_id") if data else None
    return uuid.UUID(prev) if prev else None


def unset_binding(plan_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/plans/{plan_id}/binding")


def delete(plan_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/plans/{plan_id}")


def undelete(plan_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/plans/{plan_id}/undelete")


def delete_prep_deleted(plan_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/plans/{plan_id}/prep-deleted")


def delete_prep_deletes_from__team(team_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/teams/{team_id}/plans/prep-deleted")


def put_in_excel_settings(plan_id: uuid.UUID, excel_settings_id: uuid.UUID) -> schemas.PlanShow:
    data = get_api_client().put(f"/api/v1/plans/{plan_id}/excel-settings",
                                json={"excel_settings_id": str(excel_settings_id)})
    return schemas.PlanShow.model_validate(data)
