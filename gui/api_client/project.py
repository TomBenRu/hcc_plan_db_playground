"""Desktop-API-Client: Project-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(name: str) -> schemas.ProjectShow:
    data = get_api_client().post("/api/v1/projects", json={"name": name})
    return schemas.ProjectShow.model_validate(data)


def update_name(name: str, project_id: uuid.UUID) -> schemas.Project:
    data = get_api_client().patch(f"/api/v1/projects/{project_id}/name",
                                  json={"name": name})
    return schemas.Project.model_validate(data)


def update(project: schemas.ProjectShow) -> schemas.ProjectShow:
    data = get_api_client().put(f"/api/v1/projects/{project.id}",
                                json=project.model_dump(mode="json"))
    return schemas.ProjectShow.model_validate(data)


def put_in_time_of_day(project_id: uuid.UUID, time_of_day_id: uuid.UUID) -> schemas.ProjectShow:
    data = get_api_client().post(f"/api/v1/projects/{project_id}/time-of-days/{time_of_day_id}")
    return schemas.ProjectShow.model_validate(data)


def remove_in_time_of_day(project_id: uuid.UUID, time_of_day_id: uuid.UUID) -> schemas.ProjectShow:
    data = get_api_client().delete(f"/api/v1/projects/{project_id}/time-of-days/{time_of_day_id}")
    return schemas.ProjectShow.model_validate(data)


def new_time_of_day_standard(project_id: uuid.UUID,
                              time_of_day_id: uuid.UUID) -> tuple[schemas.ProjectShow, uuid.UUID | None]:
    data = get_api_client().post(
        f"/api/v1/projects/{project_id}/time-of-day-standards/{time_of_day_id}")
    old_id = uuid.UUID(data["old_standard_id"]) if data["old_standard_id"] else None
    return schemas.ProjectShow.model_validate(data["project"]), old_id


def remove_time_of_day_standard(project_id: uuid.UUID,
                                 time_of_day_id: uuid.UUID) -> schemas.ProjectShow:
    data = get_api_client().delete(
        f"/api/v1/projects/{project_id}/time-of-day-standards/{time_of_day_id}")
    return schemas.ProjectShow.model_validate(data)


def new_time_of_day_enum_standard(time_of_day_enum_id: uuid.UUID) -> schemas.ProjectShow:
    data = get_api_client().post(
        f"/api/v1/time-of-day-enums/{time_of_day_enum_id}/project-standard")
    return schemas.ProjectShow.model_validate(data)


def remove_time_of_day_enum_standard(time_of_day_enum_id: uuid.UUID) -> schemas.ProjectShow:
    data = get_api_client().delete(
        f"/api/v1/time-of-day-enums/{time_of_day_enum_id}/project-standard")
    return schemas.ProjectShow.model_validate(data)


def put_in_excel_settings(project_id: uuid.UUID, excel_settings_id: uuid.UUID) -> schemas.ProjectShow:
    data = get_api_client().put(
        f"/api/v1/projects/{project_id}/excel-settings/{excel_settings_id}")
    return schemas.ProjectShow.model_validate(data)