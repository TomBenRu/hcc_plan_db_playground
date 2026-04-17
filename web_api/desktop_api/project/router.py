"""Desktop-API: Project-Endpunkte (/api/v1/projects)."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/projects", tags=["desktop-projects"])


class ProjectNameBody(BaseModel):
    name: str


@router.patch("/{project_id}/name", response_model=schemas.Project)
def update_project_name(project_id: uuid.UUID, body: ProjectNameBody, _: DesktopUser):
    return db_services.Project.update_name(body.name, project_id)


@router.put("/{project_id}", response_model=schemas.ProjectShow)
def update_project(project_id: uuid.UUID, body: schemas.ProjectShow, _: DesktopUser):
    return db_services.Project.update(body)