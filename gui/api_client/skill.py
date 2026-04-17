"""Desktop-API-Client: Skill-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(skill: schemas.SkillCreate) -> schemas.Skill:
    data = get_api_client().post("/api/v1/skills", json=skill.model_dump(mode="json"))
    return schemas.Skill.model_validate(data)


def update(skill: schemas.SkillUpdate) -> schemas.Skill:
    data = get_api_client().put(f"/api/v1/skills/{skill.id}",
                                json=skill.model_dump(mode="json"))
    return schemas.Skill.model_validate(data)


def delete(skill_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/skills/{skill_id}")


def prep_delete(skill_id: uuid.UUID) -> schemas.Skill:
    data = get_api_client().post(f"/api/v1/skills/{skill_id}/prep-delete")
    return schemas.Skill.model_validate(data)


def undelete(skill_id: uuid.UUID) -> schemas.Skill:
    data = get_api_client().post(f"/api/v1/skills/{skill_id}/undelete")
    return schemas.Skill.model_validate(data)