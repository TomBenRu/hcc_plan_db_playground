"""db_services.py — SQLModel/SQLAlchemy 2.x Version

Migriert von PonyORM. Jede Methode verwaltet ihre eigene Session via get_session().
Cross-Service-Aufrufe werden innerhalb derselben Session inlined.
"""

import datetime
import inspect
import json
import logging
from typing import Optional
from uuid import UUID

import pandas as pd
from sqlalchemy import or_
from sqlmodel import select

from . import schemas, schemas_plan_api, models
from .authentication import hash_psw
from .database import get_session
from .models import _utcnow
from .enums import Gender

logger = logging.getLogger(__name__)

LOGGING_ENABLED = False


def log_function_info(cls):
    if not LOGGING_ENABLED:
        return
    logger.info(f'function: {cls.__name__}.{inspect.currentframe().f_back.f_code.co_name}\n'
                f'args: {inspect.currentframe().f_back.f_locals}')


# ═══════════════════════════════════════════════════════════════════════════════
# API-Schnittstelle
# ═══════════════════════════════════════════════════════════════════════════════


class EntitiesApiToDB:
    @classmethod
    def create_project(cls, project: schemas_plan_api.Project) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = models.Project(id=project.id, name=project.name)
            session.add(project_db)
            session.flush()
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def delete_project(cls, project_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            session.delete(project_db)

    @classmethod
    def create_person(cls, person: schemas_plan_api.PersonShow) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, person.project.id)
            address_db = models.Address(street='keine Angabe', postal_code='keine Angabe',
                                        city='keine Angabe', project=project_db)
            session.add(address_db)
            person_db = models.Person(id=person.id, f_name=person.f_name, l_name=person.l_name, gender=Gender.divers,
                                      email=person.email, phone_nr='', username=person.username, password=person.password,
                                      project=project_db, address=address_db)
            session.add(person_db)
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def delete_person(cls, person_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            session.delete(person_db)

    @classmethod
    def create_team(cls, team: schemas_plan_api.Team) -> schemas.TeamShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, team.dispatcher.project.id)
            team_db = models.Team(id=team.id, name=team.name, project=project_db)
            session.add(team_db)
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def delete_team(cls, team_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team_id)
            session.delete(team_db)

    @classmethod
    def create_plan_period(cls, plan_period: schemas_plan_api.PlanPeriod) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, plan_period.team.id)
            plan_period_db = models.PlanPeriod(id=plan_period.id, start=plan_period.start, end=plan_period.end,
                                               deadline=plan_period.deadline, notes_for_employees=plan_period.notes,
                                               closed=plan_period.closed, remainder=True, team=team_db)
            session.add(plan_period_db)
            session.flush()
            return schemas.PlanPeriodShow.model_validate(plan_period_db)

    @classmethod
    def delete_plan_period(cls, plan_period_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            plan_period_db = session.get(models.PlanPeriod, plan_period_id)
            session.delete(plan_period_db)


# ═══════════════════════════════════════════════════════════════════════════════
# Projekt-Kern
# ═══════════════════════════════════════════════════════════════════════════════


class Project:
    @classmethod
    def get(cls, project_id: UUID) -> schemas.ProjectShow:
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def get_all(cls) -> list[schemas.ProjectShow]:
        with get_session() as session:
            projects = session.exec(select(models.Project)).all()
            return [schemas.ProjectShow.model_validate(p) for p in projects]

    @classmethod
    def create(cls, name: str) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = models.Project(name=name)
            session.add(project_db)
            session.flush()
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def update_name(cls, name: str, project_id) -> schemas.Project:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            project_db.name = name
            session.flush()
            return schemas.Project.model_validate(project_db)

    @classmethod
    def update(cls, project: schemas.ProjectShow) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project.id)
            for k, v in project.model_dump(include={'name', 'active'}).items():
                setattr(project_db, k, v)
            project_db.time_of_days.clear()
            for t_o_d in project.time_of_days:
                project_db.time_of_days.append(session.get(models.TimeOfDay, t_o_d.id))
            session.flush()
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def put_in_time_of_day(cls, project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            project_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def remove_in_time_of_day(cls, project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            project_db.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def new_time_of_day_standard(cls, project_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ProjectShow, UUID | None]:
        log_function_info(cls)
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

    @classmethod
    def remove_time_of_day_standard(cls, project_id: UUID, time_of_day_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            project_db.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.ProjectShow.model_validate(project_db)

    @classmethod
    def new_time_of_day_enum_standard(cls, time_of_day_enum_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            tode_db = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
            tode_db.project.time_of_day_enum_standards.append(tode_db)
            session.flush()
            return schemas.ProjectShow.model_validate(tode_db.project)

    @classmethod
    def remove_time_of_day_enum_standard(cls, time_of_day_enum_id: UUID) -> schemas.ProjectShow:
        log_function_info(cls)
        with get_session() as session:
            tode_db = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
            tode_db.project.time_of_day_enum_standards.remove(tode_db)
            session.flush()
            return schemas.ProjectShow.model_validate(tode_db.project)


class Team:
    @classmethod
    def get(cls, team_id: UUID) -> schemas.TeamShow:
        with get_session() as session:
            return schemas.TeamShow.model_validate(session.get(models.Team, team_id))

    @classmethod
    def get_all_from__project(cls, project_id: UUID, minimal: bool = False) -> list[schemas.TeamShow | tuple[str, UUID]]:
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            if not project_db:
                return []
            if minimal:
                return [(t.name, t.id) for t in project_db.teams]
            return [schemas.TeamShow.model_validate(t) for t in project_db.teams]

    @classmethod
    def create(cls, team_name: str, project_id: UUID, dispatcher_id: UUID = None):
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            dispatcher_db = session.get(models.Person, dispatcher_id) if dispatcher_id else None
            team_db = models.Team(name=team_name, project=project_db, dispatcher=dispatcher_db)
            session.add(team_db)
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def update(cls, team: schemas.Team) -> schemas.TeamShow:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team.id)
            team_db.name = team.name
            team_db.dispatcher = session.get(models.Person, team.dispatcher.id) if team.dispatcher else None
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def update_notes(cls, team_id: UUID, notes: str) -> schemas.TeamShow:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team_id)
            team_db.notes = notes
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def put_in_comb_loc_possible(cls, team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team_id)
            team_db.combination_locations_possibles.append(
                session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def put_in_excel_settings(cls, team_id: UUID, excel_settings_id: UUID) -> schemas.TeamShow:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team_id)
            team_db.excel_export_settings = session.get(models.ExcelExportSettings, excel_settings_id)
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def remove_comb_loc_possible(cls, team_id: UUID, comb_loc_possible_id: UUID) -> schemas.TeamShow:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team_id)
            team_db.combination_locations_possibles.remove(
                session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.TeamShow.model_validate(team_db)

    @classmethod
    def delete(cls, team_id: UUID) -> schemas.Team:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.get(models.Team, team_id)
            team_db.prep_delete = _utcnow()
            session.flush()
            return schemas.Team.model_validate(team_db)


class Person:
    @classmethod
    def get(cls, person_id: UUID) -> schemas.PersonShow:
        with get_session() as session:
            return schemas.PersonShow.model_validate(session.get(models.Person, person_id))

    @classmethod
    def get_full_name_of_person(cls, person_id: UUID) -> str:
        with get_session() as session:
            p = session.get(models.Person, person_id)
            return f'{p.f_name} {p.l_name}'

    @classmethod
    def get_all_from__project(cls, project_id: UUID, minimal: bool = False) -> list[schemas.PersonShow | tuple[str, UUID]]:
        with get_session() as session:
            persons = session.exec(
                select(models.Person).where(
                    models.Person.project_id == project_id,
                    models.Person.prep_delete.is_(None)
                )
            ).all()
            return ([(p.full_name, p.id) for p in persons] if minimal
                    else [schemas.PersonShow.model_validate(p) for p in persons])

    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.PersonShow]:
        with get_session() as session:
            persons = session.exec(
                select(models.Person).join(models.ActorPlanPeriod)
                .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)
            ).unique().all()
            return [schemas.PersonShow.model_validate(p) for p in persons]

    @classmethod
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        with get_session() as session:
            pp_db = session.get(models.PlanPeriod, plan_period_id)
            return {app.person.full_name: app.person.id for app in pp_db.actor_plan_periods}

    @classmethod
    def get_all_possible_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        with get_session() as session:
            pp_db = session.get(models.PlanPeriod, plan_period_id)
            assigns = session.exec(
                select(models.TeamActorAssign).where(
                    models.TeamActorAssign.team_id == pp_db.team_id,
                    models.TeamActorAssign.start < pp_db.end,
                    or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > pp_db.end)
                )
            ).all()
            return {taa.person.full_name: taa.person.id for taa in assigns}

    @classmethod
    def get_dispatchers_from__project(cls, project_id: UUID) -> list[schemas.PersonShow]:
        with get_session() as session:
            dispatchers = session.exec(
                select(models.Person).join(models.Team, models.Team.dispatcher_id == models.Person.id)
                .where(models.Person.project_id == project_id)
            ).unique().all()
            return [schemas.PersonShow.model_validate(d) for d in dispatchers]

    @classmethod
    def create(cls, person: schemas.PersonCreate, project_id: UUID, person_id: UUID = None) -> schemas.Person:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            if person.address:
                address_db = models.Address(**person.address.model_dump(exclude={'project_id'}), project=project_db)
                session.add(address_db)
            else:
                address_db = None
            person_data = person.model_dump(exclude={'address'})
            person_data['password'] = hash_psw(person.password)
            if person_id:
                person_data['id'] = person_id
            person_db = models.Person(**person_data, address=address_db, project=project_db)
            session.add(person_db)
            session.flush()
            return schemas.Person.model_validate(person_db)

    @classmethod
    def create_persons_from_xlsx(cls, file_name: str, project_id: UUID) -> list[schemas.Person]:
        log_function_info(cls)
        with get_session() as session:
            team_db = session.exec(select(models.Team).where(models.Team.project_id == project_id)).first()
            try:
                df = pd.read_excel(file_name)
            except Exception as e:
                raise ValueError(f'Error while reading xlsx file: {e}')
            persons_list: list[schemas.Person] = []
            project_db = session.get(models.Project, project_id)
            for _, row in df.iterrows():
                person_db = models.Person(
                    f_name=row['First name'], l_name=row['Last name'],
                    email='fake@email.com', gender=Gender.divers, phone_nr=None,
                    username=row['username'], password=hash_psw('password'),
                    project=project_db, address=None)
                session.add(person_db)
                session.flush()
                taa = models.TeamActorAssign(start=datetime.date.today(), person=person_db, team=team_db)
                session.add(taa)
                session.flush()
                persons_list.append(schemas.Person.model_validate(person_db))
            return persons_list

    @classmethod
    def update(cls, person: schemas.PersonShow) -> schemas.Person:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person.id)
            if person_db.address:
                if person.address:
                    addr = session.get(models.Address, person.address.id)
                    for k, v in person.address.model_dump(include={'name', 'street', 'postal_code', 'city'}).items():
                        setattr(addr, k, v)
                else:
                    person_db.address = None
            elif person.address:
                person_db.address = session.get(models.Address, person.address.id)
            person_db.time_of_days.clear()
            for t_o_d in person.time_of_days:
                person_db.time_of_days.append(session.get(models.TimeOfDay, t_o_d.id))
            for k, v in person.model_dump(include={'f_name', 'l_name', 'email', 'gender', 'phone_nr', 'requested_assignments', 'notes'}).items():
                setattr(person_db, k, v)
            session.flush()
            return schemas.Person.model_validate(person_db)

    @classmethod
    def update_project_of_admin(cls, person_id: UUID, project_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.project_of_admin = session.get(models.Project, project_id)
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def put_in_time_of_day(cls, person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def remove_in_time_of_day(cls, person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def new_time_of_day_standard(cls, person_id: UUID, time_of_day_id: UUID) -> tuple[schemas.PersonShow, UUID | None]:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            tod_db = session.get(models.TimeOfDay, time_of_day_id)
            old_id = None
            for t in list(person_db.time_of_day_standards):
                if t.time_of_day_enum.id == tod_db.time_of_day_enum.id:
                    person_db.time_of_day_standards.remove(t)
                    old_id = t.id
                    break
            person_db.time_of_day_standards.append(tod_db)
            session.flush()
            return schemas.PersonShow.model_validate(person_db), old_id

    @classmethod
    def remove_time_of_day_standard(cls, person_id: UUID, time_of_day_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def delete(cls, person_id: UUID) -> schemas.Person:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.prep_delete = _utcnow()
            session.flush()
            return schemas.Person.model_validate(person_db)

    @classmethod
    def put_in_comb_loc_possible(cls, person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.combination_locations_possibles.append(
                session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def remove_comb_loc_possible(cls, person_id: UUID, comb_loc_possible_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.combination_locations_possibles.remove(
                session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def put_in_location_pref(cls, person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def remove_location_pref(cls, person_id: UUID, actor_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def put_in_partner_location_pref(cls, person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.actor_partner_location_prefs_defaults.append(
                session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def remove_partner_location_pref(cls, person_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.actor_partner_location_prefs_defaults.remove(
                session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def add_skill(cls, person_id: UUID, skill_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.skills.append(session.get(models.Skill, skill_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def remove_skill(cls, person_id: UUID, skill_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.skills.remove(session.get(models.Skill, skill_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def put_in_flag(cls, person_id: UUID, flag_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.flags.append(session.get(models.Flag, flag_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)

    @classmethod
    def remove_flag(cls, person_id: UUID, flag_id: UUID) -> schemas.PersonShow:
        log_function_info(cls)
        with get_session() as session:
            person_db = session.get(models.Person, person_id)
            person_db.flags.remove(session.get(models.Flag, flag_id))
            session.flush()
            return schemas.PersonShow.model_validate(person_db)


# ═══════════════════════════════════════════════════════════════════════════════
# LocationOfWork, Assigns, TimeOfDay, TimeOfDayEnum
# ═══════════════════════════════════════════════════════════════════════════════


class LocationOfWork:
    @classmethod
    def get(cls, location_id: UUID) -> schemas.LocationOfWorkShow:
        with get_session() as session:
            return schemas.LocationOfWorkShow.model_validate(session.get(models.LocationOfWork, location_id))

    @classmethod
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.LocationOfWorkShow]:
        with get_session() as session:
            locs = session.exec(select(models.LocationOfWork).where(
                models.LocationOfWork.project_id == project_id,
                models.LocationOfWork.prep_delete.is_(None))).all()
            return [schemas.LocationOfWorkShow.model_validate(loc) for loc in locs]

    @classmethod
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        with get_session() as session:
            pp_db = session.get(models.PlanPeriod, plan_period_id)
            return {lpp.location_of_work.name: lpp.location_of_work.id
                    for lpp in pp_db.location_plan_periods if lpp.location_of_work.prep_delete is None}

    @classmethod
    def get_all_possible_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict['str', UUID]:
        with get_session() as session:
            pp_db = session.get(models.PlanPeriod, plan_period_id)
            assigns = session.exec(select(models.TeamLocationAssign).where(
                models.TeamLocationAssign.team_id == pp_db.team_id,
                models.TeamLocationAssign.start < pp_db.end,
                or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > pp_db.end))).all()
            result = {}
            for tla in assigns:
                loc = tla.location_of_work
                if loc.prep_delete is None:
                    name = f"{loc.name} ({loc.address.city})" if loc.address and loc.address.city else loc.name
                    result[name] = loc.id
            return result

    @classmethod
    def get_all_locations_at_dates(cls, team_id: UUID, dates: list[datetime.date]) -> list[schemas.LocationOfWork]:
        with get_session() as session:
            locs: dict[UUID, models.LocationOfWork] = {}
            for date in dates:
                assigns = session.exec(select(models.TeamLocationAssign).where(
                    models.TeamLocationAssign.team_id == team_id,
                    models.TeamLocationAssign.start <= date,
                    or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > date))).all()
                for tla in assigns:
                    locs[tla.location_of_work_id] = tla.location_of_work
            return [schemas.LocationOfWork.model_validate(loc) for loc in locs.values()]

    @classmethod
    def create(cls, location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
        log_function_info(cls)
        with get_session() as session:
            project_db = session.get(models.Project, project_id)
            address_db = None
            if location.address:
                address_db = models.Address(**location.address.model_dump(exclude={'project_id'}), project=project_db)
                session.add(address_db)
            loc_db = models.LocationOfWork(name=location.name, project=project_db, address=address_db)
            session.add(loc_db)
            session.flush()
            return schemas.LocationOfWork.model_validate(loc_db)

    @classmethod
    def update(cls, location_of_work: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work.id)
            loc_db.time_of_days.clear()
            for t in location_of_work.time_of_days:
                loc_db.time_of_days.append(session.get(models.TimeOfDay, t.id))
            if loc_db.address:
                if location_of_work.address:
                    addr = session.get(models.Address, location_of_work.address.id)
                    for k, v in location_of_work.address.model_dump(include={'name', 'street', 'postal_code', 'city'}).items():
                        setattr(addr, k, v)
                else:
                    loc_db.address = None
            elif location_of_work.address:
                loc_db.address = session.get(models.Address, location_of_work.address.id)
            for k, v in location_of_work.model_dump(include={'name', 'nr_actors', 'fixed_cast'}).items():
                setattr(loc_db, k, v)
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def update_notes(cls, location_of_work_id: UUID, notes: str) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work_id)
            loc_db.notes = notes
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def put_in_time_of_day(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work_id)
            loc_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def remove_in_time_of_day(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work_id)
            loc_db.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def new_time_of_day_standard(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationOfWorkShow, UUID | None]:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work_id)
            tod_db = session.get(models.TimeOfDay, time_of_day_id)
            old_id = None
            for t in list(loc_db.time_of_day_standards):
                if t.time_of_day_enum.id == tod_db.time_of_day_enum.id:
                    loc_db.time_of_day_standards.remove(t)
                    old_id = t.id
                    break
            loc_db.time_of_day_standards.append(tod_db)
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db), old_id

    @classmethod
    def remove_time_of_day_standard(cls, location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work_id)
            if loc_db.time_of_day_standards:
                loc_db.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def update_fixed_cast(cls, location_of_work_id: UUID, fixed_cast: str,
                          fixed_cast_only_if_available: bool) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_of_work_id)
            loc_db.fixed_cast = fixed_cast
            loc_db.fixed_cast_only_if_available = fixed_cast_only_if_available
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def delete(cls, location_id: UUID) -> schemas.LocationOfWork:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_id)
            loc_db.prep_delete = _utcnow()
            session.flush()
            return schemas.LocationOfWork.model_validate(loc_db)

    @classmethod
    def add_skill_group(cls, location_id: UUID, skill_group_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_id)
            loc_db.skill_groups.append(session.get(models.SkillGroup, skill_group_id))
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)

    @classmethod
    def remove_skill_group(cls, location_id: UUID, skill_group_id: UUID) -> schemas.LocationOfWorkShow:
        log_function_info(cls)
        with get_session() as session:
            loc_db = session.get(models.LocationOfWork, location_id)
            loc_db.skill_groups.remove(session.get(models.SkillGroup, skill_group_id))
            session.flush()
            return schemas.LocationOfWorkShow.model_validate(loc_db)


class TeamActorAssign:
    @classmethod
    def get(cls, team_actor_assign_id: UUID) -> schemas.TeamActorAssignShow:
        with get_session() as session:
            return schemas.TeamActorAssignShow.model_validate(session.get(models.TeamActorAssign, team_actor_assign_id))

    @classmethod
    def get_at__date(cls, person_id: UUID, date: datetime.date | None) -> schemas.TeamActorAssignShow | None:
        with get_session() as session:
            assigns = session.exec(
                select(models.TeamActorAssign).where(models.TeamActorAssign.person_id == person_id)).all()
            if not assigns:
                return None
            if not date:
                latest = max(assigns, key=lambda x: x.start)
                if not latest.end or latest.end > datetime.date.today():
                    return schemas.TeamActorAssignShow.model_validate(latest)
                return None
            for a in assigns:
                if a.start <= date and (a.end is None or a.end > date):
                    return schemas.TeamActorAssignShow.model_validate(a)
            return None

    @classmethod
    def get_all_between_dates(cls, person_id: UUID, team_id: UUID,
                              date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamActorAssignShow]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamActorAssign).where(
                models.TeamActorAssign.team_id == team_id, models.TeamActorAssign.person_id == person_id,
                models.TeamActorAssign.start <= date_end,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end >= date_start))).all()
            return [schemas.TeamActorAssignShow.model_validate(a) for a in assigns]

    @classmethod
    def get_all_actor_ids_between_dates(cls, team_id: UUID,
                                        date_start: datetime.date, date_end: datetime.date) -> set[UUID]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamActorAssign).where(
                models.TeamActorAssign.team_id == team_id, models.TeamActorAssign.start <= date_end,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date_start))).all()
            return {a.person_id for a in assigns}

    @classmethod
    def get_all_at__date(cls, date: datetime.date, team_id: UUID) -> list[schemas.TeamActorAssignShow]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamActorAssign).where(
                models.TeamActorAssign.team_id == team_id, models.TeamActorAssign.start <= date,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date))).all()
            return [schemas.TeamActorAssignShow.model_validate(a) for a in assigns]

    @classmethod
    def get_all_teams_at_date(cls, person_id: UUID, date: datetime.date,
                              only_uuids: bool = False) -> list[schemas.TeamShow] | list[UUID]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamActorAssign).where(
                models.TeamActorAssign.person_id == person_id, models.TeamActorAssign.start <= date,
                or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date))).all()
            if only_uuids:
                return [a.team_id for a in assigns]
            return [schemas.TeamShow.model_validate(a.team) for a in assigns]

    @classmethod
    def create(cls, team_actor_assign: schemas.TeamActorAssignCreate,
               assign_id: UUID | None = None) -> schemas.TeamActorAssignShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = {'person': session.get(models.Person, team_actor_assign.person.id),
                      'team': session.get(models.Team, team_actor_assign.team.id)}
            if team_actor_assign.start:
                kwargs['start'] = team_actor_assign.start
            if assign_id:
                kwargs['id'] = assign_id
            taa = models.TeamActorAssign(**kwargs)
            session.add(taa)
            session.flush()
            return schemas.TeamActorAssignShow.model_validate(taa)

    @classmethod
    def set_end_date(cls, team_actor_assign_id: UUID, end_date: datetime.date | None = None):
        log_function_info(cls)
        with get_session() as session:
            session.get(models.TeamActorAssign, team_actor_assign_id).end = end_date

    @classmethod
    def delete(cls, team_actor_assign_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.TeamActorAssign, team_actor_assign_id))


class TeamLocationAssign:
    @classmethod
    def get(cls, team_location_assign_id: UUID) -> schemas.TeamLocationAssignShow:
        with get_session() as session:
            return schemas.TeamLocationAssignShow.model_validate(session.get(models.TeamLocationAssign, team_location_assign_id))

    @classmethod
    def get_at__date(cls, location_id: UUID, date: datetime.date | None) -> schemas.TeamLocationAssignShow | None:
        with get_session() as session:
            assigns = session.exec(select(models.TeamLocationAssign).where(
                models.TeamLocationAssign.location_of_work_id == location_id)).all()
            if not assigns:
                return None
            if not date:
                latest = max(assigns, key=lambda x: x.start)
                if not latest.end or latest.end > datetime.date.today():
                    return schemas.TeamLocationAssignShow.model_validate(latest)
                return None
            for a in assigns:
                if a.start <= date and (a.end is None or a.end > date):
                    return schemas.TeamLocationAssignShow.model_validate(a)
            return None

    @classmethod
    def get_all_of_location_between_dates(cls, location_id: UUID, team_id: UUID,
                                          date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamLocationAssignShow]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamLocationAssign).where(
                models.TeamLocationAssign.team_id == team_id, models.TeamLocationAssign.location_of_work_id == location_id,
                models.TeamLocationAssign.start <= date_end,
                or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end >= date_start))).all()
            return [schemas.TeamLocationAssignShow.model_validate(a) for a in assigns]

    @classmethod
    def get_all_between_dates(cls, team_id: UUID,
                              date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamLocationAssignShow]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamLocationAssign).where(
                models.TeamLocationAssign.team_id == team_id, models.TeamLocationAssign.start <= date_end,
                or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end >= date_start))).all()
            return [schemas.TeamLocationAssignShow.model_validate(a) for a in assigns]

    @classmethod
    def get_all_at__date(cls, date: datetime.date, team_id: UUID) -> list[schemas.TeamLocationAssignShow]:
        with get_session() as session:
            assigns = session.exec(select(models.TeamLocationAssign).where(
                models.TeamLocationAssign.team_id == team_id, models.TeamLocationAssign.start <= date,
                or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > date))).all()
            return [schemas.TeamLocationAssignShow.model_validate(a) for a in assigns]

    @classmethod
    def create(cls, team_location_assign: schemas.TeamLocationAssignCreate,
               assign_id: UUID | None = None) -> schemas.TeamLocationAssignShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = {'location_of_work': session.get(models.LocationOfWork, team_location_assign.location_of_work.id),
                      'team': session.get(models.Team, team_location_assign.team.id)}
            if team_location_assign.start:
                kwargs['start'] = team_location_assign.start
            if assign_id:
                kwargs['id'] = assign_id
            tla = models.TeamLocationAssign(**kwargs)
            session.add(tla)
            session.flush()
            return schemas.TeamLocationAssignShow.model_validate(tla)

    @classmethod
    def set_end_date(cls, team_location_assign_id: UUID, end_date: datetime.date | None = None):
        log_function_info(cls)
        with get_session() as session:
            session.get(models.TeamLocationAssign, team_location_assign_id).end = end_date

    @classmethod
    def delete(cls, team_loc_assign_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.TeamLocationAssign, team_loc_assign_id))


