"""Desktop-API-Client: Appointment-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(appointment: schemas.AppointmentCreate, plan_id: uuid.UUID) -> schemas.AppointmentShow:
    data = get_api_client().post("/api/v1/appointments", json={
        "plan_id": str(plan_id),
        "appointment": appointment.model_dump(mode="json"),
    })
    return schemas.AppointmentShow.model_validate(data)


def create_bulk(appointments: list[schemas.AppointmentCreate], plan_id: uuid.UUID) -> list[uuid.UUID]:
    data = get_api_client().post("/api/v1/appointments/bulk", json={
        "plan_id": str(plan_id),
        "appointments": [a.model_dump(mode="json") for a in appointments],
    })
    return [uuid.UUID(i) for i in data["ids"]]


def update_avail_days(appointment_id: uuid.UUID, avail_day_ids: list[uuid.UUID]) -> None:
    get_api_client().patch(f"/api/v1/appointments/{appointment_id}/avail-days",
                           json={"avail_day_ids": [str(i) for i in avail_day_ids]})


def update_notes(appointment_id: uuid.UUID, notes: str) -> None:
    get_api_client().patch(f"/api/v1/appointments/{appointment_id}/notes",
                           json={"notes": notes})


def update_guests(appointment_id: uuid.UUID, guests: list[str]) -> None:
    get_api_client().patch(f"/api/v1/appointments/{appointment_id}/guests",
                           json={"guests": guests})


def update_event(appointment_id: uuid.UUID, event_id: uuid.UUID) -> None:
    get_api_client().patch(f"/api/v1/appointments/{appointment_id}/event",
                           json={"event_id": str(event_id)})


def delete(appointment_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/appointments/{appointment_id}")


def undelete(appointment_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/appointments/{appointment_id}/undelete")


def delete_bulk(appointment_ids: list[uuid.UUID]) -> None:
    get_api_client().delete("/api/v1/appointments/bulk",
                            json={"appointment_ids": [str(i) for i in appointment_ids]})


def undelete_bulk(appointment_ids: list[uuid.UUID]) -> None:
    get_api_client().post("/api/v1/appointments/bulk/undelete",
                          json={"appointment_ids": [str(i) for i in appointment_ids]})


def reassign(appointment_id: uuid.UUID, old_person_id: uuid.UUID, new_person_id: uuid.UUID) -> None:
    get_api_client().patch(f"/api/v1/appointments/{appointment_id}/reassign", json={
        "old_person_id": str(old_person_id),
        "new_person_id": str(new_person_id),
    })
