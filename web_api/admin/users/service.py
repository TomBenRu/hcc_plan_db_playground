"""Admin-Benutzerverwaltung: Listen-Queries und Zusatz-Daten fuer die UI.

Diese Modul-Ebene bleibt absichtlich frei von FastAPI-Spezifika, damit die
Helper auch in Mutations-Endpoints (Phase 3) wiederverwendbar sind.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal, Optional

from sqlalchemy import func
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database.models import Person
from web_api.models.web_models import (
    PasswordResetToken,
    WebUser,
    WebUserRole,
    WebUserRoleLink,
)


# ── Filter-/Sort-Werte (string-literal-typed fuer Routen-Validierung) ────────

RoleFilter = Literal["all", "admin", "dispatcher", "employee", "accountant"]
StatusFilter = Literal["all", "active", "inactive", "invited"]
PersonLinkFilter = Literal["all", "linked", "unlinked"]
SortKey = Literal["name", "created", "last_modified", "last_login"]


@dataclass
class UserListRow:
    """View-Model fuer eine Tabellenzeile.

    Wir bauen das explizit als Dataclass, damit die Templates nur die Felder
    sehen, die wirklich gerendert werden — kein versehentliches Anzeigen von
    `hashed_password` u. ae. durch generisches Spreaden des ORM-Objekts.
    """

    id: uuid.UUID
    email: str
    is_active: bool
    person_id: Optional[uuid.UUID]
    person_name: Optional[str]
    roles: list[WebUserRole]
    created_at: object
    last_modified: object
    last_login_at: object
    password_changed_at: object
    pending_email: Optional[str]
    has_open_invitation: bool


@dataclass
class SidebarCounts:
    """Counts fuer die Sidebar-Filter — alle in einem Query gerechnet."""

    by_role: dict[str, int]
    by_status: dict[str, int]
    by_person_link: dict[str, int]
    total: int


# ── Persistente Hilfsabfragen ────────────────────────────────────────────────


def _open_invitation_user_ids(session: Session) -> set[uuid.UUID]:
    """User-IDs mit aktivem (nicht-verbrauchtem, nicht-abgelaufenem) Reset-Token.

    Wird als 'Einladung offen'-Marker genutzt — wir koennen das aus dem
    `PasswordResetToken`-Bestand ableiten, ohne eine zweite Tabelle einzubauen.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    rows = session.execute(
        select(PasswordResetToken.web_user_id).where(
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    ).scalars().all()
    return set(rows)


# ── Hauptabfrage ─────────────────────────────────────────────────────────────


def list_users(
    session: Session,
    *,
    role: RoleFilter = "all",
    status: StatusFilter = "all",
    person_link: PersonLinkFilter = "all",
    sort: SortKey = "name",
    search: str = "",
) -> list[UserListRow]:
    """Liefert die gefilterte/sortierte Benutzerliste als flache Zeilen.

    N+1-frei: Rollen werden via selectinload mitgeladen, Person-Namen werden
    in einem einzigen Batch-Query nachgezogen.
    """
    stmt = select(WebUser).options(selectinload(WebUser.role_links))  # type: ignore[arg-type]

    if search:
        like = f"%{search.strip().lower()}%"
        stmt = stmt.where(func.lower(WebUser.email).like(like))

    if status == "active":
        stmt = stmt.where(WebUser.is_active.is_(True))
    elif status == "inactive":
        stmt = stmt.where(WebUser.is_active.is_(False))
    # 'invited' filtern wir Python-seitig (verlangt Token-Join)

    if person_link == "linked":
        stmt = stmt.where(WebUser.person_id.is_not(None))
    elif person_link == "unlinked":
        stmt = stmt.where(WebUser.person_id.is_(None))

    if role != "all":
        # Subquery: user-IDs mit dieser Rolle
        role_enum = WebUserRole(role)
        sub = select(WebUserRoleLink.web_user_id).where(WebUserRoleLink.role == role_enum)
        stmt = stmt.where(WebUser.id.in_(sub))

    users: list[WebUser] = list(session.execute(stmt).scalars().all())

    open_invites = _open_invitation_user_ids(session)

    if status == "invited":
        users = [u for u in users if u.id in open_invites]

    # Person-Namen in einem Batch ziehen
    person_ids = [u.person_id for u in users if u.person_id]
    persons_by_id: dict[uuid.UUID, str] = {}
    if person_ids:
        rows = session.execute(
            select(Person.id, Person.f_name, Person.l_name).where(Person.id.in_(person_ids))
        ).all()
        persons_by_id = {pid: f"{f or ''} {l or ''}".strip() for pid, f, l in rows}

    result: list[UserListRow] = []
    for u in users:
        result.append(
            UserListRow(
                id=u.id,
                email=u.email,
                is_active=u.is_active,
                person_id=u.person_id,
                person_name=persons_by_id.get(u.person_id) if u.person_id else None,
                roles=sorted({lnk.role for lnk in u.role_links}, key=lambda r: r.value),
                created_at=u.created_at,
                last_modified=u.last_modified,
                last_login_at=u.last_login_at,
                password_changed_at=u.password_changed_at,
                pending_email=u.pending_email,
                has_open_invitation=u.id in open_invites,
            )
        )

    # Sortierung Python-seitig — Datenmengen sind klein (kein Production-System
    # mit > paar hundert Web-Usern), und die Sort-Keys mischen DB-Felder mit
    # abgeleiteten Werten (person_name aus Batch). Eine vereinheitlichte Sort-
    # Logik in Python ist wartbarer als zwei Pfade (DB-ORDER-BY vs. Python).
    if sort == "name":
        result.sort(key=lambda r: (r.person_name or "").lower() or r.email)
    elif sort == "created":
        result.sort(key=lambda r: r.created_at, reverse=True)
    elif sort == "last_modified":
        result.sort(key=lambda r: r.last_modified, reverse=True)
    elif sort == "last_login":
        # None = "nie eingeloggt" sortiert ans Ende
        result.sort(
            key=lambda r: (r.last_login_at is None, -(r.last_login_at.timestamp() if r.last_login_at else 0))
        )

    return result


# ── Sidebar-Counts ───────────────────────────────────────────────────────────


def compute_sidebar_counts(session: Session) -> SidebarCounts:
    """Berechnet alle Filter-Counts in moeglichst wenigen Queries.

    Optimiert fuer Klarheit, nicht maximale Effizienz — bei ein paar hundert
    Usern macht jeder zusaetzliche Query unter 5 ms aus.
    """
    by_role: dict[str, int] = {r.value: 0 for r in WebUserRole}
    role_rows = session.execute(
        select(WebUserRoleLink.role, func.count()).group_by(WebUserRoleLink.role)
    ).all()
    for role_val, cnt in role_rows:
        by_role[role_val.value if hasattr(role_val, "value") else role_val] = cnt

    total = session.execute(select(func.count()).select_from(WebUser)).scalar_one()
    active_count = session.execute(
        select(func.count()).select_from(WebUser).where(WebUser.is_active.is_(True))
    ).scalar_one()
    linked = session.execute(
        select(func.count()).select_from(WebUser).where(WebUser.person_id.is_not(None))
    ).scalar_one()

    open_invites = _open_invitation_user_ids(session)

    return SidebarCounts(
        by_role=by_role,
        by_status={
            "all": total,
            "active": active_count,
            "inactive": total - active_count,
            "invited": len(open_invites),
        },
        by_person_link={
            "all": total,
            "linked": linked,
            "unlinked": total - linked,
        },
        total=total,
    )


# ── Detail-Lookup ────────────────────────────────────────────────────────────


@dataclass
class UserDetail:
    """View-Model fuer den Drawer."""

    user: WebUser
    person: Optional[Person]
    has_open_invitation: bool
    roles: list[WebUserRole]


def get_user_detail(session: Session, user_id: uuid.UUID) -> UserDetail:
    """Laedt einen WebUser inkl. Rollen, verknuepfter Person und Einladungs-Status."""
    user = session.execute(
        select(WebUser)
        .where(WebUser.id == user_id)
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).scalar_one_or_none()
    if user is None:
        from fastapi import HTTPException, status

        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden")

    person = session.get(Person, user.person_id) if user.person_id else None
    open_invites = _open_invitation_user_ids(session)
    return UserDetail(
        user=user,
        person=person,
        has_open_invitation=user.id in open_invites,
        roles=sorted({lnk.role for lnk in user.role_links}, key=lambda r: r.value),
    )


# ── Personen-Suche fuer das Verknuepfungs-Dropdown ───────────────────────────


@dataclass
class PersonSearchResult:
    id: uuid.UUID
    f_name: str
    l_name: str
    email: str
    is_linked: bool  # True, wenn die Person bereits an einen WebUser haengt


def search_persons(
    session: Session,
    *,
    query: str,
    limit: int = 20,
    include_linked: bool = False,
) -> list[PersonSearchResult]:
    """Sucht Personen nach Name oder Email fuer das Person-Link-Dropdown.

    `include_linked=False` (Default): Personen, die schon mit einem anderen
    WebUser verknuepft sind, werden ausgeblendet — sonst landet der Admin
    direkt in einer UNIQUE-Violation.
    """
    q = query.strip().lower()
    if not q:
        return []

    like = f"%{q}%"
    stmt = (
        select(Person.id, Person.f_name, Person.l_name, Person.email)
        .where(Person.prep_delete.is_(None))
        .where(
            func.lower(Person.f_name).like(like)
            | func.lower(Person.l_name).like(like)
            | func.lower(Person.email).like(like)
        )
        .limit(limit * 2)  # Buffer, falls wir gleich filtern
    )
    rows = list(session.execute(stmt).all())

    linked_person_ids: set[uuid.UUID] = set()
    if not include_linked and rows:
        ids = [pid for pid, _, _, _ in rows]
        linked_person_ids = set(
            session.execute(
                select(WebUser.person_id).where(WebUser.person_id.in_(ids))
            ).scalars().all()
        )

    results: list[PersonSearchResult] = []
    for pid, f_name, l_name, email in rows:
        is_linked = pid in linked_person_ids
        if not include_linked and is_linked:
            continue
        results.append(
            PersonSearchResult(
                id=pid, f_name=f_name, l_name=l_name, email=email, is_linked=is_linked
            )
        )
        if len(results) >= limit:
            break
    return results
