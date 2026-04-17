"""Desktop-API: AvailDay-Endpunkte (/api/v1/avail-days)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/avail-days", tags=["desktop-avail-days"])


class AvailDayCreateBody(BaseModel):
    date: datetime.date
    actor_plan_period_id: uuid.UUID
    time_of_day_id: uuid.UUID


class AvailDayTimeOfDayBody(BaseModel):
    time_of_day_id: uuid.UUID


class AvailDayTimeOfDaysBody(BaseModel):
    time_of_days: list[schemas.TimeOfDay]


@router.post("", response_model=schemas.AvailDayShow, status_code=status.HTTP_201_CREATED)
def create_avail_day(body: AvailDayCreateBody, _: DesktopUser):
    actor_plan_period = db_services.ActorPlanPeriod.get(body.actor_plan_period_id)
    time_of_day = db_services.TimeOfDay.get(body.time_of_day_id)
    avail_day_create = schemas.AvailDayCreate(
        date=body.date, actor_plan_period=actor_plan_period, time_of_day=time_of_day
    )
    return db_services.AvailDay.create(avail_day_create)


@router.delete("/{avail_day_id}", response_model=schemas.AvailDayShow)
def delete_avail_day(avail_day_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.delete(avail_day_id)


@router.patch("/{avail_day_id}/time-of-day", response_model=schemas.AvailDayShow)
def update_time_of_day(avail_day_id: uuid.UUID, body: AvailDayTimeOfDayBody, _: DesktopUser):
    return db_services.AvailDay.update_time_of_day(avail_day_id, body.time_of_day_id)


@router.patch("/{avail_day_id}/time-of-days", response_model=schemas.AvailDayShow)
def update_time_of_days(avail_day_id: uuid.UUID, body: AvailDayTimeOfDaysBody, _: DesktopUser):
    return db_services.AvailDay.update_time_of_days(avail_day_id, body.time_of_days)