"""Settings-Service: Frist-Berechnung (Project → Team → Default 48h).

Es gibt zwei Fristen:
- Absagefrist (`cancellation_deadline_hours`)
- Tausch-Frist (`swap_deadline_hours`)

Beide folgen derselben Hierarchie: Team-Override → Projekt-Default → 48h-Fallback.
Sie sind unabhängig konfigurierbar, der Default ist aber identisch.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import PlanPeriod, Team
from web_api.models.web_models import ProjectSettings, TeamNotificationSettings


@dataclass
class EffectiveSettings:
    deadline_hours: int
    source: str  # "team" | "project" | "default"
    swap_deadline_hours: int = 48
    swap_source: str = "default"


DEFAULT_DEADLINE_HOURS = 48
DEFAULT_SWAP_DEADLINE_HOURS = 48


def get_project_deadline_hours(session: Session, project_id: uuid.UUID) -> int:
    """Lädt den projektweiten Absagefrist-Default. Liefert 48h, wenn noch keine Row existiert."""
    setting = session.execute(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).scalars().first()
    return setting.cancellation_deadline_hours if setting else DEFAULT_DEADLINE_HOURS


def get_project_swap_deadline_hours(session: Session, project_id: uuid.UUID) -> int:
    """Lädt den projektweiten Tausch-Frist-Default. Liefert 48h, wenn noch keine Row existiert."""
    setting = session.execute(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).scalars().first()
    return setting.swap_deadline_hours if setting else DEFAULT_SWAP_DEADLINE_HOURS


def get_effective_deadline(session: Session, team_id: uuid.UUID) -> EffectiveSettings:
    """Ermittelt beide effektiven Fristen für ein Team in einem Pass.

    Für jede Frist separat: Team-Override → Projekt-Default → globaler 48h-Fallback.
    """
    team_setting = session.execute(
        sa_select(TeamNotificationSettings).where(TeamNotificationSettings.team_id == team_id)
    ).scalars().first()

    project_setting = None
    team = session.get(Team, team_id)
    if team:
        project_setting = session.execute(
            sa_select(ProjectSettings).where(ProjectSettings.project_id == team.project_id)
        ).scalars().first()

    # Absagefrist
    if team_setting and team_setting.cancellation_deadline_hours is not None:
        cancellation_hours = team_setting.cancellation_deadline_hours
        cancellation_source = "team"
    elif project_setting:
        cancellation_hours = project_setting.cancellation_deadline_hours
        cancellation_source = "project"
    else:
        cancellation_hours = DEFAULT_DEADLINE_HOURS
        cancellation_source = "default"

    # Tausch-Frist (gleiche Hierarchie, eigene Spalten)
    if team_setting and team_setting.swap_deadline_hours is not None:
        swap_hours = team_setting.swap_deadline_hours
        swap_source = "team"
    elif project_setting:
        swap_hours = project_setting.swap_deadline_hours
        swap_source = "project"
    else:
        swap_hours = DEFAULT_SWAP_DEADLINE_HOURS
        swap_source = "default"

    return EffectiveSettings(
        deadline_hours=cancellation_hours,
        source=cancellation_source,
        swap_deadline_hours=swap_hours,
        swap_source=swap_source,
    )


def upsert_project_settings(
    session: Session, project_id: uuid.UUID, deadline_hours: int
) -> ProjectSettings:
    """Setzt die projektweite Absagefrist. Tausch-Frist bleibt unverändert."""
    existing = session.execute(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).scalars().first()
    if existing:
        existing.cancellation_deadline_hours = deadline_hours
        session.add(existing)
        return existing
    new = ProjectSettings(project_id=project_id, cancellation_deadline_hours=deadline_hours)
    session.add(new)
    return new


def upsert_project_swap_deadline(
    session: Session, project_id: uuid.UUID, swap_deadline_hours: int
) -> ProjectSettings:
    """Setzt die projektweite Tausch-Frist. Absagefrist bleibt unverändert."""
    existing = session.execute(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).scalars().first()
    if existing:
        existing.swap_deadline_hours = swap_deadline_hours
        session.add(existing)
        return existing
    new = ProjectSettings(project_id=project_id, swap_deadline_hours=swap_deadline_hours)
    session.add(new)
    return new


def upsert_team_settings(
    session: Session, team_id: uuid.UUID, deadline_hours: int | None
) -> TeamNotificationSettings:
    """Setzt den Team-Override für die Absagefrist (None = erbt vom Projekt)."""
    existing = session.execute(
        sa_select(TeamNotificationSettings).where(TeamNotificationSettings.team_id == team_id)
    ).scalars().first()
    if existing:
        existing.cancellation_deadline_hours = deadline_hours
        session.add(existing)
        return existing
    new = TeamNotificationSettings(team_id=team_id, cancellation_deadline_hours=deadline_hours)
    session.add(new)
    return new


def upsert_team_swap_deadline(
    session: Session, team_id: uuid.UUID, swap_deadline_hours: int | None
) -> TeamNotificationSettings:
    """Setzt den Team-Override für die Tausch-Frist (None = erbt vom Projekt)."""
    existing = session.execute(
        sa_select(TeamNotificationSettings).where(TeamNotificationSettings.team_id == team_id)
    ).scalars().first()
    if existing:
        existing.swap_deadline_hours = swap_deadline_hours
        session.add(existing)
        return existing
    new = TeamNotificationSettings(team_id=team_id, swap_deadline_hours=swap_deadline_hours)
    session.add(new)
    return new
