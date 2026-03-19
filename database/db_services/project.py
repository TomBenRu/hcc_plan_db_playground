"""Service-Funktionen für Project (Projekt / Mandant).

Ein Projekt ist die oberste Organisationsebene und enthält Teams, Personen,
Standorte und Tageszeit-Definitionen. Verwaltet projektweite Tageszeit-Defaults
(`time_of_day_standards`, `time_of_day_enum_standards`) die als Vorlage für
neue Entitäten dienen.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(project_id: UUID) -> schemas.ProjectShow:
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        return schemas.ProjectShow.model_validate(project_db)


def get_all() -> list[schemas.ProjectShow]:
    with get_session() as session:
        projects = session.exec(select(models.Project)).all()
        return [schemas.ProjectShow.model_validate(p) for p in projects]


def create(name: str) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = models.Project(name=name)
        session.add(project_db)
        session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def update_name(name: str, project_id) -> schemas.Project:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        project_db.name = name
        session.flush()
        return schemas.Project.model_validate(project_db)


def update(project: schemas.ProjectShow) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project.id)
        for k, v in project.model_dump(include={'name', 'active'}).items():
            setattr(project_db, k, v)
        project_db.time_of_days.clear()
        for t_o_d in project.time_of_days:
            project_db.time_of_days.append(session.get(models.TimeOfDay, t_o_d.id))
        session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def put_in_time_of_day(project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        project_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def remove_in_time_of_day(project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        project_db.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def new_time_of_day_standard(project_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ProjectShow, UUID | None]:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        time_of_day_db = session.get(models.TimeOfDay, time_of_day_id)
        old_time_of_day_standard_id = None
        for t_o_d in list(project_db.time_of_day_standards):
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                project_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        project_db.time_of_day_standards.append(time_of_day_db)
        session.flush()
        return schemas.ProjectShow.model_validate(project_db), old_time_of_day_standard_id


def remove_time_of_day_standard(project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        project_db.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def new_time_of_day_enum_standard(time_of_day_enum_id: UUID) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        tode_db = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
        tode_db.project.time_of_day_enum_standards.append(tode_db)
        session.flush()
        return schemas.ProjectShow.model_validate(tode_db.project)


def remove_time_of_day_enum_standard(time_of_day_enum_id: UUID) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        tode_db = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
        tode_db.project.time_of_day_enum_standards.remove(tode_db)
        session.flush()
        return schemas.ProjectShow.model_validate(tode_db.project)