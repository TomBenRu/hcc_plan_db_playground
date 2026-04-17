"""Desktop-API: TimeOfDayEnum-Endpunkte (/api/v1/time-of-day-enums)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/time-of-day-enums", tags=["desktop-time-of-day-enums"])


class TimeOfDayEnumCreateBody(BaseModel):
    name: str
    abbreviation: str
    time_index: int
    project_id: uuid.UUID
    time_of_day_enum_id: uuid.UUID | None = None


@router.post("", response_model=schemas.TimeOfDayEnumShow, status_code=status.HTTP_201_CREATED)
def create_time_of_day_enum(body: TimeOfDayEnumCreateBody, _: DesktopUser):
    project = db_services.Project.get(body.project_id)
    tode_create = schemas.TimeOfDayEnumCreate(
        name=body.name, abbreviation=body.abbreviation,
        time_index=body.time_index, project=project,
    )
    return db_services.TimeOfDayEnum.create(tode_create, body.time_of_day_enum_id)


@router.put("/{tode_id}", response_model=schemas.TimeOfDayEnumShow)
def update_time_of_day_enum(tode_id: uuid.UUID, body: schemas.TimeOfDayEnum, _: DesktopUser):
    return db_services.TimeOfDayEnum.update(body)


@router.post("/{tode_id}/prep-delete", response_model=schemas.TimeOfDayEnumShow)
def prep_delete(tode_id: uuid.UUID, _: DesktopUser):
    return db_services.TimeOfDayEnum.prep_delete(tode_id)


@router.post("/{tode_id}/undo-prep-delete", response_model=schemas.TimeOfDayEnumShow)
def undo_prep_delete(tode_id: uuid.UUID, _: DesktopUser):
    return db_services.TimeOfDayEnum.undo_prep_delete(tode_id)


@router.post("/{tode_id}/project-standard", response_model=schemas.ProjectShow)
def new_project_standard(tode_id: uuid.UUID, _: DesktopUser):
    return db_services.Project.new_time_of_day_enum_standard(tode_id)


@router.delete("/{tode_id}/project-standard", response_model=schemas.ProjectShow)
def remove_project_standard(tode_id: uuid.UUID, _: DesktopUser):
    return db_services.Project.remove_time_of_day_enum_standard(tode_id)