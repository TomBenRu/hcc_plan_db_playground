"""Schutz-Pruefungen vor Soft-/Hard-Delete von Teams, Standorten und Personen.

Soft-Delete: blockiert bei aktiver Plan-Period (``prep_delete IS NULL``).
Hard-Delete: blockiert bei JEDER Plan-Period — auch soft-deleted, auch closed —
damit ``Team.plan_periods cascade_delete=True`` nicht ungewollt historische
Plaene mitloescht.

``LocationPlanPeriod`` und ``ActorPlanPeriod`` haben kein ``prep_delete``-Feld:
Soft- und Hard-Delete fuer einen Standort/eine Person haben deshalb denselben
Schutz — die Funktion und ihr Alias decken beide Pfade ab.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlmodel import Session, select

from database.models import ActorPlanPeriod, LocationPlanPeriod, PlanPeriod


def count_active_plan_periods_for_team(session: Session, team_id: uuid.UUID) -> int:
    """Aktive PPs eines Teams (nicht soft-deletet)."""
    stmt = (
        select(func.count())
        .select_from(PlanPeriod)
        .where(
            PlanPeriod.team_id == team_id,
            PlanPeriod.prep_delete.is_(None),  # type: ignore[union-attr]
        )
    )
    return session.execute(stmt).scalar_one()


def count_any_plan_periods_for_team(session: Session, team_id: uuid.UUID) -> int:
    """JEDE PP des Teams — inkl. soft-deletete + closed. Schutz vor Hard-Delete-
    Cascade auf historische Plaene."""
    stmt = select(func.count()).select_from(PlanPeriod).where(PlanPeriod.team_id == team_id)
    return session.execute(stmt).scalar_one()


def count_active_location_plan_periods(
    session: Session, location_id: uuid.UUID
) -> int:
    """``LocationPlanPeriod`` hat kein ``prep_delete`` — alle existierenden
    zaehlen als 'aktiv'."""
    stmt = (
        select(func.count())
        .select_from(LocationPlanPeriod)
        .where(LocationPlanPeriod.location_of_work_id == location_id)
    )
    return session.execute(stmt).scalar_one()


count_any_location_plan_periods = count_active_location_plan_periods
"""Alias fuer Klarheit am Aufrufer — die Semantik ist identisch."""


def count_active_actor_plan_periods(session: Session, person_id: uuid.UUID) -> int:
    """``ActorPlanPeriod`` hat kein ``prep_delete`` — alle existierenden
    zaehlen als 'aktiv'. Spiegel zu ``count_active_location_plan_periods``."""
    stmt = (
        select(func.count())
        .select_from(ActorPlanPeriod)
        .where(ActorPlanPeriod.person_id == person_id)
    )
    return session.execute(stmt).scalar_one()


count_any_actor_plan_periods = count_active_actor_plan_periods
"""Alias fuer Klarheit am Aufrufer — die Semantik ist identisch."""
