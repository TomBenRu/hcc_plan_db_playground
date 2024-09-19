import datetime
import inspect
import json
import logging
import time
from functools import wraps
from typing import Optional, Callable
from uuid import UUID

from pony.orm import db_session, commit, select, desc

from . import schemas, schemas_plan_api
from .authentication import hash_psw
from . import models
from .enums import Gender


def log_function_info(cls):
    logging.info(f'function: {cls.__module__}.{cls.__name__}.{inspect.currentframe().f_back.f_code.co_name}\n'
                 f'args: {inspect.currentframe().f_back.f_locals}')


def logger(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        print(f'Calling {func.__name__} with args {args} and kwargs {kwargs}')
        return func(*args, **kwargs)
    return wrapper


class EntitiesApiToDB:
    @classmethod
    @db_session
    def create_project(cls, project: schemas_plan_api.Project) -> schemas.ProjectShow:
        log_function_info(cls)
        project_db = models.Project(id=project.id, name=project.name)
        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session
    def delete_project(cls, project_id: UUID) -> None:
        log_function_info(cls)
        models.Project.get(id=project_id).delete()

    @classmethod
    @db_session
    def create_person(cls, person: schemas_plan_api.PersonShow) -> schemas.PersonShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=person.project.id)
        address_db = models.Address(street='keine Angabe', postal_code='keine Angabe',
                                    city='keine Angabe', project=project_db)
        person_db = models.Person(id=person.id, f_name=person.f_name, l_name=person.l_name, gender=Gender.divers,
                                  email=person.email, phone_nr='', username=person.username, password=person.password,
                                  project=project_db, address=address_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session
    def delete_person(cls, person_id: UUID) -> None:
        log_function_info(cls)
        models.Person.get(id=person_id).delete()

    @classmethod
    @db_session
    def create_team(cls, team: schemas_plan_api.Team) -> schemas.TeamShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=team.dispatcher.project.id)
        team_db = models.Team(id=team.id, name=team.name, project=project_db)
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session
    def delete_team(cls, team_id: UUID) -> None:
        log_function_info(cls)
        models.Team.get(id=team_id).delete()

    @classmethod
    @db_session
    def create_plan_period(cls, plan_period: schemas_plan_api.PlanPeriod) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=plan_period.team.id)
        plan_period_db = models.PlanPeriod(id=plan_period.id, start=plan_period.start, end=plan_period.end,
                                           deadline=plan_period.deadline, notes_for_emloyees=plan_period.notes,
                                           closed=plan_period.closed, remainder=True, team=team_db)
        return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    @db_session
    def delete_plan_period(cls, plan_period_id: UUID) -> None:
        log_function_info(cls)
        models.PlanPeriod.get(id=plan_period_id).delete()


class Project:
    @classmethod
    @db_session
    def get(cls, project_id: UUID) -> schemas.ProjectShow:
        project_db = models.Project[project_id]
        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session
    def get_all(cls) -> list[schemas.ProjectShow]:
        return [schemas.ProjectShow.model_validate(p) for p in models.Project.select()]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, name: str) -> schemas.ProjectShow:
        log_function_info(cls)
        project_db = models.Project(name=name)
        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_name(cls, name: str, project_id) -> schemas.Project:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        project_db.name = name
        return schemas.Project.model_validate(project_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, project: schemas.ProjectShow) -> schemas.ProjectShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project.id)
        project_db.set(**project.model_dump(include={'name', 'active'}))
        project_db.time_of_days.clear()
        for t_o_d in project.time_of_days:
            project_db.time_of_days.add(models.TimeOfDay[t_o_d.id])
        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_time_of_day(cls, project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        project_db.time_of_days.add(time_of_day_db)

        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_in_time_of_day(cls, project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        project_db.time_of_days.remove(time_of_day_db)

        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(cls, project_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ProjectShow, UUID | None]:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        old_time_of_day_standard_id = None
        for t_o_d in project_db.time_of_day_standards:  # todo: dieser Prozess muss auf höhere Ebene verlagert werden!
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                project_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        project_db.time_of_day_standards.add(time_of_day_db)
        return schemas.ProjectShow.model_validate(project_db), old_time_of_day_standard_id

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(cls, project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        project_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_enum_standard(cls, time_of_day_enum_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        time_of_day_enum_db = models.TimeOfDayEnum.get(id=time_of_day_enum_id)
        time_of_day_enum_db.project.time_of_day_enum_standards.add(time_of_day_enum_db)

        return schemas.ProjectShow.model_validate(time_of_day_enum_db.project)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_enum_standard(cls, time_of_day_enum_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        time_of_day_enum_db = models.TimeOfDayEnum.get(id=time_of_day_enum_id)
        time_of_day_enum_db.project.time_of_day_enum_standards.remove(time_of_day_enum_db)

        return schemas.ProjectShow.model_validate(time_of_day_enum_db.project)


class Team:
    @classmethod
    @db_session
    def get(cls, team_id: UUID) -> schemas.TeamShow:
        team_db = models.Team.get_for_update(id=team_id)
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.TeamShow]:
        if project_in_db := models.Project.get_for_update(lambda p: p.id == project_id):
            return [schemas.TeamShow.model_validate(t) for t in project_in_db.teams]
        else:
            return []

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, team_name: str, project_id: UUID, dispatcher_id: UUID = None):
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        dispatcher_db = models.Person.get_for_update(id=dispatcher_id) if dispatcher_id else None
        team_db = models.Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, team: schemas.Team) -> schemas.TeamShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team.id)
        dispatcher_db = models.Person.get_for_update(id=team.dispatcher.id) if team.dispatcher else None
        team_db.name = team.name
        team_db.dispatcher = dispatcher_db
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_notes(cls, team_id: UUID, notes: str) -> schemas.TeamShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team_id)
        team_db.notes = notes
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(cls, team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        team_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_excel_settings(cls, team_id: UUID, excel_settings_id: UUID) -> schemas.TeamShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team_id)
        excel_settings_db = models.ExcelExportSettings.get_for_update(id=excel_settings_id)
        team_db.excel_export_settings = excel_settings_db
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(cls, team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        team_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.TeamShow.model_validate(team_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, team_id: UUID) -> schemas.Team:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team_id)
        team_db.prep_delete = datetime.datetime.utcnow()
        return schemas.Team.model_validate(team_db)


