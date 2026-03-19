import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(cast_rule_id: UUID) -> schemas.CastRuleShow:
    with get_session() as session:
        return schemas.CastRuleShow.model_validate(session.get(models.CastRule, cast_rule_id))


def get_all_from__project(project_id: UUID) -> list[schemas.CastRuleShow]:
    with get_session() as session:
        return [schemas.CastRuleShow.model_validate(cr) for cr in session.get(models.Project, project_id).cast_rules]


def create(project_id: UUID, name: str, rule: str, restore_id: UUID | None = None) -> schemas.CastRuleShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(project=session.get(models.Project, project_id), name=name, rule=rule)
        if restore_id:
            kwargs['id'] = restore_id
        cr = models.CastRule(**kwargs)
        session.add(cr)
        session.flush()
        return schemas.CastRuleShow.model_validate(cr)


def update(cast_rule_id: UUID, name: str, rule: str) -> schemas.CastRuleShow:
    log_function_info()
    with get_session() as session:
        cr = session.get(models.CastRule, cast_rule_id)
        cr.name = name
        cr.rule = rule
        session.flush()
        return schemas.CastRuleShow.model_validate(cr)


def set_prep_delete(cast_rule_id: UUID) -> schemas.CastRuleShow:
    log_function_info()
    with get_session() as session:
        cr = session.get(models.CastRule, cast_rule_id)
        cr.prep_delete = _utcnow()
        session.flush()
        return schemas.CastRuleShow.model_validate(cr)


def undelete(cast_rule_id: UUID) -> schemas.CastRuleShow:
    log_function_info()
    with get_session() as session:
        cr = session.get(models.CastRule, cast_rule_id)
        cr.prep_delete = None
        session.flush()
        return schemas.CastRuleShow.model_validate(cr)


def delete(cast_rule_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.CastRule, cast_rule_id))