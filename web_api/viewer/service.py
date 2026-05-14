"""Viewer-Service: projektweiter Team-Lookup fuer die Read-Only-Plan-Sicht.

Im Gegensatz zu `dispatcher.service.get_teams_for_dispatcher` filtert die
Viewer-Sicht nicht auf `Team.dispatcher_id`, sondern liefert *alle* aktiven
Teams des Projekts, in dem der eingeloggte User-Person-Eintrag wohnt.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select as sa_select
from sqlalchemy.orm import selectinload
from sqlmodel import Session

from database.models import Person, Team, TeamActorAssign
from web_api.dispatcher.service import TeamInfo
from web_api.models.web_models import WebUser


def get_user_project_id(session: Session, user: WebUser) -> uuid.UUID:
    """Liefert die `project_id` der mit dem WebUser verknuepften Person.

    Wirft 403, wenn der Viewer kein Person-Konto hat — ohne Person-Verknuepfung
    laesst sich nicht zuverlaessig bestimmen, welches Projekt er sehen darf.
    Der Admin kann die Verknuepfung jederzeit ueber /admin/users im Drawer setzen.
    """
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=(
                "Diesem Konto ist keine Person zugeordnet — der Administrator "
                "muss eine Person verknüpfen, damit das Projekt bestimmt werden kann."
            ),
        )
    person = session.get(Person, user.person_id)
    if person is None or person.prep_delete is not None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Verknüpfte Person nicht mehr verfügbar.",
        )
    return person.project_id


def get_all_teams_in_project(session: Session, project_id: uuid.UUID) -> list[TeamInfo]:
    """Alle aktiven Teams in einem Projekt — sortiert nach Name.

    Wiederverwendet die `TeamInfo`-Pydantic-Struktur aus dispatcher.service,
    damit Plan-Templates 1:1 ueber my_teams iterieren koennen, egal aus
    welcher Quelle die Liste kommt.
    """
    rows = session.execute(
        sa_select(Team.id, Team.name, Team.project_id)
        .where(Team.project_id == project_id)
        .where(Team.prep_delete.is_(None))
        .order_by(Team.name)
    ).mappings().all()
    return [TeamInfo(**row) for row in rows]


# ── Personen-Stammdaten (Phase 4b) ───────────────────────────────────────────


@dataclass
class PersonRow:
    """View-Model fuer die Personen-Listentabelle."""

    id: uuid.UUID
    f_name: str
    l_name: str
    email: str
    phone_nr: str | None
    role: str | None  # PersonRoleEnum.value oder None
    is_soft_deleted: bool
    current_team_names: list[str]  # heute aktive Team-Zuordnungen


def _current_team_names(person: Person, today: date) -> list[str]:
    """Heute aktive Team-Zuordnungen — start <= today und end IS NULL oder > today."""
    names: list[str] = []
    for assign in person.team_actor_assigns:
        if assign.start > today:
            continue
        if assign.end is not None and assign.end <= today:
            continue
        if assign.team is None or assign.team.prep_delete is not None:
            continue
        names.append(assign.team.name)
    return sorted(set(names))


def list_persons_in_project(
    session: Session,
    *,
    project_id: uuid.UUID,
    team_id: uuid.UUID | None = None,
    include_deleted: bool = False,
    search: str = "",
) -> list[PersonRow]:
    """Listet alle Personen eines Projekts fuer die Read-Only-Stammdaten-Sicht.

    N+1-frei: team_actor_assigns + team via selectinload mitgeladen.
    Team-Filter bezieht sich auf *heute aktive* Zuordnungen — wer in der
    Vergangenheit dort war, wird ausgeblendet.
    """
    stmt = (
        sa_select(Person)
        .where(Person.project_id == project_id)
        .options(
            selectinload(Person.team_actor_assigns).selectinload(TeamActorAssign.team)
        )
    )
    if not include_deleted:
        stmt = stmt.where(Person.prep_delete.is_(None))

    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Person.f_name).like(like),
                func.lower(Person.l_name).like(like),
                func.lower(Person.email).like(like),
            )
        )

    persons = list(session.execute(stmt).scalars().all())
    today = date.today()

    rows: list[PersonRow] = []
    for p in persons:
        team_names = _current_team_names(p, today)
        if team_id is not None:
            # Python-seitiger Filter, weil current_team_names date-abhaengig ist
            # und nicht trivial in SQL ausgedrueckt werden kann.
            requested_team = next(
                (a.team for a in p.team_actor_assigns if a.team and a.team.id == team_id),
                None,
            )
            if requested_team is None or requested_team.name not in team_names:
                continue
        rows.append(
            PersonRow(
                id=p.id,
                f_name=p.f_name,
                l_name=p.l_name,
                email=p.email,
                phone_nr=p.phone_nr,
                role=p.role.value if p.role else None,
                is_soft_deleted=p.prep_delete is not None,
                current_team_names=team_names,
            )
        )
    rows.sort(key=lambda r: (r.l_name.lower(), r.f_name.lower()))
    return rows


@dataclass
class PersonDetail:
    """Detail fuer den Drawer."""

    person: Person
    team_history: list[tuple[str, date, date | None]]  # (team_name, start, end)


def get_person_detail(
    session: Session,
    *,
    project_id: uuid.UUID,
    person_id: uuid.UUID,
) -> PersonDetail:
    """Liefert eine Person inkl. vollstaendiger Team-Historie (chronologisch).

    Wirft 404, wenn die Person nicht zum Projekt gehoert — Cross-Project-
    Information-Leak-Schutz.
    """
    person = session.execute(
        sa_select(Person)
        .where(Person.id == person_id)
        .options(
            selectinload(Person.team_actor_assigns).selectinload(TeamActorAssign.team),
            selectinload(Person.address),
        )
    ).scalar_one_or_none()
    if person is None or person.project_id != project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")

    history: list[tuple[str, date, date | None]] = []
    for assign in person.team_actor_assigns:
        if assign.team is None:
            continue
        history.append((assign.team.name, assign.start, assign.end))
    history.sort(key=lambda row: row[1], reverse=True)

    return PersonDetail(person=person, team_history=history)


def resolve_selected_team(
    session: Session,
    *,
    project_id: uuid.UUID,
    requested_team_id: uuid.UUID | None,
    available_teams: list[TeamInfo],
) -> uuid.UUID | None:
    """Bestimmt das anzuzeigende Team fuer Read-Views mit Team-Sidebar.

    Bei `requested_team_id` muss das Team aktiv und im Projekt sein — sonst
    wird es ignoriert (statt 404; ein Viewer soll bei verwaister URL nicht
    sofort eine harte Fehlerseite sehen). Fallback: erstes Team in der Liste.
    """
    if requested_team_id is not None:
        for t in available_teams:
            if t.id == requested_team_id:
                return t.id
    if available_teams:
        return available_teams[0].id
    return None