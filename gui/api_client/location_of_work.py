"""Desktop-API-Client: LocationOfWork-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


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