import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(skill_group_id: UUID) -> schemas.SkillGroupShow:
    with get_session() as session:
        return schemas.SkillGroupShow.model_validate(session.get(models.SkillGroup, skill_group_id))


def get_all_from__location_of_work(location_of_work_id: UUID) -> list[schemas.SkillGroupShow]:
    with get_session() as session:
        return [schemas.SkillGroupShow.model_validate(sg)
                for sg in session.get(models.LocationOfWork, location_of_work_id).skill_groups]


def get_all_from__event(event_id: UUID) -> list[schemas.SkillGroupShow]:
    with get_session() as session:
        return [schemas.SkillGroupShow.model_validate(sg)
                for sg in session.get(models.Event, event_id).skill_groups]


def create(skill_group: schemas.SkillGroupCreate, skill_group_id: UUID = None) -> schemas.SkillGroupShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(skill=session.get(models.Skill, skill_group.skill_id), nr_actors=skill_group.nr_persons)
        if skill_group_id:
            kwargs['id'] = skill_group_id
        sg = models.SkillGroup(**kwargs)
        session.add(sg)
        session.flush()
        return schemas.SkillGroupShow.model_validate(sg)


def delete(skill_group_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.SkillGroup, skill_group_id))


def update(skill_group: schemas.SkillGroupUpdate) -> schemas.SkillGroupShow:
    log_function_info()
    with get_session() as session:
        sg = session.get(models.SkillGroup, skill_group.id)
        sg.skill = session.get(models.Skill, skill_group.skill_id)
        sg.nr_actors = skill_group.nr_persons
        session.flush()
        return schemas.SkillGroupShow.model_validate(sg)