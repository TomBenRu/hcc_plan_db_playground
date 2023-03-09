import datetime
from uuid import UUID

from pony.orm import db_session, commit

from . import schemas
from .authentication import hash_psw
from .models import Project, Team, Person, LocationOfWork, Address, TimeOfDay, ExcelExportSettings


@db_session
def new_project(name: str):
    Project(name=name)


@db_session
def update_project(project: schemas.ProjectShow) -> schemas.ProjectShow:
    project_db = Project[project.id]
    for key, val in project.dict(include={'name', 'active'}).items():
        project_db.__setattr__(key, val)
    project_db.time_of_days_default.clear()
    for tod in project.time_of_days_default:
        project_db.time_of_days_default.add(TimeOfDay[tod.id])
    return schemas.ProjectShow.from_orm(project_db)


@db_session
def new_team(team_name: str, project_id: UUID, dispatcher_id: UUID = None):
    project_db = Project.get_for_update(lambda p: p.id == project_id)
    dispatcher_db = Person.get_for_update(lambda p: p.id == dispatcher_id) if dispatcher_id else None
    team_db = Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
    return schemas.TeamShow.from_orm(team_db)


@db_session
def update_team(team: schemas.Team) -> schemas.TeamShow:
    team_db = Team.get_for_update(lambda t: t.id == team.id)
    dispatcher_db = Person.get_for_update(lambda p: p.id == team.dispatcher.id) if team.dispatcher else None
    team_db.name = team.name
    team_db.dispatcher = dispatcher_db
    return schemas.TeamShow.from_orm(team_db)


@db_session
def delete_team(team_id: UUID) -> schemas.Team:
    team_db = Team.get_for_update(lambda t: t.id == team_id)
    team_db.prep_delete = datetime.datetime.utcnow()
    return schemas.Team.from_orm(team_db)


@db_session
def get_project(project_id: UUID) -> schemas.ProjectShow:
    project_db = Project[project_id]
    return schemas.ProjectShow.from_orm(project_db)


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
def get_location_of_work_of_project(location_id: UUID) -> schemas.LocationOfWorkShow:
    location_db = LocationOfWork[location_id]
    return schemas.LocationOfWorkShow.from_orm(location_db)


@db_session
def get_locations_of_work_of_project(project_id: UUID) -> list[schemas.LocationOfWorkShow]:
    project_in_db = Project[project_id]
    locations_in_db = LocationOfWork.select(lambda l: l.project == project_in_db and not l.prep_delete)
    return [schemas.LocationOfWorkShow.from_orm(l) for l in locations_in_db]


@db_session
def create_location_of_work(location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
    project_db = Project[project_id]
    address_db = Address(**location.address.dict(), project=project_db)
    location_db = LocationOfWork(name=location.name, project=project_db, address=address_db)
    return schemas.LocationOfWork.from_orm(location_db)


@db_session
def update_location_of_work(location_of_work: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
    location_db = LocationOfWork.get_for_update(lambda l: l.id == location_of_work.id)
    location_db.time_of_days.clear()
    for t_o_d in location_of_work.time_of_days:
        location_db.time_of_days.add(TimeOfDay.get_for_update(lambda t: t.id == t_o_d.id))
    if location_db.address:
        address = update_address(location_of_work.address)
    else:
        address = create_address(schemas.AddressCreate(street=location_of_work.address.street,
                                                       postal_code=location_of_work.address.postal_code,
                                                       city=location_of_work.address.city))
    location_db.address = Address.get_for_update(lambda a: a.id == address.id)
    if location_of_work.team:
        location_db.team = Team.get_for_update(lambda t: t.id == location_of_work.team.id)
    '''Es fehlt noch: combination_locations_possibles'''
    for key, val in location_of_work.dict(include={'name', 'nr_actors'}).items():
        location_db.__setattr__(key, val)

    return schemas.LocationOfWorkShow.from_orm(location_db)






@db_session
def delete_location_of_work(location_id: UUID) -> schemas.LocationOfWork:
    location_db = LocationOfWork[location_id]
    location_db.prep_delete = datetime.datetime.utcnow()
    return schemas.LocationOfWork.from_orm(location_db)


@db_session
def get_teams_of_project(project_id: UUID) -> list[schemas.Team]:
    teams_db = Team.select(lambda t: t.project == Project[project_id])
    return [schemas.Team.from_orm(t) for t in teams_db]


@db_session
def get_time_of_day(time_of_day_id: UUID):
    time_of_day_db = TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
    return schemas.TimeOfDayShow.from_orm(time_of_day_db)


@db_session
def create_time_of_day(time_of_day: schemas.TimeOfDayCreate, project_id: UUID) -> schemas.TimeOfDayShow:
    project_db = Project[project_id]
    time_of_day_db = TimeOfDay(**time_of_day.dict(), project=project_db)
    return schemas.TimeOfDayShow.from_orm(time_of_day_db)


@db_session
def update_time_of_day(time_of_day: schemas.TimeOfDay):
    time_of_day_db = TimeOfDay.get_for_update(lambda t: t.id == time_of_day.id)
    time_of_day_db.name = time_of_day.name
    time_of_day_db.start = time_of_day.start
    time_of_day_db.end = time_of_day.end
    return schemas.TimeOfDay.from_orm(time_of_day_db)


@db_session
def put_time_of_day_to_model(time_of_day: schemas.TimeOfDay,
                             pydantic_model: schemas.ModelWithTimeOfDays | schemas.Project, db_model):
    if (not isinstance(pydantic_model, schemas.ModelWithTimeOfDays)) and (not isinstance(pydantic_model, schemas.Project)):
        raise ValueError
    time_of_day_db = TimeOfDay.get_for_update(lambda t: t.id == time_of_day.id)
    if isinstance(pydantic_model, schemas.Project):
        instance_db = Project.get_for_update(lambda p: p.id == time_of_day.project.id)
        instance_db.time_of_days_default.add(time_of_day_db)
    else:
        instance_db = db_model.get_for_update(lambda m: m.id == pydantic_model.id)
        instance_db.time_of_days.add(time_of_day_db)
    return type(pydantic_model).from_orm(instance_db)




@db_session
def delete_time_of_day(time_of_day_id: UUID) -> schemas.TimeOfDay:
    time_of_day_db = TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
    time_of_day_db.prep_delete = datetime.datetime.utcnow()
    return schemas.TimeOfDay.from_orm(time_of_day_db)


@db_session
def update_excel_export_settings(excel_export_settings: schemas.ExcelExportSettings) -> schemas.ExcelExportSettings:
    excel_export_settings_db = ExcelExportSettings.get_for_update(lambda e: e.id == excel_export_settings.id)
    for key, val in excel_export_settings.dict(exclude={'id'}).items():
        excel_export_settings_db.__setattr__(key, val)
    return schemas.ExcelExportSettings.from_orm(excel_export_settings_db)


@db_session
def create_address(address: schemas.AddressCreate) -> schemas.Address:
    address_db = Address(street=address.street, postal_code=address.postal_code, city=address.city)
    return schemas.Address.from_orm(address_db)


@db_session
def update_address(address: schemas.Address) -> schemas.Address:
    address_db = Address.get_for_update(lambda a: a.id == address.id)
    for key, val in address.dict(include={'street', 'postal_code', 'city'}).items():
        address_db.__setattr__(key, val)
    return schemas.Address.from_orm(address_db)
