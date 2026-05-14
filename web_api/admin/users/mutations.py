"""Admin-Benutzerverwaltung: Mutations + Guards.

Trennt die Schreib-Operationen sauber von Listen-Queries (`service.py`).
Jede Mutation prueft die Guards selbststaendig — der Router-Layer muss nur
den Caller authentifizieren und Body-Parameter weiterreichen.

Audit-Trail: jede Mutation logged ueber `logger.info("user_admin_action", ...)`,
sodass die spaetere `audit_log`-Tabelle die strukturierten extras ernten kann
(siehe Memory: todo_audit_infrastructure_april2026).
"""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from database.models import Person
from web_api.models.web_models import (
    WebUser,
    WebUserRole,
    WebUserRoleLink,
)

logger = logging.getLogger(__name__)


# ── Guards ───────────────────────────────────────────────────────────────────


def _count_active_admins(session: Session, exclude_user_id: Optional[uuid.UUID] = None) -> int:
    """Anzahl aktiver Admins, optional ohne einen bestimmten User."""
    stmt = (
        select(func.count(WebUser.id.distinct()))
        .select_from(WebUser)
        .join(WebUserRoleLink, WebUserRoleLink.web_user_id == WebUser.id)
        .where(WebUser.is_active.is_(True))
        .where(WebUserRoleLink.role == WebUserRole.admin)
    )
    if exclude_user_id is not None:
        stmt = stmt.where(WebUser.id != exclude_user_id)
    return session.execute(stmt).scalar_one()


def _load_target(session: Session, target_id: uuid.UUID) -> WebUser:
    target = session.get(WebUser, target_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden")
    return target


# ── Mutations ────────────────────────────────────────────────────────────────


def toggle_role(
    session: Session,
    *,
    actor: WebUser,
    target_id: uuid.UUID,
    role: WebUserRole,
    enable: bool,
) -> WebUser:
    """Fuegt eine Rolle hinzu (enable=True) oder entfernt sie (enable=False).

    Guards:
      - Eigene admin-Rolle nicht entfernbar (sonst lockt sich der Admin selbst aus).
      - Letzter aktiver Admin behaelt seine admin-Rolle (System ohne Admin = tot).
    """
    target = _load_target(session, target_id)
    existing = session.execute(
        select(WebUserRoleLink).where(
            WebUserRoleLink.web_user_id == target.id,
            WebUserRoleLink.role == role,
        )
    ).scalar_one_or_none()

    if enable:
        if existing is None:
            session.add(WebUserRoleLink(web_user_id=target.id, role=role))
        # idempotent — kein Fehler, wenn Rolle schon vorhanden
    else:
        # Self-Demote-Schutz fuer Admin
        if role == WebUserRole.admin and actor.id == target.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Sie können sich Ihre eigene Admin-Rolle nicht entziehen.",
            )
        # Letzter-Admin-Schutz
        if role == WebUserRole.admin:
            other_admins = _count_active_admins(session, exclude_user_id=target.id)
            if other_admins == 0:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Dies ist der letzte aktive Administrator — Rolle kann nicht entfernt werden.",
                )
        if existing is not None:
            session.delete(existing)

    session.commit()
    session.refresh(target)
    logger.info(
        "user_admin_action",
        extra={
            "action": "role_enable" if enable else "role_disable",
            "actor_id": str(actor.id),
            "target_id": str(target.id),
            "role": role.value,
        },
    )
    return target


def set_active(
    session: Session,
    *,
    actor: WebUser,
    target_id: uuid.UUID,
    is_active: bool,
) -> WebUser:
    """Aktiviert/deaktiviert einen User.

    Guards:
      - Eigenes Konto nicht deaktivierbar.
      - Letzter aktiver Admin nicht deaktivierbar.
    """
    target = _load_target(session, target_id)

    if not is_active:
        if actor.id == target.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Sie können Ihr eigenes Konto nicht deaktivieren.",
            )
        # Wenn Target ein Admin ist: pruefen, ob nach Deaktivierung noch einer bleibt
        target_is_admin = session.execute(
            select(WebUserRoleLink).where(
                WebUserRoleLink.web_user_id == target.id,
                WebUserRoleLink.role == WebUserRole.admin,
            )
        ).scalar_one_or_none() is not None
        if target_is_admin:
            other_admins = _count_active_admins(session, exclude_user_id=target.id)
            if other_admins == 0:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Dies ist der letzte aktive Administrator — Konto kann nicht deaktiviert werden.",
                )

    target.is_active = is_active
    session.add(target)
    session.commit()
    session.refresh(target)
    logger.info(
        "user_admin_action",
        extra={
            "action": "activate" if is_active else "deactivate",
            "actor_id": str(actor.id),
            "target_id": str(target.id),
        },
    )
    return target


def link_person(
    session: Session,
    *,
    actor: WebUser,
    target_id: uuid.UUID,
    person_id: Optional[uuid.UUID],
) -> WebUser:
    """Setzt oder loescht die Person-Verknuepfung.

    Wenn person_id is None: Verknuepfung loesen.
    Sonst: Person muss existieren, nicht soft-deleted sein, und darf nicht
    bereits an einen anderen WebUser haengen (UNIQUE-Constraint auf person_id).
    """
    target = _load_target(session, target_id)

    if person_id is None:
        target.person_id = None
    else:
        person = session.get(Person, person_id)
        if person is None or person.prep_delete is not None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Person nicht gefunden oder gelöscht.",
            )
        # Pruefen, ob die Person schon einem anderen WebUser zugeordnet ist
        other = session.execute(
            select(WebUser).where(
                WebUser.person_id == person_id,
                WebUser.id != target.id,
            )
        ).scalar_one_or_none()
        if other is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Diese Person ist bereits mit dem Konto {other.email} verknüpft.",
            )
        target.person_id = person_id

    session.add(target)
    session.commit()
    session.refresh(target)
    logger.info(
        "user_admin_action",
        extra={
            "action": "link_person" if person_id is not None else "unlink_person",
            "actor_id": str(actor.id),
            "target_id": str(target.id),
            "person_id": str(person_id) if person_id else None,
        },
    )
    return target
