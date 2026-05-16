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
    LocationPlanPeriod,
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


@dataclass(slots=True)
class PersonInOtherTeamWarning:
    """Person hat bereits eine offene Mitgliedschaft in einem **anderen** Team.

    Im Gegensatz zu ``LocationOccupiedConflict`` ist das KEIN harter Block —
    Person↔Team ist N:N und Doppel-Mitgliedschaft ist erlaubt. Aber der Dialog
    gibt dem Admin die Chance, bewusst zuzuordnen oder die Altmitgliedschaft
    zu schliessen. Der Router rendert dafuer ``conflict_dialog.html`` mit
    ``kind="person_in_other_team"`` (3 Optionen: Trotzdem / Replace /
    Abbrechen)."""

    existing_assign_id: uuid.UUID
    existing_start: date
    existing_end: date | None
    blocking_team_id: uuid.UUID
    blocking_team_name: str


@dataclass(slots=True)
class LocationOccupiedConflict:
    """Standort ist bereits durch ein **anderes** Team belegt (offene TLA).

    Wird vom Router auf den ``conflict_dialog.html``-Branch
    ``kind="location_occupied"`` gemappt — der zeigt das blockierende Team und
    bietet einen Replace-Button, der die Altzuordnung schliesst und das neue
    TLA atomar anlegt."""

    existing_assign_id: uuid.UUID
    existing_start: date
    existing_end: date | None
    blocking_team_id: uuid.UUID
    blocking_team_name: str


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


