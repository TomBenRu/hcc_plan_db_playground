"""Desktop-API: TimeOfDay-Endpunkte (/api/v1/time-of-days)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/time-of-days", tags=["desktop-time-of-days"])


class TimeOfDayCreateBody(BaseModel):
    name: str
    time_of_day_enum_id: uuid.UUID
    start: datetime.time
    end: datetime.time
    project_id: uuid.UUID
    project_standard_id: uuid.UUID | None = None


@router.post("", response_model=schemas.TimeOfDay, status_code=status.HTTP_201_CREATED)
def create_time_of_day(body: TimeOfDayCreateBody, _: DesktopUser):
    tode = db_services.TimeOfDayEnum.get(body.time_of_day_enum_id)
    project_standard = (db_services.Project.get(body.project_standard_id)
                        if body.project_standard_id else None)
    tod_create = schemas.TimeOfDayCreate(
        name=body.name, time_of_day_enum=tode,
        start=body.start, end=body.end,
        project_standard=project_standard,
    )
    return db_services.TimeOfDay.create(tod_create, body.project_id)


@router.put("/{time_of_day_id}", response_model=schemas.TimeOfDay)
def update_time_of_day(time_of_day_id: uuid.UUID, body: schemas.TimeOfDay, _: DesktopUser):
    return db_services.TimeOfDay.update(body)


@router.delete("/{time_of_day_id}", response_model=schemas.TimeOfDay)
def delete_time_of_day(time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.TimeOfDay.delete(time_of_day_id)


@router.post("/{time_of_day_id}/undelete", response_model=schemas.TimeOfDay)
def undo_delete_time_of_day(time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.TimeOfDay.undo_delete(time_of_day_id)


@router.delete("/projects/{project_id}/unused", status_code=status.HTTP_204_NO_CONTENT)
def delete_unused_in_project(project_id: uuid.UUID, _: DesktopUser):
    """Soft-loescht alle unreferenzierten TimeOfDays des Projekts."""
    db_services.TimeOfDay.delete_unused(project_id)


@router.delete("/projects/{project_id}/prep-deleted", status_code=status.HTTP_204_NO_CONTENT)
def delete_prep_deletes_in_project(project_id: uuid.UUID, _: DesktopUser):
    """Hartes Loeschen aller prep-deleted TimeOfDays des Projekts (irreversibel)."""
    db_services.TimeOfDay.delete_prep_deletes(project_id)