import datetime
import inspect
import logging
from typing import Optional
from uuid import UUID

from pony.orm import db_session

from . import schemas
from .authentication import hash_psw
from . import models


class Project:
    @staticmethod
    @db_session
    def get(project_id: UUID) -> schemas.ProjectShow:
        project_db = models.Project[project_id]
        return schemas.ProjectShow.from_orm(project_db)

    @staticmethod
    @db_session
    def get_all() -> list[schemas.ProjectShow]:
        return [schemas.ProjectShow.from_orm(p) for p in models.Project.select()]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(name: str) -> schemas.ProjectShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project(name=name)
        return schemas.ProjectShow.from_orm(project_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update_name(name: str, project_id) -> schemas.Project:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        project_db.name = name
        return schemas.Project.from_orm(project_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(project: schemas.ProjectShow) -> schemas.ProjectShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project.id)
        project_db.set(**project.dict(include={'name', 'active'}))
        project_db.time_of_days_default.clear()
        for tod in project.time_of_days_default:
            project_db.time_of_days_default.add(models.TimeOfDay[tod.id])
        return schemas.ProjectShow.from_orm(project_db)


class Team:
    @staticmethod
    @db_session
    def get_all_from__project(projet_id: UUID) -> list[schemas.TeamShow]:
        project_in_db = models.Project.get_for_update(lambda p: p.id == projet_id)
        if not project_in_db:
            return []
        return [schemas.TeamShow.from_orm(t) for t in project_in_db.teams]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(team_name: str, project_id: UUID, dispatcher_id: UUID = None):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        dispatcher_db = models.Person.get_for_update(id=dispatcher_id) if dispatcher_id else None
        team_db = models.Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
        return schemas.TeamShow.from_orm(team_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(team: schemas.Team) -> schemas.TeamShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_db = models.Team.get_for_update(id=team.id)
        dispatcher_db = models.Person.get_for_update(id=team.dispatcher.id) if team.dispatcher else None
        team_db.name = team.name
        team_db.dispatcher = dispatcher_db
        return schemas.TeamShow.from_orm(team_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(team_id: UUID) -> schemas.Team:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_db = models.Team.get_for_update(id=team_id)
        team_db.prep_delete = datetime.datetime.utcnow()
        return schemas.Team.from_orm(team_db)


class Person:
    @staticmethod
    @db_session
    def get(person_id: UUID) -> schemas.PersonShow:
        person_db = models.Person.get_for_update(id=person_id)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session
    def get_all_from__project(project_id: UUID) -> list[schemas.PersonShow]:
        project_in_db = models.Project.get_for_update(id=project_id)
        persons_in_db = models.Person.select(lambda p: p.project == project_in_db and not p.prep_delete)
        return [schemas.PersonShow.from_orm(p) for p in persons_in_db]

    @staticmethod
    @db_session
    def get_all_from__team(team_id: UUID) -> list[schemas.PersonShow]:
        persons_db = models.Person.select(lambda p: p.team_of_actor.id == team_id)
        return [schemas.PersonShow.from_orm(p) for p in persons_db]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(person: schemas.PersonCreate, project_id: UUID) -> schemas.Person:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_in_db = models.Project.get_for_update(id=project_id)
        address_in_db = models.Address(**person.address.dict(), project=project_in_db)
        hashed_password = hash_psw(person.password)
        person.password = hashed_password
        person_db = models.Person(**person.dict(exclude={'address'}), address=address_in_db, project=project_in_db)
        return schemas.Person.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(person: schemas.PersonShow) -> schemas.Person:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person.id)
        if person_db.address:
            address = Address.update(person.address)
        else:
            address = Address.create(
                schemas.AddressCreate(**person.address.dict(include={'street', 'postal_code', 'city'})))
        person_db.address = models.Address.get_for_update(id=address.id)
        person_db.time_of_days.clear()
        for t_o_d in person.time_of_days:
            person_db.time_of_days.add(models.TimeOfDay.get_for_update(id=t_o_d.id))
        person_db.set(
            **person.dict(include={'f_name', 'l_name', 'email', 'gender', 'phone_nr', 'requested_assignments'}))

        '''Es fehlen noch actor_partner_location_prefs, combination_locations_possibles'''

        return schemas.Person.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update_team_of_actor(person_id: UUID, team_id: UUID | None):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        team_db = models.Team.get_for_update(id=team_id) if team_id else None
        person_db.team_of_actor = team_db
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update_project_of_admin(person_id: UUID, project_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        project_db = models.Project.get_for_update(id=project_id)
        person_db.project_of_admin = project_db
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(person_id: UUID) -> schemas.Person:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        person_db.prep_delete = datetime.datetime.utcnow()
        return schemas.Person.from_orm(person_db)


class LocationOfWork:
    @staticmethod
    @db_session
    def get(location_id: UUID) -> schemas.LocationOfWorkShow:
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        return schemas.LocationOfWorkShow.from_orm(location_db)

    @staticmethod
    @db_session
    def get_all_from__project(project_id: UUID) -> list[schemas.LocationOfWorkShow]:
        project_in_db = models.Project[project_id]
        locations_in_db = models.LocationOfWork.select(lambda l: l.project == project_in_db and not l.prep_delete)
        return [schemas.LocationOfWorkShow.from_orm(loc) for loc in locations_in_db]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        address_db = models.Address(**location.address.dict(), project=project_db)
        location_db = models.LocationOfWork(name=location.name, project=project_db, address=address_db)
        return schemas.LocationOfWork.from_orm(location_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(location_of_work: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get_for_update(id=location_of_work.id)
        location_db.time_of_days.clear()
        for t_o_d in location_of_work.time_of_days:
            location_db.time_of_days.add(models.TimeOfDay.get_for_update(id=t_o_d.id))
        if location_db.address:
            address = Address.update(location_of_work.address)
        else:
            address = Address.create(schemas.AddressCreate(street=location_of_work.address.street,
                                                           postal_code=location_of_work.address.postal_code,
                                                           city=location_of_work.address.city))
        location_db.address = models.Address.get_for_update(id=address.id)
        if location_of_work.team:
            location_db.team = models.Team.get_for_update(id=location_of_work.team.id)
        else:
            location_db.team = None
        # for key, val in location_of_work.dict(include={'name', 'nr_actors'}).items():
        #     location_db.__setattr__(key, val)
        location_db.set(**location_of_work.dict(include={'name', 'nr_actors', 'fixed_cast'}))

        return schemas.LocationOfWorkShow.from_orm(location_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(location_id: UUID) -> schemas.LocationOfWork:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        location_db.prep_delete = datetime.datetime.utcnow()
        return schemas.LocationOfWork.from_orm(location_db)


class TimeOfDay:
    @staticmethod
    @db_session
    def get(time_of_day_id: UUID):
        time_of_day_db = models.TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
        return schemas.TimeOfDayShow.from_orm(time_of_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(time_of_day: schemas.TimeOfDayCreate, project_id: UUID) -> schemas.TimeOfDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay(**time_of_day.dict(), project=project_db)
        return schemas.TimeOfDayShow.from_orm(time_of_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(time_of_day: schemas.TimeOfDay):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day.id)
        time_of_day_db.name = time_of_day.name
        time_of_day_db.start = time_of_day.start
        time_of_day_db.end = time_of_day.end
        return schemas.TimeOfDay.from_orm(time_of_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_to_model(time_of_day: schemas.TimeOfDay,
                     pydantic_model: schemas.ModelWithTimeOfDays | schemas.Project, db_model):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        if not (isinstance(pydantic_model, schemas.ModelWithTimeOfDays) or isinstance(pydantic_model, schemas.Project)):
            raise ValueError
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day.id)
        if isinstance(pydantic_model, schemas.Project):
            instance_db = models.Project.get_for_update(id=time_of_day.project.id)
            instance_db.time_of_days_default.add(time_of_day_db)
        else:
            instance_db = db_model.get_for_update(id=pydantic_model.id)
            instance_db.time_of_days.add(time_of_day_db)
        return type(pydantic_model).from_orm(instance_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(time_of_day_id: UUID) -> schemas.TimeOfDay:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        time_of_day_db = models.TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
        time_of_day_db.prep_delete = datetime.datetime.utcnow()
        return schemas.TimeOfDay.from_orm(time_of_day_db)


class ExcelExportSettings:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(excel_export_settings: schemas.ExcelExportSettings) -> schemas.ExcelExportSettings:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        excel_export_settings_db = models.ExcelExportSettings.get_for_update(lambda e: e.id == excel_export_settings.id)
        # for key, val in excel_export_settings.dict(exclude={'id'}).items():
        #     excel_export_settings_db.__setattr__(key, val)
        excel_export_settings_db.set(**excel_export_settings.dict(exclude={'id'}))

        return schemas.ExcelExportSettings.from_orm(excel_export_settings_db)


class Address:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(address: schemas.AddressCreate) -> schemas.Address:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        address_db = models.Address(street=address.street, postal_code=address.postal_code, city=address.city)
        return schemas.Address.from_orm(address_db)

    @ staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(address: schemas.Address) -> schemas.Address:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        address_db = models.Address.get_for_update(lambda a: a.id == address.id)
        # for key, val in address.dict(include={'street', 'postal_code', 'city'}).items():
        #     address_db.__setattr__(key, val)
        address_db.set(**address.dict(include={'street', 'postal_code', 'city'}))
        return schemas.Address.from_orm(address_db)


class PlanPeriod:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_db = models.Team.get_for_update(id=plan_period.team.id)
        plan_period_db = models.PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                                           notes=plan_period.notes, team=team_db)
        return schemas.PlanPeriodShow.from_orm(plan_period_db)


class LocationPlanPeriod:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(plan_period_id: UUID, location_id: UUID) -> schemas.LocationPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        location_plan_period_db = models.LocationPlanPeriod(plan_period=plan_period_db, location_of_work=location_db)
        return schemas.LocationPlanPeriodShow.from_orm(location_plan_period_db)


class EventGroup:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(*, location_plan_period_id: Optional[UUID] = None,
               event_group_id: Optional[UUID] = None) -> schemas.EventGroupShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_plan_period_db = (models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
                                   if location_plan_period_id else None)
        event_group_db = models.EventGroup.get_for_update(id=event_group_id) if event_group_id else None
        new_event_group_db = models.EventGroup(location_plan_period=location_plan_period_db, event_group=event_group_db)

        return schemas.EventGroupShow.from_orm(new_event_group_db)


class ActorPlanPeriod:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(plan_period_id: UUID, person_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        person_db = models.Person.get_for_update(id=person_id)
        actor_plan_period_db = models.ActorPlanPeriod(plan_period=plan_period_db, person=person_db)

        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(actor_plan_period: schemas.ActorPlanPeriodUpdate) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period.id)
        actor_plan_period_db.set(notes=actor_plan_period.notes)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)


class AvailDayGroup:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(*, actor_plan_period_id: Optional[UUID] = None,
               avail_day_group_id: Optional[UUID] = None) -> schemas.AvailDayGroupShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(
            id=actor_plan_period_id) if actor_plan_period_id else None
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id) if avail_day_group_id else None
        new_avail_day_group = models.AvailDayGroup(actor_plan_period=actor_plan_period_db,
                                                   avail_day_group=avail_day_group_db)

        return schemas.AvailDayGroupShow.from_orm(new_avail_day_group)


class AvailDay:
    @staticmethod
    @db_session
    def get(actor_plan_period_id: UUID, day: datetime.date, time_of_day_id) -> schemas.AvailDayShow:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        avail_day_db = models.AvailDay.get_for_update(
            lambda ad: ad.actor_plan_period == actor_plan_period_db and ad.day == day and
                       ad.time_of_day == models.TimeOfDay.get_for_update(id=time_of_day_id) and not ad.prep_delete)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session
    def get_all_from__actor_plan_period(actor_plan_period_id: UUID) -> list[schemas.AvailDayShow]:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        avail_days_db = models.AvailDay.select(lambda a: a.actor_plan_period == actor_plan_period_db)
        return [schemas.AvailDayShow.from_orm(ad) for ad in avail_days_db]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(avail_day: schemas.AvailDayCreate) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=avail_day.actor_plan_period.id)
        master_avail_day_group_db = actor_plan_period_db.avail_day_group
        avail_day_group_db = AvailDayGroup.create(avail_day_group_id=master_avail_day_group_db.id)
        avail_day_db = models.AvailDay(
            day=avail_day.day, time_of_day=models.TimeOfDay.get_for_update(id=avail_day.time_of_day.id),
            avail_day_group=models.AvailDayGroup.get_for_update(id=avail_day_group_db.id),
            actor_plan_period=actor_plan_period_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(avail_day_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        deleted = schemas.AvailDayShow.from_orm(avail_day_db)
        avail_day_group = avail_day_db.avail_day_group
        avail_day_db.delete()
        while True:
            if not avail_day_group:
                break
            if avail_day_group.avail_day_groups.is_empty() and not avail_day_group.actor_plan_period:
                avail_day_group, avail_day_group_to_delete = avail_day_group.avail_day_group, avail_day_group
                avail_day_group_to_delete.delete()
            else:
                break
        return deleted
