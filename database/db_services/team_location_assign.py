"""Service-Funktionen für TeamLocationAssign (Standort-Team-Zuweisung).

Speichert, in welchem Zeitraum (start bis end) ein Arbeitsort einem Team
zugeordnet ist. Analog zu TeamActorAssign mit datumsbezogenen Überschneidungs-
abfragen. Wird u. a. genutzt, um in `location_of_work.get_all_possible_from__plan_period_minimal`
die für eine PlanPeriod relevanten Standorte zu ermitteln.
"""
import datetime
from uuid import UUID

from sqlalchemy import or_
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(team_location_assign_id: UUID) -> schemas.TeamLocationAssignShow:
    with get_session() as session:
        return schemas.TeamLocationAssignShow.model_validate(session.get(models.TeamLocationAssign, team_location_assign_id))


def get_at__date(location_id: UUID, date: datetime.date | None) -> schemas.TeamLocationAssignShow | None:
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


def get_all_of_location_between_dates(location_id: UUID, team_id: UUID,
                                      date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamLocationAssignShow]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamLocationAssign).where(
            models.TeamLocationAssign.team_id == team_id, models.TeamLocationAssign.location_of_work_id == location_id,
            models.TeamLocationAssign.start <= date_end,
            or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end >= date_start))).all()
        return [schemas.TeamLocationAssignShow.model_validate(a) for a in assigns]


def get_all_between_dates(team_id: UUID,
                          date_start: datetime.date, date_end: datetime.date) -> list[schemas.TeamLocationAssignShow]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamLocationAssign).where(
            models.TeamLocationAssign.team_id == team_id, models.TeamLocationAssign.start <= date_end,
            or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end >= date_start))).all()
        return [schemas.TeamLocationAssignShow.model_validate(a) for a in assigns]


def get_all_at__date(date: datetime.date, team_id: UUID) -> list[schemas.TeamLocationAssignShow]:
    with get_session() as session:
        assigns = session.exec(select(models.TeamLocationAssign).where(
            models.TeamLocationAssign.team_id == team_id, models.TeamLocationAssign.start <= date,
            or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > date))).all()
        return [schemas.TeamLocationAssignShow.model_validate(a) for a in assigns]


def create(team_location_assign: schemas.TeamLocationAssignCreate,
           assign_id: UUID | None = None) -> schemas.TeamLocationAssignShow:
    log_function_info()
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


def set_end_date(team_location_assign_id: UUID, end_date: datetime.date | None = None):
    log_function_info()
    with get_session() as session:
        session.get(models.TeamLocationAssign, team_location_assign_id).end = end_date


def delete(team_loc_assign_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.TeamLocationAssign, team_loc_assign_id))