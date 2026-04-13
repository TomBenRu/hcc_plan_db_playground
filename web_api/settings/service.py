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


def get_effective_deadline(session: Session, team_id: uuid.UUID) -> EffectiveSettings:
    """Ermittelt die effektive Absagefrist: Team → Project → Default 48h."""
    team_setting = session.exec(
        sa_select(TeamNotificationSettings).where(TeamNotificationSettings.team_id == team_id)
    ).first()
    if team_setting and team_setting.cancellation_deadline_hours is not None:
        return EffectiveSettings(deadline_hours=team_setting.cancellation_deadline_hours, source="team")

    team = session.get(Team, team_id)
    if team:
        project_setting = session.exec(
            sa_select(ProjectSettings).where(ProjectSettings.project_id == team.project_id)
        ).first()
        if project_setting:
            return EffectiveSettings(
                deadline_hours=project_setting.cancellation_deadline_hours, source="project"
            )

    return EffectiveSettings(deadline_hours=48, source="default")


def upsert_project_settings(
    session: Session, project_id: uuid.UUID, deadline_hours: int
) -> ProjectSettings:
    existing = session.exec(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).first()
    if existing:
        existing.deadline_hours = deadline_hours  # type: ignore[assignment]
        existing.cancellation_deadline_hours = deadline_hours
        session.add(existing)
        return existing
    new = ProjectSettings(project_id=project_id, cancellation_deadline_hours=deadline_hours)
    session.add(new)
    return new


def upsert_team_settings(
    session: Session, team_id: uuid.UUID, deadline_hours: int | None
) -> TeamNotificationSettings:
    existing = session.exec(
        sa_select(TeamNotificationSettings).where(TeamNotificationSettings.team_id == team_id)
    ).first()
    if existing:
        existing.cancellation_deadline_hours = deadline_hours
        session.add(existing)
        return existing
    new = TeamNotificationSettings(team_id=team_id, cancellation_deadline_hours=deadline_hours)
    session.add(new)
    return new