class TimeOfDay:
    @classmethod
    def get(cls, time_of_day_id: UUID, reduced: bool = False) -> schemas.TimeOfDayShow | schemas.TimeOfDay:
        with get_session() as session:
            tod = session.get(models.TimeOfDay, time_of_day_id)
            return schemas.TimeOfDay.model_validate(tod) if reduced else schemas.TimeOfDayShow.model_validate(tod)

    @classmethod
    def get_time_of_days_from__event(cls, event_id: UUID) -> list[schemas.TimeOfDay]:
        with get_session() as session:
            return [schemas.TimeOfDay.model_validate(t) for t in session.get(models.Event, event_id).time_of_days]

    @classmethod
    def get_all_from_location_plan_period(cls, location_plan_period_id: UUID) -> list[schemas.TimeOfDay]:
        with get_session() as session:
            return [schemas.TimeOfDay.model_validate(t) for t in session.get(models.LocationPlanPeriod, location_plan_period_id).time_of_days]

    @classmethod
    def create(cls, time_of_day: schemas.TimeOfDayCreate, project_id: UUID) -> schemas.TimeOfDay:
        log_function_info(cls)
        with get_session() as session:
            tod = models.TimeOfDay(name=time_of_day.name,
                                   time_of_day_enum=session.get(models.TimeOfDayEnum, time_of_day.time_of_day_enum.id),
                                   project=session.get(models.Project, project_id),
                                   start=time_of_day.start, end=time_of_day.end)
            session.add(tod)
            session.flush()
            return schemas.TimeOfDay.model_validate(tod)

    @classmethod
    def update(cls, time_of_day: schemas.TimeOfDay):
        log_function_info(cls)
        with get_session() as session:
            tod = session.get(models.TimeOfDay, time_of_day.id)
            tod.name = time_of_day.name
            tod.start = time_of_day.start
            tod.end = time_of_day.end
            tod.time_of_day_enum = session.get(models.TimeOfDayEnum, time_of_day.time_of_day_enum.id)
            session.flush()
            return schemas.TimeOfDay.model_validate(tod)

    @classmethod
    def put_to_model(cls, time_of_day: schemas.TimeOfDay, pydantic_model: schemas.ModelWithTimeOfDays, db_model):
        log_function_info(cls)
        if not (isinstance(pydantic_model, schemas.ModelWithTimeOfDays) or isinstance(pydantic_model, schemas.Project)):
            raise ValueError
        with get_session() as session:
            instance_db = session.get(db_model, pydantic_model.id)
            instance_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day.id))
            session.flush()
            return type(pydantic_model).model_validate(instance_db)

    @classmethod
    def delete(cls, time_of_day_id: UUID) -> schemas.TimeOfDay:
        log_function_info(cls)
        with get_session() as session:
            tod = session.get(models.TimeOfDay, time_of_day_id)
            tod.prep_delete = _utcnow()
            session.flush()
            return schemas.TimeOfDay.model_validate(tod)

    @classmethod
    def undo_delete(cls, time_of_day_id: UUID) -> schemas.TimeOfDay:
        log_function_info(cls)
        with get_session() as session:
            tod = session.get(models.TimeOfDay, time_of_day_id)
            tod.prep_delete = None
            session.flush()
            return schemas.TimeOfDay.model_validate(tod)

    @classmethod
    def delete_unused(cls, project_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            tods = session.exec(select(models.TimeOfDay).where(models.TimeOfDay.project_id == project_id)).all()
            for t in tods:
                if t.prep_delete:
                    continue
                empty = [t.persons_defaults, t.actor_plan_periods_defaults, t.avail_days_defaults,
                         t.avail_days, t.locations_of_work_defaults, t.location_plan_periods_defaults,
                         t.events_defaults, t.events]
                if not t.project_defaults and all(not c for c in empty):
                    t.prep_delete = _utcnow()

    @classmethod
    def delete_prep_deletes(cls, project_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            tods = session.exec(select(models.TimeOfDay).where(models.TimeOfDay.project_id == project_id)).all()
            for t in tods:
                if t.prep_delete:
                    session.delete(t)


class TimeOfDayEnum:
    @classmethod
    def get(cls, time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        with get_session() as session:
            return schemas.TimeOfDayEnumShow.model_validate(session.get(models.TimeOfDayEnum, time_of_day_enum_id))

    @classmethod
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.TimeOfDayEnumShow]:
        with get_session() as session:
            return [schemas.TimeOfDayEnumShow.model_validate(e) for e in session.get(models.Project, project_id).time_of_day_enums]

    @classmethod
    def create(cls, time_of_day_enum: schemas.TimeOfDayEnumCreate,
               time_of_day_enum_id: UUID = None) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(name=time_of_day_enum.name, abbreviation=time_of_day_enum.abbreviation,
                          time_index=time_of_day_enum.time_index,
                          project=session.get(models.Project, time_of_day_enum.project.id))
            if time_of_day_enum_id:
                kwargs['id'] = time_of_day_enum_id
            tode = models.TimeOfDayEnum(**kwargs)
            session.add(tode)
            session.flush()
            return schemas.TimeOfDayEnumShow.model_validate(tode)

    @classmethod
    def update(cls, time_of_day_enum: schemas.TimeOfDayEnum) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        with get_session() as session:
            tode = session.get(models.TimeOfDayEnum, time_of_day_enum.id)
            for k, v in time_of_day_enum.model_dump(include={'name', 'abbreviation', 'time_index'}).items():
                setattr(tode, k, v)
            session.flush()
            return schemas.TimeOfDayEnumShow.model_validate(tode)

    @classmethod
    def prep_delete(cls, time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        with get_session() as session:
            tode = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
            tode.prep_delete = _utcnow()
            session.flush()
            return schemas.TimeOfDayEnumShow.model_validate(tode)

    @classmethod
    def undo_prep_delete(cls, time_of_day_enum_id: UUID) -> schemas.TimeOfDayEnumShow:
        log_function_info(cls)
        with get_session() as session:
            tode = session.get(models.TimeOfDayEnum, time_of_day_enum_id)
            tode.prep_delete = None
            session.flush()
            return schemas.TimeOfDayEnumShow.model_validate(tode)

    @classmethod
    def delete(cls, time_of_day_enum_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.TimeOfDayEnum, time_of_day_enum_id))

    @classmethod
    def consolidate_indexes(cls, project_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            enums = session.exec(select(models.TimeOfDayEnum).where(
                models.TimeOfDayEnum.project_id == project_id,
                models.TimeOfDayEnum.prep_delete.is_(None))).all()
            for i, tode in enumerate(sorted(enums, key=lambda x: x.time_index), start=1):
                tode.time_index = i
                session.flush()


# ═══════════════════════════════════════════════════════════════════════════════
# Stamm-Entities (Leaf)
# ═══════════════════════════════════════════════════════════════════════════════


class ExcelExportSettings:
    @classmethod
    def get(cls, excel_export_settings_id: UUID) -> schemas.ExcelExportSettingsShow:
        with get_session() as session:
            return schemas.ExcelExportSettingsShow.model_validate(session.get(models.ExcelExportSettings, excel_export_settings_id))

    @classmethod
    def create(cls, excel_settings: schemas.ExcelExportSettingsCreate) -> schemas.ExcelExportSettingsShow:
        log_function_info(cls)
        with get_session() as session:
            ees = models.ExcelExportSettings(**excel_settings.model_dump())
            session.add(ees)
            session.flush()
            return schemas.ExcelExportSettingsShow.model_validate(ees)

    @classmethod
    def update(cls, excel_export_settings: schemas.ExcelExportSettings) -> schemas.ExcelExportSettings:
        log_function_info(cls)
        with get_session() as session:
            ees = session.get(models.ExcelExportSettings, excel_export_settings.id)
            for k, v in excel_export_settings.model_dump(exclude={'id'}).items():
                setattr(ees, k, v)
            session.flush()
            return schemas.ExcelExportSettings.model_validate(ees)


class Address:
    @classmethod
    def get(cls, address_id: UUID) -> schemas.Address:
        with get_session() as session:
            return schemas.Address.model_validate(session.get(models.Address, address_id))

    @classmethod
    def get_all_from__project(cls, project_id: UUID, include_prep_delete: bool = False) -> list[schemas.Address]:
        with get_session() as session:
            stmt = select(models.Address).where(models.Address.project_id == project_id)
            if not include_prep_delete:
                stmt = stmt.where(models.Address.prep_delete.is_(None))
            return [schemas.Address.model_validate(a) for a in session.exec(stmt).all()]

    @classmethod
    def create(cls, address: schemas.AddressCreate) -> schemas.Address:
        log_function_info(cls)
        with get_session() as session:
            addr = models.Address(project=session.get(models.Project, address.project_id),
                                  street=address.street, postal_code=address.postal_code,
                                  city=address.city, name=address.name)
            session.add(addr)
            session.flush()
            return schemas.Address.model_validate(addr)

    @classmethod
    def update(cls, address: schemas.Address) -> schemas.Address:
        log_function_info(cls)
        with get_session() as session:
            addr = session.get(models.Address, address.id)
            for k, v in address.model_dump(include={'name', 'street', 'postal_code', 'city'}).items():
                setattr(addr, k, v)
            session.flush()
            return schemas.Address.model_validate(addr)

    @classmethod
    def delete(cls, address_id: UUID, soft_delete: bool = True) -> schemas.Address | None:
        log_function_info(cls)
        with get_session() as session:
            addr = session.get(models.Address, address_id)
            if soft_delete:
                addr.prep_delete = _utcnow()
                session.flush()
                return schemas.Address.model_validate(addr)
            session.delete(addr)
            return None

    @classmethod
    def undelete(cls, address_id: UUID) -> schemas.Address:
        log_function_info(cls)
        with get_session() as session:
            addr = session.get(models.Address, address_id)
            addr.prep_delete = None
            session.flush()
            return schemas.Address.model_validate(addr)


class MaxFairShiftsOfApp:
    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.MaxFairShiftsOfAppShow]:
        with get_session() as session:
            mfs_list = session.exec(select(models.MaxFairShiftsOfApp).join(models.ActorPlanPeriod)
                                    .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
            return [schemas.MaxFairShiftsOfAppShow.model_validate(m) for m in mfs_list]

    @classmethod
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict[UUID, tuple[int, int]]:
        with get_session() as session:
            mfs_list = session.exec(select(models.MaxFairShiftsOfApp).join(models.ActorPlanPeriod)
                                    .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
            return {m.actor_plan_period_id: (m.max_shifts, m.fair_shifts) for m in mfs_list}

    @classmethod
    def create(cls, max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppCreate) -> schemas.MaxFairShiftsOfAppShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(max_shifts=max_fair_shifts_per_app.max_shifts,
                          fair_shifts=max_fair_shifts_per_app.fair_shifts,
                          actor_plan_period=session.get(models.ActorPlanPeriod, max_fair_shifts_per_app.actor_plan_period_id))
            if max_fair_shifts_per_app.id:
                kwargs['id'] = max_fair_shifts_per_app.id
            mfs = models.MaxFairShiftsOfApp(**kwargs)
            session.add(mfs)
            session.flush()
            return schemas.MaxFairShiftsOfAppShow.model_validate(mfs)

    @classmethod
    def delete(cls, max_fair_shifts_per_app_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.MaxFairShiftsOfApp, max_fair_shifts_per_app_id))


class CastRule:
    @classmethod
    def get(cls, cast_rule_id: UUID) -> schemas.CastRuleShow:
        with get_session() as session:
            return schemas.CastRuleShow.model_validate(session.get(models.CastRule, cast_rule_id))

    @classmethod
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.CastRuleShow]:
        with get_session() as session:
            return [schemas.CastRuleShow.model_validate(cr) for cr in session.get(models.Project, project_id).cast_rules]

    @classmethod
    def create(cls, project_id: UUID, name: str, rule: str, restore_id: UUID | None = None) -> schemas.CastRuleShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(project=session.get(models.Project, project_id), name=name, rule=rule)
            if restore_id:
                kwargs['id'] = restore_id
            cr = models.CastRule(**kwargs)
            session.add(cr)
            session.flush()
            return schemas.CastRuleShow.model_validate(cr)

    @classmethod
    def update(cls, cast_rule_id: UUID, name: str, rule: str) -> schemas.CastRuleShow:
        log_function_info(cls)
        with get_session() as session:
            cr = session.get(models.CastRule, cast_rule_id)
            cr.name = name
            cr.rule = rule
            session.flush()
            return schemas.CastRuleShow.model_validate(cr)

    @classmethod
    def set_prep_delete(cls, cast_rule_id: UUID) -> schemas.CastRuleShow:
        log_function_info(cls)
        with get_session() as session:
            cr = session.get(models.CastRule, cast_rule_id)
            cr.prep_delete = _utcnow()
            session.flush()
            return schemas.CastRuleShow.model_validate(cr)

    @classmethod
    def undelete(cls, cast_rule_id: UUID) -> schemas.CastRuleShow:
        log_function_info(cls)
        with get_session() as session:
            cr = session.get(models.CastRule, cast_rule_id)
            cr.prep_delete = None
            session.flush()
            return schemas.CastRuleShow.model_validate(cr)

    @classmethod
    def delete(cls, cast_rule_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.CastRule, cast_rule_id))


# ═══════════════════════════════════════════════════════════════════════════════
# Planungs-Entities
# ═══════════════════════════════════════════════════════════════════════════════


class PlanPeriod:
    @classmethod
    def get(cls, plan_period_id: UUID) -> schemas.PlanPeriodShow:
        with get_session() as session:
            return schemas.PlanPeriodShow.model_validate(session.get(models.PlanPeriod, plan_period_id))

    @classmethod
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.PlanPeriodShow]:
        with get_session() as session:
            pps = session.exec(select(models.PlanPeriod).join(models.Team)
                               .where(models.Team.project_id == project_id)).all()
            return [schemas.PlanPeriodShow.model_validate(p) for p in pps]

    @classmethod
    def get_all_from__team(cls, team_id: UUID) -> list[schemas.PlanPeriodShow]:
        with get_session() as session:
            pps = session.exec(select(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)).all()
            return [schemas.PlanPeriodShow.model_validate(p) for p in pps]

    @classmethod
    def get_all_from__team_minimal(cls, team_id: UUID) -> list[schemas.PlanPeriodMinimal]:
        with get_session() as session:
            pps = session.exec(select(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)).all()
            return [schemas.PlanPeriodMinimal.model_validate(p) for p in pps]

    @classmethod
    def create(cls, plan_period: schemas.PlanPeriodCreate) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            pp = models.PlanPeriod(start=plan_period.start, end=plan_period.end, deadline=plan_period.deadline,
                                   notes=plan_period.notes, notes_for_employees=plan_period.notes_for_employees,
                                   team=session.get(models.Team, plan_period.team.id))
            session.add(pp)
            session.flush()
            return schemas.PlanPeriodShow.model_validate(pp)

    @classmethod
    def update(cls, plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            pp = session.get(models.PlanPeriod, plan_period.id)
            pp.start = plan_period.start
            pp.end = plan_period.end
            pp.deadline = plan_period.deadline
            pp.notes = plan_period.notes
            pp.notes_for_employees = plan_period.notes_for_employees
            pp.remainder = plan_period.remainder
            for app in pp.actor_plan_periods:
                for ad in app.avail_days:
                    if not (plan_period.start <= ad.date <= plan_period.end) and not ad.prep_delete:
                        ad.prep_delete = _utcnow()
            for lpp in pp.location_plan_periods:
                for event in lpp.events:
                    if not (plan_period.start <= event.date <= plan_period.end) and not event.prep_delete:
                        event.prep_delete = _utcnow()
            session.flush()
            return schemas.PlanPeriodShow.model_validate(pp)

    @classmethod
    def update_notes(cls, plan_period_id: UUID, notes: str) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            pp = session.get(models.PlanPeriod, plan_period_id)
            pp.notes = notes
            session.flush()
            return schemas.PlanPeriodShow.model_validate(pp)

    @classmethod
    def delete(cls, plan_period_id: UUID) -> schemas.PlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            pp = session.get(models.PlanPeriod, plan_period_id)
            pp.prep_delete = _utcnow()
            session.flush()
            return schemas.PlanPeriodShow.model_validate(pp)

    @classmethod
    def undelete(cls, plan_period_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            pp = session.get(models.PlanPeriod, plan_period_id)
            pp.prep_delete = None
            session.flush()
            return schemas.PlanPeriodShow.model_validate(pp)

    @classmethod
    def delete_prep_deletes(cls, team_id: UUID):
        with get_session() as session:
            pps = session.exec(select(models.PlanPeriod).where(
                models.PlanPeriod.team_id == team_id, models.PlanPeriod.prep_delete.isnot(None))).all()
            for pp in pps:
                session.delete(pp)


class LocationPlanPeriod:
    @classmethod
    def get(cls, location_plan_period_id: UUID) -> schemas.LocationPlanPeriodShow:
        with get_session() as session:
            return schemas.LocationPlanPeriodShow.model_validate(session.get(models.LocationPlanPeriod, location_plan_period_id))

    @classmethod
    def create(cls, plan_period_id: UUID, location_id: UUID, location_plan_period_id: UUID = None) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(plan_period=session.get(models.PlanPeriod, plan_period_id),
                          location_of_work=session.get(models.LocationOfWork, location_id))
            if location_plan_period_id:
                kwargs['id'] = location_plan_period_id
            lpp = models.LocationPlanPeriod(**kwargs)
            session.add(lpp)
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)

    @classmethod
    def delete(cls, location_plan_period_id: UUID):
        with get_session() as session:
            session.delete(session.get(models.LocationPlanPeriod, location_plan_period_id))

    @classmethod
    def update_notes(cls, location_plan_period_id: UUID, notes: str) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            lpp.notes = notes
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)

    @classmethod
    def put_in_time_of_day(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            lpp.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)

    @classmethod
    def remove_in_time_of_day(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            lpp.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)

    @classmethod
    def remove_time_of_day_standard(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            lpp.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)

    @classmethod
    def new_time_of_day_standard(cls, location_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationPlanPeriodShow, UUID | None]:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            tod = session.get(models.TimeOfDay, time_of_day_id)
            old_id = None
            for t in list(lpp.time_of_day_standards):
                if t.time_of_day_enum.id == tod.time_of_day_enum.id:
                    lpp.time_of_day_standards.remove(t)
                    old_id = t.id
                    break
            lpp.time_of_day_standards.append(tod)
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp), old_id

    @classmethod
    def update_fixed_cast(cls, location_plan_period_id: UUID, fixed_cast: str,
                          fixed_cast_only_if_available: bool) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            lpp.fixed_cast = fixed_cast
            lpp.fixed_cast_only_if_available = fixed_cast_only_if_available
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)

    @classmethod
    def update_num_actors(cls, location_plan_period_id: UUID, num_actors: int) -> schemas.LocationPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            lpp.nr_actors = num_actors
            session.flush()
            return schemas.LocationPlanPeriodShow.model_validate(lpp)