class Person:
    @classmethod
    @db_session
    def get(cls, person_id: UUID) -> schemas.PersonShow:
        person_db = models.Person.get_for_update(id=person_id)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session
    def get_full_name_of_person(cls, person_id: UUID) -> str:
        person_db = models.Person.get(id=person_id)
        return f'{person_db.f_name} {person_db.l_name}'

    @classmethod
    @db_session
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.PersonShow]:
        project_in_db = models.Project.get_for_update(id=project_id)
        persons_in_db = models.Person.select(lambda p: p.project == project_in_db and not p.prep_delete)
        return [schemas.PersonShow.model_validate(p) for p in persons_in_db]

    @classmethod
    @db_session
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.PersonShow]:
        plan_period_db = models.PlanPeriod.get(id=plan_period_id)
        persons_db = models.Person.select(lambda p: p.actor_plan_periods.select(lambda app: app.plan_period == plan_period_db))

        return [schemas.PersonShow.model_validate(p) for p in persons_db]

    @classmethod
    @db_session
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        """
        gibt alle der Planperiode zugehörigen Mitarbeiter zurück.
        Ausgabe: Dictionary Mitarbeitername: Mitarbeiter_id
        """
        persons_db = {app.person.full_name: app.person.id
                      for app in models.PlanPeriod.get(id=plan_period_id).actor_plan_periods}
        return persons_db

    @classmethod
    @db_session
    def get_all_possible_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        """
        gibt in der Zeitspanne der Planperiode verfügbaren Mitarbeiter zurück, welche nicht zum Löschen markiert sind.
        Ausgabe: Dictionary Mitarbeitername: Mitarbeiter_id
        """
        plan_period_db = models.PlanPeriod.get(id=plan_period_id)
        start, end, team = plan_period_db.start, plan_period_db.end, plan_period_db.team
        team_actor_assigns = (models.TeamActorAssign.select()
                              .filter(lambda t: t.team == team)
                              .filter(lambda t: (t.end > end) if t.end else True)
                              .filter(lambda t: t.start < end))
        print([(taa.person.full_name, taa.team.name, taa.start, taa.end) for taa in team_actor_assigns])
        return {taa.person.full_name: taa.person.id for taa in team_actor_assigns}

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, person: schemas.PersonCreate, project_id: UUID) -> schemas.Person:
        log_function_info(cls)
        project_in_db = models.Project.get_for_update(id=project_id)
        address_in_db = models.Address(**person.address.model_dump(), project=project_in_db)
        hashed_password = hash_psw(person.password)
        person.password = hashed_password
        person_db = models.Person(**person.model_dump(exclude={'address'}), address=address_in_db, project=project_in_db)
        return schemas.Person.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, person: schemas.PersonShow) -> schemas.Person:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person.id)
        if person_db.address:
            address = Address.update(person.address)
        else:
            address = Address.create(
                schemas.AddressCreate(**person.address.model_dump(include={'street', 'postal_code', 'city'})))
        person_db.address = models.Address.get_for_update(id=address.id)
        person_db.time_of_days.clear()
        for t_o_d in person.time_of_days:
            person_db.time_of_days.add(models.TimeOfDay.get_for_update(id=t_o_d.id))
        person_db.set(
            **person.model_dump(include={'f_name', 'l_name', 'email', 'gender', 'phone_nr', 'requested_assignments', 'notes'}))

        '''Es fehlen noch actor_partner_location_prefs, combination_locations_possibles'''

        return schemas.Person.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_project_of_admin(cls, person_id: UUID, project_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        project_db = models.Project.get_for_update(id=project_id)
        person_db.project_of_admin = project_db
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_time_of_day(cls, person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        person_db.time_of_days.add(time_of_day_db)

        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_in_time_of_day(cls, person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        person_db.time_of_days.remove(time_of_day_db)

        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(cls, person_id: UUID, time_of_day_id: UUID) -> tuple[schemas.PersonShow, UUID | None]:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in person_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                person_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        person_db.time_of_day_standards.add(time_of_day_db)
        return schemas.PersonShow.model_validate(person_db), old_time_of_day_standard_id

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(cls, person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        person_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, person_id: UUID) -> schemas.Person:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        person_db.prep_delete = datetime.datetime.utcnow()
        return schemas.Person.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(cls, person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        person_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(cls, person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        person_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_location_pref(cls, person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        person_db.actor_location_prefs_defaults.add(location_pref_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_location_pref(cls, person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        person_db.actor_location_prefs_defaults.remove(location_pref_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_partner_location_pref(cls, person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        person_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_partner_location_pref(cls, person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        person_db.actor_partner_location_prefs_defaults.remove(partner_location_pref_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_flag(cls, person_id: UUID, flag_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        flag_db = models.Flag.get_for_update(id=flag_id)
        person_db.flags.add(flag_db)
        return schemas.PersonShow.model_validate(person_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_flag(cls, person_id: UUID, flag_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        person_db = models.Person.get_for_update(id=person_id)
        flag_db = models.Flag.get_for_update(id=flag_id)
        person_db.flags.remove(flag_db)
        return schemas.PersonShow.model_validate(person_db)


class LocationOfWork:
    @classmethod
    @db_session
    def get(cls, location_id: UUID) -> schemas.LocationOfWorkShow:
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        return schemas.LocationOfWorkShow.model_validate(location_db)

    @classmethod
    @db_session
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.LocationOfWorkShow]:
        project_in_db = models.Project[project_id]
        locations_in_db = models.LocationOfWork.select(lambda l: l.project == project_in_db and not l.prep_delete)
        return [schemas.LocationOfWorkShow.model_validate(loc) for loc in locations_in_db]

    @classmethod
    @db_session
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        """
        gibt alle der Planperiode zugehörigen Locations zurück, welche nicht zum Löschen markiert sind.
        Ausgabe: Dictionary Location-Name: Location_id
        """
        locations_db = {lpp.location_of_work.name: lpp.location_of_work.id
                        for lpp in models.PlanPeriod.get(id=plan_period_id).location_plan_periods}
        return locations_db

    @classmethod
    @db_session
    def get_all_possible_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        """
        gibt in der Zeitspanne der Planperiode verfügbaren Mitarbeiter zurück, welche nicht zum Löschen markiert sind.
        Ausgabe: Dictionary Mitarbeitername: Mitarbeiter_id
        """
        plan_period_db = models.PlanPeriod.get(id=plan_period_id)
        start, end, team = plan_period_db.start, plan_period_db.end, plan_period_db.team
        team_location_assigns = (models.TeamLocationAssign.select()
                                 .filter(lambda t: t.team == team)
                                 .filter(lambda t: (t.end > end) if t.end else True)
                                 .filter(lambda t: t.start < end))
        print([(tla.location_of_work.name, tla.location_of_work.address.city) for tla in team_location_assigns])
        return {tla.location_of_work.name_and_city: tla.location_of_work.id for tla in team_location_assigns}

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        print(f'{location.address.model_dump()=}')
        address_db = models.Address(**location.address.model_dump(), project=project_db)
        print(f'{address_db.to_dict()=}')
        location_db = models.LocationOfWork(name=location.name, project=project_db, address=address_db)
        return schemas.LocationOfWork.model_validate(location_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, location_of_work: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
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
        location_db.set(**location_of_work.model_dump(include={'name', 'nr_actors', 'fixed_cast'}))

        return schemas.LocationOfWorkShow.model_validate(location_db)

    @classmethod
    @db_session
    def update_notes(cls, location_of_work_id: UUID, notes: str) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        location_of_work_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        location_of_work_db.set(notes=notes)
        return schemas.LocationOfWorkShow.model_validate(location_of_work_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_time_of_day(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        location_of_work_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        location_of_work_db.time_of_days.add(time_of_day_db)

        return schemas.LocationOfWorkShow.model_validate(location_of_work_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_in_time_of_day(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        location_of_work_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        location_of_work_db.time_of_days.remove(time_of_day_db)

        return schemas.LocationOfWorkShow.model_validate(location_of_work_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationOfWorkShow, UUID | None]:
        log_function_info(cls)
        location_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in location_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                location_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        location_db.time_of_day_standards.add(time_of_day_db)
        return schemas.LocationOfWorkShow.model_validate(location_db), old_time_of_day_standard_id

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        location_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        if location_db.time_of_day_standards:
            location_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.LocationOfWorkShow.model_validate(location_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_fixed_cast(cls, location_of_work_id: UUID, fixed_cast: str) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        location_of_work_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        location_of_work_db.fixed_cast = fixed_cast

        return schemas.LocationOfWorkShow.model_validate(location_of_work_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, location_id: UUID) -> schemas.LocationOfWork:
        log_function_info(cls)
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        location_db.prep_delete = datetime.datetime.utcnow()
        return schemas.LocationOfWork.model_validate(location_db)


class TeamActorAssign:
    @classmethod
    @db_session
    def get(cls, team_actor_assign_id: UUID) -> schemas.TeamActorAssignShow:
        team_actor_assign_db = models.TeamActorAssign.get_for_update(id=team_actor_assign_id)
        return schemas.TeamActorAssignShow.model_validate(team_actor_assign_db)

    @classmethod
    @db_session
    def get_at__date(cls, person_id: UUID, date: datetime.date | None) -> schemas.TeamActorAssignShow | None:
        """Bei date == None wird das aktuellste Assignment zurückgegeben."""

        all_assignments_db = models.TeamActorAssign.select(lambda x: x.person.id == person_id)

        if not all_assignments_db.count():
            assignment_db = None
        else:
            if not date:
                latest_assignment = max(all_assignments_db, key=lambda x: x.start)
                if not latest_assignment.end or (latest_assignment.end > datetime.date.today()):
                    assignment_db = latest_assignment
                else:
                    assignment_db = None
            else:
                for assignm in all_assignments_db:
                    if assignm.start <= date and (assignm.end > date or assignm.end is None):
                        assignment_db = assignm
                        break
                else:
                    assignment_db = None

        return None if not assignment_db else schemas.TeamActorAssignShow.model_validate(assignment_db)

    @classmethod
    @db_session
    def get_all_between_dates(
            cls, person_id: UUID, team_id: UUID,
            date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamActorAssignShow]:
        assignments_db = (models.TeamActorAssign.select()
                          .filter(lambda taa: taa.team.id == team_id).filter(lambda taa: taa.person.id == person_id)
                          .filter(lambda taa: taa.start <= date_end).filter(lambda taa: taa.end >= date_start or taa.end is None))
        return [schemas.TeamActorAssignShow.model_validate(taa) for taa in assignments_db]

    @classmethod
    @db_session
    def get_all_at__date(cls, date: datetime.date, team_id: UUID) -> list[schemas.TeamActorAssignShow]:
        all_actor_location_assigns = models.TeamActorAssign.select(
            lambda tla: tla.start <= date and (tla.end is None or tla.end > date) and tla.team.id == team_id)
        return [schemas.TeamActorAssignShow.model_validate(tla) for tla in all_actor_location_assigns]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, team_actor_assign: schemas.TeamActorAssignCreate,
               assign_id: UUID | None = None) -> schemas.TeamActorAssignShow:
        log_function_info(cls)
        person_db = models.Person.get(id=team_actor_assign.person.id)
        team_db = models.Team.get(id=team_actor_assign.team.id)
        if team_actor_assign.start:
            if assign_id:
                new_team_aa = models.TeamActorAssign(start=team_actor_assign.start, person=person_db, team=team_db,
                                                     id=assign_id)
            else:
                new_team_aa = models.TeamActorAssign(start=team_actor_assign.start, person=person_db, team=team_db)
        else:
            if assign_id:
                new_team_aa = models.TeamActorAssign(person=person_db, team=team_db, id=assign_id)
            else:
                new_team_aa = models.TeamActorAssign(person=person_db, team=team_db)
        return schemas.TeamActorAssignShow.model_validate(new_team_aa)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def set_end_date(cls, team_actor_assign_id: UUID, end_date: datetime.date | None = None):
        log_function_info(cls)
        team_actor_assign_db = models.TeamActorAssign.get_for_update(id=team_actor_assign_id)
        team_actor_assign_db.end = end_date

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, team_actor_assign_id: UUID):
        log_function_info(cls)
        team_actor_assign_db = models.TeamActorAssign.get_for_update(id=team_actor_assign_id)
        team_actor_assign_db.delete()


class TeamLocationAssign:
    @classmethod
    @db_session
    def get(cls, team_location_assign_id: UUID) -> schemas.TeamLocationAssignShow:
        team_location_assign_db = models.TeamLocationAssign.get_for_update(id=team_location_assign_id)
        return schemas.TeamLocationAssignShow.model_validate(team_location_assign_db)

    @classmethod
    @db_session
    def get_at__date(cls, location_id: UUID, date: datetime.date | None) -> schemas.TeamLocationAssignShow | None:
        """Bei date == None wird das aktuellste Assignment zurückgegeben."""

        all_assignments_db = models.TeamLocationAssign.select(lambda x: x.location_of_work.id == location_id)

        if not all_assignments_db.count():
            assignment_db = None
        else:
            if not date:
                latest_assignment = max(all_assignments_db, key=lambda x: x.start)
                if not latest_assignment.end or (latest_assignment.end > datetime.date.today()):
                    assignment_db = latest_assignment
                else:
                    assignment_db = None
            else:
                for assignm in all_assignments_db:
                    if assignm.start <= date and (assignm.end > date or assignm.end is None):
                        assignment_db = assignm
                        break
                else:
                    assignment_db = None

        return None if not assignment_db else schemas.TeamLocationAssignShow.model_validate(assignment_db)

    @classmethod
    @db_session
    def get_all_between_dates(
            cls, location_id: UUID, team_id: UUID,
            date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamLocationAssignShow]:
        assignments_db = (models.TeamLocationAssign.select()
                          .filter(lambda tla: tla.team.id == team_id)
                          .filter(lambda tla: tla.location_of_work.id == location_id)
                          .filter(lambda tla: tla.start <= date_end)
                          .filter(lambda tla: tla.end >= date_start or tla.end is None))
        return [schemas.TeamLocationAssignShow.model_validate(tla) for tla in assignments_db]

    @classmethod
    @db_session
    def get_all_at__date(cls, date: datetime.date, team_id: UUID) -> list[schemas.TeamLocationAssignShow]:
        all_team_location_assigns = models.TeamLocationAssign.select(
            lambda tla: tla.start <= date and (tla.end is None or tla.end > date) and tla.team.id == team_id)
        return [schemas.TeamLocationAssignShow.model_validate(tla) for tla in all_team_location_assigns]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, team_location_assign: schemas.TeamLocationAssignCreate,
               assign_id: UUID | None = None) -> schemas.TeamLocationAssignShow:
        """Wenn eine assign_id angegeben ist, wird der neu erstellten team_location_assign diese UUID als
        Primärschlüssel zugeordnet."""
        log_function_info(cls)
        location_db = models.LocationOfWork.get(id=team_location_assign.location_of_work.id)
        team_db = models.Team.get(id=team_location_assign.team.id)
        if team_location_assign.start:
            if assign_id:
                new_team_la = models.TeamLocationAssign(start=team_location_assign.start, location_of_work=location_db,
                                                        team=team_db, id=assign_id)
            else:
                new_team_la = models.TeamLocationAssign(start=team_location_assign.start, location_of_work=location_db,
                                                        team=team_db)
        else:
            if assign_id:
                new_team_la = models.TeamLocationAssign(location_of_work=location_db, team=team_db, id=assign_id)
            else:
                new_team_la = models.TeamLocationAssign(location_of_work=location_db, team=team_db)
        return schemas.TeamLocationAssignShow.model_validate(new_team_la)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def set_end_date(cls, team_location_assign_id: UUID, end_date: datetime.date | None = None):
        log_function_info(cls)
        team_location_assign_db = models.TeamLocationAssign.get_for_update(id=team_location_assign_id)
        team_location_assign_db.end = end_date

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, team_loc_assign_id: UUID):
        log_function_info(cls)
        team_loc_assign_db = models.TeamLocationAssign.get_for_update(id=team_loc_assign_id)
        team_loc_assign_db.delete()


class TimeOfDay:
    @classmethod
    @db_session
    def get(cls, time_of_day_id: UUID):
        time_of_day_db = models.TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
        return schemas.TimeOfDayShow.model_validate(time_of_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, time_of_day: schemas.TimeOfDayCreate, project_id: UUID) -> schemas.TimeOfDay:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day.time_of_day_enum.id)

        time_of_day_db = models.TimeOfDay(name=time_of_day.name,
                                          time_of_day_enum=time_of_day_enum_db,
                                          project=project_db,
                                          start=time_of_day.start,
                                          end=time_of_day.end)
        # PonyOrm hat offenbar Probleme erzeugte Entities mit Optional-Values gleich im Anschluss zu validieren.
        # Daher dieser Umweg:
        time_of_day_partial = time_of_day_db.to_dict(exclude=['prep_delete', 'project_standard', 'project_defaults'],
                                                     related_objects=True)

        return schemas.TimeOfDay(**time_of_day_partial, prep_delete=None, project_standard=None)


    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, time_of_day: schemas.TimeOfDay):
        log_function_info(cls)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day.id)
        time_of_day_db.name = time_of_day.name
        time_of_day_db.start = time_of_day.start
        time_of_day_db.end = time_of_day.end
        time_of_day_db.time_of_day_enum = models.TimeOfDayEnum.get_for_update(id=time_of_day.time_of_day_enum.id)
        return schemas.TimeOfDay.model_validate(time_of_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_to_model(cls, time_of_day: schemas.TimeOfDay,
                     pydantic_model: schemas.ModelWithTimeOfDays, db_model):
        log_function_info(cls)
        if not (isinstance(pydantic_model, schemas.ModelWithTimeOfDays) or isinstance(pydantic_model, schemas.Project)):
            raise ValueError
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day.id)
        instance_db = db_model.get_for_update(id=pydantic_model.id)
        instance_db.time_of_days.add(time_of_day_db)
        return type(pydantic_model).model_validate(instance_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, time_of_day_id: UUID) -> schemas.TimeOfDay:
        log_function_info(cls)
        time_of_day_db = models.TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
        time_of_day_db.prep_delete = datetime.datetime.utcnow()
        return schemas.TimeOfDay.model_validate(time_of_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undo_delete(cls, time_of_day_id: UUID) -> schemas.TimeOfDay:
        log_function_info(cls)
        time_of_day_db = models.TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
        time_of_day_db.prep_delete = None
        return schemas.TimeOfDay.model_validate(time_of_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_unused(cls, project_id: UUID) -> None:
        log_function_info(cls)
        t_o_ds_from__project = models.TimeOfDay.select(lambda t: t.project.id == project_id)
        for t_o_d in t_o_ds_from__project:
            if t_o_d.prep_delete:
                continue
            empty_check = [t_o_d.persons_defaults, t_o_d.actor_plan_periods_defaults,
                           t_o_d.avail_days_defaults, t_o_d.avail_days, t_o_d.locations_of_work_defaults,
                           t_o_d.location_plan_periods_defaults, t_o_d.events_defaults, t_o_d.events]
            if all([not t_o_d.project_defaults, all(default.is_empty() for default in empty_check)]):
                t_o_d.prep_delete = datetime.datetime.utcnow()

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(cls, project_id: UUID) -> None:
        log_function_info(cls)
        t_o_ds_from__project = models.TimeOfDay.select(lambda t: t.project.id == project_id)
        for t_o_d in t_o_ds_from__project:
            if t_o_d.prep_delete:
                t_o_d.delete()


class TimeOfDayEnum:
    @classmethod
    @db_session
    def get(cls, time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum_id)
        return schemas.TimeOfDayEnumShow.model_validate(time_of_day_enum_db)

    @classmethod
    @db_session
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.TimeOfDayEnumShow]:
        project_db = models.Project.get_for_update(id=project_id)
        return [schemas.TimeOfDayEnumShow.model_validate(t_o_d_enum) for t_o_d_enum in project_db.time_of_day_enums]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, time_of_day_enum: schemas.TimeOfDayEnumCreate,
               time_of_day_enum_id: UUID = None) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=time_of_day_enum.project.id)
        if time_of_day_enum_id:
            time_of_day_enum_db = models.TimeOfDayEnum(id=time_of_day_enum_id,
                                                       name=time_of_day_enum.name,
                                                       abbreviation=time_of_day_enum.abbreviation,
                                                       time_index=time_of_day_enum.time_index,
                                                       project=project_db
                                                       )
        else:
            time_of_day_enum_db = models.TimeOfDayEnum(name=time_of_day_enum.name,
                                                       abbreviation=time_of_day_enum.abbreviation,
                                                       time_index=time_of_day_enum.time_index,
                                                       project=project_db)

        return schemas.TimeOfDayEnumShow.model_validate(time_of_day_enum_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, time_of_day_enum: schemas.TimeOfDayEnum) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum.id)
        time_of_day_enum_db.set(**time_of_day_enum.model_dump(include={'name', 'abbreviation', 'time_index'}))

        return schemas.TimeOfDayEnumShow.model_validate(time_of_day_enum_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def prep_delete(cls, time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum_id)
        project_id = time_of_day_enum_db.project.id
        time_of_day_enum_db.prep_delete = datetime.datetime.utcnow()

        return schemas.TimeOfDayEnumShow.model_validate(time_of_day_enum_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undo_prep_delete(cls, time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum_id)
        project_id = time_of_day_enum_db.project.id
        time_of_day_enum_db.prep_delete = None

        return schemas.TimeOfDayEnumShow.model_validate(time_of_day_enum_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, time_of_day_enum_id: UUID):
        log_function_info(cls)
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum_id)
        project_id = time_of_day_enum_db.project.id
        time_of_day_enum_db.delete()

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def consolidate_indexes(cls, project_id: UUID):
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_enums = (t for t in TimeOfDayEnum.get_all_from__project(project_id) if not t.prep_delete)
        for i, t_o_d_enum in enumerate(sorted(time_of_day_enums, key=lambda x: x.time_index), start=1):
            t_o_d_enum_db = models.TimeOfDayEnum.get_for_update(id=t_o_d_enum.id)
            t_o_d_enum_db.time_index = i
            commit()


class ExcelExportSettings:
    @classmethod
    @db_session
    def get(cls, excel_export_settings_id: UUID) -> schemas.ExcelExportSettingsShow:
        excel_export_settings_db = models.ExcelExportSettings.get_for_update(id=excel_export_settings_id)
        return schemas.ExcelExportSettingsShow.model_validate(excel_export_settings_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, excel_settings: schemas.ExcelExportSettingsCreate) -> schemas.ExcelExportSettingsShow:
        log_function_info(cls)
        excel_settings_db = models.ExcelExportSettings(**excel_settings.model_dump())
        return schemas.ExcelExportSettingsShow.model_validate(excel_settings_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, excel_export_settings: schemas.ExcelExportSettings) -> schemas.ExcelExportSettings:
        log_function_info(cls)
        excel_export_settings_db = models.ExcelExportSettings.get_for_update(lambda e: e.id == excel_export_settings.id)
        excel_export_settings_db.set(**excel_export_settings.model_dump(exclude={'id'}))

        return schemas.ExcelExportSettings.model_validate(excel_export_settings_db)


class Address:
    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, address: schemas.AddressCreate) -> schemas.Address:
        log_function_info(cls)
        address_db = models.Address(street=address.street, postal_code=address.postal_code, city=address.city)
        return schemas.Address.model_validate(address_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, address: schemas.Address) -> schemas.Address:
        log_function_info(cls)
        address_db = models.Address.get_for_update(lambda a: a.id == address.id)
        # for key, val in address.model_dump(include={'street', 'postal_code', 'city'}).items():
        #     address_db.__setattr__(key, val)
        address_db.set(**address.model_dump(include={'street', 'postal_code', 'city'}))
        return schemas.Address.model_validate(address_db)


class MaxFairShiftsOfApp:
    @classmethod
    @db_session
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.MaxFairShiftsOfAppShow]:
        max_fair_shifts = (models.MaxFairShiftsOfApp.select()
                           .filter(lambda mfs: mfs.actor_plan_period.plan_period.id == plan_period_id))
        return [schemas.MaxFairShiftsOfAppShow.model_validate(mfs) for mfs in max_fair_shifts]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppCreate) -> schemas.MaxFairShiftsOfAppShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=max_fair_shifts_per_app.actor_plan_period_id)
        if not max_fair_shifts_per_app.id:
            max_fair_shifts_per_app_db = models.MaxFairShiftsOfApp(
                max_shifts=max_fair_shifts_per_app.max_shifts,
                fair_shifts=max_fair_shifts_per_app.fair_shifts,
                actor_plan_period=actor_plan_period_db
            )
        else:
            max_fair_shifts_per_app_db = models.MaxFairShiftsOfApp(
                id=max_fair_shifts_per_app.id,
                max_shifts=max_fair_shifts_per_app.max_shifts,
                fair_shifts=max_fair_shifts_per_app.fair_shifts,
                actor_plan_period=actor_plan_period_db
            )
        return schemas.MaxFairShiftsOfAppShow.model_validate(max_fair_shifts_per_app_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, max_fair_shifts_per_app_id: UUID):
        log_function_info(cls)
        max_fair_shifts_per_app_db = models.MaxFairShiftsOfApp.get_for_update(id=max_fair_shifts_per_app_id)
        max_fair_shifts_per_app_db.delete()


class PlanPeriod:
    @classmethod
    @db_session
    def get(cls, plan_period_id: UUID) -> schemas.PlanPeriodShow:
        return schemas.PlanPeriodShow.model_validate(models.PlanPeriod.get_for_update(id=plan_period_id))

    @classmethod
    @db_session
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.PlanPeriodShow]:
        plan_periods_db = models.PlanPeriod.select(lambda pp: pp.project.id == project_id)
        return [schemas.PlanPeriodShow.model_validate(p) for p in plan_periods_db]
    @classmethod
    @db_session
    def get_all_from__team(cls, team_id: UUID) -> list[schemas.PlanPeriodShow]:
        plan_periods_db = models.PlanPeriod.select(lambda pp: pp.team.id == team_id)
        return [schemas.PlanPeriodShow.model_validate(p) for p in plan_periods_db]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=plan_period.team.id)
        plan_period_db = models.PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                                           notes=plan_period.notes, team=team_db)
        return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period.id)
        plan_period_db.set(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                           notes=plan_period.notes, notes_for_employees=plan_period.notes_for_employees,
                           remainder=plan_period.remainder)
        for actor_plan_period in plan_period_db.actor_plan_periods:
            for avail_day in actor_plan_period.avail_days:
                if not (plan_period.start <= avail_day.date <= plan_period.end) and not avail_day.prep_delete:
                    avail_day.prep_delete = datetime.datetime.utcnow()
        for location_plan_period in plan_period_db.location_plan_periods:
            for event in location_plan_period.events:
                if not (plan_period.start <= event.date <= plan_period.end) and not event.prep_delete:
                    event.prep_delete = datetime.datetime.utcnow()

        return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_notes(cls, plan_period_id: UUID, notes: str) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        plan_period_db.notes = notes

        return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, plan_period_id: UUID) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        plan_period_db.prep_delete = datetime.datetime.utcnow()

        return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(cls, plan_period_id: UUID):
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        plan_period_db.prep_delete = None

        return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(cls, team_id: UUID):
        pp_with_prep_deletes_db = models.PlanPeriod.select(lambda pp: pp.team.id == team_id and pp.prep_delete)
        for plan_period in pp_with_prep_deletes_db:
            plan_period.delete()


class LocationPlanPeriod:
    @classmethod
    @db_session
    def get(cls, location_plan_period_id: UUID) -> schemas.LocationPlanPeriodShow:
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)

        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, plan_period_id: UUID, location_id: UUID, location_plan_period_id: UUID = None) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        if location_plan_period_id:
            location_plan_period_db = models.LocationPlanPeriod(id=location_plan_period_id, plan_period=plan_period_db,
                                                                location_of_work=location_db)
        else:
            location_plan_period_db = models.LocationPlanPeriod(plan_period=plan_period_db,
                                                                location_of_work=location_db)
        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, location_plan_period_id: UUID):
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        location_plan_period_db.delete()

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_notes(cls, location_plan_period_id: UUID, notes: str) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        location_plan_period_db.set(notes=notes)
        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_time_of_day(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        location_plan_period_db.time_of_days.add(time_of_day_db)

        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_in_time_of_day(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        location_plan_period_db.time_of_days.remove(time_of_day_db)

        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        location_plan_period_db.time_of_day_standards.remove(time_of_day_db)

        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationPlanPeriodShow, UUID | None]:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in location_plan_period_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                location_plan_period_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        location_plan_period_db.time_of_day_standards.add(time_of_day_db)
        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db), old_time_of_day_standard_id

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_fixed_cast(cls, location_plan_period_id: UUID, fixed_cast: str) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        location_plan_period_db.fixed_cast = fixed_cast

        return schemas.LocationPlanPeriodShow.model_validate(location_plan_period_db)