def _open_blocking_team_actor_assign(
    session: Session,
    *,
    person_id: uuid.UUID,
    other_than_team_id: uuid.UUID,
    today: date,
) -> TeamActorAssign | None:
    """Liefert eine offene TAA der Person, die zu einem **anderen** Team als
    ``other_than_team_id`` gehoert.

    Anders als bei Standort↔Team ist das KEIN harter Block (Person↔Team ist
    N:N), sondern Grundlage fuer den Warning-Dialog ``person_in_other_team``.
    Sortiert nach ``start`` aufsteigend — bei mehreren parallelen Mitglied-
    schaften wird die aelteste zurueckgegeben (die hat im Replace-Pfad das
    laengste ``end > start``-Fenster und kann am sichersten geschlossen
    werden).
    """
    stmt = (
        select(TeamActorAssign)
        .where(
            TeamActorAssign.person_id == person_id,
            TeamActorAssign.team_id != other_than_team_id,
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


def list_past_team_members(session: Session, team_id: uuid.UUID) -> list[TeamActorAssign]:
    """Vergangene Mitgliedschaften (``end <= today``), zuletzt beendete zuerst.
    Aktive (``end IS NULL`` oder ``end > today``) bleiben aussen vor."""
    today = date.today()
    stmt = (
        select(TeamActorAssign)
        .where(
            TeamActorAssign.team_id == team_id,
            TeamActorAssign.end.is_not(None),  # type: ignore[union-attr]
            TeamActorAssign.end <= today,  # type: ignore[union-attr]
        )
        .order_by(TeamActorAssign.end.desc())  # type: ignore[union-attr]
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


def list_past_person_teams(
    session: Session, person_id: uuid.UUID
) -> list[TeamActorAssign]:
    """Vergangene Team-Mitgliedschaften einer Person — Spiegel zu
    ``list_past_team_members`` aus Person-Sicht."""
    today = date.today()
    stmt = (
        select(TeamActorAssign)
        .where(
            TeamActorAssign.person_id == person_id,
            TeamActorAssign.end.is_not(None),  # type: ignore[union-attr]
            TeamActorAssign.end <= today,  # type: ignore[union-attr]
        )
        .order_by(TeamActorAssign.end.desc())  # type: ignore[union-attr]
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


def _open_blocking_team_location_assign(
    session: Session,
    *,
    location_id: uuid.UUID,
    other_than_team_id: uuid.UUID,
    today: date,
) -> TeamLocationAssign | None:
    """Liefert eine offene TLA fuer ``location_id``, die zu einem **anderen**
    Team als ``other_than_team_id`` gehoert.

    Geschaeftsregel (2026-05-16): ein Standort darf zu jedem Zeitpunkt
    hoechstens einem Team zugeordnet sein. Dieser Helper wird in
    ``add_team_location`` aufgerufen und liefert die blockierende TLA, falls
    eine existiert. ``start <= today`` schraenkt bewusst NICHT ein —
    Future-TLAs sind ebenfalls blockierend, damit kein Overlap entstehen kann.
    """
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.location_of_work_id == location_id,
            TeamLocationAssign.team_id != other_than_team_id,
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


def list_past_team_locations(
    session: Session, team_id: uuid.UUID
) -> list[TeamLocationAssign]:
    """Vergangene Standort-Zuordnungen eines Teams (``end <= today``)."""
    today = date.today()
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.team_id == team_id,
            TeamLocationAssign.end.is_not(None),  # type: ignore[union-attr]
            TeamLocationAssign.end <= today,  # type: ignore[union-attr]
        )
        .order_by(TeamLocationAssign.end.desc())  # type: ignore[union-attr]
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


def list_past_location_teams(
    session: Session, location_id: uuid.UUID
) -> list[TeamLocationAssign]:
    """Vergangene Team-Zuordnungen einer Location — Spiegel zu
    ``list_past_team_locations`` aus Location-Sicht."""
    today = date.today()
    stmt = (
        select(TeamLocationAssign)
        .where(
            TeamLocationAssign.location_of_work_id == location_id,
            TeamLocationAssign.end.is_not(None),  # type: ignore[union-attr]
            TeamLocationAssign.end <= today,  # type: ignore[union-attr]
        )
        .order_by(TeamLocationAssign.end.desc())  # type: ignore[union-attr]
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
    force_other_team: bool = False,
) -> TeamActorAssign:
    """Erzeugt einen ``TeamActorAssign`` (Default ``start=heute``).

    Wirft 409 mit ``AssignConflict``, wenn eine offene Mitgliedschaft im
    **gleichen** Team existiert. Wirft 409 mit ``PersonInOtherTeamWarning``,
    wenn die Person eine offene Mitgliedschaft in einem **anderen** Team hat
    und ``force_other_team`` nicht gesetzt ist — Person↔Team ist N:N, aber
    der Dialog gibt dem Admin die Chance, das bewusst zu bestaetigen.
    """
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

    # 1) selbe (Person, Team) bereits offen → Standard-Konflikt (hard block)
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

    # 2) Person hat offene Mitgliedschaft in einem ANDEREN Team → Warning
    #    (kein Block; Admin kann via force_other_team durchwinken oder
    #    via replace_team_member die Alt-Mitgliedschaft schliessen)
    if not force_other_team:
        blocking = _open_blocking_team_actor_assign(
            session, person_id=person_id, other_than_team_id=team.id, today=today
        )
        if blocking is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=PersonInOtherTeamWarning(
                    existing_assign_id=blocking.id,
                    existing_start=blocking.start,
                    existing_end=blocking.end,
                    blocking_team_id=blocking.team_id,
                    blocking_team_name=blocking.team.name,
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


def replace_team_member(
    session: Session,
    *,
    person: Person,
    new_team: Team,
    new_start: date | None,
    actor: WebUser,
) -> TeamActorAssign:
    """Loest eine Person↔Team-Mehrfachbelegung atomar auf: schliesst die
    blockierende offene Mitgliedschaft mit ``end = max(new_start - 1, today)``
    und legt eine neue Mitgliedschaft fuer ``new_team`` an.

    Datums-Logik:
    - ``new_start = today`` → ``old.end = today`` (1 Tag Ueberlappung am
      letzten Tag der alten Mitgliedschaft — wuerden wir gestern setzen,
      blockt der ``end >= today``-Check)
    - ``new_start > today`` → ``old.end = new_start - 1`` (sauberer Uebergang,
      kein Overlap)
    """
    from datetime import timedelta

    if person.project_id != new_team.project_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Person und Team gehoeren nicht zum selben Projekt",
        )

    today = date.today()
    effective_new_start = new_start or today
    if new_start is not None and new_start < today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Start-Datum darf nicht in der Vergangenheit liegen",
        )

    blocking = _open_blocking_team_actor_assign(
        session, person_id=person.id, other_than_team_id=new_team.id, today=today
    )
    if blocking is None:
        # Race: blockierende Mitgliedschaft wurde zwischenzeitlich beendet —
        # einfacher normaler Add (mit force, falls jemand inzwischen eine
        # NEUE andere Mitgliedschaft angelegt hat — Admin hat die Replace-
        # Aktion bewusst gewaehlt).
        return add_team_member(
            session,
            team=new_team,
            person_id=person.id,
            start=new_start,
            actor=actor,
            force_other_team=True,
        )

    desired_old_end = effective_new_start - timedelta(days=1)
    old_end = max(desired_old_end, today)

    if old_end <= blocking.start:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Die bestehende Mitgliedschaft beginnt am "
                f"{blocking.start.strftime('%d.%m.%Y')}. Ein Beenden vor "
                "diesem Datum ist nicht moeglich."
            ),
        )

    blocking.end = old_end
    new_assign = TeamActorAssign(
        person=person, team=new_team, start=effective_new_start, end=None
    )
    session.add(new_assign)
    session.commit()
    session.refresh(new_assign)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_member_replaced",
            "actor_id": str(actor.id),
            "target_id": str(new_assign.id),
            "previous_assign_id": str(blocking.id),
        },
    )
    return new_assign


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

    # 1) selbe (Location, Team) bereits offen → Standard-Konflikt
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

    # 2) Location bereits einem **anderen** Team offen zugeordnet
    blocking = _open_blocking_team_location_assign(
        session, location_id=location_id, other_than_team_id=team.id, today=today
    )
    if blocking is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=LocationOccupiedConflict(
                existing_assign_id=blocking.id,
                existing_start=blocking.start,
                existing_end=blocking.end,
                blocking_team_id=blocking.team_id,
                blocking_team_name=blocking.team.name,
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


def replace_team_location(
    session: Session,
    *,
    location: LocationOfWork,
    new_team: Team,
    actor: WebUser,
) -> TeamLocationAssign:
    """Loest eine offene Standort↔Team-Doppelbelegung atomar auf.

    Schliesst die blockierende offene TLA mit ``end=today`` und legt eine
    neue TLA fuer ``new_team`` mit ``start=today+1`` an. Damit ist die
    Reihenfolge eindeutig (kein Datum liegt in der Vergangenheit; das alte
    TLA endet bevor das neue beginnt).

    Sonderfall: blockierende TLA hat ``start >= today`` — dann waere
    ``end <= start`` und der DB-Constraint wuerde greifen. In dem Fall
    erwarten wir, dass der User die Future-TLA manuell entfernt; wir
    geben hier einen 422 zurueck."""
    from datetime import timedelta

    if location.project_id != new_team.project_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Standort und Team gehoeren nicht zum selben Projekt",
        )

    today = date.today()
    blocking = _open_blocking_team_location_assign(
        session, location_id=location.id, other_than_team_id=new_team.id, today=today
    )
    if blocking is None:
        # Race: blockierendes Team wurde zwischenzeitlich beendet. Fallback
        # auf normales Add (start=today).
        return add_team_location(
            session, team=new_team, location_id=location.id, start=None, actor=actor
        )

    if blocking.start >= today:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Zuordnung zu „{blocking.team.name}\" beginnt erst am "
                f"{blocking.start.strftime('%d.%m.%Y')}. Bitte diese zuerst "
                "im Drawer des Teams entfernen."
            ),
        )

    new_start = today + timedelta(days=1)
    blocking.end = today
    new_assign = TeamLocationAssign(
        location_of_work=location, team=new_team, start=new_start, end=None
    )
    session.add(new_assign)
    session.commit()
    session.refresh(new_assign)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_location_replaced",
            "actor_id": str(actor.id),
            "target_id": str(new_assign.id),
            "previous_assign_id": str(blocking.id),
        },
    )
    return new_assign


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