# ═══════════════════════════════════════════════════════════════════════════════
# Event/Cast
# ═══════════════════════════════════════════════════════════════════════════════


class EventGroup:
    @classmethod
    def get(cls, event_group_id: UUID) -> schemas.EventGroupShow:
        with get_session() as session:
            return schemas.EventGroupShow.model_validate(session.get(models.EventGroup, event_group_id))

    @classmethod
    def get_master_from__location_plan_period(cls, location_plan_period_id: UUID) -> schemas.EventGroupShow:
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, location_plan_period_id)
            return schemas.EventGroupShow.model_validate(lpp.event_group)

    @classmethod
    def get_child_groups_from__parent_group(cls, event_group_id) -> list[schemas.EventGroupShow]:
        with get_session() as session:
            eg = session.get(models.EventGroup, event_group_id)
            return [schemas.EventGroupShow.model_validate(e) for e in eg.event_groups]

    @classmethod
    def get_grand_parent_event_group_id_from_event(cls, event_id: UUID) -> UUID | None:
        with get_session() as session:
            event = session.get(models.Event, event_id)
            return event.event_group.event_group.id if event.event_group.event_group else None

    @classmethod
    def create(cls, *, location_plan_period_id: Optional[UUID] = None,
               event_group_id: Optional[UUID] = None, undo_group_id: UUID = None) -> schemas.EventGroupShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = {}
            if location_plan_period_id:
                kwargs['location_plan_period'] = session.get(models.LocationPlanPeriod, location_plan_period_id)
            if event_group_id:
                kwargs['event_group'] = session.get(models.EventGroup, event_group_id)
            if undo_group_id:
                kwargs['id'] = undo_group_id
            eg = models.EventGroup(**kwargs)
            session.add(eg)
            session.flush()
            return schemas.EventGroupShow.model_validate(eg)

    @classmethod
    def update_nr_event_groups(cls, event_group_id: UUID, nr_event_groups: int | None) -> schemas.EventGroupShow:
        log_function_info(cls)
        with get_session() as session:
            eg = session.get(models.EventGroup, event_group_id)
            eg.nr_event_groups = nr_event_groups
            session.flush()
            return schemas.EventGroupShow.model_validate(eg)

    @classmethod
    def update_variation_weight(cls, event_group_id: UUID, variation_weight: int) -> schemas.EventGroupShow:
        log_function_info(cls)
        with get_session() as session:
            eg = session.get(models.EventGroup, event_group_id)
            eg.variation_weight = variation_weight
            session.flush()
            return schemas.EventGroupShow.model_validate(eg)

    @classmethod
    def set_new_parent(cls, event_group_id: UUID, new_parent_id: UUID) -> schemas.EventGroupShow:
        log_function_info(cls)
        with get_session() as session:
            eg = session.get(models.EventGroup, event_group_id)
            eg.event_group = session.get(models.EventGroup, new_parent_id)
            session.flush()
            return schemas.EventGroupShow.model_validate(eg)

    @classmethod
    def delete(cls, event_group_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.EventGroup, event_group_id))


