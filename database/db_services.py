import datetime
import inspect
import logging
from typing import Optional
from uuid import UUID

from pony.orm import db_session, commit

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
        project_db.time_of_days.clear()
        for t_o_d in project.time_of_days:
            project_db.time_of_days.add(models.TimeOfDay[t_o_d.id])
        return schemas.ProjectShow.from_orm(project_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(project_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ProjectShow, UUID | None]:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        old_time_of_day_standard_id = None
        for t_o_d in project_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                project_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        project_db.time_of_day_standards.add(time_of_day_db)
        return schemas.ProjectShow.from_orm(project_db), old_time_of_day_standard_id

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        project_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.ProjectShow.from_orm(project_db)


class Team:
    @staticmethod
    @db_session
    def get(team_id: UUID) -> schemas.TeamShow:
        team_db = models.Team.get_for_update(id=team_id)
        return schemas.TeamShow.from_orm(team_db)

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
    def put_in_comb_loc_possible(team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_db = models.Team.get_for_update(id=team_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        team_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.TeamShow.from_orm(team_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_db = models.Team.get_for_update(id=team_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        team_db.combination_locations_possibles.remove(comb_loc_possible_db)
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
            **person.dict(include={'f_name', 'l_name', 'email', 'gender', 'phone_nr', 'requested_assignments', 'notes'}))

        '''Es fehlen noch actor_partner_location_prefs, combination_locations_possibles'''

        return schemas.Person.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def assign_to_team(person_id: UUID, team_id: UUID | None,
                       start: datetime.date | None) -> schemas.TeamActorAssignShow | None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        start = start or datetime.date.today()
        person_db = models.Person.get_for_update(id=person_id)
        team_db = models.Team.get_for_update(id=team_id) if team_id else None

        if not person_db.team_actor_assigns.is_empty():  # if actor_db has team assignments

            latest_assignment_db = max(models.TeamActorAssign.select(lambda a: a.person == person_db),
                                       key=lambda tla: tla.start)
            while latest_assignment_db and latest_assignment_db.start > start:  # delete all assignments with start later than start of new assignment
                latest_assignment_db.delete()
                if assignments := models.TeamActorAssign.select(lambda a: a.person == person_db):
                    latest_assignment_db = max(assignments, key=lambda tla: tla.start)
                else:
                    latest_assignment_db = None
            if latest_assignment_db:
                if latest_assignment_db.end is None or latest_assignment_db.end >= start:
                    if latest_assignment_db.team.id != team_id:
                        latest_assignment_db.end = start
                        created_assignment = TeamActorAssign.create(
                            schemas.TeamActorAssignCreate(start=start, person=person_db, team=team_db))
                    else:
                        latest_assignment_db.end = None
                        created_assignment = None
                else:
                    created_assignment = TeamActorAssign.create(
                        schemas.TeamActorAssignCreate(start=start, person=person_db, team=team_db))
            else:
                created_assignment = TeamActorAssign.create(
                    schemas.TeamActorAssignCreate(start=start, person=person_db, team=team_db))

        else:
            created_assignment = TeamActorAssign.create(
                schemas.TeamActorAssignCreate(start=start, person=person_db, team=team_db))

        return schemas.TeamActorAssignShow.from_orm(created_assignment) if created_assignment else None

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_from_team(person_id: UUID, end_date: datetime.date) -> schemas.TeamActorAssignShow | None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        if person_db.team_actor_assigns.is_empty():
            raise LookupError('Die Location ist noch keinem Team zugeordnet.')
        assignments_to_delete = [a for a in person_db.team_actor_assigns if a.start >= end_date]
        for assignm in assignments_to_delete:
            assignm.delete()
        latest_assignment = max(person_db.team_actor_assigns,
                                key=lambda x: x.start) if person_db.team_actor_assigns else None
        if latest_assignment and (latest_assignment.end is None or latest_assignment.end > end_date):
            latest_assignment.end = end_date

        return schemas.TeamActorAssignShow.from_orm(latest_assignment) if latest_assignment else None

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
    def new_time_of_day_standard(person_id: UUID, time_of_day_id: UUID) -> tuple[schemas.PersonShow, UUID | None]:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in person_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                person_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        person_db.time_of_day_standards.add(time_of_day_db)
        return schemas.PersonShow.from_orm(person_db), old_time_of_day_standard_id

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        if person_db.time_of_day_standards:
            person_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(person_id: UUID) -> schemas.Person:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        person_db.prep_delete = datetime.datetime.utcnow()
        return schemas.Person.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        person_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        person_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_location_pref(person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        person_db.actor_location_prefs_defaults.add(location_pref_db)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_location_pref(person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        person_db.actor_location_prefs_defaults.remove(location_pref_db)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_partner_location_pref(person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        person_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
        return schemas.PersonShow.from_orm(person_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_partner_location_pref(person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get_for_update(id=person_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        person_db.actor_partner_location_prefs_defaults.remove(partner_location_pref_db)
        return schemas.PersonShow.from_orm(person_db)


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
        location_db.set(**location_of_work.dict(include={'name', 'nr_actors', 'fixed_cast'}))

        return schemas.LocationOfWorkShow.from_orm(location_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def assign_to_team(location_id: UUID, team_id: UUID,
                       start: datetime.date | None) -> schemas.TeamLocationAssignShow | None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')

        start = start or datetime.date.today()
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        team_db = models.Team.get_for_update(id=team_id) if team_id else None

        if not location_db.team_location_assigns.is_empty():  # if location_db has team assignments

            latest_assignment_db = max(models.TeamLocationAssign.select(lambda a: a.location_of_work == location_db),
                                       key=lambda tla: tla.start)
            while latest_assignment_db and latest_assignment_db.start > start:  # delete all assignments with start later than start of new assignment
                latest_assignment_db.delete()
                if assignments := models.TeamLocationAssign.select(lambda a: a.location_of_work == location_db):
                    latest_assignment_db = max(assignments, key=lambda tla: tla.start)
                else:
                    latest_assignment_db = None
            if latest_assignment_db:
                if latest_assignment_db.end is None or latest_assignment_db.end >= start:
                    if latest_assignment_db.team.id != team_id:
                        latest_assignment_db.end = start
                        created_assignment = TeamLocationAssign.create(
                            schemas.TeamLocationAssignCreate(start=start, location_of_work=location_db, team=team_db))
                    else:
                        latest_assignment_db.end = None
                        created_assignment = None
                else:
                    created_assignment = TeamLocationAssign.create(
                        schemas.TeamLocationAssignCreate(start=start, location_of_work=location_db, team=team_db))
            else:
                created_assignment = TeamLocationAssign.create(
                    schemas.TeamLocationAssignCreate(start=start, location_of_work=location_db, team=team_db))

        else:
            created_assignment = TeamLocationAssign.create(
                schemas.TeamLocationAssignCreate(start=start, location_of_work=location_db, team=team_db))

        return schemas.TeamLocationAssignShow.from_orm(created_assignment) if created_assignment else None


    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_from_team(location_id: UUID, end: datetime.date) -> schemas.TeamLocationAssignShow | None:
        """Setzt das Ende des Assignments auf ein neues Datum."""
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        if location_db.team_location_assigns.is_empty():
            raise LookupError('Die Location ist noch keinem Team zugeordnet.')
        assignments_to_delete = [a for a in location_db.team_location_assigns if a.start >= end]
        for assignm in assignments_to_delete:
            assignm.delete()
        latest_assignment = max(location_db.team_location_assigns, key=lambda x: x.start) if location_db.team_location_assigns else None
        if latest_assignment and (latest_assignment.end is None or latest_assignment.end > end):
            latest_assignment.end = end

        return schemas.TeamLocationAssignShow.from_orm(latest_assignment) if latest_assignment else None

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(location_of_work_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationOfWorkShow, UUID | None]:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in location_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                location_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        location_db.time_of_day_standards.add(time_of_day_db)
        return schemas.LocationOfWorkShow.from_orm(location_db), old_time_of_day_standard_id

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get_for_update(id=location_of_work_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        if location_db.time_of_day_standards:
            location_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.LocationOfWorkShow.from_orm(location_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(location_id: UUID) -> schemas.LocationOfWork:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get_for_update(id=location_id)
        location_db.prep_delete = datetime.datetime.utcnow()
        return schemas.LocationOfWork.from_orm(location_db)


class TeamActorAssign:
    @staticmethod
    @db_session
    def get(team_actor_assign_id: UUID) -> schemas.TeamActorAssignShow:
        team_actor_assign_db = models.TeamActorAssign.get_for_update(id=team_actor_assign_id)
        return schemas.TeamActorAssignShow.from_orm(team_actor_assign_db)

    @staticmethod
    @db_session
    def get_at__date(person_id: UUID, date: datetime.date | None) -> schemas.TeamActorAssignShow | None:
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

        return None if not assignment_db else schemas.TeamActorAssignShow.from_orm(assignment_db)

    @staticmethod
    @db_session
    def get_all_at__date(date: datetime.date, team_id: UUID) -> list[schemas.TeamActorAssignShow]:
        all_actor_location_assigns = models.TeamActorAssign.select(
            lambda tla: tla.start <= date and (tla.end is None or tla.end > date) and tla.team.id == team_id)
        return [schemas.TeamActorAssignShow.from_orm(tla) for tla in all_actor_location_assigns]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(team_actor_assign: schemas.TeamActorAssignCreate) -> schemas.TeamActorAssignShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        person_db = models.Person.get(id=team_actor_assign.person.id)
        team_db = models.Team.get(id=team_actor_assign.team.id)
        if team_actor_assign.start:
            new_team_aa = models.TeamActorAssign(start=team_actor_assign.start, person=person_db, team=team_db)
        else:
            new_team_aa = models.TeamActorAssign(person=person_db, team=team_db)
        return schemas.TeamActorAssignShow.from_orm(new_team_aa)


class TeamLocationAssign:
    @staticmethod
    @db_session
    def get(team_location_assign_id: UUID) -> schemas.TeamActorAssignShow:
        team_location_assign_db = models.TeamActorAssign.get_for_update(id=team_location_assign_id)
        return schemas.TeamActorAssignShow.from_orm(team_location_assign_db)

    @staticmethod
    @db_session
    def get_at__date(location_id: UUID, date: datetime.date | None) -> schemas.TeamLocationAssignShow | None:
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

        return None if not assignment_db else schemas.TeamLocationAssignShow.from_orm(assignment_db)

    @staticmethod
    @db_session
    def get_all_at__date(date: datetime.date, team_id: UUID) -> list[schemas.TeamLocationAssignShow]:
        all_team_location_assigns = models.TeamLocationAssign.select(
            lambda tla: tla.start <= date and (tla.end is None or tla.end > date) and tla.team.id == team_id)
        return [schemas.TeamLocationAssignShow.from_orm(tla) for tla in all_team_location_assigns]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(team_location_assign: schemas.TeamLocationAssignCreate) -> schemas.TeamLocationAssignShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        location_db = models.LocationOfWork.get(id=team_location_assign.location_of_work.id)
        team_db = models.Team.get(id=team_location_assign.team.id)
        if team_location_assign.start:
            new_team_la = models.TeamLocationAssign(start=team_location_assign.start, location_of_work=location_db,
                                                    team=team_db)
        else:
            new_team_la = models.TeamLocationAssign(location_of_work=location_db, team=team_db)
        return schemas.TeamLocationAssignShow.from_orm(new_team_la)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def set_end_to_none(team_location_assign_id: UUID):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_location_assign_db = models.TeamLocationAssign.get_for_update(id=team_location_assign_id)
        team_location_assign_db.end = None

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(team_loc_assign_id: UUID):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_loc_assign_db = models.TeamLocationAssign.get_for_update(id=team_loc_assign_id)
        team_loc_assign_db.delete()


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
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day.time_of_day_enum.id)

        exclude = {'time_of_day_enum', 'project_standard'}  # if time_of_day.id else {'id', 'time_of_day_enum', 'project_standard'}
        time_of_day_db = models.TimeOfDay(**time_of_day.dict(exclude=exclude),
                                          project=project_db, time_of_day_enum=time_of_day_enum_db)
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
        time_of_day_db.time_of_day_enum = models.TimeOfDayEnum.get_for_update(id=time_of_day.time_of_day_enum.id)
        return schemas.TimeOfDay.from_orm(time_of_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_to_model(time_of_day: schemas.TimeOfDay,
                     pydantic_model: schemas.ModelWithTimeOfDays, db_model):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        if not (isinstance(pydantic_model, schemas.ModelWithTimeOfDays) or isinstance(pydantic_model, schemas.Project)):
            raise ValueError
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day.id)
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

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def undo_delete(time_of_day_id: UUID) -> schemas.TimeOfDay:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        time_of_day_db = models.TimeOfDay.get_for_update(lambda t: t.id == time_of_day_id)
        time_of_day_db.prep_delete = None
        return schemas.TimeOfDay.from_orm(time_of_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_unused(projec_id: UUID) -> None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        t_o_ds_from__project = models.TimeOfDay.select(lambda t: t.project.id == projec_id)
        for t_o_d in t_o_ds_from__project:
            if t_o_d.prep_delete:
                continue
            empty_check = [t_o_d.persons_defaults, t_o_d.actor_plan_periods_defaults,
                           t_o_d.avail_days_defaults, t_o_d.avail_days, t_o_d.locations_of_work_defaults,
                           t_o_d.location_plan_periods_defaults, t_o_d.events_defaults, t_o_d.events]
            if all([(not t_o_d.project_defaults), all([default.is_empty() for default in empty_check])]):
                t_o_d.prep_delete = datetime.datetime.utcnow()

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(projec_id: UUID) -> None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        t_o_ds_from__project = models.TimeOfDay.select(lambda t: t.project.id == projec_id)
        for t_o_d in t_o_ds_from__project:
            if t_o_d.prep_delete:
                t_o_d.delete()


class TimeOfDayEnum:
    @staticmethod
    @db_session
    def get(time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum_id)
        return schemas.TimeOfDayEnumShow.from_orm(time_of_day_enum_db)

    @staticmethod
    @db_session
    def get_all_from__project(project_id: UUID) -> list[schemas.TimeOfDayEnumShow]:
        project_db = models.Project.get_for_update(id=project_id)
        return [schemas.TimeOfDayEnumShow.from_orm(t_o_d_enum) for t_o_d_enum in project_db.time_of_day_enums]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(time_of_day_enum: schemas.TimeOfDayEnumCreate) -> schemas.TimeOfDayEnumShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=time_of_day_enum.project.id)
        time_of_day_enum_db = models.TimeOfDayEnum(name=time_of_day_enum.name,
                                                   abbreviation=time_of_day_enum.abbreviation,
                                                   time_index=time_of_day_enum.time_index,
                                                   project=project_db)
        commit()
        TimeOfDayEnum.__consolidate_indexes(time_of_day_enum.project.id)
        return schemas.TimeOfDayEnumShow.from_orm(time_of_day_enum_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(time_of_day_enum: schemas.TimeOfDayEnumShow) -> schemas.TimeOfDayEnumShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum.id)
        time_of_day_enum_db.set(**time_of_day_enum.dict(include={'name', 'abbreviation', 'time_index'}))
        commit()
        TimeOfDayEnum.__consolidate_indexes(time_of_day_enum.project.id)
        return schemas.TimeOfDayEnumShow.from_orm(time_of_day_enum_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(time_of_day_enum_id: UUID):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        time_of_day_enum_db = models.TimeOfDayEnum.get_for_update(id=time_of_day_enum_id)
        project_id = time_of_day_enum_db.project.id
        time_of_day_enum_db.delete()
        commit()
        TimeOfDayEnum.__consolidate_indexes(project_id)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def __consolidate_indexes(project_id: UUID):
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=project_id)
        time_of_day_enums = TimeOfDayEnum.get_all_from__project(project_id)
        for i, t_o_d_enum in enumerate(sorted(time_of_day_enums, key=lambda x: x.time_index), start=1):
            t_o_d_enum_db = models.TimeOfDayEnum.get_for_update(id=t_o_d_enum.id)
            t_o_d_enum_db.time_index = i
            commit()


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
    @db_session
    def get_all_from__project(project_id: UUID) -> list[schemas.PlanPeriodShow]:
        plan_periods_db = models.PlanPeriod.select(lambda pp: pp.project.id == project_id)
        return [schemas.PlanPeriodShow.from_orm(p) for p in plan_periods_db]

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        team_db = models.Team.get_for_update(id=plan_period.team.id)
        plan_period_db = models.PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                                           notes=plan_period.notes, team=team_db)
        return schemas.PlanPeriodShow.from_orm(plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update(plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        plan_period_db = models.PlanPeriod.get_for_update(id=plan_period.id)
        plan_period_db.set(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                           notes=plan_period.notes, remainder=plan_period.remainder)
        for actor_plan_period in plan_period_db.actor_plan_periods:
            for avail_day in actor_plan_period.avail_days:
                if not (plan_period.start <= avail_day <= plan_period.end) and not avail_day.prep_delete:
                    avail_day.prep_delete = datetime.datetime.utcnow()
        for location_plan_period in plan_period_db.location_plan_periods:
            for event in location_plan_period.events:
                if not (plan_period.start <= event <= plan_period.end) and not event.prep_delete:
                    event.prep_delete = datetime.datetime.utcnow()

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
    @db_session
    def get(actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodShow:
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

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
    def update(actor_plan_period: schemas.ActorPlanPeriodShow) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period.id)

        actor_plan_period_db.time_of_days.clear()
        for t_o_d in actor_plan_period.time_of_days:
            actor_plan_period_db.time_of_days.add(models.TimeOfDay.get_for_update(id=t_o_d.id))
        actor_plan_period_db.set(
            **actor_plan_period.dict(
                include={'notes', 'requested_assignments'}))

        '''Es fehlen noch actor_partner_location_prefs, combination_locations_possibles'''

        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def update_notes(actor_plan_period: schemas.ActorPlanPeriodUpdate) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period.id)
        actor_plan_period_db.set(notes=actor_plan_period.notes)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_time_of_day_standard(actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)
        if actor_plan_period_db.time_of_day_standards:
            actor_plan_period_db.time_of_day_standards.remove(time_of_day_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def new_time_of_day_standard(actor_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ActorPlanPeriodShow, UUID | None]:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        time_of_day_db = models.TimeOfDay.get_for_update(id=time_of_day_id)

        old_time_of_day_standard_id = None
        for t_o_d in actor_plan_period_db.time_of_day_standards:
            if t_o_d.time_of_day_enum.id == time_of_day_db.time_of_day_enum.id:
                actor_plan_period_db.time_of_day_standards.remove(t_o_d)
                old_time_of_day_standard_id = t_o_d.id
                break
        actor_plan_period_db.time_of_day_standards.add(time_of_day_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db), old_time_of_day_standard_id

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        actor_plan_period_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        actor_plan_period_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_location_pref(actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_plan_period_db.actor_location_prefs_defaults.add(location_pref_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_location_pref(actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_plan_period_db.actor_location_prefs_defaults.remove(location_pref_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_partner_location_pref(actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_plan_period_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
        return schemas.ActorPlanPeriodShow.from_orm(actor_plan_period_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_partner_location_pref(actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_plan_period_db = models.ActorPlanPeriod.get_for_update(id=actor_plan_period_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_plan_period_db.actor_partner_location_prefs_defaults.remove(partner_location_pref_db)
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
    def get(avail_day_id: UUID) -> schemas.AvailDayShow:
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session
    def get_from__pp_date_tod(actor_plan_period_id: UUID, day: datetime.date, time_of_day_id) -> schemas.AvailDayShow:
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
    def update_time_of_days(avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        time_of_days_db = [models.TimeOfDay.get_for_update(id=t.id) for t in time_of_days]
        avail_day_db.time_of_days.clear()
        avail_day_db.time_of_days.add(time_of_days_db)
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

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_comb_loc_possible(avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        avail_day_db.combination_locations_possibles.add(comb_loc_possible_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_comb_loc_possible(avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        comb_loc_possible_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_possible_id)
        avail_day_db.combination_locations_possibles.remove(comb_loc_possible_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_location_pref(avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        avail_day_db.actor_location_prefs_defaults.add(location_pref_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_location_pref(avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        location_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        avail_day_db.actor_location_prefs_defaults.remove(location_pref_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def put_in_partner_location_pref(avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        avail_day_db.actor_partner_location_prefs_defaults.add(partner_location_pref_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def remove_partner_location_pref(avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        avail_day_db = models.AvailDay.get_for_update(id=avail_day_id)
        partner_location_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        avail_day_db.actor_partner_location_prefs_defaults.remove(partner_location_pref_db)
        return schemas.AvailDayShow.from_orm(avail_day_db)


class CombinationLocationsPossible:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(comb_loc_poss: schemas.CombinationLocationsPossibleCreate) -> schemas.CombinationLocationsPossibleShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        project_db = models.Project.get_for_update(id=comb_loc_poss.project.id)
        new_comb_loc_poss = models.CombinationLocationsPossible(project=project_db)
        for loc in comb_loc_poss.locations_of_work:
            new_comb_loc_poss.locations_of_work.add(models.LocationOfWork.get_for_update(id=loc.id))

        return schemas.CombinationLocationsPossibleShow.from_orm(new_comb_loc_poss)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        comb_loc_poss_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_poss_id)
        comb_loc_poss_db.prep_delete = datetime.datetime.utcnow()

        return schemas.CombinationLocationsPossibleShow.from_orm(comb_loc_poss_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        comb_loc_poss_db = models.CombinationLocationsPossible.get_for_update(id=comb_loc_poss_id)
        comb_loc_poss_db.prep_delete = None

        return schemas.CombinationLocationsPossibleShow.from_orm(comb_loc_poss_db)


class ActorLocationPref:
    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(actor_loc_pref: schemas.ActorLocationPrefCreate) -> schemas.ActorLocationPrefShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')

        project_db = models.Project.get_for_update(id=actor_loc_pref.person.project.id)
        person_db = models.Person.get_for_update(id=actor_loc_pref.person.id)
        location_db = models.LocationOfWork.get_for_update(id=actor_loc_pref.location_of_work.id)
        actor_loc_pref_db = models.ActorLocationPref(score=actor_loc_pref.score, project=project_db, person=person_db,
                                                     location_of_work=location_db)
        return schemas.ActorLocationPrefShow.from_orm(actor_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_loc_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_loc_pref_db.prep_delete = datetime.datetime.utcnow()

        return schemas.ActorLocationPrefShow.from_orm(actor_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_loc_pref_db = models.ActorLocationPref.get_for_update(id=actor_loc_pref_id)
        actor_loc_pref_db.prep_delete = None

        return schemas.ActorLocationPrefShow.from_orm(actor_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_unused(projec_id: UUID) -> list[UUID]:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        a_l_prefs_from__project = models.ActorLocationPref.select(lambda a: a.project.id == projec_id)

        deleted_a_l_pref_ids = []
        for a_l_pref in a_l_prefs_from__project:
            if a_l_pref.prep_delete:
                continue
            empty_check = [a_l_pref.actor_plan_periods_defaults, a_l_pref.avail_days_defaults]
            if all([default.is_empty() for default in empty_check]) and not a_l_pref.person_default:
                a_l_pref.prep_delete = datetime.datetime.utcnow()
                deleted_a_l_pref_ids.append(a_l_pref.id)
        return deleted_a_l_pref_ids

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(projec_id: UUID) -> None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        a_l_prefs_form__project = models.ActorLocationPref.select(lambda a: a.project.id == projec_id)
        for a_l_pref in a_l_prefs_form__project:
            if a_l_pref.prep_delete:
                a_l_pref.delete()


class ActorPartnerLocationPref:
    @staticmethod
    @db_session
    def get(actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        return schemas.ActorPartnerLocationPrefShow.from_orm(actor_partner_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def create(actor_partner_loc_pref: schemas.ActorPartnerLocationPrefCreate) -> schemas.ActorPartnerLocationPrefShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')

        person_db = models.Person.get_for_update(id=actor_partner_loc_pref.person.id)
        partner_db = models.Person.get_for_update(id=actor_partner_loc_pref.partner.id)
        location_db = models.LocationOfWork.get_for_update(id=actor_partner_loc_pref.location_of_work.id)
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref(score=actor_partner_loc_pref.score,
                                                                    person=person_db, partner=partner_db,
                                                                    location_of_work=location_db)
        return schemas.ActorPartnerLocationPrefShow.from_orm(actor_partner_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def modify(actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow) -> schemas.ActorPartnerLocationPrefShow:
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref.id)
        if actor_partner_loc_pref.person_default:
            person_default_db = models.Person.get_for_update(id=actor_partner_loc_pref.person_default.id)
        else:
            person_default_db = None
        actor_plan_periods_defaults_db = [models.ActorPlanPeriod.get_for_update(id=app.id)
                                          for app in actor_partner_loc_pref.actor_plan_periods_defaults]
        avail_days_dafaults_db = [models.AvailDay.get_for_update(id=ad.id)
                                  for ad in actor_partner_loc_pref.avail_days_dafaults]
        actor_partner_loc_pref_db.person_default = person_default_db
        actor_partner_loc_pref_db.actor_plan_periods_defaults.clear()
        actor_partner_loc_pref_db.actor_plan_periods_defaults.add(actor_plan_periods_defaults_db)
        actor_partner_loc_pref_db.avail_days_dafaults.clear()
        actor_partner_loc_pref_db.avail_days_dafaults.add(avail_days_dafaults_db)

        return schemas.ActorPartnerLocationPrefShow.from_orm(actor_partner_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete(actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_partner_loc_pref_db.prep_delete = datetime.datetime.utcnow()

        return schemas.ActorPartnerLocationPrefShow.from_orm(actor_partner_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def undelete(actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        actor_partner_loc_pref_db = models.ActorPartnerLocationPref.get_for_update(id=actor_partner_loc_pref_id)
        actor_partner_loc_pref_db.prep_delete = None

        return schemas.ActorPartnerLocationPrefShow.from_orm(actor_partner_loc_pref_db)

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_unused(person_id: UUID) -> list[UUID]:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        apl_prefs_from__person = models.ActorPartnerLocationPref.select(lambda a: a.person.id == person_id)

        deleted_apl_pref_ids = []
        for apl_pref in apl_prefs_from__person:
            if apl_pref.prep_delete:
                continue
            empty_check = [apl_pref.actor_plan_periods_defaults, apl_pref.avail_days_defaults]
            if all([default.is_empty() for default in empty_check]) and not apl_pref.person_default:
                apl_pref.prep_delete = datetime.datetime.utcnow()
                deleted_apl_pref_ids.append(apl_pref.id)
        return deleted_apl_pref_ids

    @staticmethod
    @db_session(sql_debug=True, show_values=True)
    def delete_prep_deletes(person_id: UUID) -> None:
        logging.info(f'function: {__name__}.{__class__.__name__}.{inspect.currentframe().f_code.co_name}\n'
                     f'args: {locals()}')
        apl_prefs_form__person = models.ActorPartnerLocationPref.select(lambda a: a.person.id == person_id)
        for apl_pref in apl_prefs_form__person:
            if apl_pref.prep_delete:
                apl_pref.delete()