def list_open_overlapping_plan_periods_for_tla(
    session: Session, *, tla: TeamLocationAssign
) -> list[PlanPeriod]:
    """Spiegel zu ``list_open_overlapping_plan_periods_for_taa`` fuer
    Standort↔Team-Zuordnungen.

    Liefert offene PPs des TLA-Teams (``closed=False AND prep_delete IS NULL``),
    deren Zeitraum mit dem TLA-Zeitraum ueberschneidet und fuer die noch
    **keine** LocationPlanPeriod fuer den Standort existiert.
    """
    stmt = (
        select(PlanPeriod)
        .outerjoin(
            LocationPlanPeriod,
            (LocationPlanPeriod.plan_period_id == PlanPeriod.id)
            & (LocationPlanPeriod.location_of_work_id == tla.location_of_work_id),
        )
        .where(
            PlanPeriod.team_id == tla.team_id,
            PlanPeriod.closed.is_(False),  # type: ignore[union-attr]
            PlanPeriod.prep_delete.is_(None),  # type: ignore[union-attr]
            LocationPlanPeriod.id.is_(None),  # type: ignore[union-attr]
            tla.start <= PlanPeriod.end,
        )
        .order_by(PlanPeriod.start)
    )
    if tla.end is not None:
        stmt = stmt.where(PlanPeriod.start <= tla.end)
    return list(session.exec(stmt).all())
