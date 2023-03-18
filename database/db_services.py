import datetime
import inspect
import logging
from typing import Optional
from uuid import UUID

from pony.orm import db_session, show

from . import schemas
from .authentication import hash_psw
from .models import Project, Team, Person, LocationOfWork, Address, TimeOfDay, ExcelExportSettings, PlanPeriod, \
    LocationPlanPeriod, EventGroup, ActorPlanPeriod, AvailDayGroup


@db_session(sql_debug=True, show_values=True)
def new_project(name: str):
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    Project(name=name)


@db_session(sql_debug=True, show_values=True)
def update_project_name(name: str, project_id) -> schemas.Project:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    project_db = Project.get_for_update(id=project_id)
    project_db.name = name
    return schemas.Project.from_orm(project_db)


@db_session(sql_debug=True, show_values=True)
def update_project(project: schemas.ProjectShow) -> schemas.ProjectShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    project_db = Project.get_for_update(id=project.id)
    project_db.set(**project.dict(include={'name', 'active'}))
    project_db.time_of_days_default.clear()
    for tod in project.time_of_days_default:
        project_db.time_of_days_default.add(TimeOfDay[tod.id])
    return schemas.ProjectShow.from_orm(project_db)


@db_session(sql_debug=True, show_values=True)
def new_team(team_name: str, project_id: UUID, dispatcher_id: UUID = None):
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    project_db = Project.get_for_update(id=project_id)
    dispatcher_db = Person.get_for_update(id=dispatcher_id) if dispatcher_id else None
    team_db = Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
    return schemas.TeamShow.from_orm(team_db)


@db_session(sql_debug=True, show_values=True)
def update_team(team: schemas.Team) -> schemas.TeamShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    team_db = Team.get_for_update(id=team.id)
    dispatcher_db = Person.get_for_update(id=team.dispatcher.id) if team.dispatcher else None
    team_db.name = team.name
    team_db.dispatcher = dispatcher_db
    return schemas.TeamShow.from_orm(team_db)


@db_session(sql_debug=True, show_values=True)
def delete_team(team_id: UUID) -> schemas.Team:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    team_db = Team.get_for_update(id=team_id)
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
def get_teams_of_project(projet_id: UUID) -> list[schemas.TeamShow]:
    project_in_db = Project.get(lambda p: p.id == projet_id)
    if not project_in_db:
        return []
    return [schemas.TeamShow.from_orm(t) for t in project_in_db.teams]


@db_session
def get_person(person_id: UUID) -> schemas.PersonShow:
    person_db = Person.get_for_update(id=person_id)
    return schemas.PersonShow.from_orm(person_db)


@db_session
def get_persons_of_project(project_id: UUID) -> list[schemas.PersonShow]:
    project_in_db = Project[project_id]
    persons_in_db = Person.select(lambda p: p.project == project_in_db and not p.prep_delete)
    return [schemas.PersonShow.from_orm(p) for p in persons_in_db]


@db_session
def get_persons_of_team(team_id: UUID) -> list[schemas.PersonShow]:
    persons_db = Person.select(lambda p: p.team_of_actor.id == team_id)
    return [schemas.PersonShow.from_orm(p) for p in persons_db]


@db_session(sql_debug=True, show_values=True)
def create_person(person: schemas.PersonCreate, project_id: UUID) -> schemas.Person:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    project_in_db = Project.get_for_update(id=project_id)
    address_in_db = Address(**person.address.dict(), project=project_in_db)
    hashed_password = hash_psw(person.password)
    person.password = hashed_password
    person_db = Person(**person.dict(exclude={'address'}), address=address_in_db, project=project_in_db)
    return schemas.Person.from_orm(person_db)


@db_session(sql_debug=True, show_values=True)
def update_person(person: schemas.PersonShow) -> schemas.Person:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    person_db = Person.get_for_update(id=person.id)
    if person_db.address:
        address = update_address(person.address)
    else:
        address = create_address(schemas.AddressCreate(**person.address.dict(include={'street', 'postal_code', 'city'})))
    person_db.address = Address.get_for_update(id=address.id)
    for t_o_d in person.time_of_days:
        person_db.time_of_days.add(TimeOfDay.get_for_update(id=t_o_d.id))
    person_db.set(**person.dict(include={'f_name', 'l_name', 'email', 'gender', 'phone_nr', 'requested_assignments'}))

    '''Es fehlen noch actor_partner_location_prefs, combination_locations_possibles'''

    return schemas.Person.from_orm(person_db)




@db_session(sql_debug=True, show_values=True)
def update_person__team_of_actor(person_id: UUID, team_id: UUID | None):
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    person_db = Person.get_for_update(id=person_id)
    team_db = Team.get_for_update(id=team_id) if team_id else None
    person_db.team_of_actor = team_db
    return schemas.PersonShow.from_orm(person_db)


