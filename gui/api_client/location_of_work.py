"""Desktop-API-Client: LocationOfWork-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(location: schemas.LocationOfWorkCreate,
           project_id: uuid.UUID) -> schemas.LocationOfWork:
    data = get_api_client().post("/api/v1/locations-of-work", json={
        "location": location.model_dump(mode="json"),
        "project_id": str(project_id),
    })
    return schemas.LocationOfWork.model_validate(data)


def delete(location_id: uuid.UUID) -> schemas.LocationOfWork:
    data = get_api_client().delete(f"/api/v1/locations-of-work/{location_id}")
    return schemas.LocationOfWork.model_validate(data)


def undelete(location_id: uuid.UUID) -> schemas.LocationOfWork:
    data = get_api_client().post(f"/api/v1/locations-of-work/{location_id}/undelete")
    return schemas.LocationOfWork.model_validate(data)


def update_notes(location_id: uuid.UUID, notes: str) -> schemas.LocationOfWorkShow:
    data = get_api_client().patch(f"/api/v1/locations-of-work/{location_id}/notes",
                                  json={"notes": notes})
    return schemas.LocationOfWorkShow.model_validate(data)


def update(location: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
    data = get_api_client().put(f"/api/v1/locations-of-work/{location.id}",
                                json=location.model_dump(mode="json"))
    return schemas.LocationOfWorkShow.model_validate(data)


def update_fixed_cast(location_id: uuid.UUID, fixed_cast: str,
                      fixed_cast_only_if_available: bool) -> schemas.LocationOfWorkShow:
    data = get_api_client().patch(f"/api/v1/locations-of-work/{location_id}/fixed-cast", json={
        "fixed_cast": fixed_cast,
        "fixed_cast_only_if_available": fixed_cast_only_if_available,
    })
    return schemas.LocationOfWorkShow.model_validate(data)


def put_in_time_of_day(location_id: uuid.UUID,
                        time_of_day_id: uuid.UUID) -> schemas.LocationOfWorkShow:
    data = get_api_client().post(
        f"/api/v1/locations-of-work/{location_id}/time-of-days/{time_of_day_id}")
    return schemas.LocationOfWorkShow.model_validate(data)


def remove_in_time_of_day(location_id: uuid.UUID,
                           time_of_day_id: uuid.UUID) -> schemas.LocationOfWorkShow:
    data = get_api_client().delete(
        f"/api/v1/locations-of-work/{location_id}/time-of-days/{time_of_day_id}")
    return schemas.LocationOfWorkShow.model_validate(data)


def new_time_of_day_standard(location_id: uuid.UUID, time_of_day_id: uuid.UUID
                              ) -> tuple[schemas.LocationOfWorkShow, uuid.UUID | None]:
    data = get_api_client().post(
        f"/api/v1/locations-of-work/{location_id}/time-of-day-standards/{time_of_day_id}")
    old_id = uuid.UUID(data["old_standard_id"]) if data["old_standard_id"] else None
    return schemas.LocationOfWorkShow.model_validate(data["location_of_work"]), old_id


def remove_time_of_day_standard(location_id: uuid.UUID,
                                 time_of_day_id: uuid.UUID) -> schemas.LocationOfWorkShow:
    data = get_api_client().delete(
        f"/api/v1/locations-of-work/{location_id}/time-of-day-standards/{time_of_day_id}")
    return schemas.LocationOfWorkShow.model_validate(data)


def add_skill_group(location_id: uuid.UUID,
                     skill_group_id: uuid.UUID) -> schemas.LocationOfWorkShow:
    data = get_api_client().post(
        f"/api/v1/locations-of-work/{location_id}/skill-groups/{skill_group_id}")
    return schemas.LocationOfWorkShow.model_validate(data)


def remove_skill_group(location_id: uuid.UUID,
                        skill_group_id: uuid.UUID) -> schemas.LocationOfWorkShow:
    data = get_api_client().delete(
        f"/api/v1/locations-of-work/{location_id}/skill-groups/{skill_group_id}")
    return schemas.LocationOfWorkShow.model_validate(data)