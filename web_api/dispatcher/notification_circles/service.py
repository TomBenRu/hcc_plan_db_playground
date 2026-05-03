"""Service-Schicht fuer Notification-Circles pro Arbeitsort.

Verwaltet das Modus-Bit `location_of_work.notification_circle_restricted`
und die Whitelist-Mitgliedschaft in `location_notification_circle`.
Liest Pool-Kandidaten aus dem Team-Loc-Geflecht (Variante B aus dem
Implementierungsplan): aktive WebUser, deren Person via heute aktivem
TeamActorAssign zu einem Team gehoert, das via heute aktivem
TeamLocationAssign mit dem Arbeitsort verbunden ist.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import distinct, func
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    LocationOfWork,
    Person,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)
from web_api.models.web_models import LocationNotificationCircle, WebUser


# ── Datenklassen ──────────────────────────────────────────────────────────────


@dataclass
class EligibleUser:
    """Pool-Kandidat fuer die Whitelist-Auswahl."""

    web_user_id: uuid.UUID
    email: str
    person_name: str


@dataclass
class CircleMember:
    """Aktiver Whitelist-Eintrag (mit Pool-Filter, Karteileichen sind raus)."""

    web_user_id: uuid.UUID
    email: str
    person_name: str
    added_at: date


@dataclass
class LocationCircleSummary:
    """Liste-Zeile pro Arbeitsort fuer den Dispatcher."""

    location_id: uuid.UUID
    location_name: str
    team_name: str
    restricted: bool
    member_count: int


# ── Pool ──────────────────────────────────────────────────────────────────────


def _today() -> date:
    return date.today()


def _active_taa_filter(today: date):
    return (TeamActorAssign.start <= today) & (
        (TeamActorAssign.end.is_(None)) | (TeamActorAssign.end > today)
    )


def _active_tla_filter(today: date):
    return (TeamLocationAssign.start <= today) & (
        (TeamLocationAssign.end.is_(None)) | (TeamLocationAssign.end > today)
    )


def get_eligible_users_for_location(
    session: Session,
    location_id: uuid.UUID,
) -> list[EligibleUser]:
    """Aktive WebUser, die heute ueber TeamActorAssign + TeamLocationAssign
    mit dem Arbeitsort verbunden sind (Pool fuer die Whitelist-Auswahl).

    `DISTINCT` auf web_user.id, weil Multi-Team-Personen sonst mehrfach
    auftreten wuerden (eine Zeile je Team-Loc-Pfad).
    """
    today = _today()
    rows = session.execute(
        sa_select(
            distinct(WebUser.id).label("web_user_id"),
            WebUser.email,
            Person.f_name,
            Person.l_name,
        )
        .select_from(WebUser)
        .join(Person, Person.id == WebUser.person_id)
        .join(TeamActorAssign, TeamActorAssign.person_id == Person.id)
        .join(Team, Team.id == TeamActorAssign.team_id)
        .join(TeamLocationAssign, TeamLocationAssign.team_id == Team.id)
        .where(TeamLocationAssign.location_of_work_id == location_id)
        .where(WebUser.is_active.is_(True))
        .where(Team.prep_delete.is_(None))
        .where(_active_taa_filter(today))
        .where(_active_tla_filter(today))
        .order_by(Person.l_name, Person.f_name)
    ).mappings().all()

    return [
        EligibleUser(
            web_user_id=r["web_user_id"],
            email=r["email"],
            person_name=f"{r['f_name']} {r['l_name']}",
        )
        for r in rows
    ]


def get_circle_members(
    session: Session,
    location_id: uuid.UUID,
) -> list[CircleMember]:
    """Aktuelle Whitelist-Mitglieder, gefiltert ueber den Pool.

    Karteileichen (Personen, die nicht mehr im Team sind) erscheinen
    nicht — eine Cleanup-Routine ist nicht noetig.
    """
    today = _today()
    rows = session.execute(
        sa_select(
            distinct(WebUser.id).label("web_user_id"),
            WebUser.email,
            Person.f_name,
            Person.l_name,
            LocationNotificationCircle.created_at,
        )
        .select_from(WebUser)
        .join(Person, Person.id == WebUser.person_id)
        .join(TeamActorAssign, TeamActorAssign.person_id == Person.id)
        .join(Team, Team.id == TeamActorAssign.team_id)
        .join(TeamLocationAssign, TeamLocationAssign.team_id == Team.id)
        .join(
            LocationNotificationCircle,
            (LocationNotificationCircle.web_user_id == WebUser.id)
            & (LocationNotificationCircle.location_of_work_id == location_id),
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


# ── Visibility / Authorisierung ──────────────────────────────────────────────


def _dispatcher_team_ids(session: Session, person_id: uuid.UUID) -> list[uuid.UUID]:
    """Alle aktiven Teams, in denen die Person Dispatcher ist."""
    rows = session.execute(
        sa_select(Team.id)
        .where(Team.dispatcher_id == person_id)
        .where(Team.prep_delete.is_(None))
    ).all()
    return [r[0] for r in rows]


def assert_dispatcher_owns_location(
    session: Session,
    user: WebUser,
    location_id: uuid.UUID,
) -> None:
    """403 falls der Arbeitsort in keinem Team liegt, in dem der User
    Dispatcher ist (Visibility-Regel a aus dem Plan)."""
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknuepft.",
        )

    team_ids = _dispatcher_team_ids(session, user.person_id)
    if not team_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Keine Dispatcher-Rechte.")

    today = _today()
    hit = session.execute(
        sa_select(LocationOfWork.id)
        .join(TeamLocationAssign, TeamLocationAssign.location_of_work_id == LocationOfWork.id)
        .where(LocationOfWork.id == location_id)
        .where(LocationOfWork.prep_delete.is_(None))
        .where(TeamLocationAssign.team_id.in_(team_ids))
        .where(_active_tla_filter(today))
        .limit(1)
    ).first()

    if hit is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Keine Dispatcher-Rechte fuer diesen Arbeitsort.",
        )


def list_locations_for_dispatcher(
    session: Session,
    user: WebUser,
) -> list[LocationCircleSummary]:
    """Alle Arbeitsorte aller Teams, in denen der User Dispatcher ist —
    je mit Modus-Status und Member-Count fuer die Liste-View."""
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
            LocationOfWork.notification_circle_restricted.label("restricted"),
            Team.name.label("team_name"),
            func.count(distinct(LocationNotificationCircle.web_user_id)).label("member_count"),
        )
        .select_from(LocationOfWork)
        .join(TeamLocationAssign, TeamLocationAssign.location_of_work_id == LocationOfWork.id)
        .join(Team, Team.id == TeamLocationAssign.team_id)
        .outerjoin(
            LocationNotificationCircle,
            LocationNotificationCircle.location_of_work_id == LocationOfWork.id,
        )
        .where(LocationOfWork.prep_delete.is_(None))
        .where(Team.id.in_(team_ids))
        .where(_active_tla_filter(today))
        .group_by(LocationOfWork.id, LocationOfWork.name, LocationOfWork.notification_circle_restricted, Team.name)
        .order_by(Team.name, LocationOfWork.name)
    ).mappings().all()

    return [
        LocationCircleSummary(
            location_id=r["loc_id"],
            location_name=r["loc_name"],
            team_name=r["team_name"],
            restricted=r["restricted"],
            member_count=r["member_count"],
        )
        for r in rows
    ]


# ── CRUD-Mutationen ──────────────────────────────────────────────────────────


def set_location_restriction_mode(
    session: Session,
    location_id: uuid.UUID,
    restricted: bool,
    user: WebUser,
) -> bool:
    """Setzt das Modus-Bit. Liefert den neuen Wert.

    Eigentuemer-Check ueber `assert_dispatcher_owns_location` MUSS vorher
    durch den Caller laufen (Router-Endpoint).
    """
    loc = session.get(LocationOfWork, location_id)
    if loc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")
    loc.notification_circle_restricted = restricted
    session.add(loc)
    session.commit()
    return restricted


def add_members(
    session: Session,
    location_id: uuid.UUID,
    web_user_ids: list[uuid.UUID],
    added_by: WebUser,
) -> int:
    """Fuegt Pool-validierte WebUser zur Whitelist hinzu. Liefert die
    Anzahl der NEU eingefuegten Zeilen (idempotent: Duplikate werden
    silently uebersprungen).

    Pool-Validierung: jede `web_user_id` muss im `get_eligible_users_for_location`
    enthalten sein, sonst 403 (verhindert Direkt-API-Spoofing). Das ist
    *nicht* nur eine UI-Convenience — der Pool ist die Autorisierungs-
    grenze fuer welche Personen in der Whitelist landen duerfen.
    """
    if not web_user_ids:
        return 0

    eligible_ids = {u.web_user_id for u in get_eligible_users_for_location(session, location_id)}
    requested = set(web_user_ids)
    invalid = requested - eligible_ids
    if invalid:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"User auerhalb des Pools: {sorted(str(i) for i in invalid)}",
        )

    # Bestehende Mitgliedschaften abziehen, damit der Insert idempotent ist.
    existing = {
        row[0]
        for row in session.execute(
            sa_select(LocationNotificationCircle.web_user_id)
            .where(LocationNotificationCircle.location_of_work_id == location_id)
            .where(LocationNotificationCircle.web_user_id.in_(requested))
        ).all()
    }
    to_insert = requested - existing
    for wuid in to_insert:
        session.add(
            LocationNotificationCircle(
                location_of_work_id=location_id,
                web_user_id=wuid,
                added_by_id=added_by.id,
            )
        )
    session.commit()
    return len(to_insert)


def remove_member(
    session: Session,
    location_id: uuid.UUID,
    web_user_id: uuid.UUID,
) -> bool:
    """Entfernt einen Member. Liefert True falls eine Zeile geloescht wurde.

    Eigentuemer-Check ueber `assert_dispatcher_owns_location` MUSS vorher
    durch den Caller laufen (Router-Endpoint).
    """
    row = session.get(
        LocationNotificationCircle,
        (location_id, web_user_id),
    )
    if row is None:
        return False
    session.delete(row)
    session.commit()
    return True


def count_restricted_locations_for_dispatcher(
    session: Session,
    user: WebUser,
) -> int:
    """Anzahl Arbeitsorte mit `restricted=True` im Visibility-Scope des
    Dispatchers — fuer den Dashboard-Tile-Counter."""
    if user.person_id is None:
        return 0

    team_ids = _dispatcher_team_ids(session, user.person_id)
    if not team_ids:
        return 0

    today = _today()
    return session.execute(
        sa_select(func.count(distinct(LocationOfWork.id)))
        .select_from(LocationOfWork)
        .join(TeamLocationAssign, TeamLocationAssign.location_of_work_id == LocationOfWork.id)
        .where(LocationOfWork.prep_delete.is_(None))
        .where(LocationOfWork.notification_circle_restricted.is_(True))
        .where(TeamLocationAssign.team_id.in_(team_ids))
        .where(_active_tla_filter(today))
    ).scalar_one()
