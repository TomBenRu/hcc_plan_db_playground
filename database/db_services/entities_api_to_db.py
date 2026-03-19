"""Synchronisations-Funktionen zwischen der externen Plan-API und der lokalen DB.

Dieses Modul übersetzt eingehende `schemas_plan_api`-Objekte (externe API-Daten)
in lokale SQLModel-Datenbankeinträge. Es wird verwendet, wenn Projekte, Personen,
Teams oder Planperioden über die API angelegt oder entfernt werden müssen.
Neu erstellte Personen erhalten dabei automatisch eine Platzhalter-Adresse.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, schemas_plan_api, models
from ..database import get_session
from ..models import _utcnow
from ..enums import Gender
from ._common import log_function_info


def create_project(project: schemas_plan_api.Project) -> schemas.ProjectShow:
    log_function_info()
    with get_session() as session:
        project_db = models.Project(id=project.id, name=project.name)
        session.add(project_db)
        session.flush()
        return schemas.ProjectShow.model_validate(project_db)


def delete_project(project_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, project_id)
        session.delete(project_db)


def create_person(person: schemas_plan_api.PersonShow) -> schemas.PersonShow:
    log_function_info()
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


def delete_person(person_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        person_db = session.get(models.Person, person_id)
        session.delete(person_db)


def create_team(team: schemas_plan_api.Team) -> schemas.TeamShow:
    log_function_info()
    with get_session() as session:
        project_db = session.get(models.Project, team.dispatcher.project.id)
        team_db = models.Team(id=team.id, name=team.name, project=project_db)
        session.add(team_db)
        session.flush()
        return schemas.TeamShow.model_validate(team_db)


def delete_team(team_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, team_id)
        session.delete(team_db)


def create_plan_period(plan_period: schemas_plan_api.PlanPeriod) -> schemas.PlanPeriodShow:
    log_function_info()
    with get_session() as session:
        team_db = session.get(models.Team, plan_period.team.id)
        plan_period_db = models.PlanPeriod(id=plan_period.id, start=plan_period.start, end=plan_period.end,
                                           deadline=plan_period.deadline, notes_for_employees=plan_period.notes,
                                           closed=plan_period.closed, remainder=True, team=team_db)
        session.add(plan_period_db)
        session.flush()
        return schemas.PlanPeriodShow.model_validate(plan_period_db)


def delete_plan_period(plan_period_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        plan_period_db = session.get(models.PlanPeriod, plan_period_id)
        session.delete(plan_period_db)