"""Service-Funktionen für LocationOfWork (Arbeitsort).

Verwaltet Arbeitsorte innerhalb eines Projekts inklusive optionaler Adresse,
Tageszeiten, Standortkombinationen, fixed_cast und SkillGroups. Unterstützt
Soft-Delete. Spezielle Abfragen liefern alle zu einer PlanPeriod passenden
Orte (inkl. Zeitraumprüfung gegen TeamLocationAssign) für Dropdown-Auswahlen.
"""
import datetime
from uuid import UUID

from sqlalchemy import and_, or_
from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import location_of_work_show_options, team_location_assign_with_location_options


def get(location_id: UUID) -> schemas.LocationOfWorkShow:
    with get_session() as session:
        return schemas.LocationOfWorkShow.model_validate(session.get(models.LocationOfWork, location_id))


def get_many(location_ids: list[UUID]) -> dict[UUID, schemas.LocationOfWorkShow]:
    """Lädt mehrere Locations in einer einzigen Query.

    Ersetzt N einzelne get()-Aufrufe in get_weekdays_locations() durch
    eine Batch-Abfrage. Gibt {location_id: LocationOfWorkShow} zurück.
    """
    if not location_ids:
        return {}
    with get_session() as session:
        locs = session.exec(
            select(models.LocationOfWork).where(models.LocationOfWork.id.in_(location_ids))
        ).all()
        return {loc.id: schemas.LocationOfWorkShow.model_validate(loc) for loc in locs}


def exists_any_from__project(project_id: UUID) -> bool:
    """Gibt True zurück, wenn das Projekt mindestens einen aktiven Standort hat (kein model_validate)."""
    with get_session() as session:
        stmt = select(models.LocationOfWork).where(
            models.LocationOfWork.project_id == project_id,
            models.LocationOfWork.prep_delete.is_(None)
        ).limit(1)
        return session.exec(stmt).first() is not None


def get_all_from__project(project_id: UUID) -> list[schemas.LocationOfWorkShow]:
    with get_session() as session:
        stmt = (select(models.LocationOfWork)
                .where(
                    models.LocationOfWork.project_id == project_id,
                    models.LocationOfWork.prep_delete.is_(None),
                )
                .options(*location_of_work_show_options()))
        locs = session.exec(stmt).unique().all()
        return [schemas.LocationOfWorkShow.model_validate(loc) for loc in locs]


def get_all_from__plan_period_minimal(plan_period_id: UUID) -> dict['str', UUID]:
    with get_session() as session:
        pp_db = session.get(models.PlanPeriod, plan_period_id)
        return {lpp.location_of_work.name: lpp.location_of_work.id
                for lpp in pp_db.location_plan_periods if lpp.location_of_work.prep_delete is None}


def get_all_possible_from__plan_period_minimal(plan_period_id: UUID) -> dict['str', UUID]:
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


def get_all_locations_at_dates(team_id: UUID, dates: list[datetime.date]) -> list[schemas.LocationOfWork]:
    """Gibt alle Standorte zurück, die an mindestens einem der gegebenen Termine aktiv sind.

    Ersetzt N einzelne Queries (eine je Datum) durch einen einzigen OR-Query — die
    Bedingungen für alle Daten werden als OR-Klausel zusammengefasst.
    """
    if not dates:
        return []
    with get_session() as session:
        date_conditions = [
            and_(
                models.TeamLocationAssign.start <= d,
                or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > d)
            )
            for d in dates
        ]
        assigns = session.exec(
            select(models.TeamLocationAssign)
            .where(
                models.TeamLocationAssign.team_id == team_id,
                or_(*date_conditions)
            )
            .options(*team_location_assign_with_location_options())
        ).unique().all()
        seen: dict[UUID, models.LocationOfWork] = {}
        for tla in assigns:
            if tla.location_of_work_id not in seen:
                seen[tla.location_of_work_id] = tla.location_of_work
        return [schemas.LocationOfWork.model_validate(loc) for loc in seen.values()]


def get_locations_of_team_between_dates(team_id: UUID, date_start: datetime.date,
                                        date_end: datetime.date) -> list[schemas.LocationOfWork]:
    """Alle Standorte, die dem Team in [date_start, date_end] zugeordnet waren (Vereinigung, 1 Query).

    Ersetzt N einzelne get_locations_of_team_at_date()-Aufrufe durch einen einzigen
    Range-JOIN-Query — effizienter als get_all_locations_at_dates() bei vielen Tagen.
    """
    with get_session() as session:
        assigns = session.exec(
            select(models.TeamLocationAssign)
            .where(
                models.TeamLocationAssign.team_id == team_id,
                models.TeamLocationAssign.start <= date_end,
                or_(models.TeamLocationAssign.end.is_(None), models.TeamLocationAssign.end > date_start),
            )
            .options(*team_location_assign_with_location_options())
        ).unique().all()
        seen: set[UUID] = set()
        result: list[schemas.LocationOfWork] = []
        for tla in assigns:
            loc = tla.location_of_work
            if loc.id not in seen and (not loc.prep_delete or loc.prep_delete.date() > date_end):
                seen.add(loc.id)
                result.append(schemas.LocationOfWork.model_validate(loc))
    return sorted(result, key=lambda x: x.name + x.address.city)


def create(location: schemas.LocationOfWorkCreate, project_id: UUID) -> schemas.LocationOfWork:
    log_function_info()
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


def update(location_of_work: schemas.LocationOfWorkShow) -> schemas.LocationOfWorkShow:
    log_function_info()
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


def update_notes(location_of_work_id: UUID, notes: str) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_of_work_id)
        loc_db.notes = notes
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)


def put_in_time_of_day(location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_of_work_id)
        loc_db.time_of_days.append(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)


def remove_in_time_of_day(location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_of_work_id)
        loc_db.time_of_days.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)


def new_time_of_day_standard(location_of_work_id: UUID, time_of_day_id: UUID) -> tuple[schemas.LocationOfWorkShow, UUID | None]:
    log_function_info()
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


def remove_time_of_day_standard(location_of_work_id: UUID, time_of_day_id: UUID) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_of_work_id)
        if loc_db.time_of_day_standards:
            loc_db.time_of_day_standards.remove(session.get(models.TimeOfDay, time_of_day_id))
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)


def update_fixed_cast(location_of_work_id: UUID, fixed_cast: str,
                      fixed_cast_only_if_available: bool) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_of_work_id)
        loc_db.fixed_cast = fixed_cast
        loc_db.fixed_cast_only_if_available = fixed_cast_only_if_available
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)


def delete(location_id: UUID) -> schemas.LocationOfWork:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_id)
        loc_db.prep_delete = _utcnow()
        session.flush()
        return schemas.LocationOfWork.model_validate(loc_db)


def add_skill_group(location_id: UUID, skill_group_id: UUID) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_id)
        loc_db.skill_groups.append(session.get(models.SkillGroup, skill_group_id))
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)


def remove_skill_group(location_id: UUID, skill_group_id: UUID) -> schemas.LocationOfWorkShow:
    log_function_info()
    with get_session() as session:
        loc_db = session.get(models.LocationOfWork, location_id)
        loc_db.skill_groups.remove(session.get(models.SkillGroup, skill_group_id))
        session.flush()
        return schemas.LocationOfWorkShow.model_validate(loc_db)