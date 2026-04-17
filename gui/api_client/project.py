"""Desktop-API-Client: Project-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def update_name(name: str, project_id: uuid.UUID) -> schemas.Project:
    data = get_api_client().patch(f"/api/v1/projects/{project_id}/name",
                                  json={"name": name})
    return schemas.Project.model_validate(data)


def update(project: schemas.ProjectShow) -> schemas.ProjectShow:
    data = get_api_client().put(f"/api/v1/projects/{project.id}",
                                json=project.model_dump(mode="json"))
    return schemas.ProjectShow.model_validate(data)