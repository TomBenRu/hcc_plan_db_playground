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