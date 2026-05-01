"""Service-Layer für persönliche Einstellungen — aktuell nur Location-Farben."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import ActorPlanPeriod, Address, LocationOfWork, LocationPlanPeriod, PlanPeriod, Team
from web_api.common import location_display_name
from web_api.models.web_models import UserLocationColor, WebUser
from web_api.palette import default_location_color


@dataclass
class LocationColorRow:
    """Eine Zeile der Settings-Seite — ein Einsatzort mit Farb-Kontext."""

    id: uuid.UUID
    display_name: str  # "Name City"
    current_color: str  # Override oder Default
    has_override: bool


def get_color_overrides(session: Session, web_user_id: uuid.UUID) -> dict[uuid.UUID, str]:
    """Lädt alle Farb-Überschreibungen des Users als `{location_id: hex}`-Dict.

    Einmal pro Request laden und an die Kalender-Services durchreichen —
    vermeidet N+1-Lookups im Event-Konstruktions-Loop.
    """
    rows = session.execute(
        sa_select(UserLocationColor.location_of_work_id, UserLocationColor.color)
        .where(UserLocationColor.web_user_id == web_user_id)
    ).all()
    return {row.location_of_work_id: row.color for row in rows}


def get_visible_locations_with_colors(
    session: Session,
    web_user: WebUser,
) -> list[LocationColorRow]:
    """Alle für den User sichtbaren Einsatzorte mit ihrer aktuellen Farbe.

    Sichtbar = Locations aus Plan-Perioden der Teams, in denen der User
    - als Mitarbeiter eingetragen ist (`ActorPlanPeriod.person_id`), oder
    - als Dispatcher eingetragen ist (`Team.dispatcher_id`).
    Der Doppel-Kontext stellt sicher, dass ein Dispatcher, der nicht selbst
    mitspielt, trotzdem die Farben aller Locations seiner Teams konfigurieren
    kann. Soft-gelöschte Locations werden ausgeschlossen.
    """
    if web_user.person_id is None:
        return []

    employee_team_ids = set(session.execute(
        sa_select(PlanPeriod.team_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.plan_period_id == PlanPeriod.id)
        .join(Team, Team.id == PlanPeriod.team_id)
        .where(ActorPlanPeriod.person_id == web_user.person_id)
        .where(PlanPeriod.prep_delete.is_(None))
        .where(Team.prep_delete.is_(None))
        .distinct()
    ).scalars().all())
    dispatcher_team_ids = set(session.execute(
        sa_select(Team.id)
        .where(Team.dispatcher_id == web_user.person_id)
        .where(Team.prep_delete.is_(None))
    ).scalars().all())
    team_ids = list(employee_team_ids | dispatcher_team_ids)
    if not team_ids:
        return []

    loc_rows = session.execute(
        sa_select(LocationOfWork.id, LocationOfWork.name, Address.city)
        .select_from(LocationPlanPeriod)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .outerjoin(Address, Address.id == LocationOfWork.address_id)
        .join(PlanPeriod, PlanPeriod.id == LocationPlanPeriod.plan_period_id)
        .where(PlanPeriod.team_id.in_(team_ids))
        .where(LocationOfWork.prep_delete.is_(None))
        .distinct()
        .order_by(LocationOfWork.name)
    ).all()

    overrides = get_color_overrides(session, web_user.id)
    result: list[LocationColorRow] = []
    for loc_id, name, city in loc_rows:
        has_override = loc_id in overrides
        result.append(LocationColorRow(
            id=loc_id,
            display_name=location_display_name(name, city),
            current_color=overrides[loc_id] if has_override else default_location_color(loc_id),
            has_override=has_override,
        ))
    return result


def set_location_color(
    session: Session,
    web_user_id: uuid.UUID,
    location_of_work_id: uuid.UUID,
    color: str,
) -> UserLocationColor:
    """Upsert: legt Override an oder aktualisiert bestehenden."""
    existing = session.get(UserLocationColor, (web_user_id, location_of_work_id))
    if existing is None:
        entry = UserLocationColor(
            web_user_id=web_user_id,
            location_of_work_id=location_of_work_id,
            color=color,
        )
        session.add(entry)
        session.flush()
        return entry
    existing.color = color
    session.flush()
    return existing


def delete_location_color(
    session: Session,
    web_user_id: uuid.UUID,
    location_of_work_id: uuid.UUID,
) -> None:
    """Löscht den Override — der User fällt zurück auf den deterministischen Default."""
    existing = session.get(UserLocationColor, (web_user_id, location_of_work_id))
    if existing is not None:
        session.delete(existing)
        session.flush()
