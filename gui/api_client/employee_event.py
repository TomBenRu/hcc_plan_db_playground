"""Desktop-API-Client: EmployeeEvent-Operationen."""

import uuid

from employee_event.schemas.common_schemas import SuccessResponseSchema
from employee_event.schemas.employee_event_schemas import (
    EventCreate, EventDetail, EventUpdate,
)
from gui.api_client.client import get_api_client


def create(event: EventCreate) -> EventDetail:
    data = get_api_client().post("/api/v1/employee-events",
                                 json=event.model_dump(mode="json"))
    return EventDetail.model_validate(data)


def update(event: EventUpdate) -> EventDetail:
    data = get_api_client().put(f"/api/v1/employee-events/{event.id}",
                                json=event.model_dump(mode="json"))
    return EventDetail.model_validate(data)


def delete(event_id: uuid.UUID) -> SuccessResponseSchema:
    data = get_api_client().delete(f"/api/v1/employee-events/{event_id}")
    return SuccessResponseSchema.model_validate(data)


def undelete(event_id: uuid.UUID) -> SuccessResponseSchema:
    data = get_api_client().post(f"/api/v1/employee-events/{event_id}/undelete")
    return SuccessResponseSchema.model_validate(data)


def update_google_calendar_id(event_id: uuid.UUID,
                               google_calendar_event_id: str) -> SuccessResponseSchema:
    data = get_api_client().patch(
        f"/api/v1/employee-events/{event_id}/google-calendar-id",
        json={"google_calendar_event_id": google_calendar_event_id},
    )
    return SuccessResponseSchema.model_validate(data)