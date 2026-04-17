"""Desktop-API: Appointment-Endpunkte (/api/v1/appointments)."""

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel import Session

from database import db_services, schemas
from web_api.dependencies import get_db_session
from web_api.desktop_api.auth import DesktopUser
from web_api.plan_adjustment.service import reassign_appointment

router = APIRouter(prefix="/appointments", tags=["desktop-appointments"])


# ── Request-Bodies ────────────────────────────────────────────────────────────


class AppointmentCreateBody(BaseModel):
    plan_id: uuid.UUID
    appointment: schemas.AppointmentCreate


class AppointmentBulkCreateBody(BaseModel):
    plan_id: uuid.UUID
    appointments: list[schemas.AppointmentCreate]


class AppointmentBulkIdsBody(BaseModel):
    appointment_ids: list[uuid.UUID]


class AppointmentAvailDaysBody(BaseModel):
    avail_day_ids: list[uuid.UUID]


class AppointmentNotesBody(BaseModel):
    notes: str


class AppointmentGuestsBody(BaseModel):
    guests: list[str]


class AppointmentEventBody(BaseModel):
    event_id: uuid.UUID


class AppointmentReassignBody(BaseModel):
    old_person_id: uuid.UUID
    new_person_id: uuid.UUID


class BulkCreateResponse(BaseModel):
    ids: list[uuid.UUID]


# ── Endpunkte ─────────────────────────────────────────────────────────────────


@router.post("", response_model=schemas.AppointmentShow, status_code=status.HTTP_201_CREATED)
def create_appointment(body: AppointmentCreateBody, _: DesktopUser):
    return db_services.Appointment.create(body.appointment, body.plan_id)


# /bulk* MUSS vor /{appointment_id} stehen — sonst matcht "bulk" als UUID.
@router.post("/bulk", response_model=BulkCreateResponse, status_code=status.HTTP_201_CREATED)
def create_appointments_bulk(body: AppointmentBulkCreateBody, _: DesktopUser):
    ids = db_services.Appointment.create_bulk(body.appointments, body.plan_id)
    return BulkCreateResponse(ids=ids)


@router.delete("/bulk", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointments_bulk(body: AppointmentBulkIdsBody, _: DesktopUser):
    db_services.Appointment.delete_bulk(body.appointment_ids)


@router.post("/bulk/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_appointments_bulk(body: AppointmentBulkIdsBody, _: DesktopUser):
    db_services.Appointment.undelete_bulk(body.appointment_ids)


@router.patch("/{appointment_id}/avail-days", status_code=status.HTTP_204_NO_CONTENT)
def update_avail_days(appointment_id: uuid.UUID, body: AppointmentAvailDaysBody, _: DesktopUser):
    db_services.Appointment.update_avail_days(appointment_id, body.avail_day_ids)


@router.patch("/{appointment_id}/notes", status_code=status.HTTP_204_NO_CONTENT)
def update_appointment_notes(appointment_id: uuid.UUID, body: AppointmentNotesBody, _: DesktopUser):
    db_services.Appointment.update_notes(appointment_id, body.notes)


@router.patch("/{appointment_id}/guests", status_code=status.HTTP_204_NO_CONTENT)
def update_guests(appointment_id: uuid.UUID, body: AppointmentGuestsBody, _: DesktopUser):
    db_services.Appointment.update_guests(appointment_id, body.guests)


@router.patch("/{appointment_id}/event", status_code=status.HTTP_204_NO_CONTENT)
def update_appointment_event(appointment_id: uuid.UUID, body: AppointmentEventBody, _: DesktopUser):
    db_services.Appointment.update_event(appointment_id, body.event_id)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(appointment_id: uuid.UUID, _: DesktopUser):
    db_services.Appointment.delete(appointment_id)


@router.post("/{appointment_id}/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_appointment(appointment_id: uuid.UUID, _: DesktopUser):
    db_services.Appointment.undelete(appointment_id)


@router.patch("/{appointment_id}/reassign", status_code=status.HTTP_204_NO_CONTENT)
def reassign(
    appointment_id: uuid.UUID,
    body: AppointmentReassignBody,
    _: DesktopUser,
    session: Session = Depends(get_db_session),
):
    reassign_appointment(session, appointment_id, body.old_person_id, body.new_person_id)