class EventGroup:
    @classmethod
    @db_session
    def get(cls, event_group_id: UUID) -> schemas.EventGroupShow:
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)
        return schemas.EventGroupShow.model_validate(event_group_db)

    @classmethod
    @db_session
    def get_master_from__location_plan_period(cls, location_plan_period_id: UUID) -> schemas.EventGroupShow:
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        event_group_db = location_plan_period_db.event_group
        return schemas.EventGroupShow.model_validate(event_group_db)

    @classmethod
    @db_session
    def get_child_groups_from__parent_group(cls, event_group_id) -> list[schemas.EventGroupShow]:
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)

        return [schemas.EventGroupShow.model_validate(e) for e in event_group_db.event_groups]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, *, location_plan_period_id: Optional[UUID] = None,
               event_group_id: Optional[UUID] = None, undo_group_id: UUID = None) -> schemas.EventGroupShow:
        log_function_info(cls)
        location_plan_period_db = (models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
                                   if location_plan_period_id else None)
        event_group_db = models.EventGroup.get_for_update(id=event_group_id) if event_group_id else None

        if undo_group_id:
            new_event_group_db = models.EventGroup(id=undo_group_id, location_plan_period=location_plan_period_db,
                                                   event_group=event_group_db)
        else:
            new_event_group_db = models.EventGroup(location_plan_period=location_plan_period_db,
                                                   event_group=event_group_db)

        return schemas.EventGroupShow.model_validate(new_event_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_nr_event_groups(cls, event_group_id: UUID, nr_event_groups: int | None) -> schemas.EventGroupShow:
        log_function_info(cls)
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)
        event_group_db.nr_event_groups = nr_event_groups

        return schemas.EventGroupShow.model_validate(event_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_variation_weight(cls, event_group_id: UUID, variation_weight: int) -> schemas.EventGroupShow:
        log_function_info(cls)
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)
        event_group_db.variation_weight = variation_weight

        return schemas.EventGroupShow.model_validate(event_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def set_new_parent(cls, event_group_id: UUID, new_parent_id: UUID) -> schemas.EventGroupShow:
        log_function_info(cls)
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)
        new_parent_db = models.EventGroup.get_for_update(id=new_parent_id)
        event_group_db.event_group = new_parent_db

        return schemas.EventGroupShow.model_validate(event_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, event_group_id: UUID):
        log_function_info(cls)
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)
        event_group_db.delete()


