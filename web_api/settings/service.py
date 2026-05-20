"""Settings-Service: Absagefrist-Berechnung (Project → Team → Default 48h)."""

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


DEFAULT_DEADLINE_HOURS = 48


def get_project_deadline_hours(session: Session, project_id: uuid.UUID) -> int:
    """Lädt den projektweiten Default. Liefert 48h, wenn noch keine Row existiert."""
    setting = session.execute(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).scalars().first()
    return setting.cancellation_deadline_hours if setting else DEFAULT_DEADLINE_HOURS


def get_effective_deadline(session: Session, team_id: uuid.UUID) -> EffectiveSettings:
    """Ermittelt die effektive Absagefrist: Team → Project → Default 48h."""
    team_setting = session.execute(
        sa_select(TeamNotificationSettings).where(TeamNotificationSettings.team_id == team_id)
    ).scalars().first()
    if team_setting and team_setting.cancellation_deadline_hours is not None:
        return EffectiveSettings(deadline_hours=team_setting.cancellation_deadline_hours, source="team")

    team = session.get(Team, team_id)
    if team:
        project_setting = session.execute(
            sa_select(ProjectSettings).where(ProjectSettings.project_id == team.project_id)
        ).scalars().first()
        if project_setting:
            return EffectiveSettings(
                deadline_hours=project_setting.cancellation_deadline_hours, source="project"
            )

    return EffectiveSettings(deadline_hours=DEFAULT_DEADLINE_HOURS, source="default")


def upsert_project_settings(
    session: Session, project_id: uuid.UUID, deadline_hours: int
) -> ProjectSettings:
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


def upsert_team_settings(
    session: Session, team_id: uuid.UUID, deadline_hours: int | None
) -> TeamNotificationSettings:
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
