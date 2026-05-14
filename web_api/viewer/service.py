"""Viewer-Service: projektweiter Team-Lookup fuer die Read-Only-Plan-Sicht.

Im Gegensatz zu `dispatcher.service.get_teams_for_dispatcher` filtert die
Viewer-Sicht nicht auf `Team.dispatcher_id`, sondern liefert *alle* aktiven
Teams des Projekts, in dem der eingeloggte User-Person-Eintrag wohnt.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import Person, Team
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