class CastGroup:
    @classmethod
    @db_session
    def get(cls, cast_group_id: UUID) -> schemas.CastGroupShow:
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.CastGroupShow]:
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)

        return [schemas.CastGroupShow.model_validate(cg) for cg in plan_period_db.cast_groups]

    @classmethod
    @db_session
    def get_cast_group_of_event(cls, event_id: UUID) -> schemas.CastGroupShow:
        cast_group_db = models.Event.get(id=event_id).cast_group
        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, *, plan_period_id: UUID, restore_cast_group: schemas.CastGroupShow = None) -> schemas.CastGroupShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        if restore_cast_group:
            cast_rule_db = (models.CastRule.get_for_update(id=restore_cast_group.cast_rule.id)
                            if restore_cast_group.cast_rule else None)
            parent_groups_db = [models.CastGroup.get_for_update(id=cg.id) for cg in restore_cast_group.parent_groups]
            child_groups_db = [models.CastGroup.get_for_update(id=cg.id) for cg in restore_cast_group.child_groups]
            cast_group_db = models.CastGroup(id=restore_cast_group.id, nr_actors=0,
                                             plan_period=plan_period_db, cast_rule=cast_rule_db)
            commit()
            cast_group_db.parent_groups.add(parent_groups_db)
            cast_group_db.child_groups.add(child_groups_db)
            cast_group_db.set(**restore_cast_group.model_dump(include={'nr_actors', 'fixed_cast', 'strict_cast_pref'}))
        else:
            cast_group_db = models.CastGroup(nr_actors=0, plan_period=plan_period_db)
        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def set_new_parent(cls, cast_group_id: UUID, new_parent_id: UUID | None) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        new_parent_db = models.CastGroup.get_for_update(id=new_parent_id)
        cast_group_db.parent_groups.add(new_parent_db)

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_from_parent(cls, cast_group_id: UUID, parent_group_id: UUID | None) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        parent_group_db = models.CastGroup.get_for_update(id=parent_group_id)
        cast_group_db.parent_groups.remove(parent_group_db)

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_fixed_cast(cls, cast_group_id: UUID, fixed_cast: str) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        cast_group_db.fixed_cast = fixed_cast

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_nr_actors(cls, cast_group_id: UUID, nr_actors: int) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        cast_group_db.nr_actors = nr_actors

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_strict_cast_pref(cls, cast_group_id: UUID, strict_cast_pref: int) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        cast_group_db.strict_cast_pref = strict_cast_pref

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_custom_rule(cls, cast_group_id: UUID, custom_rule: str) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        cast_group_db.custom_rule = custom_rule

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_cast_rule(cls, cast_group_id: UUID, cast_rule_id: UUID | None) -> schemas.CastGroupShow:
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        cast_rule_db = models.CastRule.get_for_update(id=cast_rule_id) if cast_rule_id else None
        cast_group_db.cast_rule = cast_rule_db

        return schemas.CastGroupShow.model_validate(cast_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, cast_group_id: UUID):
        log_function_info(cls)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group_id)
        cast_group_db.delete()


