"""Desktop-API: Event-Endpunkte (/api/v1/events)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/events", tags=["desktop-events"])


class EventCreateBody(BaseModel):
    location_plan_period_id: uuid.UUID
    date: datetime.date
    time_of_day_id: uuid.UUID


class EventTimeOfDayDateBody(BaseModel):
    time_of_day_id: uuid.UUID
    date: datetime.date | None = None


class EventNotesBody(BaseModel):
    notes: str


class EventTimeOfDaysBody(BaseModel):
    time_of_days: list[schemas.TimeOfDay]


@router.post("", response_model=schemas.EventShow, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreateBody, _: DesktopUser):
    lpp = db_services.LocationPlanPeriod.get(body.location_plan_period_id)
    tod = db_services.TimeOfDay.get(body.time_of_day_id)
    event_create = schemas.EventCreate(
        location_plan_period=lpp, date=body.date, time_of_day=tod, flags=[]
    )
    return db_services.Event.create(event_create)


@router.delete("/{event_id}", response_model=schemas.EventShow)
def delete_event(event_id: uuid.UUID, _: DesktopUser):
    return db_services.Event.delete(event_id)


@router.patch("/{event_id}/time-of-day-date", status_code=status.HTTP_204_NO_CONTENT)
def update_time_of_day_and_date(event_id: uuid.UUID, body: EventTimeOfDayDateBody, _: DesktopUser):
    db_services.Event.update_time_of_day_and_date(event_id, body.time_of_day_id, body.date)


@router.patch("/{event_id}/notes", status_code=status.HTTP_204_NO_CONTENT)
def update_event_notes(event_id: uuid.UUID, body: EventNotesBody, _: DesktopUser):
    db_services.Event.update_notes(event_id, body.notes)


@router.patch("/{event_id}/time-of-days", response_model=schemas.EventShow)
def update_event_time_of_days(event_id: uuid.UUID, body: EventTimeOfDaysBody, _: DesktopUser):
    return db_services.Event.update_time_of_days(event_id, body.time_of_days)


@router.post("/{event_id}/flags/{flag_id}", response_model=schemas.EventShow)
def put_in_flag(event_id: uuid.UUID, flag_id: uuid.UUID, _: DesktopUser):
    return db_services.Event.put_in_flag(event_id, flag_id)


@router.delete("/{event_id}/flags/{flag_id}", response_model=schemas.EventShow)
def remove_flag(event_id: uuid.UUID, flag_id: uuid.UUID, _: DesktopUser):
    return db_services.Event.remove_flag(event_id, flag_id)


@router.post("/{event_id}/skill-groups/{skill_group_id}", response_model=schemas.EventShow)
def add_skill_group(event_id: uuid.UUID, skill_group_id: uuid.UUID, _: DesktopUser):
    return db_services.Event.add_skill_group(event_id, skill_group_id)


@router.delete("/{event_id}/skill-groups/{skill_group_id}", response_model=schemas.EventShow)
def remove_skill_group(event_id: uuid.UUID, skill_group_id: uuid.UUID, _: DesktopUser):
    return db_services.Event.remove_skill_group(event_id, skill_group_id)