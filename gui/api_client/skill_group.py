"""Desktop-API-Client: SkillGroup-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(skill_group: schemas.SkillGroupCreate) -> schemas.SkillGroupShow:
    data = get_api_client().post("/api/v1/skill-groups",
                                 json=skill_group.model_dump(mode="json"))
    return schemas.SkillGroupShow.model_validate(data)


def update(skill_group: schemas.SkillGroupUpdate) -> schemas.SkillGroupShow:
    data = get_api_client().put(f"/api/v1/skill-groups/{skill_group.id}",
                                json=skill_group.model_dump(mode="json"))
    return schemas.SkillGroupShow.model_validate(data)


def delete(skill_group_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/skill-groups/{skill_group_id}")