"""Service-Funktionen für Plan (Dienstplan).

Ein Plan ist das Ergebnis eines Solver-Durchlaufs und gehört zu einer
PlanPeriod. Er enthält Appointments (Besetzungen), Notizen und
Excel-Exporteinstellungen. Soft-Delete erlaubt das vorübergehende Ausblenden;
`delete_prep_deletes_from__team` führt das endgültige Bereinigen durch.
Bietet mehrere Abfragevarianten (nach Team, PlanPeriod, Name) in minimaler
und vollständiger Form.
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info
from ._eager_loading import plan_show_options


def create(plan_period_id: UUID, name: str, notes: str = '') -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = models.Plan(name=name, plan_period=session.get(models.PlanPeriod, plan_period_id), notes=notes)
        session.add(plan)
        session.flush()
        return schemas.PlanShow.model_validate(plan)


def update_notes(plan_id: UUID, notes: str) -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        plan.notes = notes
        session.flush()
        return schemas.PlanShow.model_validate(plan)


def delete(plan_id: UUID) -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        plan.prep_delete = _utcnow()
        session.flush()
        return schemas.PlanShow.model_validate(plan)


def undelete(plan_id: UUID) -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        plan.prep_delete = None
        session.flush()
        return schemas.PlanShow.model_validate(plan)


def get(plan_id: UUID, small: bool = False) -> schemas.PlanShow | schemas.Plan:
    with get_session() as session:
        if small:
            return schemas.Plan.model_validate(session.get(models.Plan, plan_id))
        stmt = select(models.Plan).where(models.Plan.id == plan_id).options(*plan_show_options())
        plan = session.exec(stmt).unique().one()
        return schemas.PlanShow.model_validate(plan)


def get_from__name(plan_name: str, minimal: bool = False) -> schemas.PlanShow | schemas.Plan | None:
    """Sucht einen Plan nach Name.

    minimal=True gibt schemas.Plan (id, name, prep_delete) zurück ohne
    Eager-Loading der tiefen Relationen — für Existenzprüfungen und
    Operationen, die nur plan.id benötigen (~120ms statt ~2400ms).
    """
    with get_session() as session:
        stmt = select(models.Plan).where(models.Plan.name == plan_name)
        if not minimal:
            stmt = stmt.options(*plan_show_options())
            plan = session.exec(stmt).unique().first()
            return schemas.PlanShow.model_validate(plan) if plan else None
        plan = session.exec(stmt).first()
        return schemas.Plan.model_validate(plan) if plan else None


def get_all_from__team(team_id: UUID,
                       minimal: bool = False, inclusive_prep_deleted=False) -> list[schemas.PlanShow] | dict[str, UUID]:
    with get_session() as session:
        if not minimal:
            stmt = (select(models.Plan).join(models.PlanPeriod)
                    .where(models.PlanPeriod.team_id == team_id)
                    .options(*plan_show_options()))
            plans = session.exec(stmt).unique().all()
            return [schemas.PlanShow.model_validate(p) for p in plans]
        stmt = select(models.Plan).join(models.PlanPeriod).where(models.PlanPeriod.team_id == team_id)
        if not inclusive_prep_deleted:
            stmt = stmt.where(models.Plan.prep_delete.is_(None))
        stmt = stmt.order_by(models.PlanPeriod.start, models.Plan.name)
        plans = session.exec(stmt).all()
        return {p.name: p.id for p in plans}


def get_prep_deleted_from__team(team_id: UUID) -> list[UUID]:
    with get_session() as session:
        plans = session.exec(select(models.Plan).join(models.PlanPeriod)
                             .where(models.PlanPeriod.team_id == team_id,
                                    models.Plan.prep_delete.isnot(None))).all()
        return [p.id for p in plans]


def get_all_from__plan_period(plan_period_id: UUID) -> list[schemas.PlanShow]:
    with get_session() as session:
        stmt = (select(models.Plan).where(models.Plan.plan_period_id == plan_period_id)
                .options(*plan_show_options()))
        plans = session.exec(stmt).unique().all()
        return [schemas.PlanShow.model_validate(p) for p in plans]


def get_all_from__plan_period_minimal(plan_period_id: UUID) -> dict[str, UUID]:
    with get_session() as session:
        plans = session.exec(select(models.Plan).where(
            models.Plan.plan_period_id == plan_period_id, models.Plan.prep_delete.is_(None))).all()
        return {p.name: p.id for p in plans}


def get_location_columns(plan_id: UUID):
    with get_session() as session:
        return session.get(models.Plan, plan_id).location_columns


def delete_prep_deleted(plan_id):
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        if not plan.prep_delete:
            raise LookupError(f'Plan {plan.name} ist not marked to delete.')
        session.delete(plan)


def delete_prep_deletes_from__team(team_id: UUID):
    log_function_info()
    with get_session() as session:
        plans = session.exec(select(models.Plan).join(models.PlanPeriod)
                             .where(models.PlanPeriod.team_id == team_id,
                                    models.Plan.prep_delete.isnot(None))).all()
        for p in plans:
            session.delete(p)


def update_name(plan_id: UUID, new_name: str) -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        plan.name = new_name
        session.flush()
        return schemas.PlanShow.model_validate(plan)


def update_location_columns(plan_id: UUID, location_columns: str) -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        plan.location_columns = location_columns
        session.flush()
        return schemas.PlanShow.model_validate(plan)


def put_in_excel_settings(plan_id: UUID, excel_settings_id: UUID) -> schemas.PlanShow:
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        plan.excel_export_settings = session.get(models.ExcelExportSettings, excel_settings_id)
        session.flush()
        return schemas.PlanShow.model_validate(plan)