class CastGroup:
    @classmethod
    def get(cls, cast_group_id: UUID) -> schemas.CastGroupShow:
        with get_session() as session:
            return schemas.CastGroupShow.model_validate(session.get(models.CastGroup, cast_group_id))

    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.CastGroupShow]:
        with get_session() as session:
            return [schemas.CastGroupShow.model_validate(cg)
                    for cg in session.get(models.PlanPeriod, plan_period_id).cast_groups]

    @classmethod
    def get_all_from__location_plan_period_at_date(
            cls, location_plan_period_id: UUID, date: datetime.date) -> list[schemas.CastGroupShow]:
        with get_session() as session:
            cgs = session.exec(
                select(models.CastGroup).join(models.Event)
                .where(models.Event.date == date,
                       models.Event.location_plan_period_id == location_plan_period_id)
            ).all()
            return [schemas.CastGroupShow.model_validate(cg) for cg in cgs]

    @classmethod
    def get_cast_group_of_event(cls, event_id: UUID) -> schemas.CastGroupShow:
        with get_session() as session:
            return schemas.CastGroupShow.model_validate(session.get(models.Event, event_id).cast_group)

    @classmethod
    def create(cls, *, plan_period_id: UUID, restore_cast_group: schemas.CastGroupShow = None) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            pp = session.get(models.PlanPeriod, plan_period_id)
            if restore_cast_group:
                cast_rule = session.get(models.CastRule, restore_cast_group.cast_rule.id) if restore_cast_group.cast_rule else None
                cg = models.CastGroup(id=restore_cast_group.id, nr_actors=0, plan_period=pp, cast_rule=cast_rule)
                session.add(cg)
                session.flush()
                for pg in restore_cast_group.parent_groups:
                    cg.parent_groups.append(session.get(models.CastGroup, pg.id))
                for child in restore_cast_group.child_groups:
                    cg.child_groups.append(session.get(models.CastGroup, child.id))
                cg.nr_actors = restore_cast_group.nr_actors
                cg.fixed_cast = restore_cast_group.fixed_cast
                cg.strict_cast_pref = restore_cast_group.strict_cast_pref
            else:
                cg = models.CastGroup(nr_actors=0, plan_period=pp)
                session.add(cg)
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def set_new_parent(cls, cast_group_id: UUID, new_parent_id: UUID | None) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.parent_groups.append(session.get(models.CastGroup, new_parent_id))
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def remove_from_parent(cls, cast_group_id: UUID, parent_group_id: UUID | None) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.parent_groups.remove(session.get(models.CastGroup, parent_group_id))
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def update_fixed_cast(cls, cast_group_id: UUID, fixed_cast: str,
                          fixed_cast_only_if_available: bool) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.fixed_cast = fixed_cast
            cg.fixed_cast_only_if_available = fixed_cast_only_if_available
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def update_nr_actors(cls, cast_group_id: UUID, nr_actors: int) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.nr_actors = nr_actors
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def update_strict_cast_pref(cls, cast_group_id: UUID, strict_cast_pref: int) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.strict_cast_pref = strict_cast_pref
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def update_prefer_fixed_cast_events(cls, cast_group_id: UUID, prefer_fixed_cast_events: bool) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.prefer_fixed_cast_events = prefer_fixed_cast_events
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def update_custom_rule(cls, cast_group_id: UUID, custom_rule: str) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.custom_rule = custom_rule
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def update_cast_rule(cls, cast_group_id: UUID, cast_rule_id: UUID | None) -> schemas.CastGroupShow:
        log_function_info(cls)
        with get_session() as session:
            cg = session.get(models.CastGroup, cast_group_id)
            cg.cast_rule = session.get(models.CastRule, cast_rule_id) if cast_rule_id else None
            session.flush()
            return schemas.CastGroupShow.model_validate(cg)

    @classmethod
    def delete(cls, cast_group_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.CastGroup, cast_group_id))


