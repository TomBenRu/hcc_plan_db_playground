import datetime
from uuid import UUID

from pony.orm import db_session

from . import schemas
from .authentication import hash_psw
from .models import Project, Team, Person, LocationOfWork, Address


@db_session()
def new_project(name: str):
    Project(name=name)


@db_session
def new_team(team_name: str, proj_name: str):
    team_db = Team(name=team_name, project=Project.get(lambda p: p.name == proj_name))
    return schemas.Team.from_orm(team_db)


def create_project_and_team(proj_name: str, team_name: str):
    new_project(proj_name)
    new_team(team_name, proj_name)


@db_session
def get_projects() -> list[schemas.ProjectShow]:
    return [schemas.ProjectShow.from_orm(p) for p in Project.select()]


@db_session
def get_teams_of_project(projet_id: UUID) -> list[schemas.Team]:
    project_in_db = Project.get(lambda p: p.id == projet_id)
    if not project_in_db:
        return []
    return [schemas.Team.from_orm(t) for t in project_in_db.teams]


@db_session
def get_persons_of_project(project_id: UUID) -> list[schemas.PersonShow]:
    project_in_db = Project[project_id]
    persons_in_db = Person.select(lambda p: p.project == project_in_db and not p.prep_delete)
    return [schemas.PersonShow.from_orm(p) for p in persons_in_db]


@db_session
def create_person(person: schemas.PersonCreate, project_id: UUID) -> schemas.Person:
    project_in_db = Project[project_id]
    address_in_db = Address(**person.address.dict(), project=project_in_db)
    hashed_password = hash_psw(person.password)
    person.password = hashed_password
    person_db = Person(**person.dict(exclude={'address'}), address=address_in_db, project=project_in_db)
    return schemas.Person.from_orm(person_db)


@db_session
def delete_person(person_id: UUID) -> schemas.Person:
    person_db = Person[person_id]
    person_db.prep_delete = datetime.datetime.utcnow()
    return schemas.Person.from_orm(person_db)


@db_session
def get_locations_of_work_of_project(project_id: UUID) -> list[schemas.LocationOfWork]:
    project_in_db = Project[project_id]
    locations_in_db = LocationOfWork.select(lambda l: l.project == project_in_db and not l.prep_delete)
    return [schemas.LocationOfWork.from_orm(l) for l in locations_in_db]


@db_session
def create_location_of_work(location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
    project_db = Project[project_id]
    address_db = Address(**location.address.dict(), project=project_db)
    location_db = LocationOfWork(name=location.name, project=project_db, address=address_db)
    return schemas.LocationOfWork.from_orm(location_db)


@db_session
def delete_location_of_work(location_id: UUID) -> schemas.LocationOfWork:
    location_db = LocationOfWork[location_id]
    location_db.prep_delete = datetime.datetime.utcnow()
    return schemas.LocationOfWork.from_orm(location_db)