class CastRule:
    @classmethod
    @db_session
    def get(cls, cast_rule_id: UUID) -> schemas.CastRuleShow:
        cast_rule_db = models.CastRule.get_for_update(id=cast_rule_id)
        return schemas.CastRuleShow.model_validate(cast_rule_db)

    @classmethod
    @db_session
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.CastRuleShow]:
        project_db = models.Project.get_for_update(id=project_id)
        return [schemas.CastRuleShow.model_validate(cl) for cl in project_db.cast_rules]

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, project_id: UUID, name: str, rule: str, restore_id: UUID | None = None) -> schemas.CastRuleShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=project_id)
        if restore_id:
            cast_rule_db = models.CastRule(id=restore_id, project=project_db, name=name, rule=rule)
        else:
            cast_rule_db = models.CastRule(project=project_db, name=name, rule=rule)

        return schemas.CastRuleShow.model_validate(cast_rule_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, cast_rule_id: UUID):
        log_function_info(cls)
        cast_rule_db = models.CastRule.get_for_update(id=cast_rule_id)
        cast_rule_db.delete()


class Event:
    @classmethod
    @db_session
    def get(cls, event_id: UUID) -> schemas.EventShow:
        event_db = models.Event.get_for_update(id=event_id)
        return schemas.EventShow.model_validate(event_db)

    @classmethod
    @db_session
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.EventShow]:
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        events_db = models.Event.select(lambda e: e.plan_period == plan_period_db)

        return [schemas.EventShow.model_validate(e) for e in events_db]

    @classmethod
    @db_session
    def get_all_from__plan_period_date_time_of_day(cls, plan_period_id: UUID,
                                                   date: datetime.date, time_index: int) -> list[schemas.EventShow]:
        plan_period_db = models.PlanPeriod.get(id=plan_period_id)
        events_db = models.Event.select(lambda e: e.plan_period == plan_period_db and e.date == date
                                                  and e.time_of_day.time_of_day_enum.time_index == time_index)
        return [schemas.EventShow.model_validate(e) for e in events_db]

    @classmethod
    @db_session
    def get_all_from__location_plan_period(cls, location_plan_period_id) -> list[schemas.EventShow]:
        events_db = models.Event.select(lambda e: e.location_plan_period.id == location_plan_period_id)

        return [schemas.EventShow.model_validate(e) for e in events_db]

    @classmethod
    @db_session
    def get_from__event_group(cls, event_group_id) -> schemas.EventShow | None:
        event_group_db = models.EventGroup.get_for_update(id=event_group_id)
        event_db = event_group_db.event
        return schemas.EventShow.model_validate(event_db) if event_db else None

    @classmethod
    @db_session
    def get_from__location_pp_date_tod(cls, location_plan_period_id: UUID, date: datetime.date,
                                       time_of_day_id) -> schemas.EventShow:
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=location_plan_period_id)
        event_db = models.Event.get_for_update(
            lambda e: e.location_plan_period == location_plan_period_db and e.date == date and
                      e.time_of_day == models.TimeOfDay.get_for_update(id=time_of_day_id) and not e.prep_delete)

        return schemas.EventShow.model_validate(event_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, event: schemas.EventCreate) -> schemas.EventShow:
        log_function_info(cls)
        location_plan_period_db = models.LocationPlanPeriod.get_for_update(id=event.location_plan_period.id)
        master_event_group_db = location_plan_period_db.event_group
        event_group = EventGroup.create(event_group_id=master_event_group_db.id)
        cast_group = CastGroup.create(plan_period_id=event.location_plan_period.plan_period.id)
        cast_group_db = models.CastGroup.get_for_update(id=cast_group.id)
        cast_group_db.nr_actors = location_plan_period_db.nr_actors
        cast_group_db.fixed_cast = location_plan_period_db.fixed_cast
        event_db = models.Event(
            date=event.date, time_of_day=models.TimeOfDay.get_for_update(id=event.time_of_day.id),
            event_group=models.EventGroup.get_for_update(id=event_group.id),
            cast_group=models.CastGroup.get_for_update(id=cast_group.id),
            location_plan_period=location_plan_period_db)

        return schemas.EventShow.model_validate(event_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_time_of_day(cls, event_id: UUID, new_time_of_day_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        event_db = models.Event.get_for_update(id=event_id)
        new_time_of_day_db = models.TimeOfDay.get_for_update(id=new_time_of_day_id)
        event_db.time_of_day = new_time_of_day_db

        return schemas.EventShow.model_validate(event_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, event_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        event_db = models.Event.get_for_update(id=event_id)
        deleted = schemas.EventShow.model_validate(event_db)
        event_group_db = event_db.event_group
        cast_group_db = event_db.cast_group
        event_db.delete()
        event_group_db.delete()
        cast_group_db.delete()

        return deleted

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_flag(cls, event_id: UUID, flag_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        event_db = models.Event.get_for_update(id=event_id)
        flag_db = models.Flag.get_for_update(id=flag_id)
        event_db.flags.add(flag_db)
        return schemas.EventShow.model_validate(event_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_flag(cls, event_id: UUID, flag_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        event_db = models.Event.get_for_update(id=event_id)
        flag_db = models.Flag.get_for_update(id=flag_id)
        event_db.flags.remove(flag_db)
        return schemas.EventShow.model_validate(event_db)


class ActorPlanPeriod:
    @classmethod
    @db_session
    def get(cls, actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodShow:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, plan_period_id: UUID, person_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        person_db = models.Person.get_for_update(id=person_id)
        actor_plan_period_db = models.ActorPlanPeriod(plan_period=plan_period_db, person=person_db)

        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update(cls, actor_plan_period: schemas.ActorPlanPeriodShow) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period.id)

        actor_plan_period_db.time_of_days.clear()
        for t_o_d in actor_plan_period.time_of_days:
            actor_plan_period_db.time_of_days.add(models.TimeOfDay.get_for_update(id=t_o_d.id))
        actor_plan_period_db.set(
            **actor_plan_period.model_dump(
                include={'notes', 'requested_assignments'}))

        '''Es fehlen noch actor_partner_location_prefs, combination_locations_possibles'''

        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_notes(cls, actor_plan_period: schemas.ActorPlanPeriodUpdate) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period.id)
        actor_plan_period_db.set(notes=actor_plan_period.notes)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_requested_assignments(cls, actor_plan_period_id: UUID,
                                     requested_assignments: int) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        actor_plan_period_db.set(requested_assignments=requested_assignments)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_time_of_day(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        actor_plan_period_db.time_of_days.add(time_of_day_db)

        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_in_time_of_day(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        actor_plan_period_db.time_of_days.remove(time_of_day_db)

        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        actor_plan_period_db.time_of_day_standards.remove(time_of_day_db)

        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ActorPlanPeriodShow, UUID | None]:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in actor_plan_period_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                actor_plan_period_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        actor_plan_period_db.time_of_day_standards.add(time_of_day_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db), old_time_of_day_standard_id

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(cls, actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        actor_plan_period_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(cls, actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        actor_plan_period_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_location_pref(cls, actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_plan_period_db.actor_location_prefs_defaults.add(location_pref_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_location_pref(cls, actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_plan_period_db.actor_location_prefs_defaults.remove(location_pref_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_partner_location_pref(cls, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_plan_period_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_partner_location_pref(cls, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_plan_period_db.actor_partner_location_prefs_defaults.remove(partner_location_pref_db)
        return schemas.ActorPlanPeriodShow.model_validate(actor_plan_period_db)


class AvailDayGroup:
    @classmethod
    @db_session
    def get(cls, avail_day_group_id: UUID) -> schemas.AvailDayGroupShow:
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        return schemas.AvailDayGroupShow.model_validate(avail_day_group_db)

    @classmethod
    @db_session
    def get_master_from__actor_plan_period(cls, actor_plan_period_id: UUID) -> schemas.AvailDayGroupShow:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        avail_day_group_db = actor_plan_period_db.avail_day_group
        return schemas.AvailDayGroupShow.model_validate(avail_day_group_db)

    @classmethod
    @db_session
    def get_child_groups_from__parent_group(cls, avail_day_group_id) -> list[schemas.AvailDayGroupShow]:
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        return [schemas.AvailDayGroupShow.model_validate(adg) for adg in avail_day_group_db.avail_day_groups]


    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, *, actor_plan_period_id: Optional[UUID] = None,
               avail_day_group_id: Optional[UUID] = None, undo_id: UUID = None) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(
            id=actor_plan_period_id) if actor_plan_period_id else None
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id) if avail_day_group_id else None
        if undo_id:
            new_avail_day_group = models.AvailDayGroup(id=undo_id, actor_plan_period=actor_plan_period_db,
                                                       avail_day_group=avail_day_group_db)
        else:
            new_avail_day_group = models.AvailDayGroup(actor_plan_period=actor_plan_period_db,
                                                       avail_day_group=avail_day_group_db)

        return schemas.AvailDayGroupShow.model_validate(new_avail_day_group)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_nr_avail_day_groups(cls, avail_day_group_id: UUID,
                                   nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        avail_day_group_db.nr_avail_day_groups = nr_avail_day_groups

        return schemas.AvailDayGroupShow.model_validate(avail_day_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_variation_weight(cls, avail_day_group_id: UUID, variation_weight: int) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        avail_day_group_db.variation_weight = variation_weight

        return schemas.AvailDayGroupShow.model_validate(avail_day_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_mandatory_nr_avail_day_groups(
            cls, avail_day_group_id: UUID, mandatory_nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        avail_day_group_db.mandatory_nr_avail_day_groups = mandatory_nr_avail_day_groups

        return schemas.AvailDayGroupShow.model_validate(avail_day_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def set_new_parent(cls, avail_day_group_id: UUID, new_parent_id: UUID) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        new_parent_db = models.AvailDayGroup.get_for_update(id=new_parent_id)
        avail_day_group_db.avail_day_group = new_parent_db

        return schemas.AvailDayGroupShow.model_validate(avail_day_group_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, avail_day_group_id: UUID):
        log_function_info(cls)
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        avail_day_group_db.delete()


class AvailDay:
    @classmethod
    @db_session
    def get(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session
    def get_from__actor_pp_date_tod(cls, actor_plan_period_id: UUID, date: datetime.date, time_of_day_id) -> schemas.AvailDayShow:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        avail_day_db = models.AvailDay.get_for_update(
            lambda ad: ad.actor_plan_period == actor_plan_period_db and ad.date == date and
                       ad.time_of_day == models.TimeOfDay.get_for_update(id=time_of_day_id) and not ad.prep_delete)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.AvailDayShow]:
        plan_period_db = models.PlanPeriod.get(id=plan_period_id)
        avail_days_db = models.AvailDay.select(lambda avd: avd.plan_period == plan_period_db)

        return [schemas.AvailDayShow.model_validate(avd) for avd in avail_days_db]

    @classmethod
    @db_session
    def get_all_from__actor_plan_period(cls, actor_plan_period_id: UUID) -> list[schemas.AvailDayShow]:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        avail_days_db = models.AvailDay.select(lambda a: a.actor_plan_period == actor_plan_period_db)
        return [schemas.AvailDayShow.model_validate(ad) for ad in avail_days_db]

    @classmethod
    @db_session
    def get_all_from__plan_period_date(cls, plan_period_id: UUID, date: datetime.date) -> list[schemas.AvailDayShow]:
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        avail_days_db = models.AvailDay.select(lambda a: a.plan_period == plan_period_db and a.date == date)

        return [schemas.AvailDayShow.model_validate(avd) for avd in avail_days_db]

    @classmethod
    @db_session
    def get_all_from__plan_period__date__time_of_day__location_prefs(
            cls, plan_period_id: UUID, date: datetime.date, time_of_day_index: int,
            location_of_work_ids: set[UUID]) -> list[schemas.AvailDayShow]:
        """location_of_work_ids: locations aller Events welche an diesem Tag zu dieser Tageszeit gesetzt sind.
        Gibt alle avail_day zurück, welche in der Planperiode zu einer Tageszeit eines Tages gesetzt sind.
        Wenn der Actor eines avail_days in keiner Location der Tageszeit eingesetzt werden will,
        wird dieser avail_day aussortiert"""
        plan_period_db = models.PlanPeriod.get(id=plan_period_id)
        avail_days_db = models.AvailDay.select(
            lambda a: a.plan_period == plan_period_db and a.date == date
                      and a.time_of_day.time_of_day_enum.time_index == time_of_day_index)
        # Wenn der Actor eines avail_days in keiner Location der Tageszeit eingesetzt werden will,
        # wird dieser avail_day aussortiert:
        avail_days_db = [
            avd for avd in avail_days_db
            if any(
                not avd.actor_location_prefs_defaults.select(
                    lambda alp: alp.location_of_work.id == location_of_work_id and alp.score == 0
                ).first() for location_of_work_id in location_of_work_ids
            )
        ]

        return [schemas.AvailDayShow.model_validate(avd) for avd in avail_days_db]

    @classmethod
    @db_session
    def get_from__avail_day_group(cls, avail_day_group_id) -> schemas.AvailDayShow | None:
        avail_day_group_db = models.AvailDayGroup.get_for_update(id=avail_day_group_id)
        avail_day_db = avail_day_group_db.avail_day
        return schemas.AvailDayShow.model_validate(avail_day_db) if avail_day_db else None

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, avail_day: schemas.AvailDayCreate) -> schemas.AvailDayShow:
        """Es wird eine AvailDay-AvailDayGroup für den avail_day angelegt, welche der Master-AvailDayGroup der
        ActorPlanPeriod zugeordnet ist. Der AvailDay-AvailDayGroup wird der avail_day zugeordnet."""
        log_function_info(cls)
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=avail_day.actor_plan_period.id)
        master_avail_day_group_db = actor_plan_period_db.avail_day_group
        avail_day_group_db = AvailDayGroup.create(avail_day_group_id=master_avail_day_group_db.id)
        avail_day_db = models.AvailDay(
            date=avail_day.date, time_of_day=models.TimeOfDay.get_for_update(id=avail_day.time_of_day.id),
            avail_day_group=models.AvailDayGroup.get_for_update(id=avail_day_group_db.id),
            actor_plan_period=actor_plan_period_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_time_of_day(cls, avail_day_id: UUID, new_time_of_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        new_time_of_day_db = models.TimeOfDay.get_for_update(id=new_time_of_day_id)
        avail_day_db.time_of_day = new_time_of_day_db

        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_time_of_days(cls, avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        time_of_days_db = [models.TimeOfDay.get_for_update(id=t.id) for t in time_of_days]
        avail_day_db.time_of_days.clear()
        avail_day_db.time_of_days.add(time_of_days_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        deleted = schemas.AvailDayShow.model_validate(avail_day_db)
        avail_day_group_db = avail_day_db.avail_day_group
        avail_day_db.delete()
        avail_day_group_db.delete()
        return deleted

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(cls, avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        avail_day_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(cls, avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        avail_day_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_location_pref(cls, avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        avail_day_db.actor_location_prefs_defaults.add(location_pref_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_location_pref(cls, avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        avail_day_db.actor_location_prefs_defaults.remove(location_pref_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_partner_location_pref(cls, avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        avail_day_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_partner_location_pref(cls, avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        avail_day_db.actor_partner_location_prefs_defaults.remove(partner_location_pref_db)
        return schemas.AvailDayShow.model_validate(avail_day_db)


class CombinationLocationsPossible:
    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, comb_loc_poss: schemas.CombinationLocationsPossibleCreate) -> schemas.CombinationLocationsPossibleShow:
        log_function_info(cls)
        project_db = models.Project.get_for_update(id=comb_loc_poss.project.id)
        new_comb_loc_poss = models.CombinationLocationsPossible(project=project_db,
                                                                time_span_between=comb_loc_poss.time_span_between)
        for loc in comb_loc_poss.locations_of_work:
            new_comb_loc_poss.locations_of_work.add(models.LocationOfWork.get_for_update(id=loc.id))

        return schemas.CombinationLocationsPossibleShow.model_validate(new_comb_loc_poss)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
        log_function_info(cls)
        comb_loc_poss_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_poss_id)
        comb_loc_poss_db.prep_delete = datetime.datetime.utcnow()

        return schemas.CombinationLocationsPossibleShow.model_validate(comb_loc_poss_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(cls, comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
        log_function_info(cls)
        comb_loc_poss_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_poss_id)
        comb_loc_poss_db.prep_delete = None

        return schemas.CombinationLocationsPossibleShow.model_validate(comb_loc_poss_db)


class ActorLocationPref:
    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, actor_loc_pref: schemas.ActorLocationPrefCreate) -> schemas.ActorLocationPrefShow:
        log_function_info(cls)

        project_db = models.Project.get_for_update(id=actor_loc_pref.person.project.id)
        person_db = models.Person.get_for_update(id=actor_loc_pref.person.id)
        location_db = models.LocationOfWork.get_for_update(id=actor_loc_pref.location_of_work.id)
        actor_loc_pref_db = models.ActorLocationPref(score=actor_loc_pref.score, project=project_db, person=person_db,
                                                     location_of_work=location_db)
        return schemas.ActorLocationPrefShow.model_validate(actor_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
        log_function_info(cls)
        actor_loc_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_loc_pref_db.prep_delete = datetime.datetime.utcnow()

        return schemas.ActorLocationPrefShow.model_validate(actor_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(cls, actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
        log_function_info(cls)
        actor_loc_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_loc_pref_db.prep_delete = None

        return schemas.ActorLocationPrefShow.model_validate(actor_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_unused(cls, project_id: UUID) -> list[UUID]:
        log_function_info(cls)
        a_l_prefs_from__project = models.ActorLocationPref.select(lambda a: a.project.id == project_id)

        deleted_a_l_pref_ids = []
        for a_l_pref in a_l_prefs_from__project:
            if a_l_pref.prep_delete:
                continue
            empty_check = [a_l_pref.actor_plan_periods_defaults, a_l_pref.avail_days_defaults]
            if all(default.is_empty() for default in empty_check) and not a_l_pref.person_default:
                a_l_pref.prep_delete = datetime.datetime.utcnow()
                deleted_a_l_pref_ids.append(a_l_pref.id)
        return deleted_a_l_pref_ids

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(cls, project_id: UUID) -> None:
        log_function_info(cls)
        a_l_prefs_form__project = models.ActorLocationPref.select(lambda a: a.project.id == project_id)
        for a_l_pref in a_l_prefs_form__project:
            if a_l_pref.prep_delete:
                a_l_pref.delete()


class ActorPartnerLocationPref:
    @classmethod
    @db_session
    def get(cls, actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        return schemas.ActorPartnerLocationPrefShow.model_validate(actor_partner_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefCreate) -> schemas.ActorPartnerLocationPrefShow:
        log_function_info(cls)

        person_db = models.Person.get_for_update(id=actor_partner_loc_pref.person.id)
        partner_db = models.Person.get_for_update(id=actor_partner_loc_pref.partner.id)
        location_db = models.LocationOfWork.get_for_update(id=actor_partner_loc_pref.location_of_work.id)
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref(score=actor_partner_loc_pref.score,
                                                                    person=person_db, partner=partner_db,
                                                                    location_of_work=location_db)
        return schemas.ActorPartnerLocationPrefShow.model_validate(actor_partner_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def modify(cls, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow) -> schemas.ActorPartnerLocationPrefShow:
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref.id)
        if actor_partner_loc_pref.person_default:
            person_default_db = models.Person.get_for_update(id=actor_partner_loc_pref.person_default.id)
        else:
            person_default_db = None
        actor_plan_periods_defaults_db = [models.ActorPlanPeriod.get_for_update(id=app.id)
                                          for app in actor_partner_loc_pref.actor_plan_periods_defaults]
        avail_days_defaults_db = [models.AvailDay.get_for_update(id=ad.id)
                                  for ad in actor_partner_loc_pref.avail_days_defaults]
        actor_partner_loc_pref_db.person_default = person_default_db
        actor_partner_loc_pref_db.actor_plan_periods_defaults.clear()
        actor_partner_loc_pref_db.actor_plan_periods_defaults.add(actor_plan_periods_defaults_db)
        actor_partner_loc_pref_db.avail_days_dafaults.clear()
        actor_partner_loc_pref_db.avail_days_dafaults.add(avail_days_defaults_db)

        return schemas.ActorPartnerLocationPrefShow.model_validate(actor_partner_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        log_function_info(cls)
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_partner_loc_pref_db.prep_delete = datetime.datetime.utcnow()

        return schemas.ActorPartnerLocationPrefShow.model_validate(actor_partner_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(cls, actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        log_function_info(cls)
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_partner_loc_pref_db.prep_delete = None

        return schemas.ActorPartnerLocationPrefShow.model_validate(actor_partner_loc_pref_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_unused(cls, person_id: UUID) -> list[UUID]:
        log_function_info(cls)
        apl_prefs_from__person = models.ActorPartnerLocationPref.select(lambda a: a.person.id == person_id)

        deleted_apl_pref_ids = []
        for apl_pref in apl_prefs_from__person:
            if apl_pref.prep_delete:
                continue
            empty_check = [apl_pref.actor_plan_periods_defaults, apl_pref.avail_days_defaults]
            if all(default.is_empty() for default in empty_check) and not apl_pref.person_default:
                apl_pref.prep_delete = datetime.datetime.utcnow()
                deleted_apl_pref_ids.append(apl_pref.id)
        return deleted_apl_pref_ids

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(cls, person_id: UUID) -> None:
        log_function_info(cls)
        apl_prefs_form__person = models.ActorPartnerLocationPref.select(lambda a: a.person.id == person_id)
        for apl_pref in apl_prefs_form__person:
            if apl_pref.prep_delete:
                apl_pref.delete()


class Plan:
    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, plan_period_id: UUID, name: str, notes: str = '') -> schemas.PlanShow:
        log_function_info(cls)
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period_id)
        plan_db = models.Plan(name=name, plan_period=plan_period_db, notes=notes)

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_notes(cls, plan_id: UUID, notes: str) -> schemas.PlanShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        plan_db.notes = notes

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, plan_id: UUID) -> schemas.PlanShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        plan_db.prep_delete = datetime.datetime.utcnow()

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(cls, plan_id: UUID) -> schemas.PlanShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        plan_db.prep_delete = None

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session
    def get(cls, plan_id: UUID) -> schemas.PlanShow:
        plan_db = models.Plan.get(id=plan_id)

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session
    def get_from__name(cls, plan_name: str) -> schemas.PlanShow | None:
        plan_db = models.Plan.get_for_update(name=plan_name)

        return schemas.PlanShow.model_validate(plan_db) if plan_db else None

    @classmethod
    @db_session
    def get_all_from__team(cls, team_id: UUID,
                           minimal: bool = False, inclusive_prep_deleted=False) -> list[schemas.PlanShow] | dict[str, UUID]:
        """
        Wenn minimal == True:
        Lediglich ein Dictionary mit plan.name und plan.id wird zurückgegeben.
        Zum Löschen markierte Pläne werden ausgeschlossen.
        Sortierung: (plan.start, plan.name), reversed.
        Wenn minimal == False:
        Eine Liste aller Pläne als schemas.PlanShow wird zurückgegeben.
        """
        if not minimal:
            plans_db = models.Plan.select(lambda x: x.plan_period.team.id == team_id)
            return [schemas.PlanShow.model_validate(p) for p in plans_db]
        else:
            if not inclusive_prep_deleted:
                plans_db = (models.Plan
                            .select(lambda x: x.plan_period.team.id == team_id and not x.prep_delete)
                            .sort_by(lambda p: (p.plan_period.start, p.name)))
            else:
                plans_db = (models.Plan
                            .select(lambda x: x.plan_period.team.id == team_id)
                            .sort_by(lambda p: (p.plan_period.start, p.name)))
            return {p.name: p.id for p in plans_db}

    @classmethod
    @db_session
    def get_prep_deleted_from__team(cls, team_id: UUID) -> list[UUID]:
        plans_db = models.Plan.select(lambda x: x.plan_period.team.id == team_id and x.prep_delete)
        return [p.id for p in plans_db]

    @classmethod
    @db_session
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.PlanShow]:
        plans_db = models.Plan.select(lambda x: x.plan_period.id == plan_period_id)

        return [schemas.PlanShow.model_validate(p) for p in plans_db]

    @classmethod
    @db_session
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict[str, UUID]:
        plans_db = (models.Plan.select(lambda x: x.plan_period.id == plan_period_id)
                    .filter(lambda p: p.plan_period.id == plan_period_id)
                    .filter(lambda p: p.prep_delete is None))
        return {p.name: p.id for p in plans_db}

    @classmethod
    @db_session
    def get_location_columns(cls, plan_id: UUID):
        location_columns = models.Plan.get_for_update(id=plan_id).location_columns
        return location_columns


    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deleted(cls, plan_id):
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        if not plan_db.prep_delete:
            raise LookupError(f'Plan {plan_db.name} ist not marked to delete.')
        plan_db.delete()

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes_from__team(cls, team_id: UUID):
        log_function_info(cls)
        team_db = models.Team.get_for_update(id=team_id)
        plans_to_delete = models.Plan.select(lambda x: x.plan_period.team == team_db and x.prep_delete)
        for plan in plans_to_delete:
            plan.delete()

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_name(cls, plan_id: UUID, new_name: str) -> schemas.PlanShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        plan_db.name = new_name

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_location_columns(cls, plan_id: UUID, location_columns: str) -> schemas.PlanShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        plan_db.location_columns = location_columns

        return schemas.PlanShow.model_validate(plan_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_excel_settings(cls, plan_id: UUID, excel_settings_id: UUID) -> schemas.PlanShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        excel_settings_db = models.ExcelExportSettings.get_for_update(id=excel_settings_id)
        plan_db.excel_export_settings = excel_settings_db
        return schemas.PlanShow.model_validate(plan_db)


class Appointment:
    @classmethod
    @db_session
    def get(cls, appointment_id: UUID) -> schemas.AppointmentShow:
        appointment_db = models.Appointment.get_for_update(id=appointment_id)
        return schemas.AppointmentShow.model_validate(appointment_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def create(cls, appointment: schemas.AppointmentCreate, plan_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        plan_db = models.Plan.get_for_update(id=plan_id)
        event_db = models.Event.get_for_update(id=appointment.event.id)
        avail_days_db = [models.AvailDay.get_for_update(id=avd.id) for avd in appointment.avail_days]
        appointment_db = models.Appointment(
            avail_days=avail_days_db, event=event_db, plan=plan_db, notes=appointment.notes)

        return schemas.AppointmentShow.model_validate(appointment_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_avail_days(cls, appointment_id: UUID, avail_day_ids: list[UUID]) -> schemas.AppointmentShow:
        log_function_info(cls)
        appointment_db = models.Appointment.get_for_update(id=appointment_id)
        appointment_db.avail_days.clear()
        for avd_id in avail_day_ids:
            appointment_db.avail_days.add(models.AvailDay.get(id=avd_id))
        return schemas.AppointmentShow.model_validate(appointment_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def update_guests(cls, appointment_id: UUID, guests: list[str]) -> schemas.AppointmentShow:
        log_function_info(cls)
        appointment_db = models.Appointment.get_for_update(id=appointment_id)
        appointment_db.guests = json.dumps(guests)
        return schemas.AppointmentShow.model_validate(appointment_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(cls, appointment_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        appointment_db = models.Appointment.get_for_update(id=appointment_id)
        appointment_db.prep_delete = datetime.datetime.utcnow()

        return schemas.AppointmentShow.model_validate(appointment_db)

    @classmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(cls, appointment_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        appointment_db = models.Appointment.get_for_update(id=appointment_id)
        appointment_db.prep_delete = None

        return schemas.AppointmentShow.model_validate(appointment_db)
