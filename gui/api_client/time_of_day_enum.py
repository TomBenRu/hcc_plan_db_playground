"""Desktop-API-Client: TimeOfDayEnum-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(time_of_day_enum: schemas.TimeOfDayEnumCreate,
           time_of_day_enum_id: uuid.UUID | None = None) -> schemas.TimeOfDayEnumShow:
    data = get_api_client().post("/api/v1/time-of-day-enums", json={
        "name": time_of_day_enum.name,
        "abbreviation": time_of_day_enum.abbreviation,
        "time_index": time_of_day_enum.time_index,
        "project_id": str(time_of_day_enum.project.id),
        "time_of_day_enum_id": str(time_of_day_enum_id) if time_of_day_enum_id else None,
    })
    return schemas.TimeOfDayEnumShow.model_validate(data)


def update(time_of_day_enum: schemas.TimeOfDayEnum) -> schemas.TimeOfDayEnumShow:
    data = get_api_client().put(f"/api/v1/time-of-day-enums/{time_of_day_enum.id}",
                                json=time_of_day_enum.model_dump(mode="json"))
    return schemas.TimeOfDayEnumShow.model_validate(data)


def prep_delete(tode_id: uuid.UUID) -> schemas.TimeOfDayEnumShow:
    data = get_api_client().post(f"/api/v1/time-of-day-enums/{tode_id}/prep-delete")
    return schemas.TimeOfDayEnumShow.model_validate(data)


def undo_prep_delete(tode_id: uuid.UUID) -> schemas.TimeOfDayEnumShow:
    data = get_api_client().post(f"/api/v1/time-of-day-enums/{tode_id}/undo-prep-delete")
    return schemas.TimeOfDayEnumShow.model_validate(data)