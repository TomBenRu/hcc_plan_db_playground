"""Desktop-API: LocationOfWork-Endpunkte (/api/v1/locations-of-work).

Hinweis: skill_group-Collection-Ops folgen in Phase 5d.
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


class NewTimeOfDayStandardResponse(BaseModel):
    location_of_work: schemas.LocationOfWorkShow
    old_standard_id: uuid.UUID | None


@router.put("/{location_id}", response_model=schemas.LocationOfWorkShow)
def update_location(location_id: uuid.UUID, body: schemas.LocationOfWorkShow, _: DesktopUser):
    return db_services.LocationOfWork.update(body)


@router.patch("/{location_id}/fixed-cast", response_model=schemas.LocationOfWorkShow)
def update_fixed_cast(location_id: uuid.UUID, body: FixedCastBody, _: DesktopUser):
    return db_services.LocationOfWork.update_fixed_cast(
        location_id, body.fixed_cast, body.fixed_cast_only_if_available,
    )


@router.post("/{location_id}/time-of-days/{time_of_day_id}",
             response_model=schemas.LocationOfWorkShow)
def put_in_time_of_day(location_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.LocationOfWork.put_in_time_of_day(location_id, time_of_day_id)


@router.delete("/{location_id}/time-of-days/{time_of_day_id}",
               response_model=schemas.LocationOfWorkShow)
def remove_in_time_of_day(location_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.LocationOfWork.remove_in_time_of_day(location_id, time_of_day_id)


@router.post("/{location_id}/time-of-day-standards/{time_of_day_id}",
             response_model=NewTimeOfDayStandardResponse)
def new_time_of_day_standard(location_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    loc, old_id = db_services.LocationOfWork.new_time_of_day_standard(location_id, time_of_day_id)
    return NewTimeOfDayStandardResponse(location_of_work=loc, old_standard_id=old_id)


@router.delete("/{location_id}/time-of-day-standards/{time_of_day_id}",
               response_model=schemas.LocationOfWorkShow)
def remove_time_of_day_standard(location_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.LocationOfWork.remove_time_of_day_standard(location_id, time_of_day_id)