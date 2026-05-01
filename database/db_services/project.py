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
from ._eager_loading import project_show_options
from ._soft_delete import active_team_pp_criteria


def get(project_id: UUID, *, include_deleted_teams: bool = False) -> schemas.ProjectShow:
    """Lädt ein Projekt mit allen Beziehungen.

    `include_deleted_teams=False` (Default) blendet soft-deleted Teams (und
    deren PlanPeriods) aus der `Project.teams[]`-Liste aus.
    """
    with get_session() as session:
        stmt = (select(models.Project)
                .where(models.Project.id == project_id)
                .options(*project_show_options()))
        if not include_deleted_teams:
            stmt = stmt.options(*active_team_pp_criteria())
        project = session.exec(stmt).unique().one()
        return schemas.ProjectShow.model_validate(project)


def get_all(*, include_deleted_teams: bool = False) -> list[schemas.ProjectShow]:
    with get_session() as session:
        stmt = select(models.Project)
        if not include_deleted_teams:
            stmt = stmt.options(*active_team_pp_criteria())
        projects = session.exec(stmt).all()
        return [schemas.ProjectShow.model_validate(p) for p in projects]


def exists_any() -> bool:
    """Gibt True zurück, wenn mindestens ein Projekt existiert (kein model_validate)."""
    with get_session() as session:
        return session.exec(select(models.Project).limit(1)).first() is not None


def get_first_id() -> 'UUID | None':
    """Gibt die ID des ersten Projekts zurück ohne model_validate (schneller Startup-Pfad)."""
    with get_session() as session:
        project = session.exec(select(models.Project).limit(1)).first()
        return project.id if project else None


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
        tod = session.get(models.TimeOfDay, time_of_day_id)
        if tod in project_db.time_of_days:
            project_db.time_of_days.remove(tod)
            session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def put_in_excel_settings(project_id: UUID, excel_settings_id: UUID) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        project_db.excel_export_settings = session.get(models.ExcelExportSettings, excel_settings_id)
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
        tod = session.get(models.TimeOfDay, time_of_day_id)
        # Idempotent: No-op, wenn TOD nicht (mehr) in der Standards-Liste steht
        # (z. B. weil der Caller sowohl time-of-days als auch time-of-day-standards
        # sequentiell aufraeumt und die Cascade bereits einen Teil erledigt hat).
        if tod in project_db.time_of_day_standards:
            project_db.time_of_day_standards.remove(tod)
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