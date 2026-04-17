"""Desktop-API: LocationOfWork-Endpunkte (/api/v1/locations-of-work).

Hinweis: time_of_day-/skill_group-Collection-Ops folgen in Phase 5b/5d.
"""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/locations-of-work", tags=["desktop-locations-of-work"])


class FixedCastBody(BaseModel):
    fixed_cast: str
    fixed_cast_only_if_available: bool


@router.put("/{location_id}", response_model=schemas.LocationOfWorkShow)
def update_location(location_id: uuid.UUID, body: schemas.LocationOfWorkShow, _: DesktopUser):
    return db_services.LocationOfWork.update(body)


@router.patch("/{location_id}/fixed-cast", response_model=schemas.LocationOfWorkShow)
def update_fixed_cast(location_id: uuid.UUID, body: FixedCastBody, _: DesktopUser):
    return db_services.LocationOfWork.update_fixed_cast(
        location_id, body.fixed_cast, body.fixed_cast_only_if_available,
    )