@db_session(sql_debug=True, show_values=True)
def update_person__project_of_admin(person_id: UUID, project_id: UUID) -> schemas.PersonShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    person_db = Person.get_for_update(id=person_id)
    project_db = Project.get_for_update(id=project_id)
    person_db.project_of_admin = project_db
    return schemas.PersonShow.from_orm(person_db)


@db_session(sql_debug=True, show_values=True)
def delete_person(person_id: UUID) -> schemas.Person:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    person_db = Person.get_for_update(id=person_id)
    person_db.prep_delete = datetime.datetime.utcnow()
    return schemas.Person.from_orm(person_db)


@db_session
def get_location_of_work_of_project(location_id: UUID) -> schemas.LocationOfWorkShow:
    location_db = LocationOfWork.get_for_update(id=location_id)
    return schemas.LocationOfWorkShow.from_orm(location_db)


@db_session
def get_locations_of_work_of_project(project_id: UUID) -> list[schemas.LocationOfWorkShow]:
    project_in_db = Project[project_id]
    locations_in_db = LocationOfWork.select(lambda l: l.project == project_in_db and not l.prep_delete)
    return [schemas.LocationOfWorkShow.from_orm(l) for l in locations_in_db]


@db_session(sql_debug=True, show_values=True)
def create_location_of_work(location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    project_db = Project.get_for_update(id=project_id)
    address_db = Address(**location.address.dict(), project=project_db)
    location_db = LocationOfWork(name=location.name, project=project_db, address=address_db)
    return schemas.LocationOfWork.from_orm(location_db)


@db_session(sql_debug=True, show_values=True)
def update_location_of_work(location_of_work: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    location_db = LocationOfWork.get_for_update(id=location_of_work.id)
    location_db.time_of_days.clear()
    for t_o_d in location_of_work.time_of_days:
        location_db.time_of_days.add(TimeOfDay.get_for_update(id=t_o_d.id))
    if location_db.address:
        address = update_address(location_of_work.address)
    else:
        address = create_address(schemas.AddressCreate(street=location_of_work.address.street,
                                                       postal_code=location_of_work.address.postal_code,
                                                       city=location_of_work.address.city))
    location_db.address = Address.get_for_update(id=address.id)
    if location_of_work.team:
        location_db.team = Team.get_for_update(id=location_of_work.team.id)
    else:
        location_db.team = None
    # for key, val in location_of_work.dict(include={'name', 'nr_actors'}).items():
    #     location_db.__setattr__(key, val)
    location_db.set(**location_of_work.dict(include={'name', 'nr_actors', 'fixed_cast'}))

    return schemas.LocationOfWorkShow.from_orm(location_db)


@db_session(sql_debug=True, show_values=True)
def delete_location_of_work(location_id: UUID) -> schemas.LocationOfWork:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    location_db = LocationOfWork.get_for_update(id=location_id)
    location_db.prep_delete = datetime.datetime.utcnow()
    return schemas.LocationOfWork.from_orm(location_db)


@db_session
def get_teams_of_project(project_id: UUID) -> list[schemas.TeamShow]:
    teams_db = Team.select(lambda t: t.project == Project[project_id])
    return [schemas.TeamShow.from_orm(t) for t in teams_db]


@db_session
def get_time_of_day(time_of_day_id: UUID):
    time_of_day_db = TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
    return schemas.TimeOfDayShow.from_orm(time_of_day_db)


@db_session(sql_debug=True, show_values=True)
def create_time_of_day(time_of_day: schemas.TimeOfDayCreate, project_id: UUID) -> schemas.TimeOfDayShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    project_db = Project.get_for_update(id=project_id)
    time_of_day_db = TimeOfDay(**time_of_day.dict(), project=project_db)
    return schemas.TimeOfDayShow.from_orm(time_of_day_db)


@db_session(sql_debug=True, show_values=True)
def update_time_of_day(time_of_day: schemas.TimeOfDay):
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    time_of_day_db = TimeOfDay.get_for_update(id=time_of_day.id)
    time_of_day_db.name = time_of_day.name
    time_of_day_db.start = time_of_day.start
    time_of_day_db.end = time_of_day.end
    return schemas.TimeOfDay.from_orm(time_of_day_db)


@db_session(sql_debug=True, show_values=True)
def put_time_of_day_to_model(time_of_day: schemas.TimeOfDay,
                             pydantic_model: schemas.ModelWithTimeOfDays | schemas.Project, db_model):
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    if not (isinstance(pydantic_model, schemas.ModelWithTimeOfDays) or isinstance(pydantic_model, schemas.Project)):
        raise ValueError
    time_of_day_db = TimeOfDay.get_for_update(id=time_of_day.id)
    if isinstance(pydantic_model, schemas.Project):
        instance_db = Project.get_for_update(id=time_of_day.project.id)
        instance_db.time_of_days_default.add(time_of_day_db)
    else:
        instance_db = db_model.get_for_update(id=pydantic_model.id)
        instance_db.time_of_days.add(time_of_day_db)
    return type(pydantic_model).from_orm(instance_db)


@db_session(sql_debug=True, show_values=True)
def delete_time_of_day(time_of_day_id: UUID) -> schemas.TimeOfDay:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    time_of_day_db = TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
    time_of_day_db.prep_delete = datetime.datetime.utcnow()
    return schemas.TimeOfDay.from_orm(time_of_day_db)


@db_session(sql_debug=True, show_values=True)
def update_excel_export_settings(excel_export_settings: schemas.ExcelExportSettings) -> schemas.ExcelExportSettings:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    excel_export_settings_db = ExcelExportSettings.get_for_update(lambda e: e.id == excel_export_settings.id)
    # for key, val in excel_export_settings.dict(exclude={'id'}).items():
    #     excel_export_settings_db.__setattr__(key, val)
    excel_export_settings_db.set(**excel_export_settings.dict(exclude={'id'}))

    return schemas.ExcelExportSettings.from_orm(excel_export_settings_db)


@db_session(sql_debug=True, show_values=True)
def create_address(address: schemas.AddressCreate) -> schemas.Address:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    address_db = Address(street=address.street, postal_code=address.postal_code, city=address.city)
    return schemas.Address.from_orm(address_db)


@db_session(sql_debug=True, show_values=True)
def update_address(address: schemas.Address) -> schemas.Address:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    address_db = Address.get_for_update(lambda a: a.id == address.id)
    # for key, val in address.dict(include={'street', 'postal_code', 'city'}).items():
    #     address_db.__setattr__(key, val)
    address_db.set(**address.dict(include={'street', 'postal_code', 'city'}))
    return schemas.Address.from_orm(address_db)


@db_session(sql_debug=True, show_values=True)
def create_planperiod(plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    team_db = Team.get_for_update(id=plan_period.team.id)
    plan_period_db = PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline, notes=plan_period.notes, team=team_db)
    return schemas.PlanPeriodShow.from_orm(plan_period_db)


@db_session(sql_debug=True, show_values=True)
def create_location_plan_period(plan_period_id: UUID, location_id: UUID) -> schemas.LocationPlanPeriodShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    plan_period_db = PlanPeriod.get_for_update(id=plan_period_id)
    location_db = LocationOfWork.get_for_update(id=location_id)
    location_plan_period_db = LocationPlanPeriod(plan_period=plan_period_db, location_of_work=location_db)
    return schemas.LocationPlanPeriodShow.from_orm(location_plan_period_db)


@db_session(sql_debug=True, show_values=True)
def create_event_group(*, location_plan_period_id: Optional[UUID] = None,
                       event_group_id: Optional[UUID] = None) -> schemas.EventGroupShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    location_plan_period_db = LocationPlanPeriod.get_for_update(id=location_plan_period_id) if location_plan_period_id else None
    event_group_db = EventGroup.get_for_update(id=event_group_id) if event_group_id else None
    new_event_group_db = EventGroup(location_plan_period=location_plan_period_db, event_group=event_group_db)

    return schemas.EventGroupShow.from_orm(new_event_group_db)


@db_session(sql_debug=True, show_values=True)
def create_actor_plan_period(plan_period_id: UUID, person_id: UUID) -> schemas.ActorPlanPeriodShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    plan_period_db = PlanPeriod.get_for_update(id=plan_period_id)
    person_db = Person.get_for_update(id=person_id)
    actor_plan_period_db = ActorPlanPeriod(plan_period=plan_period_db, person=person_db)

    return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)


@db_session(sql_debug=True, show_values=True)
def create_avail_day_group(*, actor_plan_period_id: Optional[UUID] = None,
                           avail_day_group_id: Optional[UUID] = None) -> schemas.AvailDayGroupShow:
    logging.info(f'function: {__name__}.{inspect.currentframe().f_code.co_name}\nargs: {locals()}')

    actor_plan_period_db = ActorPlanPeriod.get_for_update(id=actor_plan_period_id) if actor_plan_period_id else None
    avail_day_group_db = AvailDayGroup.get_for_update(id=avail_day_group_id) if avail_day_group_id else None
    new_avail_day_group = AvailDayGroup(actor_plan_period=actor_plan_period_db, avail_day_group=avail_day_group_db)

    return schemas.AvailDayGroupShow.from_orm(new_avail_day_group)