class Event:
    @classmethod
    def get(cls, event_id: UUID) -> schemas.EventShow:
        with get_session() as session:
            return schemas.EventShow.model_validate(session.get(models.Event, event_id))

    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.EventShow]:
        with get_session() as session:
            events = session.exec(select(models.Event).join(models.LocationPlanPeriod)
                                  .where(models.LocationPlanPeriod.plan_period_id == plan_period_id)).all()
            return [schemas.EventShow.model_validate(e) for e in events]

    @classmethod
    def get_all_from__plan_period_date_time_of_day(cls, plan_period_id: UUID,
                                                   date: datetime.date, time_index: int) -> list[schemas.EventShow]:
        with get_session() as session:
            events = session.exec(
                select(models.Event).join(models.LocationPlanPeriod)
                .join(models.TimeOfDay, models.Event.time_of_day_id == models.TimeOfDay.id)
                .join(models.TimeOfDayEnum)
                .where(models.LocationPlanPeriod.plan_period_id == plan_period_id,
                       models.Event.date == date, models.TimeOfDayEnum.time_index == time_index)
            ).all()
            return [schemas.EventShow.model_validate(e) for e in events]

    @classmethod
    def get_all_from__location_plan_period(cls, location_plan_period_id) -> list[schemas.EventShow]:
        with get_session() as session:
            events = session.exec(select(models.Event).where(
                models.Event.location_plan_period_id == location_plan_period_id)).all()
            return [schemas.EventShow.model_validate(e) for e in events]

    @classmethod
    def get_from__event_group(cls, event_group_id) -> schemas.EventShow | None:
        with get_session() as session:
            eg = session.get(models.EventGroup, event_group_id)
            return schemas.EventShow.model_validate(eg.event) if eg.event else None

    @classmethod
    def get_from__location_pp_date_tod(cls, location_plan_period_id: UUID, date: datetime.date,
                                       time_of_day_id) -> schemas.EventShow | None:
        with get_session() as session:
            event = session.exec(select(models.Event).where(
                models.Event.location_plan_period_id == location_plan_period_id,
                models.Event.date == date, models.Event.time_of_day_id == time_of_day_id,
                models.Event.prep_delete.is_(None))).first()
            return schemas.EventShow.model_validate(event) if event else None

    @classmethod
    def get_from__location_pp_date_time_index(cls, location_plan_period_id: UUID, date: datetime.date,
                                              time_index: int) -> schemas.Event | None:
        with get_session() as session:
            event = session.exec(
                select(models.Event)
                .join(models.TimeOfDay, models.Event.time_of_day_id == models.TimeOfDay.id)
                .join(models.TimeOfDayEnum)
                .where(models.Event.location_plan_period_id == location_plan_period_id,
                       models.Event.date == date, models.TimeOfDayEnum.time_index == time_index)
            ).first()
            return schemas.Event.model_validate(event) if event else None

    @classmethod
    def get_from__location_pp_date(cls, location_plan_period_id: UUID, date: datetime.date) -> list[schemas.EventShow]:
        with get_session() as session:
            events = session.exec(select(models.Event).where(
                models.Event.location_plan_period_id == location_plan_period_id,
                models.Event.date == date)).all()
            return [schemas.EventShow.model_validate(e) for e in events]

    @classmethod
    def create(cls, event: schemas.EventCreate) -> schemas.EventShow:
        """Erstellt Event mit zugehöriger EventGroup und CastGroup (inlined)."""
        log_function_info(cls)
        with get_session() as session:
            lpp = session.get(models.LocationPlanPeriod, event.location_plan_period.id)
            master_eg = lpp.event_group
            # EventGroup erstellen (inlined)
            eg = models.EventGroup(event_group=master_eg)
            session.add(eg)
            # CastGroup erstellen (inlined)
            cg = models.CastGroup(nr_actors=lpp.nr_actors, plan_period=lpp.plan_period,
                                  fixed_cast=lpp.fixed_cast, fixed_cast_only_if_available=lpp.fixed_cast_only_if_available)
            session.add(cg)
            session.flush()
            event_db = models.Event(date=event.date,
                                    time_of_day=session.get(models.TimeOfDay, event.time_of_day.id),
                                    event_group=eg, cast_group=cg, location_plan_period=lpp)
            session.add(event_db)
            session.flush()
            return schemas.EventShow.model_validate(event_db)

    @classmethod
    def update_time_of_day_and_date(cls, event_id: UUID, new_time_of_day_id: UUID,
                                    new_date: datetime.date = None) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            event.time_of_day = session.get(models.TimeOfDay, new_time_of_day_id)
            if new_date:
                event.date = new_date
            session.flush()
            return schemas.EventShow.model_validate(event)

    @classmethod
    def update_time_of_days(cls, event_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            for t in time_of_days:
                event.time_of_days.append(session.get(models.TimeOfDay, t.id))
            session.flush()
            return schemas.EventShow.model_validate(event)

    @classmethod
    def update_notes(cls, event_id: UUID, notes: str) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            event.notes = notes
            session.flush()
            return schemas.EventShow.model_validate(event)

    @classmethod
    def delete(cls, event_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            deleted = schemas.EventShow.model_validate(event)
            eg = event.event_group
            cg = event.cast_group
            session.delete(event)
            session.flush()
            session.delete(eg)
            session.delete(cg)
            return deleted

    @classmethod
    def put_in_flag(cls, event_id: UUID, flag_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            event.flags.append(session.get(models.Flag, flag_id))
            session.flush()
            return schemas.EventShow.model_validate(event)

    @classmethod
    def remove_flag(cls, event_id: UUID, flag_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            event.flags.remove(session.get(models.Flag, flag_id))
            session.flush()
            return schemas.EventShow.model_validate(event)

    @classmethod
    def add_skill_group(cls, event_id: UUID, skill_group_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            event.skill_groups.append(session.get(models.SkillGroup, skill_group_id))
            session.flush()
            return schemas.EventShow.model_validate(event)

    @classmethod
    def remove_skill_group(cls, event_id: UUID, skill_group_id: UUID) -> schemas.EventShow:
        log_function_info(cls)
        with get_session() as session:
            event = session.get(models.Event, event_id)
            event.skill_groups.remove(session.get(models.SkillGroup, skill_group_id))
            session.flush()
            return schemas.EventShow.model_validate(event)


# ═══════════════════════════════════════════════════════════════════════════════
# Größte Entities (ActorPlanPeriod, AvailDayGroup, AvailDay)
# ═══════════════════════════════════════════════════════════════════════════════


class ActorPlanPeriod:
    @classmethod
    def get(cls, actor_plan_period_id: UUID) -> schemas.ActorPlanPeriodShow:
        with get_session() as session:
            return schemas.ActorPlanPeriodShow.model_validate(session.get(models.ActorPlanPeriod, actor_plan_period_id))

    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID, maximal: bool = False) -> list[schemas.ActorPlanPeriod | schemas.ActorPlanPeriodShow]:
        with get_session() as session:
            apps = session.exec(select(models.ActorPlanPeriod).where(
                models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
            schema_cls = schemas.ActorPlanPeriodShow if maximal else schemas.ActorPlanPeriod
            return [schema_cls.model_validate(a) for a in apps]

    @classmethod
    def get_all_for_solver(cls, plan_period_id: UUID) -> dict[UUID, schemas.ActorPlanPeriodSolver]:
        with get_session() as session:
            apps = list(session.exec(select(models.ActorPlanPeriod).where(
                models.ActorPlanPeriod.plan_period_id == plan_period_id)).all())
            if not apps:
                return {}
            app_ids = [a.id for a in apps]
            avail_days = session.exec(select(models.AvailDay).where(
                models.AvailDay.actor_plan_period_id.in_(app_ids))).all()
            adg_by_app: dict[UUID, list[UUID]] = {aid: [] for aid in app_ids}
            for ad in avail_days:
                adg_by_app[ad.actor_plan_period_id].append(ad.avail_day_group_id)
            return {
                a.id: schemas.ActorPlanPeriodSolver(
                    id=a.id, requested_assignments=a.requested_assignments,
                    required_assignments=a.required_assignments,
                    person=schemas.PersonSolver(id=a.person.id, f_name=a.person.f_name, l_name=a.person.l_name),
                    plan_period=schemas.PlanPeriodSolver(id=a.plan_period.id, start=a.plan_period.start, end=a.plan_period.end),
                    avail_day_group_ids=adg_by_app[a.id])
                for a in apps}

    @classmethod
    def create(cls, plan_period_id: UUID, person_id: UUID,
               actor_plan_period_id: UUID = None) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(plan_period=session.get(models.PlanPeriod, plan_period_id),
                          person=session.get(models.Person, person_id))
            if actor_plan_period_id:
                kwargs['id'] = actor_plan_period_id
            app = models.ActorPlanPeriod(**kwargs)
            session.add(app)
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def delete(cls, actor_plan_period_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.ActorPlanPeriod, actor_plan_period_id))

    @classmethod
    def update(cls, actor_plan_period: schemas.ActorPlanPeriodShow) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period.id)
            app.time_of_days.clear()
            for t in actor_plan_period.time_of_days:
                app.time_of_days.append(session.get(models.TimeOfDay, t.id))
            for k, v in actor_plan_period.model_dump(include={'notes', 'requested_assignments'}).items():
                setattr(app, k, v)
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def update_notes(cls, actor_plan_period: schemas.ActorPlanPeriodUpdateNotes) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period.id)
            app.notes = actor_plan_period.notes
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def update_requested_assignments(cls, actor_plan_period_id: UUID,
                                     requested_assignments: int, required_assignments: bool) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.requested_assignments = requested_assignments
            app.required_assignments = required_assignments
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def put_in_time_of_day(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def remove_in_time_of_day(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def remove_time_of_day_standard(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def new_time_of_day_standard(cls, actor_plan_period_id: UUID, time_of_day_id: UUID) -> tuple[schemas.ActorPlanPeriodShow, UUID | None]:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            tod = session.get(models.TimeOfDay, time_of_day_id)
            old_id = None
            for t in list(app.time_of_day_standards):
                if t.time_of_day_enum.id == tod.time_of_day_enum.id:
                    app.time_of_day_standards.remove(t)
                    old_id = t.id
                    break
            app.time_of_day_standards.append(tod)
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app), old_id

    @classmethod
    def put_in_comb_loc_possible(cls, actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def remove_comb_loc_possible(cls, actor_plan_period_id: UUID, comb_loc_possible_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.combination_locations_possibles.remove(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def put_in_location_pref(cls, actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def remove_location_pref(cls, actor_plan_period_id: UUID, actor_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def put_in_partner_location_pref(cls, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)

    @classmethod
    def remove_partner_location_pref(cls, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.ActorPlanPeriodShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            app.actor_partner_location_prefs_defaults.remove(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
            session.flush()
            return schemas.ActorPlanPeriodShow.model_validate(app)


class AvailDayGroup:
    @classmethod
    def get(cls, avail_day_group_id: UUID) -> schemas.AvailDayGroupShow:
        with get_session() as session:
            return schemas.AvailDayGroupShow.model_validate(session.get(models.AvailDayGroup, avail_day_group_id))

    @classmethod
    def get_master_from__actor_plan_period(cls, actor_plan_period_id: UUID) -> schemas.AvailDayGroupShow:
        with get_session() as session:
            return schemas.AvailDayGroupShow.model_validate(
                session.get(models.ActorPlanPeriod, actor_plan_period_id).avail_day_group)

    @classmethod
    def get_child_groups_from__parent_group(cls, avail_day_group_id) -> list[schemas.AvailDayGroupShow]:
        with get_session() as session:
            adg = session.get(models.AvailDayGroup, avail_day_group_id)
            return [schemas.AvailDayGroupShow.model_validate(c) for c in adg.avail_day_groups]

    @classmethod
    def get_all_for_tree(cls, actor_plan_period_id: UUID) -> dict[UUID, schemas.AvailDayGroupTreeNode]:
        with get_session() as session:
            result: dict[UUID, schemas.AvailDayGroupTreeNode] = {}
            def collect(adg):
                node = schemas.AvailDayGroupTreeNode(
                    id=adg.id, variation_weight=adg.variation_weight or 1,
                    nr_avail_day_groups=adg.nr_avail_day_groups,
                    child_ids=[c.id for c in adg.avail_day_groups],
                    avail_day_id=adg.avail_day.id if adg.avail_day else None)
                result[adg.id] = node
                for child in adg.avail_day_groups:
                    collect(child)
            master = session.get(models.ActorPlanPeriod, actor_plan_period_id).avail_day_group
            collect(master)
            return result

    @classmethod
    def create(cls, *, actor_plan_period_id: Optional[UUID] = None,
               avail_day_group_id: Optional[UUID] = None, undo_id: UUID = None) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = {}
            if actor_plan_period_id:
                kwargs['actor_plan_period'] = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            if avail_day_group_id:
                kwargs['avail_day_group'] = session.get(models.AvailDayGroup, avail_day_group_id)
            if undo_id:
                kwargs['id'] = undo_id
            adg = models.AvailDayGroup(**kwargs)
            session.add(adg)
            session.flush()
            return schemas.AvailDayGroupShow.model_validate(adg)

    @classmethod
    def update_nr_avail_day_groups(cls, avail_day_group_id: UUID, nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        with get_session() as session:
            adg = session.get(models.AvailDayGroup, avail_day_group_id)
            adg.nr_avail_day_groups = nr_avail_day_groups
            session.flush()
            return schemas.AvailDayGroupShow.model_validate(adg)

    @classmethod
    def update_variation_weight(cls, avail_day_group_id: UUID, variation_weight: int) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        with get_session() as session:
            adg = session.get(models.AvailDayGroup, avail_day_group_id)
            adg.variation_weight = variation_weight
            session.flush()
            return schemas.AvailDayGroupShow.model_validate(adg)

    @classmethod
    def update_mandatory_nr_avail_day_groups(cls, avail_day_group_id: UUID, mandatory_nr_avail_day_groups: int | None) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        with get_session() as session:
            adg = session.get(models.AvailDayGroup, avail_day_group_id)
            adg.mandatory_nr_avail_day_groups = mandatory_nr_avail_day_groups
            session.flush()
            return schemas.AvailDayGroupShow.model_validate(adg)

    @classmethod
    def set_new_parent(cls, avail_day_group_id: UUID, new_parent_id: UUID) -> schemas.AvailDayGroupShow:
        log_function_info(cls)
        with get_session() as session:
            adg = session.get(models.AvailDayGroup, avail_day_group_id)
            adg.avail_day_group = session.get(models.AvailDayGroup, new_parent_id)
            session.flush()
            return schemas.AvailDayGroupShow.model_validate(adg)

    @classmethod
    def delete(cls, avail_day_group_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.AvailDayGroup, avail_day_group_id))


class RequiredAvailDayGroups:
    @classmethod
    def get(cls, required_avail_day_groups_id: UUID):
        with get_session() as session:
            obj = session.get(models.RequiredAvailDayGroups, required_avail_day_groups_id)
            return schemas.RequiredAvailDayGroups.model_validate(obj) if obj else None

    @classmethod
    def get_from__avail_day_group(cls, avail_day_group_id: UUID) -> schemas.RequiredAvailDayGroups | None:
        with get_session() as session:
            obj = session.exec(select(models.RequiredAvailDayGroups).where(
                models.RequiredAvailDayGroups.avail_day_group_id == avail_day_group_id)).first()
            return schemas.RequiredAvailDayGroups.model_validate(obj) if obj else None

    @classmethod
    def create(cls, num_avail_day_groups: int, avail_day_group_id: UUID,
               location_of_work_ids: list[UUID], undo_id: UUID = None) -> schemas.RequiredAvailDayGroups:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(avail_day_group=session.get(models.AvailDayGroup, avail_day_group_id),
                          num_avail_day_groups=num_avail_day_groups)
            if undo_id:
                kwargs['id'] = undo_id
            obj = models.RequiredAvailDayGroups(**kwargs)
            session.add(obj)
            session.flush()
            for loc_id in location_of_work_ids:
                obj.locations_of_work.append(session.get(models.LocationOfWork, loc_id))
            session.flush()
            return schemas.RequiredAvailDayGroups.model_validate(obj)

    @classmethod
    def update(cls, required_avail_day_groups_id: UUID, num_avail_day_groups: int, location_of_work_ids: list[UUID]):
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.RequiredAvailDayGroups, required_avail_day_groups_id)
            obj.num_avail_day_groups = num_avail_day_groups
            obj.locations_of_work.clear()
            for loc_id in location_of_work_ids:
                obj.locations_of_work.append(session.get(models.LocationOfWork, loc_id))
            session.flush()
            return schemas.RequiredAvailDayGroups.model_validate(obj)

    @classmethod
    def delete(cls, required_avail_day_groups_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.RequiredAvailDayGroups, required_avail_day_groups_id))


class AvailDay:
    @classmethod
    def get(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        with get_session() as session:
            return schemas.AvailDayShow.model_validate(session.get(models.AvailDay, avail_day_id))

    @classmethod
    def get_batch(cls, avail_day_ids: list[UUID]) -> dict[UUID, schemas.AvailDayShow]:
        if not avail_day_ids:
            return {}
        with get_session() as session:
            ads = session.exec(select(models.AvailDay).where(models.AvailDay.id.in_(avail_day_ids))).all()
            return {ad.id: schemas.AvailDayShow.model_validate(ad) for ad in ads}

    @classmethod
    def get_batch_minimal(cls, avail_day_ids: list[UUID]) -> dict[UUID, schemas.AvailDaySolverMinimal]:
        if not avail_day_ids:
            return {}
        with get_session() as session:
            ads = session.exec(select(models.AvailDay).where(models.AvailDay.id.in_(avail_day_ids))).all()
            return {ad.id: schemas.AvailDaySolverMinimal.model_validate(ad) for ad in ads}

    @classmethod
    def get_from__actor_pp_date_tod(cls, actor_plan_period_id: UUID, date: datetime.date,
                                    time_of_day_id) -> schemas.AvailDayShow | None:
        with get_session() as session:
            ad = session.exec(select(models.AvailDay).where(
                models.AvailDay.actor_plan_period_id == actor_plan_period_id,
                models.AvailDay.date == date, models.AvailDay.time_of_day_id == time_of_day_id,
                models.AvailDay.prep_delete.is_(None))).first()
            return schemas.AvailDayShow.model_validate(ad) if ad else None

    @classmethod
    def get_from__actor_pp_date(cls, actor_plan_period_id: UUID, date: datetime.date) -> list[schemas.AvailDayShow]:
        with get_session() as session:
            ads = session.exec(select(models.AvailDay).where(
                models.AvailDay.actor_plan_period_id == actor_plan_period_id,
                models.AvailDay.date == date)).all()
            return [schemas.AvailDayShow.model_validate(ad) for ad in ads]

    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.AvailDayShow]:
        with get_session() as session:
            ads = session.exec(select(models.AvailDay).join(models.ActorPlanPeriod)
                               .where(models.ActorPlanPeriod.plan_period_id == plan_period_id)).all()
            return [schemas.AvailDayShow.model_validate(ad) for ad in ads]

    @classmethod
    def get_all_from__actor_plan_period(cls, actor_plan_period_id: UUID) -> list[schemas.AvailDayShow]:
        with get_session() as session:
            ads = session.exec(select(models.AvailDay).where(
                models.AvailDay.actor_plan_period_id == actor_plan_period_id)).all()
            return [schemas.AvailDayShow.model_validate(ad) for ad in ads]

    @classmethod
    def get_all_from__plan_period_date(cls, plan_period_id: UUID, date: datetime.date) -> list[schemas.AvailDayShow]:
        with get_session() as session:
            ads = session.exec(select(models.AvailDay).join(models.ActorPlanPeriod)
                               .where(models.ActorPlanPeriod.plan_period_id == plan_period_id,
                                      models.AvailDay.date == date)).all()
            return [schemas.AvailDayShow.model_validate(ad) for ad in ads]

    @classmethod
    def get_all_from__plan_period__date__time_of_day__location_prefs(
            cls, plan_period_id: UUID, date: datetime.date, time_of_day_index: int,
            location_of_work_ids: set[UUID]) -> list[schemas.AvailDayShow]:
        with get_session() as session:
            ads = session.exec(
                select(models.AvailDay).join(models.ActorPlanPeriod)
                .join(models.TimeOfDay, models.AvailDay.time_of_day_id == models.TimeOfDay.id)
                .join(models.TimeOfDayEnum)
                .where(models.ActorPlanPeriod.plan_period_id == plan_period_id,
                       models.AvailDay.date == date,
                       models.TimeOfDayEnum.time_index == time_of_day_index)
            ).all()
            filtered = []
            for ad in ads:
                dominated = True
                for loc_id in location_of_work_ids:
                    blocked = any(p.location_of_work_id == loc_id and p.score == 0
                                  for p in ad.actor_location_prefs_defaults)
                    if not blocked:
                        dominated = False
                        break
                if not dominated:
                    filtered.append(schemas.AvailDayShow.model_validate(ad))
            return filtered

    @classmethod
    def get_from__avail_day_group(cls, avail_day_group_id) -> schemas.AvailDayShow | None:
        with get_session() as session:
            adg = session.get(models.AvailDayGroup, avail_day_group_id)
            return schemas.AvailDayShow.model_validate(adg.avail_day) if adg.avail_day else None

    @classmethod
    def create(cls, avail_day: schemas.AvailDayCreate) -> schemas.AvailDayShow:
        """Erstellt AvailDay mit zugehöriger AvailDayGroup (inlined)."""
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, avail_day.actor_plan_period.id)
            master_adg = app.avail_day_group
            # AvailDayGroup erstellen (inlined)
            adg = models.AvailDayGroup(avail_day_group=master_adg)
            session.add(adg)
            session.flush()
            ad = models.AvailDay(date=avail_day.date,
                                 time_of_day=session.get(models.TimeOfDay, avail_day.time_of_day.id),
                                 avail_day_group=adg, actor_plan_period=app)
            session.add(ad)
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def update_time_of_day(cls, avail_day_id: UUID, new_time_of_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.time_of_day = session.get(models.TimeOfDay, new_time_of_day_id)
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def update_time_of_days(cls, avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.time_of_days.clear()
            for t in time_of_days:
                ad.time_of_days.append(session.get(models.TimeOfDay, t.id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def delete(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            deleted = schemas.AvailDayShow.model_validate(ad)
            adg = ad.avail_day_group
            session.delete(ad)
            session.flush()
            session.delete(adg)
            return deleted

    @classmethod
    def put_in_comb_loc_possible(cls, avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def put_in_comb_loc_possibles(cls, avail_day_id: UUID, comb_loc_possible_ids: list[UUID]) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            for cid in comb_loc_possible_ids:
                ad.combination_locations_possibles.append(session.get(models.CombinationLocationsPossible, cid))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def remove_comb_loc_possible(cls, avail_day_id: UUID, comb_loc_possible_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.combination_locations_possibles.remove(session.get(models.CombinationLocationsPossible, comb_loc_possible_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def clear_comb_loc_possibles(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.combination_locations_possibles.clear()
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def put_in_location_pref(cls, avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, actor_loc_pref_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def put_in_location_prefs(cls, avail_day_id: UUID, actor_loc_pref_ids: list[UUID]) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            for pid in actor_loc_pref_ids:
                ad.actor_location_prefs_defaults.append(session.get(models.ActorLocationPref, pid))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def remove_location_pref(cls, avail_day_id: UUID, actor_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.actor_location_prefs_defaults.remove(session.get(models.ActorLocationPref, actor_loc_pref_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def clear_location_prefs(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.actor_location_prefs_defaults.clear()
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def put_in_partner_location_pref(cls, avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def put_in_partner_location_prefs(cls, avail_day_id: UUID, actor_partner_loc_pref_ids: list[UUID]) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            for pid in actor_partner_loc_pref_ids:
                ad.actor_partner_location_prefs_defaults.append(session.get(models.ActorPartnerLocationPref, pid))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def remove_partner_location_pref(cls, avail_day_id: UUID, actor_partner_loc_pref_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.actor_partner_location_prefs_defaults.remove(session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def clear_partner_location_prefs(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.actor_partner_location_prefs_defaults.clear()
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(cls, actor_plan_period_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            defaults = list(app.actor_partner_location_prefs_defaults)
            for ad in app.avail_days:
                ad.actor_partner_location_prefs_defaults.clear()
                ad.actor_partner_location_prefs_defaults.extend(defaults)

    @classmethod
    def reset_all_avail_days_location_prefs_of_actor_plan_period_to_defaults(cls, actor_plan_period_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            defaults = list(app.actor_location_prefs_defaults)
            for ad in app.avail_days:
                ad.actor_location_prefs_defaults.clear()
                ad.actor_location_prefs_defaults.extend(defaults)

    @classmethod
    def reset_all_avail_days_comb_loc_possibles_of_actor_plan_period_to_defaults(cls, actor_plan_period_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            defaults = list(app.combination_locations_possibles)
            for ad in app.avail_days:
                ad.combination_locations_possibles.clear()
                ad.combination_locations_possibles.extend(defaults)

    @classmethod
    def add_skill(cls, avail_day_id: UUID, skill_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.skills.append(session.get(models.Skill, skill_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def remove_skill(cls, avail_day_id: UUID, skill_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.skills.remove(session.get(models.Skill, skill_id))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def clear_skills(cls, avail_day_id: UUID) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            ad.skills.clear()
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def put_in_skills(cls, avail_day_id: UUID, skill_ids: list[UUID]) -> schemas.AvailDayShow:
        log_function_info(cls)
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            for sid in skill_ids:
                ad.skills.append(session.get(models.Skill, sid))
            session.flush()
            return schemas.AvailDayShow.model_validate(ad)

    @classmethod
    def clear_all_skills_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            for ad in app.avail_days:
                ad.skills.clear()

    @classmethod
    def reset_all_skills_of_actor_plan_period_to_person_defaults(cls, actor_plan_period_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            person_skills = list(app.person.skills)
            for ad in app.avail_days:
                ad.skills.clear()
                ad.skills.extend(person_skills)

    @classmethod
    def get_skill_ids_per_avail_day_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            return {ad.id: [s.id for s in ad.skills] for ad in app.avail_days}


# ═══════════════════════════════════════════════════════════════════════════════
# Verbleibende Entities (CombLoc, Prefs, Skill, SkillGroup, Plan, Appointment)
# ═══════════════════════════════════════════════════════════════════════════════


class CombinationLocationsPossible:
    @classmethod
    def create(cls, comb_loc_poss: schemas.CombinationLocationsPossibleCreate) -> schemas.CombinationLocationsPossibleShow:
        log_function_info(cls)
        with get_session() as session:
            obj = models.CombinationLocationsPossible(
                project=session.get(models.Project, comb_loc_poss.project.id),
                time_span_between=comb_loc_poss.time_span_between)
            session.add(obj)
            session.flush()
            for loc in comb_loc_poss.locations_of_work:
                obj.locations_of_work.append(session.get(models.LocationOfWork, loc.id))
            session.flush()
            return schemas.CombinationLocationsPossibleShow.model_validate(obj)

    @classmethod
    def delete(cls, comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.CombinationLocationsPossible, comb_loc_poss_id)
            obj.prep_delete = _utcnow()
            session.flush()
            return schemas.CombinationLocationsPossibleShow.model_validate(obj)

    @classmethod
    def undelete(cls, comb_loc_poss_id: UUID) -> schemas.CombinationLocationsPossibleShow:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.CombinationLocationsPossible, comb_loc_poss_id)
            obj.prep_delete = None
            session.flush()
            return schemas.CombinationLocationsPossibleShow.model_validate(obj)

    @classmethod
    def get_comb_loc_poss_ids_per_avail_day_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            return {ad.id: [c.id for c in ad.combination_locations_possibles] for ad in app.avail_days}


class ActorLocationPref:
    @classmethod
    def create(cls, actor_loc_pref: schemas.ActorLocationPrefCreate) -> schemas.ActorLocationPrefShow:
        log_function_info(cls)
        with get_session() as session:
            obj = models.ActorLocationPref(
                score=actor_loc_pref.score,
                project=session.get(models.Project, actor_loc_pref.person.project.id),
                person=session.get(models.Person, actor_loc_pref.person.id),
                location_of_work=session.get(models.LocationOfWork, actor_loc_pref.location_of_work.id))
            session.add(obj)
            session.flush()
            return schemas.ActorLocationPrefShow.model_validate(obj)

    @classmethod
    def delete(cls, actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.ActorLocationPref, actor_loc_pref_id)
            obj.prep_delete = _utcnow()
            session.flush()
            return schemas.ActorLocationPrefShow.model_validate(obj)

    @classmethod
    def undelete(cls, actor_loc_pref_id: UUID) -> schemas.ActorLocationPrefShow:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.ActorLocationPref, actor_loc_pref_id)
            obj.prep_delete = None
            session.flush()
            return schemas.ActorLocationPrefShow.model_validate(obj)

    @classmethod
    def delete_unused(cls, project_id: UUID) -> list[UUID]:
        log_function_info(cls)
        with get_session() as session:
            prefs = session.exec(select(models.ActorLocationPref).where(
                models.ActorLocationPref.project_id == project_id)).all()
            deleted_ids = []
            for p in prefs:
                if p.prep_delete:
                    continue
                if not p.actor_plan_periods_defaults and not p.avail_days_defaults and not p.person_default:
                    p.prep_delete = _utcnow()
                    deleted_ids.append(p.id)
            return deleted_ids

    @classmethod
    def delete_prep_deletes(cls, project_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            prefs = session.exec(select(models.ActorLocationPref).where(
                models.ActorLocationPref.project_id == project_id)).all()
            for p in prefs:
                if p.prep_delete:
                    session.delete(p)

    @classmethod
    def get_loc_pref_ids_per_avail_day_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            return {ad.id: [p.id for p in ad.actor_location_prefs_defaults] for ad in app.avail_days}


class ActorPartnerLocationPref:
    @classmethod
    def get(cls, actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        with get_session() as session:
            return schemas.ActorPartnerLocationPrefShow.model_validate(
                session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id))

    @classmethod
    def get_all_from__avail_day(cls, avail_day_id: UUID) -> list[schemas.ActorPartnerLocationPrefShow]:
        with get_session() as session:
            ad = session.get(models.AvailDay, avail_day_id)
            return [schemas.ActorPartnerLocationPrefShow.model_validate(p) for p in ad.actor_partner_location_prefs_defaults]

    @classmethod
    def get_ids_per_avail_day_of_actor_plan_period(cls, actor_plan_period_id: UUID) -> dict[UUID, list[UUID]]:
        with get_session() as session:
            app = session.get(models.ActorPlanPeriod, actor_plan_period_id)
            return {ad.id: [p.id for p in ad.actor_partner_location_prefs_defaults] for ad in app.avail_days}

    @classmethod
    def create(cls, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefCreate) -> schemas.ActorPartnerLocationPrefShow:
        log_function_info(cls)
        with get_session() as session:
            obj = models.ActorPartnerLocationPref(
                score=actor_partner_loc_pref.score,
                person=session.get(models.Person, actor_partner_loc_pref.person.id),
                partner=session.get(models.Person, actor_partner_loc_pref.partner.id),
                location_of_work=session.get(models.LocationOfWork, actor_partner_loc_pref.location_of_work.id))
            session.add(obj)
            session.flush()
            return schemas.ActorPartnerLocationPrefShow.model_validate(obj)

    @classmethod
    def modify(cls, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow) -> schemas.ActorPartnerLocationPrefShow:
        with get_session() as session:
            obj = session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref.id)
            obj.person_default = (session.get(models.Person, actor_partner_loc_pref.person_default.id)
                                  if actor_partner_loc_pref.person_default else None)
            obj.actor_plan_periods_defaults.clear()
            for app in actor_partner_loc_pref.actor_plan_periods_defaults:
                obj.actor_plan_periods_defaults.append(session.get(models.ActorPlanPeriod, app.id))
            obj.avail_days_defaults.clear()
            for ad in actor_partner_loc_pref.avail_days_defaults:
                obj.avail_days_defaults.append(session.get(models.AvailDay, ad.id))
            session.flush()
            return schemas.ActorPartnerLocationPrefShow.model_validate(obj)

    @classmethod
    def delete(cls, actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id)
            obj.prep_delete = _utcnow()
            session.flush()
            return schemas.ActorPartnerLocationPrefShow.model_validate(obj)

    @classmethod
    def undelete(cls, actor_partner_loc_pref_id: UUID) -> schemas.ActorPartnerLocationPrefShow:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.ActorPartnerLocationPref, actor_partner_loc_pref_id)
            obj.prep_delete = None
            session.flush()
            return schemas.ActorPartnerLocationPrefShow.model_validate(obj)

    @classmethod
    def delete_unused(cls, person_id: UUID) -> list[UUID]:
        log_function_info(cls)
        with get_session() as session:
            prefs = session.exec(select(models.ActorPartnerLocationPref).where(
                models.ActorPartnerLocationPref.person_id == person_id)).all()
            deleted_ids = []
            for p in prefs:
                if p.prep_delete:
                    continue
                if not p.actor_plan_periods_defaults and not p.avail_days_defaults and not p.person_default:
                    p.prep_delete = _utcnow()
                    deleted_ids.append(p.id)
            return deleted_ids

    @classmethod
    def delete_prep_deletes(cls, person_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            prefs = session.exec(select(models.ActorPartnerLocationPref).where(
                models.ActorPartnerLocationPref.person_id == person_id)).all()
            for p in prefs:
                if p.prep_delete:
                    session.delete(p)


class Skill:
    @classmethod
    def create(cls, skill: schemas.SkillCreate, skill_id: UUID = None) -> schemas.Skill:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(name=skill.name, notes=skill.notes, project=session.get(models.Project, skill.project_id))
            if skill_id:
                kwargs['id'] = skill_id
            obj = models.Skill(**kwargs)
            session.add(obj)
            session.flush()
            return schemas.Skill.model_validate(obj)

    @classmethod
    def get(cls, skill_id: UUID) -> schemas.Skill:
        with get_session() as session:
            return schemas.Skill.model_validate(session.get(models.Skill, skill_id))

    @classmethod
    def get_all_from__person(cls, person_id: UUID) -> list[schemas.Skill]:
        with get_session() as session:
            return [schemas.Skill.model_validate(s) for s in session.get(models.Person, person_id).skills]

    @classmethod
    def get_all_from__project(cls, project_id: UUID) -> list[schemas.Skill]:
        with get_session() as session:
            return [schemas.Skill.model_validate(s) for s in session.get(models.Project, project_id).skills]

    @classmethod
    def update(cls, skill: schemas.SkillUpdate) -> schemas.Skill:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.Skill, skill.id)
            obj.name = skill.name
            obj.notes = skill.notes
            session.flush()
            return schemas.Skill.model_validate(obj)

    @classmethod
    def prep_delete(cls, skill_id: UUID, prep_delete: datetime.datetime = None) -> schemas.Skill:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.Skill, skill_id)
            obj.prep_delete = prep_delete or _utcnow()
            session.flush()
            return schemas.Skill.model_validate(obj)

    @classmethod
    def undelete(cls, skill_id: UUID) -> schemas.Skill:
        log_function_info(cls)
        with get_session() as session:
            obj = session.get(models.Skill, skill_id)
            obj.prep_delete = None
            session.flush()
            return schemas.Skill.model_validate(obj)

    @classmethod
    def delete_prep_deletes_from__project(cls, project_id: UUID) -> None:
        log_function_info(cls)
        with get_session() as session:
            skills = session.exec(select(models.Skill).where(
                models.Skill.project_id == project_id, models.Skill.prep_delete.isnot(None))).all()
            for s in skills:
                session.delete(s)

    @classmethod
    def delete(cls, skill_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.Skill, skill_id))

    @classmethod
    def is_used(cls, skill_id: UUID) -> bool:
        with get_session() as session:
            s = session.get(models.Skill, skill_id)
            return bool(s.persons or s.avail_days or s.skill_groups)


class SkillGroup:
    @classmethod
    def get(cls, skill_group_id: UUID) -> schemas.SkillGroupShow:
        with get_session() as session:
            return schemas.SkillGroupShow.model_validate(session.get(models.SkillGroup, skill_group_id))

    @classmethod
    def get_all_from__location_of_work(cls, location_of_work_id: UUID) -> list[schemas.SkillGroupShow]:
        with get_session() as session:
            return [schemas.SkillGroupShow.model_validate(sg)
                    for sg in session.get(models.LocationOfWork, location_of_work_id).skill_groups]

    @classmethod
    def get_all_from__event(cls, event_id: UUID) -> list[schemas.SkillGroupShow]:
        with get_session() as session:
            return [schemas.SkillGroupShow.model_validate(sg)
                    for sg in session.get(models.Event, event_id).skill_groups]

    @classmethod
    def create(cls, skill_group: schemas.SkillGroupCreate, skill_group_id: UUID = None) -> schemas.SkillGroupShow:
        log_function_info(cls)
        with get_session() as session:
            kwargs = dict(skill=session.get(models.Skill, skill_group.skill_id), nr_actors=skill_group.nr_persons)
            if skill_group_id:
                kwargs['id'] = skill_group_id
            sg = models.SkillGroup(**kwargs)
            session.add(sg)
            session.flush()
            return schemas.SkillGroupShow.model_validate(sg)

    @classmethod
    def delete(cls, skill_group_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            session.delete(session.get(models.SkillGroup, skill_group_id))

    @classmethod
    def update(cls, skill_group: schemas.SkillGroupUpdate) -> schemas.SkillGroupShow:
        log_function_info(cls)
        with get_session() as session:
            sg = session.get(models.SkillGroup, skill_group.id)
            sg.skill = session.get(models.Skill, skill_group.skill_id)
            sg.nr_actors = skill_group.nr_persons
            session.flush()
            return schemas.SkillGroupShow.model_validate(sg)


class Plan:
    @classmethod
    def create(cls, plan_period_id: UUID, name: str, notes: str = '') -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = models.Plan(name=name, plan_period=session.get(models.PlanPeriod, plan_period_id), notes=notes)
            session.add(plan)
            session.flush()
            return schemas.PlanShow.model_validate(plan)

    @classmethod
    def update_notes(cls, plan_id: UUID, notes: str) -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            plan.notes = notes
            session.flush()
            return schemas.PlanShow.model_validate(plan)

    @classmethod
    def delete(cls, plan_id: UUID) -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            plan.prep_delete = _utcnow()
            session.flush()
            return schemas.PlanShow.model_validate(plan)

    @classmethod
    def undelete(cls, plan_id: UUID) -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            plan.prep_delete = None
            session.flush()
            return schemas.PlanShow.model_validate(plan)

    @classmethod
    def get(cls, plan_id: UUID, small: bool = False) -> schemas.PlanShow | schemas.Plan:
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            return schemas.Plan.model_validate(plan) if small else schemas.PlanShow.model_validate(plan)

    @classmethod
    def get_from__name(cls, plan_name: str) -> schemas.PlanShow | None:
        with get_session() as session:
            plan = session.exec(select(models.Plan).where(models.Plan.name == plan_name)).first()
            return schemas.PlanShow.model_validate(plan) if plan else None

    @classmethod
    def get_all_from__team(cls, team_id: UUID,
                           minimal: bool = False, inclusive_prep_deleted=False) -> list[schemas.PlanShow] | dict[str, UUID]:
        with get_session() as session:
            if not minimal:
                plans = session.exec(select(models.Plan).join(models.PlanPeriod)
                                     .where(models.PlanPeriod.team_id == team_id)).all()
                return [schemas.PlanShow.model_validate(p) for p in plans]
            stmt = select(models.Plan).join(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)
            if not inclusive_prep_deleted:
                stmt = stmt.where(models.Plan.prep_delete.is_(None))
            stmt = stmt.order_by(models.PlanPeriod.start, models.Plan.name)
            plans = session.exec(stmt).all()
            return {p.name: p.id for p in plans}

    @classmethod
    def get_prep_deleted_from__team(cls, team_id: UUID) -> list[UUID]:
        with get_session() as session:
            plans = session.exec(select(models.Plan).join(models.PlanPeriod)
                                 .where(models.PlanPeriod.team_id == team_id,
                                        models.Plan.prep_delete.isnot(None))).all()
            return [p.id for p in plans]

    @classmethod
    def get_all_from__plan_period(cls, plan_period_id: UUID) -> list[schemas.PlanShow]:
        with get_session() as session:
            plans = session.exec(select(models.Plan).where(models.Plan.plan_period_id == plan_period_id)).all()
            return [schemas.PlanShow.model_validate(p) for p in plans]

    @classmethod
    def get_all_from__plan_period_minimal(cls, plan_period_id: UUID) -> dict[str, UUID]:
        with get_session() as session:
            plans = session.exec(select(models.Plan).where(
                models.Plan.plan_period_id == plan_period_id, models.Plan.prep_delete.is_(None))).all()
            return {p.name: p.id for p in plans}

    @classmethod
    def get_location_columns(cls, plan_id: UUID):
        with get_session() as session:
            return session.get(models.Plan, plan_id).location_columns

    @classmethod
    def delete_prep_deleted(cls, plan_id):
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            if not plan.prep_delete:
                raise LookupError(f'Plan {plan.name} ist not marked to delete.')
            session.delete(plan)

    @classmethod
    def delete_prep_deletes_from__team(cls, team_id: UUID):
        log_function_info(cls)
        with get_session() as session:
            plans = session.exec(select(models.Plan).join(models.PlanPeriod)
                                 .where(models.PlanPeriod.team_id == team_id,
                                        models.Plan.prep_delete.isnot(None))).all()
            for p in plans:
                session.delete(p)

    @classmethod
    def update_name(cls, plan_id: UUID, new_name: str) -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            plan.name = new_name
            session.flush()
            return schemas.PlanShow.model_validate(plan)

    @classmethod
    def update_location_columns(cls, plan_id: UUID, location_columns: str) -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            plan.location_columns = location_columns
            session.flush()
            return schemas.PlanShow.model_validate(plan)

    @classmethod
    def put_in_excel_settings(cls, plan_id: UUID, excel_settings_id: UUID) -> schemas.PlanShow:
        log_function_info(cls)
        with get_session() as session:
            plan = session.get(models.Plan, plan_id)
            plan.excel_export_settings = session.get(models.ExcelExportSettings, excel_settings_id)
            session.flush()
            return schemas.PlanShow.model_validate(plan)


class Appointment:
    @classmethod
    def get(cls, appointment_id: UUID) -> schemas.AppointmentShow:
        with get_session() as session:
            return schemas.AppointmentShow.model_validate(session.get(models.Appointment, appointment_id))

    @classmethod
    def create(cls, appointment: schemas.AppointmentCreate, plan_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = models.Appointment(
                event=session.get(models.Event, appointment.event.id),
                plan=session.get(models.Plan, plan_id), notes=appointment.notes)
            session.add(app)
            session.flush()
            for ad in appointment.avail_days:
                app.avail_days.append(session.get(models.AvailDay, ad.id))
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def update_avail_days(cls, appointment_id: UUID, avail_day_ids: list[UUID]) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.Appointment, appointment_id)
            app.avail_days.clear()
            for aid in avail_day_ids:
                app.avail_days.append(session.get(models.AvailDay, aid))
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def update_notes(cls, appointment_id: UUID, notes: str) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.Appointment, appointment_id)
            app.notes = notes
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def update_guests(cls, appointment_id: UUID, guests: list[str]) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.Appointment, appointment_id)
            app.guests = json.dumps(guests)
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def update_event(cls, appointment_id: UUID, event_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.Appointment, appointment_id)
            app.event = session.get(models.Event, event_id)
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def delete(cls, appointment_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.Appointment, appointment_id)
            app.prep_delete = _utcnow()
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def undelete(cls, appointment_id: UUID) -> schemas.AppointmentShow:
        log_function_info(cls)
        with get_session() as session:
            app = session.get(models.Appointment, appointment_id)
            app.prep_delete = None
            session.flush()
            return schemas.AppointmentShow.model_validate(app)

    @classmethod
    def get_plan_names_from__event(cls, event_id: UUID) -> dict[str, int]:
        with get_session() as session:
            event = session.get(models.Event, event_id)
            if not event:
                return {}
            plan_counts: dict[str, int] = {}
            for app in event.appointments:
                if not app.prep_delete and not app.plan.prep_delete:
                    plan_counts[app.plan.name] = plan_counts.get(app.plan.name, 0) + 1
            return plan_counts
