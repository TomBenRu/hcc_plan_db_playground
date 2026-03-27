"""Service-Funktionen für RequiredAvailDayGroups (Pflicht-Verfügbarkeitstag-Gruppen).

Verknüpft eine AvailDayGroup mit einer Mindestzahl benötigter Verfügbarkeitstage
und einer Liste von Arbeitsorten. Wird vom Solver verwendet, um standortbezogene
Mindestbesetzungsregeln abzubilden. Unterstützt einen optionalen `undo_id`-Parameter
für Undo-Operationen.
"""
import datetime
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(required_avail_day_groups_id: UUID):
    with get_session() as session:
        obj = session.get(models.RequiredAvailDayGroups, required_avail_day_groups_id)
        return schemas.RequiredAvailDayGroups.model_validate(obj) if obj else None


def get_all_from__avail_day_group_ids(
        ids: list[UUID]) -> dict[UUID, 'schemas.RequiredAvailDayGroups']:
    """Batch-Laden aller RequiredAvailDayGroups für eine Liste von AvailDayGroup-IDs.

    Ersetzt N einzelne get_from__avail_day_group()-Aufrufe durch eine einzige IN-Query.
    Gibt ein Dict {avail_day_group_id: RequiredAvailDayGroups} zurück;
    IDs ohne Eintrag sind nicht im Dict enthalten.
    """
    if not ids:
        return {}
    with get_session() as session:
        stmt = (
            select(models.RequiredAvailDayGroups)
            .where(models.RequiredAvailDayGroups.avail_day_group_id.in_(ids))
            .options(
                selectinload(models.RequiredAvailDayGroups.avail_day_group),
                selectinload(models.RequiredAvailDayGroups.locations_of_work),
            )
        )
        rows = session.exec(stmt).all()
        return {r.avail_day_group_id: schemas.RequiredAvailDayGroups.model_validate(r)
                for r in rows}


def get_from__avail_day_group(avail_day_group_id: UUID) -> schemas.RequiredAvailDayGroups | None:
    with get_session() as session:
        obj = session.exec(select(models.RequiredAvailDayGroups).where(
            models.RequiredAvailDayGroups.avail_day_group_id == avail_day_group_id)).first()
        return schemas.RequiredAvailDayGroups.model_validate(obj) if obj else None


def create(num_avail_day_groups: int, avail_day_group_id: UUID,
           location_of_work_ids: list[UUID], undo_id: UUID = None) -> schemas.RequiredAvailDayGroups:
    log_function_info()
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


def update(required_avail_day_groups_id: UUID, num_avail_day_groups: int, location_of_work_ids: list[UUID]):
    log_function_info()
    with get_session() as session:
        obj = session.get(models.RequiredAvailDayGroups, required_avail_day_groups_id)
        obj.num_avail_day_groups = num_avail_day_groups
        obj.locations_of_work.clear()
        for loc_id in location_of_work_ids:
            obj.locations_of_work.append(session.get(models.LocationOfWork, loc_id))
        session.flush()
        return schemas.RequiredAvailDayGroups.model_validate(obj)


def delete(required_avail_day_groups_id: UUID):
    log_function_info()
    with get_session() as session:
        session.delete(session.get(models.RequiredAvailDayGroups, required_avail_day_groups_id))