import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def create(skill: schemas.SkillCreate, skill_id: UUID = None) -> schemas.Skill:
    log_function_info()
    with get_session() as session:
        kwargs = dict(name=skill.name, notes=skill.notes, project=session.get(models.Project, skill.project_id))
        if skill_id:
            kwargs['id'] = skill_id
        obj = models.Skill(**kwargs)
        session.add(obj)
        session.flush()
        return schemas.Skill.model_validate(obj)


def get(skill_id: UUID) -> schemas.Skill:
    with get_session() as session:
        return schemas.Skill.model_validate(session.get(models.Skill, skill_id))


def get_all_from__person(person_id: UUID) -> list[schemas.Skill]:
    with get_session() as session:
        return [schemas.Skill.model_validate(s) for s in session.get(models.Person, person_id).skills]


def get_all_from__project(project_id: UUID) -> list[schemas.Skill]:
    with get_session() as session:
        return [schemas.Skill.model_validate(s) for s in session.get(models.Project, project_id).skills]


def update(skill: schemas.SkillUpdate) -> schemas.Skill:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.Skill, skill.id)
        obj.name = skill.name
        obj.notes = skill.notes
        session.flush()
        return schemas.Skill.model_validate(obj)


def prep_delete(skill_id: UUID, prep_delete: datetime.datetime = None) -> schemas.Skill:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.Skill, skill_id)
        obj.prep_delete = prep_delete or _utcnow()
        session.flush()
        return schemas.Skill.model_validate(obj)


def undelete(skill_id: UUID) -> schemas.Skill:
    log_function_info()
    with get_session() as session:
        obj = session.get(models.Skill, skill_id)
        obj.prep_delete = None
        session.flush()
        return schemas.Skill.model_validate(obj)


def delete_prep_deletes_from__project(project_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        skills = session.exec(select(models.Skill).where(
            models.Skill.project_id == project_id, models.Skill.prep_delete.isnot(None))).all()
        for s in skills:
            session.delete(s)


def delete(skill_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.Skill, skill_id))


def is_used(skill_id: UUID) -> bool:
    with get_session() as session:
        s = session.get(models.Skill, skill_id)
        return bool(s.persons or s.avail_days or s.skill_groups)