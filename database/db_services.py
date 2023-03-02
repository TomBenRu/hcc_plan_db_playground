from uuid import UUID

from pony.orm import db_session

from . import schemas
from .models import Project, Team


@db_session()
def new_project(name: str):
    Project(name=name)


@db_session
def new_team(team_name: str, proj_name: str):
    Team(name=team_name, project=Project.get(lambda p: p.name == proj_name))


def create_project_and_team(proj_name: str, team_name: str):
    new_project(proj_name)
    new_team(team_name, proj_name)


@db_session
def get_projects() -> list[schemas.ProjectShow]:
    return [schemas.ProjectShow.from_orm(p) for p in Project.select()]


@db_session
def get_teams_of_project(projet_id: str) -> list[schemas.Team]:
    teams_in_db = Project.get(lambda p: p.id == UUID(projet_id)).teams
    return [schemas.Team.from_orm(t) for t in teams_in_db]
