"""Desktop-API: Skill-Endpunkte (/api/v1/skills)."""

import uuid

from fastapi import APIRouter, status

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/skills", tags=["desktop-skills"])


@router.post("", response_model=schemas.Skill, status_code=status.HTTP_201_CREATED)
def create_skill(body: schemas.SkillCreate, _: DesktopUser):
    return db_services.Skill.create(body)


@router.put("/{skill_id}", response_model=schemas.Skill)
def update_skill(skill_id: uuid.UUID, body: schemas.SkillUpdate, _: DesktopUser):
    return db_services.Skill.update(body)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: uuid.UUID, _: DesktopUser):
    db_services.Skill.delete(skill_id)


@router.post("/{skill_id}/prep-delete", response_model=schemas.Skill)
def prep_delete(skill_id: uuid.UUID, _: DesktopUser):
    return db_services.Skill.prep_delete(skill_id)


@router.post("/{skill_id}/undelete", response_model=schemas.Skill)
def undelete(skill_id: uuid.UUID, _: DesktopUser):
    return db_services.Skill.undelete(skill_id)