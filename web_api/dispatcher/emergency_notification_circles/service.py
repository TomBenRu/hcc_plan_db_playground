"""Service-Schicht für den Notfall-Benachrichtigungs-Kreis pro Arbeitsort.

Spiegel von `dispatcher/notification_circles/service.py`, aber:
- Tabelle `LocationEmergencyNotificationCircle` statt `LocationNotificationCircle`
- KEIN `set_location_restriction_mode` (Aktivierung implicit über Member-Existenz)
- `EmergencyLocationSummary` hat kein `restricted`-Feld

Pool-Berechnung (`get_eligible_users_for_location`) und Authorization
(`assert_dispatcher_owns_location`) werden aus `notification_circles.service`
direkt wiederverwendet — sie hängen an der `LocationOfWork`, nicht an
der spezifischen Whitelist-Tabelle.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import distinct, func
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import LocationOfWork, Person, Team, TeamActorAssign, TeamLocationAssign
from web_api.dispatcher.notification_circles.service import (
    CircleMember,
    _active_taa_filter,
    _active_tla_filter,
    _dispatcher_team_ids,
    _today,
)
from web_api.email.recipient import sql_recipient_email
from web_api.models.web_models import (
    LocationEmergencyNotificationCircle,
    LocationNotificationCircle,
    WebUser,
)


@dataclass
class EmergencyLocationSummary:
    """Liste-Zeile pro Arbeitsort für den Dispatcher (Notfall-Whitelist).

    Kein `restricted`-Flag — Aktivierung leitet sich direkt aus
    `member_count > 0` ab.
    """

    location_id: uuid.UUID
    location_name: str
    team_name: str
    member_count: int


def get_emergency_circle_members(
    session: Session,
    location_id: uuid.UUID,
) -> list[CircleMember]:
    """Aktuelle Notfall-Whitelist-Mitglieder, Pool-gefiltert.

    Karteileichen (Personen, die nicht mehr im Team sind) erscheinen nicht.
    """
    today = _today()
    rows = session.execute(
        sa_select(
            distinct(WebUser.id).label("web_user_id"),
            sql_recipient_email().label("email"),
            Person.f_name,
            Person.l_name,
            LocationEmergencyNotificationCircle.created_at,
        )
        .select_from(WebUser)
        .join(Person, Person.id == WebUser.person_id)
        .join(TeamActorAssign, TeamActorAssign.person_id == Person.id)
        .join(Team, Team.id == TeamActorAssign.team_id)
        .join(TeamLocationAssign, TeamLocationAssign.team_id == Team.id)
        .join(
            LocationEmergencyNotificationCircle,
            (LocationEmergencyNotificationCircle.web_user_id == WebUser.id)
            & (LocationEmergencyNotificationCircle.location_of_work_id == location_id),
        )
        .where(TeamLocationAssign.location_of_work_id == location_id)
        .where(WebUser.is_active.is_(True))
        .where(Team.prep_delete.is_(None))
        .where(_active_taa_filter(today))
        .where(_active_tla_filter(today))
        .order_by(Person.l_name, Person.f_name)
    ).mappings().all()

    return [
        CircleMember(
            web_user_id=r["web_user_id"],
            email=r["email"],
            person_name=f"{r['f_name']} {r['l_name']}",
            added_at=r["created_at"].date() if r["created_at"] else today,
        )
        for r in rows
    ]


def list_emergency_locations_for_dispatcher(
    session: Session,
    user: WebUser,
) -> list[EmergencyLocationSummary]:
    """Alle Arbeitsorte aller Teams, in denen der User Dispatcher ist —
    je mit Member-Count der Notfall-Whitelist."""
    if user.person_id is None:
        return []

    team_ids = _dispatcher_team_ids(session, user.person_id)
    if not team_ids:
        return []

    today = _today()
    rows = session.execute(
        sa_select(
            distinct(LocationOfWork.id).label("loc_id"),
            LocationOfWork.name.label("loc_name"),
            Team.name.label("team_name"),
            func.count(distinct(LocationEmergencyNotificationCircle.web_user_id)).label("member_count"),
        )
        .select_from(LocationOfWork)
        .join(TeamLocationAssign, TeamLocationAssign.location_of_work_id == LocationOfWork.id)
        .join(Team, Team.id == TeamLocationAssign.team_id)
        .outerjoin(
            LocationEmergencyNotificationCircle,
            LocationEmergencyNotificationCircle.location_of_work_id == LocationOfWork.id,
        )
        .where(LocationOfWork.prep_delete.is_(None))
        .where(Team.id.in_(team_ids))
        .where(_active_tla_filter(today))
        .group_by(LocationOfWork.id, LocationOfWork.name, Team.name)
        .order_by(Team.name, LocationOfWork.name)
    ).mappings().all()

    return [
        EmergencyLocationSummary(
            location_id=r["loc_id"],
            location_name=r["loc_name"],
            team_name=r["team_name"],
            member_count=r["member_count"],
        )
        for r in rows
    ]


def add_emergency_members(
    session: Session,
    location_id: uuid.UUID,
    web_user_ids: list[uuid.UUID],
    added_by: WebUser,
) -> int:
    """Fügt Pool-validierte WebUser zur Notfall-Whitelist hinzu. Liefert
    die Anzahl der NEU eingefügten Zeilen (idempotent)."""
    if not web_user_ids:
        return 0

    # Pool-Validierung über bestehende Helper-Funktion aus notification_circles.
    from web_api.dispatcher.notification_circles.service import (
        get_eligible_users_for_location,
    )

    eligible_ids = {u.web_user_id for u in get_eligible_users_for_location(session, location_id)}
    requested = set(web_user_ids)
    invalid = requested - eligible_ids
    if invalid:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"User außerhalb des Pools: {sorted(str(i) for i in invalid)}",
        )

    existing = {
        row[0]
        for row in session.execute(
            sa_select(LocationEmergencyNotificationCircle.web_user_id)
            .where(LocationEmergencyNotificationCircle.location_of_work_id == location_id)
            .where(LocationEmergencyNotificationCircle.web_user_id.in_(requested))
        ).all()
    }
    to_insert = requested - existing
    for wuid in to_insert:
        session.add(
            LocationEmergencyNotificationCircle(
                location_of_work_id=location_id,
                web_user_id=wuid,
                added_by_id=added_by.id,
            )
        )
    session.commit()
    return len(to_insert)


def remove_emergency_member(
    session: Session,
    location_id: uuid.UUID,
    web_user_id: uuid.UUID,
) -> bool:
    """Entfernt einen Notfall-Whitelist-Member. Liefert True falls eine
    Zeile gelöscht wurde."""
    row = session.get(
        LocationEmergencyNotificationCircle,
        (location_id, web_user_id),
    )
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


def count_regular_circle_members(
    session: Session,
    location_id: uuid.UUID,
) -> int:
    """Anzahl Members im regulären `location_notification_circle` der Location.

    Verwendet im Detail-Pane, um den „Aus regulärem Kreis übernehmen"-Button
    nur dann anzuzeigen, wenn überhaupt etwas zu übernehmen ist.
    """
    return session.execute(
        sa_select(func.count(LocationNotificationCircle.web_user_id))
        .where(LocationNotificationCircle.location_of_work_id == location_id)
    ).scalar_one() or 0


def clear_emergency_circle(
    session: Session,
    location_id: uuid.UUID,
) -> int:
    """Entfernt ALLE Members aus der Notfall-Whitelist der Location.
    Liefert die Anzahl der gelöschten Zeilen.

    Nach dem Clear ist die Whitelist leer und Auto-Mode greift wieder
    (Implicit-Aktivierung). Aufrufer (Router) muss vorher den Eigentümer-
    Check via `assert_dispatcher_owns_location` laufen lassen.
    """
    rows = session.execute(
        sa_select(LocationEmergencyNotificationCircle)
        .where(LocationEmergencyNotificationCircle.location_of_work_id == location_id)
    ).scalars().all()
    if not rows:
        return 0
    for row in rows:
        session.delete(row)
    session.commit()
    return len(rows)


def copy_from_regular_circle(
    session: Session,
    location_id: uuid.UUID,
    added_by: WebUser,
) -> int:
    """Übernimmt alle Members aus dem regulären `location_notification_circle`
    in die Notfall-Whitelist. Idempotent: bereits vorhandene Personen werden
    übersprungen.

    Karteileichen-Schutz: Personen, die im regulären Kreis sind aber heute
    nicht mehr im aktuellen Pool (Team verlassen, Location-Zuordnung weg),
    werden vorab herausgefiltert — sonst würde die Pool-Validierung in
    `add_emergency_members` mit 403 abbrechen und die ganze Bulk-Übernahme
    schlagen fehl.

    Liefert die Anzahl der NEU hinzugefügten Zeilen.
    """
    from web_api.dispatcher.notification_circles.service import (
        get_eligible_users_for_location,
    )

    regular_ids = set(session.execute(
        sa_select(LocationNotificationCircle.web_user_id)
        .where(LocationNotificationCircle.location_of_work_id == location_id)
    ).scalars().all())
    if not regular_ids:
        return 0

    eligible_ids = {u.web_user_id for u in get_eligible_users_for_location(session, location_id)}
    valid_ids = list(regular_ids & eligible_ids)
    if not valid_ids:
        return 0

    return add_emergency_members(session, location_id, valid_ids, added_by)
