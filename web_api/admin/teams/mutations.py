"""Admin-Teams-Mutations: Schreib-Pfade fuer Team- und Standort-Stammdaten.

- Anlage + Umbenennung + Notes-Pflege fuer Team (Admin)
- Anlage + Stammdaten-Pflege fuer Standort (Admin)
- Adress-Drei-Faelle-Logik (neue Zeile / in-place / Verknuepfung loesen) im
  Mutation-Layer — bewusst nicht im DB-Service, damit das 1:1-Verhalten der
  ``Address.location_of_work``-Back-Relation explizit bleibt.

Audit-Pattern analog ``web_api.admin.users.mutations``: ``logger.info`` mit
strukturiertem ``extra``-Dict.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlmodel import Session, select

from database.models import (
    Address,
    LocationOfWork,
    Person,
    Project,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)
from web_api.admin.teams import guards
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink

logger = logging.getLogger(__name__)


# ─── Adress-Felder ────────────────────────────────────────────────────────────


@dataclass(slots=True)
class AddressFields:
    """Adress-Eingabefelder aus dem Drawer-Form. Leere Strings werden bei
    Bedarf auf ``None`` normalisiert."""

    name: str | None
    street: str | None
    postal_code: str | None
    city: str | None

    def is_empty(self) -> bool:
        return not any((self.name, self.street, self.postal_code, self.city))

    def differs_from(self, address: Address) -> bool:
        return (
            (self.name or None) != address.name
            or (self.street or None) != address.street
            or (self.postal_code or None) != address.postal_code
            or (self.city or None) != address.city
        )


def _normalize(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def address_fields_from_form(
    name: str | None,
    street: str | None,
    postal_code: str | None,
    city: str | None,
) -> AddressFields:
    return AddressFields(
        name=_normalize(name),
        street=_normalize(street),
        postal_code=_normalize(postal_code),
        city=_normalize(city),
    )


# ─── Validierung ──────────────────────────────────────────────────────────────


class DuplicateNameError(HTTPException):
    """Spezieller HTTP-Fehler bei UniqueConstraint-Verletzung auf
    ``(project_id, name)``. Vor dem Flush abgefangen, damit das Form-Card-Partial
    den Fehler inline rendert."""

    def __init__(self, entity: str, name: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ein {entity} mit dem Namen «{name}» existiert bereits.",
        )


def _ensure_unique_team_name(
    session: Session, project_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None
) -> None:
    stmt = select(func.count()).select_from(Team).where(
        Team.project_id == project_id,
        func.lower(Team.name) == name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(Team.id != exclude_id)
    count = session.execute(stmt).scalar_one()
    if count > 0:
        raise DuplicateNameError("Team", name)


def _ensure_unique_location_name(
    session: Session, project_id: uuid.UUID, name: str, exclude_id: uuid.UUID | None
) -> None:
    stmt = select(func.count()).select_from(LocationOfWork).where(
        LocationOfWork.project_id == project_id,
        func.lower(LocationOfWork.name) == name.lower(),
    )
    if exclude_id is not None:
        stmt = stmt.where(LocationOfWork.id != exclude_id)
    count = session.execute(stmt).scalar_one()
    if count > 0:
        raise DuplicateNameError("Standort", name)


# ─── Dispatcher-Pool ──────────────────────────────────────────────────────────


def search_dispatcher_pool(
    session: Session,
    project_id: uuid.UUID,
    q: str,
    *,
    limit: int = 20,
) -> list[Person]:
    """Aktive Personen mit Dispatcher-Rolle im Projekt — gefiltert nach Name/E-Mail.

    Pool: Person.project_id == project_id, prep_delete IS NULL, und Person ist
    via WebUser.person_id mit einem aktiven WebUser verknuepft, der die
    Dispatcher-Rolle besitzt.
    """
    pattern = f"%{q.strip()}%"
    stmt = (
        select(Person)
        .join(WebUser, WebUser.person_id == Person.id)
        .join(WebUserRoleLink, WebUserRoleLink.web_user_id == WebUser.id)
        .where(
            Person.project_id == project_id,
            Person.prep_delete.is_(None),  # type: ignore[union-attr]
            WebUser.is_active.is_(True),  # type: ignore[union-attr]
            WebUserRoleLink.role == WebUserRole.dispatcher,
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


# ─── Team-Mutations ───────────────────────────────────────────────────────────


def create_team(
    session: Session,
    *,
    project: Project,
    name: str,
    dispatcher_id: uuid.UUID | None,
    notes: str | None,
    actor: WebUser,
) -> Team:
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name ist Pflichtfeld")
    _ensure_unique_team_name(session, project.id, name, exclude_id=None)

    dispatcher = None
    if dispatcher_id is not None:
        dispatcher = session.get(Person, dispatcher_id)
        if dispatcher is None or dispatcher.project_id != project.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dispatcher nicht gefunden"
            )

    team = Team(
        name=name,
        notes=_normalize(notes),
        project=project,
        dispatcher=dispatcher,
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    logger.info(
        "teams_admin_action",
        extra={"action": "team_created", "actor_id": str(actor.id), "target_id": str(team.id)},
    )
    return team


def update_team_stammdaten(
    session: Session,
    *,
    team: Team,
    name: str,
    notes: str | None,
    actor: WebUser,
) -> Team:
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name ist Pflichtfeld")
    _ensure_unique_team_name(session, team.project_id, name, exclude_id=team.id)

    renamed = name != team.name
    team.name = name
    team.notes = _normalize(notes)
    session.commit()
    session.refresh(team)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_renamed" if renamed else "team_notes_changed",
            "actor_id": str(actor.id),
            "target_id": str(team.id),
        },
    )
    return team


def update_team_dispatcher(
    session: Session,
    *,
    team: Team,
    dispatcher_id: uuid.UUID | None,
    actor: WebUser,
) -> Team:
    if dispatcher_id is None:
        team.dispatcher = None
    else:
        dispatcher = session.get(Person, dispatcher_id)
        if dispatcher is None or dispatcher.project_id != team.project_id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dispatcher nicht gefunden"
            )
        team.dispatcher = dispatcher
    session.commit()
    session.refresh(team)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_dispatcher_changed",
            "actor_id": str(actor.id),
            "target_id": str(team.id),
        },
    )
    return team


# ─── Standort-Mutations ───────────────────────────────────────────────────────


def _apply_address_fields(
    session: Session,
    *,
    location: LocationOfWork,
    project: Project,
    fields: AddressFields,
) -> None:
    """Drei-Faelle-Logik fuer Adress-Verlinkung gemaess PRD US-08.

    1. Felder leer + bestehende Adresse → Verknuepfung loesen (Address-Zeile
       bleibt stehen, um spaeter via DB-Cleanup-Job aufzuraeumen).
    2. Felder gefuellt + keine bestehende Adresse → neue Address-Zeile anlegen.
    3. Felder gefuellt + bestehende Adresse → in-place-Update der vorhandenen
       Adresse (1:1-Modell, kein Sharing).
    """
    if fields.is_empty():
        if location.address is not None:
            location.address = None
        return

    if location.address is None:
        addr = Address(
            name=fields.name,
            street=fields.street,
            postal_code=fields.postal_code,
            city=fields.city,
            project=project,
        )
        session.add(addr)
        session.flush()
        location.address = addr
        return

    # In-place-Update via session.get — analog ``db_services.location_of_work.update``.
    # Direktes Attribut-Setzen auf ``location.address`` greift unter manchen
    # Lazy-Load-Konstellationen nicht (Identity-Map-Quirk), daher hier explizit
    # das Address-Objekt aus der Session-Identity-Map holen.
    addr_db = session.get(Address, location.address.id)
    if addr_db is None:  # defensiv, sollte nicht passieren
        return
    addr_db.name = fields.name
    addr_db.street = fields.street
    addr_db.postal_code = fields.postal_code
    addr_db.city = fields.city


def create_location(
    session: Session,
    *,
    project: Project,
    name: str,
    address_fields: AddressFields,
    nr_actors: int,
    actor: WebUser,
) -> LocationOfWork:
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name ist Pflichtfeld")
    _ensure_unique_location_name(session, project.id, name, exclude_id=None)

    loc = LocationOfWork(name=name, project=project, nr_actors=nr_actors)
    session.add(loc)
    session.flush()
    _apply_address_fields(session, location=loc, project=project, fields=address_fields)
    session.commit()
    session.refresh(loc)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "location_created",
            "actor_id": str(actor.id),
            "target_id": str(loc.id),
        },
    )
    return loc


# ─── Soft-/Hard-Delete ────────────────────────────────────────────────────────


def _cleanup_open_assigns_for_team(session: Session, *, team_id: uuid.UUID) -> None:
    """Vor Soft-Delete eines Teams: offene Mitgliedschaften/Standortzuweisungen
    mit ``end=today`` schliessen, Future-Eintraege loeschen.

    Aktive Eintraege bewahren Historie — closed end-date fuer Audit-Konsistenz.
    Future-Eintraege haben noch keine historische Bedeutung → DELETE.
    """
    today = date.today()
    # TAA
    open_taas = session.exec(
        select(TeamActorAssign).where(
            TeamActorAssign.team_id == team_id,
            or_(TeamActorAssign.end.is_(None), TeamActorAssign.end > today),  # type: ignore[union-attr]
        )
    ).all()
    for taa in open_taas:
        if taa.start > today:
            session.delete(taa)
        elif taa.end is None or taa.end > today:
            taa.end = today
    # TLA analog
    open_tlas = session.exec(
        select(TeamLocationAssign).where(
            TeamLocationAssign.team_id == team_id,
            or_(TeamLocationAssign.end.is_(None), TeamLocationAssign.end > today),  # type: ignore[union-attr]
        )
    ).all()
    for tla in open_tlas:
        if tla.start > today:
            session.delete(tla)
        elif tla.end is None or tla.end > today:
            tla.end = today


def soft_delete_team(session: Session, *, team: Team, actor: WebUser) -> Team:
    if team.prep_delete is not None:
        return team  # idempotent
    active = guards.count_active_plan_periods_for_team(session, team.id)
    if active > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Team kann nicht entfernt werden — {active} aktive Planungsperiode(n).",
        )
    _cleanup_open_assigns_for_team(session, team_id=team.id)
    team.prep_delete = datetime.now(timezone.utc)
    session.commit()
    session.refresh(team)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_soft_deleted",
            "actor_id": str(actor.id),
            "target_id": str(team.id),
        },
    )
    return team


def restore_team(session: Session, *, team: Team, actor: WebUser) -> Team:
    team.prep_delete = None
    session.commit()
    session.refresh(team)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_restored",
            "actor_id": str(actor.id),
            "target_id": str(team.id),
        },
    )
    return team


def hard_delete_team(
    session: Session, *, team: Team, name_confirmation: str, actor: WebUser
) -> None:
    """Endgueltiges DELETE. Blockiert bei JEDER existierenden PlanPeriod
    (Schutz vor cascade_delete-Verlust historischer Plaene)."""
    if name_confirmation.strip() != team.name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name-Bestätigung stimmt nicht überein.",
        )
    any_pps = guards.count_any_plan_periods_for_team(session, team.id)
    if any_pps > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Endgültiges Löschen nicht möglich — {any_pps} Plan-Period(en) "
                "existieren (auch historische). Eintrag bleibt im Inaktiv-Filter."
            ),
        )
    team_id_for_log = str(team.id)
    session.delete(team)
    session.commit()
    logger.info(
        "teams_admin_action",
        extra={
            "action": "team_hard_deleted",
            "actor_id": str(actor.id),
            "target_id": team_id_for_log,
        },
    )


def _cleanup_open_assigns_for_location(
    session: Session, *, location_id: uuid.UUID
) -> None:
    today = date.today()
    open_tlas = session.exec(
        select(TeamLocationAssign).where(
            TeamLocationAssign.location_of_work_id == location_id,
            or_(TeamLocationAssign.end.is_(None), TeamLocationAssign.end > today),  # type: ignore[union-attr]
        )
    ).all()
    for tla in open_tlas:
        if tla.start > today:
            session.delete(tla)
        elif tla.end is None or tla.end > today:
            tla.end = today


def soft_delete_location(
    session: Session, *, location: LocationOfWork, actor: WebUser
) -> LocationOfWork:
    if location.prep_delete is not None:
        return location
    lpp_count = guards.count_active_location_plan_periods(session, location.id)
    if lpp_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Standort kann nicht entfernt werden — {lpp_count} aktive Location-PlanPeriod(n).",
        )
    _cleanup_open_assigns_for_location(session, location_id=location.id)
    location.prep_delete = datetime.now(timezone.utc)
    session.commit()
    session.refresh(location)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "location_soft_deleted",
            "actor_id": str(actor.id),
            "target_id": str(location.id),
        },
    )
    return location


def restore_location(
    session: Session, *, location: LocationOfWork, actor: WebUser
) -> LocationOfWork:
    location.prep_delete = None
    session.commit()
    session.refresh(location)
    logger.info(
        "teams_admin_action",
        extra={
            "action": "location_restored",
            "actor_id": str(actor.id),
            "target_id": str(location.id),
        },
    )
    return location


def hard_delete_location(
    session: Session,
    *,
    location: LocationOfWork,
    name_confirmation: str,
    actor: WebUser,
) -> None:
    if name_confirmation.strip() != location.name:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Name-Bestätigung stimmt nicht überein.",
        )
    lpp_count = guards.count_any_location_plan_periods(session, location.id)
    if lpp_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Endgültiges Löschen nicht möglich — {lpp_count} Location-PlanPeriod(n) "
                "existieren."
            ),
        )
    loc_id_for_log = str(location.id)
    session.delete(location)
    session.commit()
    logger.info(
        "teams_admin_action",
        extra={
            "action": "location_hard_deleted",
            "actor_id": str(actor.id),
            "target_id": loc_id_for_log,
        },
    )


def update_location_admin_fields(
    session: Session,
    *,
    location: LocationOfWork,
    name: str,
    address_fields: AddressFields,
    actor: WebUser,
) -> LocationOfWork:
    name = name.strip()
    if not name:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name ist Pflichtfeld")
    _ensure_unique_location_name(
        session, location.project_id, name, exclude_id=location.id
    )

    renamed = name != location.name
    address_changed = (
        location.address is None and not address_fields.is_empty()
    ) or (
        location.address is not None
        and (address_fields.is_empty() or address_fields.differs_from(location.address))
    )

    location.name = name
    _apply_address_fields(
        session, location=location, project=location.project, fields=address_fields
    )
    session.commit()
    session.refresh(location)

    if renamed:
        logger.info(
            "teams_admin_action",
            extra={
                "action": "location_renamed",
                "actor_id": str(actor.id),
                "target_id": str(location.id),
            },
        )
    if address_changed:
        logger.info(
            "teams_admin_action",
            extra={
                "action": "location_address_changed",
                "actor_id": str(actor.id),
                "target_id": str(location.id),
            },
        )
    return location
