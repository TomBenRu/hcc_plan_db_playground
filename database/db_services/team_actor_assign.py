"""Service-Funktionen für TeamActorAssign (Akteur-Team-Zuweisung).

Speichert, in welchem Zeitraum (start bis end) eine Person einem Team angehört.
Abfragen berücksichtigen datumsbezogene Überschneidungen (mit `or_`-Filter auf
`end IS NULL`). `get_at__date` gibt die aktive Zuweisung zu einem konkreten Datum
zurück und liefert `None`, wenn keine gültige Zuweisung existiert.
"""
import datetime
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(team_actor_assign_id: UUID) -> schemas.TeamActorAssignShow:
    with get_session() as session:
        return schemas.TeamActorAssignShow.model_validate(session.get(models.TeamActorAssign, team_actor_assign_id))


def get_at__date(person_id: UUID, date: datetime.date | None) -> schemas.TeamActorAssignShow | None:
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


def get_all_between_dates(person_id: UUID, team_id: UUID,
                          date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamActorAssignShow]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamActorAssign).where(
            models.TeamActorAssign.team_id == team_id, models.TeamActorAssign.person_id == person_id,
            models.TeamActorAssign.start <= date_end,
            or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end >= date_start))).all()
        return [schemas.TeamActorAssignShow.model_validate(a) for a in assigns]


def get_all_actor_ids_between_dates(team_id: UUID,
                                    date_start: datetime.date, date_end: datetime.date) -> set[UUID]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamActorAssign).where(
            models.TeamActorAssign.team_id == team_id, models.TeamActorAssign.start <= date_end,
            or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date_start))).all()
        return {a.person_id for a in assigns}


def get_all_at__date(date: datetime.date, team_id: UUID) -> list[schemas.TeamActorAssignShow]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamActorAssign).where(
            models.TeamActorAssign.team_id == team_id, models.TeamActorAssign.start <= date,
            or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date))).all()
        return [schemas.TeamActorAssignShow.model_validate(a) for a in assigns]


def get_all_teams_at_date(person_id: UUID, date: datetime.date,
                          only_uuids: bool = False) -> list[schemas.TeamShow] | list[UUID]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamActorAssign).where(
            models.TeamActorAssign.person_id == person_id, models.TeamActorAssign.start <= date,
            or_(models.TeamActorAssign.end.is_(None), models.TeamActorAssign.end > date))).all()
        if only_uuids:
            return [a.team_id for a in assigns]
        return [schemas.TeamShow.model_validate(a.team) for a in assigns]


def create(team_actor_assign: schemas.TeamActorAssignCreate,
           assign_id: UUID | None = None) -> schemas.TeamActorAssignShow:
    log_function_info()
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


def set_end_date(team_actor_assign_id: UUID, end_date: datetime.date | None = None):
    log_function_info()
    with get_session() as session:
        session.get(models.TeamActorAssign, team_actor_assign_id).end = end_date


def delete(team_actor_assign_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.TeamActorAssign, team_actor_assign_id))