from uuid import UUID

from pony.orm import db_session
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
