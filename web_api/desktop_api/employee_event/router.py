"""Desktop-API: EmployeeEvent-Endpunkte (/api/v1/employee-events)."""

import uuid

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from employee_event.db_service import EmployeeEventService
from employee_event.schemas.common_schemas import ErrorResponseSchema, SuccessResponseSchema
from employee_event.schemas.employee_event_schemas import (
    EventCreate, EventDetail, EventUpdate,
)
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/employee-events", tags=["desktop-employee-events"])


class GoogleCalendarEventIdBody(BaseModel):
    google_calendar_event_id: str


def _check(result):
    """Wirft HTTPException falls Service ErrorResponseSchema zurueckgibt."""
    if isinstance(result, ErrorResponseSchema):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result.message)
    return result


@router.post("", response_model=EventDetail, status_code=status.HTTP_201_CREATED)
def create_event(body: EventCreate, _: DesktopUser):
    return _check(EmployeeEventService().create_event(body))


@router.put("/{event_id}", response_model=EventDetail)
def update_event(event_id: uuid.UUID, body: EventUpdate, _: DesktopUser):
    return _check(EmployeeEventService().update_event(body))


@router.delete("/{event_id}", response_model=SuccessResponseSchema)
def delete_event(event_id: uuid.UUID, _: DesktopUser):
    return _check(EmployeeEventService().delete_event(event_id, soft_delete=True))


@router.post("/{event_id}/undelete", response_model=SuccessResponseSchema)
def undelete_event(event_id: uuid.UUID, _: DesktopUser):
    return _check(EmployeeEventService().undelete_event(event_id))


@router.patch("/{event_id}/google-calendar-id", response_model=SuccessResponseSchema)
def update_google_calendar_id(event_id: uuid.UUID, body: GoogleCalendarEventIdBody, _: DesktopUser):
    return _check(EmployeeEventService().update_google_calendar_event_id(
        event_id, body.google_calendar_event_id))