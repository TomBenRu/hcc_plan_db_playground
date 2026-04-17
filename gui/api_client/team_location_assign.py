"""Desktop-API-Client: TeamLocationAssign-Operationen."""

import datetime
import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(location_of_work_id: uuid.UUID, team_id: uuid.UUID,
           start: datetime.date | None = None,
           end: datetime.date | None = None,
           assign_id: uuid.UUID | None = None) -> schemas.TeamLocationAssignShow:
    data = get_api_client().post("/api/v1/team-location-assigns", json={
        "location_of_work_id": str(location_of_work_id),
        "team_id": str(team_id),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "assign_id": str(assign_id) if assign_id else None,
    })
    return schemas.TeamLocationAssignShow.model_validate(data)


def set_end_date(assign_id: uuid.UUID, end_date: datetime.date | None = None) -> None:
    get_api_client().patch(f"/api/v1/team-location-assigns/{assign_id}/end-date",
                           json={"end_date": end_date.isoformat() if end_date else None})


def delete(assign_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/team-location-assigns/{assign_id}")