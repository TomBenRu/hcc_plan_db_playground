import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
    with get_session() as session:
        return schemas.TimeOfDayEnumShow.model_validate(session.get(models.TimeOfDayEnum, time_of_day_enum_id))


def get_all_from__project(project_id: UUID) -> list[schemas.TimeOfDayEnumShow]:
    with get_session() as session:
        return [schemas.TimeOfDayEnumShow.model_validate(e) for e in session.get(models.Project, project_id).time_of_day_enums]


def create(time_of_day_enum: schemas.TimeOfDayEnumCreate,
           time_of_day_enum_id: UUID = None) -> schemas.TimeOfDayEnumShow:
    log_function_info()
    with get_session() as session:
        kwargs = dict(name=time_of_day_enum.name, abbreviation=time_of_day_enum.abbreviation,
                      time_index=time_of_day_enum.time_index,
                      project=session.get(models.Project, time_of_day_enum.project.id))
        if time_of_day_enum_id:
            kwargs['id'] = time_of_day_enum_id
        tode = models.TimeOfDayEnum(**kwargs)
        session.add(tode)
        session.flush()
        return schemas.TimeOfDayEnumShow.model_validate(tode)


def update(time_of_day_enum: schemas.TimeOfDayEnum) -> schemas.TimeOfDayEnumShow:
    log_function_info()
    with get_session() as session:
        tode = session.get(models.TimeOfDayEnum, time_of_day_enum.id)
        for k, v in time_of_day_enum.model_dump(include={'name', 'abbreviation', 'time_index'}).items():
            setattr(tode, k, v)
        session.flush()
        return schemas.TimeOfDayEnumShow.model_validate(tode)


def prep_delete(time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
    log_function_info()
    with get_session() as session:
        tode = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
        tode.prep_delete = _utcnow()
        session.flush()
        return schemas.TimeOfDayEnumShow.model_validate(tode)


def undo_prep_delete(time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
    log_function_info()
    with get_session() as session:
        tode = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
        tode.prep_delete = None
        session.flush()
        return schemas.TimeOfDayEnumShow.model_validate(tode)


def delete(time_of_day_enum_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.TimeOfDayEnum, time_of_day_enum_id))


def consolidate_indexes(project_id: UUID):
    log_function_info()
    with get_session() as session:
        enums = session.exec(select(models.TimeOfDayEnum).where(
            models.TimeOfDayEnum.project_id == project_id,
            models.TimeOfDayEnum.prep_delete.is_(None))).all()
        for i, tode in enumerate(sorted(enums, key=lambda x: x.time_index), start=1):
            tode.time_index = i
            session.flush()