import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(team_id: UUID) -> schemas.TeamShow:
    with get_session() as session:
        return schemas.TeamShow.model_validate(session.get(models.Team, team_id))


def get_all_from__project(project_id: UUID, minimal: bool = False) -> list[schemas.TeamShow | tuple[str, UUID]]:
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        if not project_db:
            return []
        if minimal:
            return [(t.name, t.id) for t in project_db.teams]
        return [schemas.TeamShow.model_validate(t) for t in project_db.teams]


def create(team_name: str, project_id: UUID, dispatcher_id: UUID = None):
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        dispatcher_db = session.get(models.Person, dispatcher_id) if dispatcher_id else None
        team_db = models.Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
        session.add(team_db)
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def update(team: schemas.Team) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team.id)
        team_db.name = team.name
        team_db.dispatcher = session.get(models.Person, team.dispatcher.id) if team.dispatcher else None
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def update_notes(team_id: UUID, notes: str) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.notes = notes
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def put_in_comb_loc_possible(team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.combination_locations_possibles.append(
            session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def put_in_excel_settings(team_id: UUID, excel_settings_id: UUID) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.excel_export_settings = session.get(models.ExcelExportSettings, excel_settings_id)
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def remove_comb_loc_possible(team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.combination_locations_possibles.remove(
            session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def delete(team_id: UUID) -> schemas.Team:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        team_db.prep_delete = _utcnow()
        session.flush()
        return schemas.Team.model_validate(team_db)