"""Desktop-API: Project-Endpunkte (/api/v1/projects)."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/projects", tags=["desktop-projects"])


class ProjectNameBody(BaseModel):
    name: str


class NewTimeOfDayStandardResponse(BaseModel):
    project: schemas.ProjectShow
    old_standard_id: uuid.UUID | None


@router.post("", response_model=schemas.ProjectShow, status_code=201)
def create_project(body: ProjectNameBody, _: DesktopUser):
    """Legt ein neues Projekt an. Bootstrap-Aktion — kein Soft-Delete vorhanden."""
    return db_services.Project.create(body.name)


@router.patch("/{project_id}/name", response_model=schemas.Project)
def update_project_name(project_id: uuid.UUID, body: ProjectNameBody, _: DesktopUser):
    return db_services.Project.update_name(body.name, project_id)


@router.put("/{project_id}", response_model=schemas.ProjectShow)
def update_project(project_id: uuid.UUID, body: schemas.ProjectShow, _: DesktopUser):
    return db_services.Project.update(body)


@router.post("/{project_id}/time-of-days/{time_of_day_id}", response_model=schemas.ProjectShow)
def put_in_time_of_day(project_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.Project.put_in_time_of_day(project_id, time_of_day_id)


@router.delete("/{project_id}/time-of-days/{time_of_day_id}", response_model=schemas.ProjectShow)
def remove_in_time_of_day(project_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.Project.remove_in_time_of_day(project_id, time_of_day_id)


@router.post("/{project_id}/time-of-day-standards/{time_of_day_id}",
             response_model=NewTimeOfDayStandardResponse)
def new_time_of_day_standard(project_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    project, old_id = db_services.Project.new_time_of_day_standard(project_id, time_of_day_id)
    return NewTimeOfDayStandardResponse(project=project, old_standard_id=old_id)


@router.delete("/{project_id}/time-of-day-standards/{time_of_day_id}",
               response_model=schemas.ProjectShow)
def remove_time_of_day_standard(project_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.Project.remove_time_of_day_standard(project_id, time_of_day_id)