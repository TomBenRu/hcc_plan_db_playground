"""Admin-Teams-Assignments: Personen-/Standort-Zuordnungen zu Teams.

Zeitabschnittsbasierte M:N via ``TeamActorAssign`` und ``TeamLocationAssign``.
Beide Modelle haben kein ``prep_delete``: ``end`` ist die Soft-Schliessung,
``session.delete()`` entfernt Future-Eintraege.

Aktive Mitgliedschaft wird definiert als
``start <= today AND (end IS NULL OR end > today)``.
Future-Eintraege: ``start > today``.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlmodel import Session, select

from database.models import (
    ActorPlanPeriod,
    LocationOfWork,
    Person,
    PlanPeriod,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)
from web_api.models.web_models import WebUser

logger = logging.getLogger(__name__)


# ─── Hilfsdatenstrukturen ─────────────────────────────────────────────────────


@dataclass(slots=True)
class AssignConflict:
    """Beschreibt einen bestehenden offenen Zuordnungs-Eintrag, der einer neuen
    Anlage im Weg steht. Wird vom Router zu einem 409-Dialog gerendert."""

    existing_assign_id: uuid.UUID
    existing_start: date
    existing_end: date | None


# ─── TeamActorAssign-Helper ───────────────────────────────────────────────────


def _open_team_actor_assign(
    session: Session,
    *,
    person_id: uuid.UUID,
    team_id: uuid.UUID,
    today: date,
) -> TeamActorAssign | None:
    """Liefert einen offenen TAA (gleiche Person × gleiches Team) zurueck,
    falls einer existiert: ``end IS NULL`` ODER ``end > today``.

    Bewusst nicht ueber ``db_services.team_actor_assign.get_at__date()``, weil
    jener Helper den Team-Soft-Delete-Filter einbaut — fuer den Konflikt-Check
    wollen wir auch reaktivierte Teams sehen (defensiv).
    """
    stmt = (
        select(TeamActorAssign)
        .where(
            TeamActorAssign.person_id == person_id,
            TeamActorAssign.team_id == team_id,
        )
        .where(
            or_(
                TeamActorAssign.end.is_(None),  # type: ignore[union-attr]
                TeamActorAssign.end > today,  # type: ignore[union-attr]
            )
        )
        .order_by(TeamActorAssign.start)
    )
    return session.exec(stmt).first()


def list_active_team_members(session: Session, team_id: uuid.UUID) -> list[TeamActorAssign]:
    today = date.today()
    stmt = (
        select(TeamActorAssign)
        .where(
            TeamActorAssign.team_id == team_id,
            TeamActorAssign.start <= today,
            or_(
                TeamActorAssign.end.is_(None),  # type: ignore[union-attr]
                TeamActorAssign.end > today,  # type: ignore[union-attr]
            ),
        )
        .order_by(TeamActorAssign.start)
    )
    return list(session.exec(stmt).all())


def list_future_team_members(session: Session, team_id: uuid.UUID) -> list[TeamActorAssign]:
    today = date.today()
    stmt = (
        select(TeamActorAssign)
        .where(TeamActorAssign.team_id == team_id, TeamActorAssign.start > today)
        .order_by(TeamActorAssign.start)
    )
    return list(session.exec(stmt).all())


def list_active_person_teams(
    session: Session, person_id: uuid.UUID
) -> list[TeamActorAssign]:
    """Aktive TAAs einer Person (Spiegel zu ``list_active_team_members``)."""
    today = date.today()
    stmt = (
        select(TeamActorAssign)
        .where(
            TeamActorAssign.person_id == person_id,
            TeamActorAssign.start <= today,
            or_(
                TeamActorAssign.end.is_(None),  # type: ignore[union-attr]
                TeamActorAssign.end > today,  # type: ignore[union-attr]
            ),
        )
        .order_by(TeamActorAssign.start)
    )
    return list(session.exec(stmt).all())


def list_future_person_teams(
    session: Session, person_id: uuid.UUID
) -> list[TeamActorAssign]:
    """Future-TAAs einer Person."""
    today = date.today()
    stmt = (
        select(TeamActorAssign)
        .where(TeamActorAssign.person_id == person_id, TeamActorAssign.start > today)
        .order_by(TeamActorAssign.start)
    )
    return list(session.exec(stmt).all())


# ─── TeamLocationAssign-Helper ────────────────────────────────────────────────


def _open_team_location_assign(
    session: Session,
    *,
    location_id: uuid.UUID,
    team_id: uuid.UUID,
    today: date,
) -> TeamLocationAssign | None:
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.location_of_work_id == location_id,
            TeamLocationAssign.team_id == team_id,
        )
        .where(
            or_(
                TeamLocationAssign.end.is_(None),  # type: ignore[union-attr]
                TeamLocationAssign.end > today,  # type: ignore[union-attr]
            )
        )
        .order_by(TeamLocationAssign.start)
    )
    return session.exec(stmt).first()


def list_active_team_locations(session: Session, team_id: uuid.UUID) -> list[TeamLocationAssign]:
    today = date.today()
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.team_id == team_id,
            TeamLocationAssign.start <= today,
            or_(
                TeamLocationAssign.end.is_(None),  # type: ignore[union-attr]
                TeamLocationAssign.end > today,  # type: ignore[union-attr]
            ),
        )
        .order_by(TeamLocationAssign.start)
    )
    return list(session.exec(stmt).all())


def list_future_team_locations(session: Session, team_id: uuid.UUID) -> list[TeamLocationAssign]:
    today = date.today()
    stmt = (
        select(TeamLocationAssign)
        .where(TeamLocationAssign.team_id == team_id, TeamLocationAssign.start > today)
        .order_by(TeamLocationAssign.start)
    )
    return list(session.exec(stmt).all())


def list_active_location_teams(
    session: Session, location_id: uuid.UUID
) -> list[TeamLocationAssign]:
    """Aktive TLAs zu einer Location (Spiegel zu ``list_active_team_locations``)."""
    today = date.today()
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.location_of_work_id == location_id,
            TeamLocationAssign.start <= today,
            or_(
                TeamLocationAssign.end.is_(None),  # type: ignore[union-attr]
                TeamLocationAssign.end > today,  # type: ignore[union-attr]
            ),
        )
        .order_by(TeamLocationAssign.start)
    )
    return list(session.exec(stmt).all())


def list_future_location_teams(
    session: Session, location_id: uuid.UUID
) -> list[TeamLocationAssign]:
    """Future-TLAs (``start > today``) zu einer Location."""
    today = date.today()
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.location_of_work_id == location_id,
            TeamLocationAssign.start > today,
        )
        .order_by(TeamLocationAssign.start)
    )
    return list(session.exec(stmt).all())


# ─── Mutations: TeamActorAssign ───────────────────────────────────────────────


def add_team_member(
    session: Session,
    *,
    team: Team,
    person_id: uuid.UUID,
    start: date | None,
    actor: WebUser,
) -> TeamActorAssign:
    """Erzeugt einen ``TeamActorAssign`` (Default ``start=heute``). Wirft 409
    mit ``AssignConflict``-Detail, wenn eine offene Mitgliedschaft existiert."""
    person = session.get(Person, person_id)
    if person is None or person.project_id != team.project_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Person nicht gefunden")

    today = date.today()
    effective_start = start or today
    if start is not None and start < today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start-Datum darf nicht in der Vergangenheit liegen",
        )

    open_assign = _open_team_actor_assign(
        session, person_id=person_id, team_id=team.id, today=today
    )
    if open_assign is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AssignConflict(
                existing_assign_id=open_assign.id,
                existing_start=open_assign.start,
                existing_end=open_assign.end,
            ),
        )

    assign = TeamActorAssign(person=person, team=team, start=effective_start, end=None)
    session.add(assign)
    session.commit()
    session.refresh(assign)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_member_added",
            "actor_id": str(actor.id),
            "target_id": str(assign.id),
        },
    )
    return assign


def set_team_member_end(
    session: Session,
    *,
    assign: TeamActorAssign,
    end: date | None,
    actor: WebUser,
) -> TeamActorAssign:
    """Setzt ``end`` auf den uebergebenen Wert. ``None`` revertiert eine
    zukuenftige End-Markierung (Mitgliedschaft wieder offen)."""
    today = date.today()
    if end is not None:
        if end <= assign.start:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End-Datum muss nach Start liegen",
            )
        if end < today:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End-Datum darf nicht in der Vergangenheit liegen",
            )

    was_revert = end is None
    assign.end = end
    session.commit()
    session.refresh(assign)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_member_reactivated" if was_revert else "team_member_ended",
            "actor_id": str(actor.id),
            "target_id": str(assign.id),
        },
    )
    return assign


# ─── Mutations: TeamLocationAssign ────────────────────────────────────────────


def add_team_location(
    session: Session,
    *,
    team: Team,
    location_id: uuid.UUID,
    start: date | None,
    actor: WebUser,
) -> TeamLocationAssign:
    location = session.get(LocationOfWork, location_id)
    if location is None or location.project_id != team.project_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Standort nicht gefunden"
        )

    today = date.today()
    effective_start = start or today
    if start is not None and start < today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start-Datum darf nicht in der Vergangenheit liegen",
        )

    open_assign = _open_team_location_assign(
        session, location_id=location_id, team_id=team.id, today=today
    )
    if open_assign is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=AssignConflict(
                existing_assign_id=open_assign.id,
                existing_start=open_assign.start,
                existing_end=open_assign.end,
            ),
        )

    assign = TeamLocationAssign(
        location_of_work=location, team=team, start=effective_start, end=None
    )
    session.add(assign)
    session.commit()
    session.refresh(assign)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_location_added",
            "actor_id": str(actor.id),
            "target_id": str(assign.id),
        },
    )
    return assign


def set_team_location_end(
    session: Session,
    *,
    assign: TeamLocationAssign,
    end: date | None,
    actor: WebUser,
) -> TeamLocationAssign:
    today = date.today()
    if end is not None:
        if end <= assign.start:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End-Datum muss nach Start liegen",
            )
        if end < today:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="End-Datum darf nicht in der Vergangenheit liegen",
            )

    was_revert = end is None
    assign.end = end
    session.commit()
    session.refresh(assign)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_location_reactivated" if was_revert else "team_location_ended",
            "actor_id": str(actor.id),
            "target_id": str(assign.id),
        },
    )
    return assign


# ─── Personen-Suche im Projekt ────────────────────────────────────────────────


def search_persons_for_team(
    session: Session,
    *,
    project_id: uuid.UUID,
    q: str,
    limit: int = 20,
) -> list[Person]:
    """Aktive Personen im Projekt — gefiltert nach Name/E-Mail-Substring."""
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Person)
        .where(
            Person.project_id == project_id,
            Person.prep_delete.is_(None),  # type: ignore[union-attr]
        )
        .order_by(Person.l_name, Person.f_name)
        .limit(limit)
    )
    if q.strip():
        stmt = stmt.where(
            (Person.f_name.ilike(pattern))  # type: ignore[union-attr]
            | (Person.l_name.ilike(pattern))  # type: ignore[union-attr]
            | (Person.email.ilike(pattern))  # type: ignore[union-attr]
        )
    return list(session.exec(stmt).all())


def search_locations_for_team(
    session: Session,
    *,
    project_id: uuid.UUID,
    q: str,
    limit: int = 20,
) -> list[LocationOfWork]:
    """Aktive Standorte im Projekt."""
    pattern = f"%{q.strip()}%"
    stmt = (
        select(LocationOfWork)
        .where(
            LocationOfWork.project_id == project_id,
            LocationOfWork.prep_delete.is_(None),  # type: ignore[union-attr]
        )
        .order_by(LocationOfWork.name)
        .limit(limit)
    )
    if q.strip():
        stmt = stmt.where(LocationOfWork.name.ilike(pattern))  # type: ignore[union-attr]
    return list(session.exec(stmt).all())


def search_teams_for_location(
    session: Session,
    *,
    project_id: uuid.UUID,
    q: str,
    limit: int = 20,
) -> list[Team]:
    """Aktive Teams im Projekt — Pool fuer den Team-Selector im Standort-Drawer."""
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Team)
        .where(
            Team.project_id == project_id,
            Team.prep_delete.is_(None),  # type: ignore[union-attr]
        )
        .order_by(Team.name)
        .limit(limit)
    )
    if q.strip():
        stmt = stmt.where(Team.name.ilike(pattern))  # type: ignore[union-attr]
    return list(session.exec(stmt).all())


def search_teams_for_person(
    session: Session,
    *,
    project_id: uuid.UUID,
    q: str,
    limit: int = 20,
) -> list[Team]:
    """Aktive Teams im Projekt — Pool fuer den Team-Selector im Mitglieder-Drawer.

    Identisch zu ``search_teams_for_location`` — die getrennte Funktion existiert
    nur fuer Lesbarkeit am Aufruf-Ort.
    """
    return search_teams_for_location(session, project_id=project_id, q=q, limit=limit)


def delete_future_team_location(
    session: Session,
    *,
    assign: TeamLocationAssign,
    actor: WebUser,
) -> None:
    """Loescht eine TLA — zulaessig nur, wenn ``start > today`` (Future-Eintrag).

    Symmetrisch zur Soft-Delete-Cleanup-Logik in ``mutations._cleanup_open_assigns_*``:
    Future-Eintraege haben noch keine historische Bedeutung und duerfen physisch
    entfernt werden; aktive/historische Eintraege bleiben fuer Audit erhalten und
    werden ueber ``end`` geschlossen.
    """
    today = date.today()
    if assign.start <= today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nur zukuenftige Zuordnungen koennen geloescht werden.",
        )
    assign_id_for_log = str(assign.id)
    session.delete(assign)
    session.commit()
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_location_future_deleted",
            "actor_id": str(actor.id),
            "target_id": assign_id_for_log,
        },
    )


def delete_future_team_actor_assign(
    session: Session,
    *,
    assign: TeamActorAssign,
    actor: WebUser,
) -> None:
    """Loescht eine TAA — zulaessig nur, wenn ``start > today`` (Future-Eintrag).
    Spiegel zu ``delete_future_team_location`` fuer Personen↔Team-Zuordnungen."""
    today = date.today()
    if assign.start <= today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nur zukuenftige Mitgliedschaften koennen geloescht werden.",
        )
    assign_id_for_log = str(assign.id)
    session.delete(assign)
    session.commit()
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_actor_future_deleted",
            "actor_id": str(actor.id),
            "target_id": assign_id_for_log,
        },
    )


# ─── Overlap-Detection fuer APP-Anlage nach TAA-Anlage ────────────────────────


def list_open_overlapping_plan_periods_for_taa(
    session: Session, *, taa: TeamActorAssign
) -> list[PlanPeriod]:
    """Liefert die offenen PlanPerioden des TAA-Teams, deren Zeitraum sich
    mit der TAA-Mitgliedschaft ueberschneidet und fuer die noch **kein** APP
    der Person existiert.

    Definitionen:
    - "offen" = ``PlanPeriod.closed = False AND prep_delete IS NULL``
    - Overlap = ``taa.start <= pp.end`` UND (``taa.end IS NULL`` ODER
      ``pp.start <= taa.end``); ``end`` ist beidseitig inklusiv (Datum)
    - "noch kein APP" = LEFT JOIN auf ``ActorPlanPeriod`` mit
      ``person_id=taa.person_id`` ergibt NULL

    Sortierung: ``pp.start`` aufsteigend, fuer stabile Reihenfolge im Dialog.
    """
    stmt = (
        select(PlanPeriod)
        .outerjoin(
            ActorPlanPeriod,
            (ActorPlanPeriod.plan_period_id == PlanPeriod.id)
            & (ActorPlanPeriod.person_id == taa.person_id),
        )
        .where(
            PlanPeriod.team_id == taa.team_id,
            PlanPeriod.closed.is_(False),  # type: ignore[union-attr]
            PlanPeriod.prep_delete.is_(None),  # type: ignore[union-attr]
            ActorPlanPeriod.id.is_(None),  # type: ignore[union-attr]
            taa.start <= PlanPeriod.end,
        )
        .order_by(PlanPeriod.start)
    )
    if taa.end is not None:
        stmt = stmt.where(PlanPeriod.start <= taa.end)
    return list(session.exec(stmt).all())
