"""Admin-Teams-Service: Read-Queries für Listenansichten und Drawer-Daten.

Listet Teams und Standorte projektweit, inklusive Inaktiv-Filter und
Live-Suche. Mutationen liegen in ``mutations.py`` und ``assignments.py``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database.models import (
    LocationOfWork,
    Person,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)
from web_api.models.web_models import WebUser, WebUserRole


# ─── Projekt-Resolver ──────────────────────────────────────────────────────────


def get_session_project(session: Session, user: WebUser) -> Project:
    """Loest das Projekt des eingeloggten Users — Admin **oder** Dispatcher.

    Unterschied zu ``web_api.admin.service.get_admin_project``: jener verlangt
    ``Person.admin_of_project_id`` und wirft 403 fuer Dispatcher-only-Konten.
    Hier nutzen wir den primaeren ``Person.project_id``-Pfad, der fuer alle
    Konten mit Person-Verknuepfung gesetzt ist.
    """
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )
    person = session.get(Person, user.person_id)
    if person is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Verknüpfte Person nicht mehr verfügbar.",
        )
    project = session.get(Project, person.project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden")
    return project


def require_admin_or_dispatcher(user: WebUser) -> None:
    """Body-seitige Rollen-Pruefung fuer Read-Routes, die Admin **und** Dispatcher
    bedienen.

    Mutations-Endpoints nutzen ``require_role(WebUserRole.admin)`` direkt — diese
    Hilfsfunktion ist nur fuer die geteilte Read-Seite und ``LoggedInUser``-typed
    Endpoints sinnvoll.
    """
    if not user.has_any_role(WebUserRole.admin, WebUserRole.dispatcher):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung")


# ─── List-View-Datenstrukturen ────────────────────────────────────────────────


@dataclass(slots=True)
class TeamListRow:
    """Schlanke Zeile fuer die Team-Liste. Vermeidet das Full-``TeamShow`` mit
    eager-loaded plan_periods/combination_locations — fuer die Liste irrelevant
    und teuer."""

    id: uuid.UUID
    name: str
    dispatcher_name: str | None
    member_count: int
    location_count: int
    prep_delete: datetime | None


@dataclass(slots=True)
class LocationListRow:
    """Analog zu ``TeamListRow``."""

    id: uuid.UUID
    name: str
    address_summary: str | None
    team_count: int
    nr_actors: int
    prep_delete: datetime | None


# ─── Read-Queries ─────────────────────────────────────────────────────────────


def list_teams_view(
    session: Session,
    project_id: uuid.UUID,
    *,
    only_inactive: bool,
    search: str,
) -> list[TeamListRow]:
    """Teams projektweit mit Dispatcher-Namen + Member-/Location-Counts.

    ``only_inactive=False`` liefert die aktiven Teams (``prep_delete IS NULL``),
    ``only_inactive=True`` liefert die soft-deleted Teams (``prep_delete IS NOT NULL``).
    Es gibt bewusst keinen Mischmodus — die Sidebar trennt Aktiv und Inaktiv strikt.
    """
    stmt = (
        select(Team)
        .where(Team.project_id == project_id)
        .options(selectinload(Team.dispatcher))  # type: ignore[arg-type]
        .order_by(Team.name)
    )
    if only_inactive:
        stmt = stmt.where(Team.prep_delete.is_not(None))  # type: ignore[union-attr]
    else:
        stmt = stmt.where(Team.prep_delete.is_(None))  # type: ignore[union-attr]
    if search:
        stmt = stmt.where(Team.name.ilike(f"%{search}%"))  # type: ignore[union-attr]

    teams = session.exec(stmt).all()
    today = date.today()
    rows: list[TeamListRow] = []
    for team in teams:
        member_count = session.execute(
            select(func.count())
            .select_from(TeamActorAssign)
            .where(
                TeamActorAssign.team_id == team.id,
                TeamActorAssign.start <= today,
                or_(TeamActorAssign.end.is_(None), TeamActorAssign.end > today),  # type: ignore[union-attr]
            )
        ).scalar_one()
        location_count = session.execute(
            select(func.count())
            .select_from(TeamLocationAssign)
            .where(
                TeamLocationAssign.team_id == team.id,
                TeamLocationAssign.start <= today,
                or_(TeamLocationAssign.end.is_(None), TeamLocationAssign.end > today),  # type: ignore[union-attr]
            )
        ).scalar_one()
        dispatcher_name = None
        if team.dispatcher:
            dispatcher_name = f"{team.dispatcher.f_name} {team.dispatcher.l_name}"
        rows.append(
            TeamListRow(
                id=team.id,
                name=team.name,
                dispatcher_name=dispatcher_name,
                member_count=member_count,
                location_count=location_count,
                prep_delete=team.prep_delete,
            )
        )
    return rows


def list_locations_view(
    session: Session,
    project_id: uuid.UUID,
    *,
    only_inactive: bool,
    search: str,
) -> list[LocationListRow]:
    """Standorte projektweit mit Adress-Zusammenfassung + Team-Count.

    Hinweis: ``db_services.location_of_work.get_all_from__project`` filtert
    soft-deleted aus und bietet keinen Schalter — wir bauen die Query daher
    direkt hier, um den Inaktiv-Filter abzubilden. Semantik wie bei
    ``list_teams_view``: ``only_inactive`` zerteilt streng nach ``prep_delete``.
    """
    stmt = (
        select(LocationOfWork)
        .where(LocationOfWork.project_id == project_id)
        .options(selectinload(LocationOfWork.address))  # type: ignore[arg-type]
        .order_by(LocationOfWork.name)
    )
    if only_inactive:
        stmt = stmt.where(LocationOfWork.prep_delete.is_not(None))  # type: ignore[union-attr]
    else:
        stmt = stmt.where(LocationOfWork.prep_delete.is_(None))  # type: ignore[union-attr]
    if search:
        stmt = stmt.where(LocationOfWork.name.ilike(f"%{search}%"))  # type: ignore[union-attr]

    locations = session.exec(stmt).all()
    today = date.today()
    rows: list[LocationListRow] = []
    for loc in locations:
        team_count = session.execute(
            select(func.count())
            .select_from(TeamLocationAssign)
            .where(
                TeamLocationAssign.location_of_work_id == loc.id,
                TeamLocationAssign.start <= today,
                or_(TeamLocationAssign.end.is_(None), TeamLocationAssign.end > today),  # type: ignore[union-attr]
            )
        ).scalar_one()
        address_summary = None
        if loc.address:
            parts = [p for p in (loc.address.street, loc.address.city) if p]
            address_summary = ", ".join(parts) or None
        rows.append(
            LocationListRow(
                id=loc.id,
                name=loc.name,
                address_summary=address_summary,
                team_count=team_count,
                nr_actors=loc.nr_actors,
                prep_delete=loc.prep_delete,
            )
        )
    return rows


def count_teams(session: Session, project_id: uuid.UUID, *, only_inactive: bool) -> int:
    stmt = select(func.count()).select_from(Team).where(Team.project_id == project_id)
    if only_inactive:
        stmt = stmt.where(Team.prep_delete.is_not(None))  # type: ignore[union-attr]
    else:
        stmt = stmt.where(Team.prep_delete.is_(None))  # type: ignore[union-attr]
    return session.execute(stmt).scalar_one()


def count_locations(session: Session, project_id: uuid.UUID, *, only_inactive: bool) -> int:
    stmt = (
        select(func.count())
        .select_from(LocationOfWork)
        .where(LocationOfWork.project_id == project_id)
    )
    if only_inactive:
        stmt = stmt.where(LocationOfWork.prep_delete.is_not(None))  # type: ignore[union-attr]
    else:
        stmt = stmt.where(LocationOfWork.prep_delete.is_(None))  # type: ignore[union-attr]
    return session.execute(stmt).scalar_one()
