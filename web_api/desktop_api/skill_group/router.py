"""Desktop-API: SkillGroup-Endpunkte (/api/v1/skill-groups)."""

import uuid

from fastapi import APIRouter, status

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/skill-groups", tags=["desktop-skill-groups"])


@router.post("", response_model=schemas.SkillGroupShow, status_code=status.HTTP_201_CREATED)
def create_skill_group(body: schemas.SkillGroupCreate, _: DesktopUser):
    return db_services.SkillGroup.create(body)


@router.put("/{skill_group_id}", response_model=schemas.SkillGroupShow)
def update_skill_group(skill_group_id: uuid.UUID, body: schemas.SkillGroupUpdate, _: DesktopUser):
    return db_services.SkillGroup.update(body)


@router.delete("/{skill_group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill_group(skill_group_id: uuid.UUID, _: DesktopUser):
    db_services.SkillGroup.delete(skill_group_id)