"""Desktop-API-Client: TimeOfDay-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(time_of_day: schemas.TimeOfDayCreate, project_id: uuid.UUID) -> schemas.TimeOfDay:
    data = get_api_client().post("/api/v1/time-of-days", json={
        "name": time_of_day.name,
        "time_of_day_enum_id": str(time_of_day.time_of_day_enum.id),
        "start": time_of_day.start.isoformat(),
        "end": time_of_day.end.isoformat(),
        "project_id": str(project_id),
        "project_standard_id": (str(time_of_day.project_standard.id)
                                 if time_of_day.project_standard else None),
    })
    return schemas.TimeOfDay.model_validate(data)


def update(time_of_day: schemas.TimeOfDay) -> schemas.TimeOfDay:
    data = get_api_client().put(f"/api/v1/time-of-days/{time_of_day.id}",
                                json=time_of_day.model_dump(mode="json"))
    return schemas.TimeOfDay.model_validate(data)


def delete(time_of_day_id: uuid.UUID) -> schemas.TimeOfDay:
    data = get_api_client().delete(f"/api/v1/time-of-days/{time_of_day_id}")
    return schemas.TimeOfDay.model_validate(data)


def undo_delete(time_of_day_id: uuid.UUID) -> schemas.TimeOfDay:
    data = get_api_client().post(f"/api/v1/time-of-days/{time_of_day_id}/undelete")
    return schemas.TimeOfDay.model_validate(data)