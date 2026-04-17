"""Desktop-API-Client: PlanPeriod-Operationen."""

import datetime
import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(start: datetime.date, end: datetime.date, deadline: datetime.date,
           remainder: bool, team_id: uuid.UUID,
           notes: str | None = None, notes_for_employees: str | None = None) -> schemas.PlanPeriodShow:
    data = get_api_client().post("/api/v1/plan-periods", json={
        "start": start.isoformat(),
        "end": end.isoformat(),
        "deadline": deadline.isoformat(),
        "notes": notes,
        "notes_for_employees": notes_for_employees,
        "remainder": remainder,
        "team_id": str(team_id),
    })
    return schemas.PlanPeriodShow.model_validate(data)


def update(plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
    data = get_api_client().put(f"/api/v1/plan-periods/{plan_period.id}",
                                json=plan_period.model_dump(mode="json"))
    return schemas.PlanPeriodShow.model_validate(data)


def update_notes(plan_period_id: uuid.UUID, notes: str) -> schemas.PlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/plan-periods/{plan_period_id}/notes",
                                  json={"notes": notes})
    return schemas.PlanPeriodShow.model_validate(data)


def delete(plan_period_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/plan-periods/{plan_period_id}")


def undelete(plan_period_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/plan-periods/{plan_period_id}/undelete")


def delete_prep_deletes(team_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/teams/{team_id}/plan-periods/prep-deleted")