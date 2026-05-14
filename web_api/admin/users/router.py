"""Admin-Benutzerverwaltung: Routen unter /admin/users.

Phase 2 + 3: Liste, Sidebar-Filter, Drawer mit Rollen-/Aktivierungs-/Person-
Mutations. Einladungs-Flow (Phase 4) wird separat angehaengt.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import Person
from web_api.admin.users.invitations import (
    build_invitation_email,
    create_invitation,
    resend_invitation,
)
from web_api.admin.users.mutations import (
    link_person,
    set_active,
    toggle_role,
)
from web_api.admin.users.service import (
    PersonLinkFilter,
    RoleFilter,
    SortKey,
    StatusFilter,
    compute_sidebar_counts,
    get_user_detail,
    list_users,
    search_persons,
)
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.config import Settings, get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import schedule_emails
from web_api.models.web_models import WebUser
from web_api.templating import templates

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


# ── Liste ────────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def users_index(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    role: RoleFilter = Query(default="all"),
    status: StatusFilter = Query(default="all"),
    person_link: PersonLinkFilter = Query(default="all"),
    sort: SortKey = Query(default="name"),
    search: str = Query(default=""),
):
    """Listenseite mit Sidebar-Filter und Tabelle."""
    rows = list_users(
        session,
        role=role,
        status=status,
        person_link=person_link,
        sort=sort,
        search=search,
    )
    counts = compute_sidebar_counts(session)

    return templates.TemplateResponse(
        "admin/users/index.html",
        {
            "request": request,
            "user": user,
            "rows": rows,
            "counts": counts,
            "filters": {
                "role": role,
                "status": status,
                "person_link": person_link,
                "sort": sort,
                "search": search,
            },
        },
    )


# ── Drawer (Detail-Partial) ──────────────────────────────────────────────────


@router.get("/{user_id}/drawer", response_class=HTMLResponse)
def user_drawer(
    user_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Liefert das Drawer-Partial fuer einen User (HTMX-Target)."""
    detail = get_user_detail(session, user_id)
    return templates.TemplateResponse(
        "admin/users/partials/drawer.html",
        {
            "request": request,
            "actor": user,
            "detail": detail,
        },
    )


# ── Rollen-Toggle ────────────────────────────────────────────────────────────


@router.post("/{user_id}/roles/{role}", response_class=HTMLResponse)
def update_role(
    user_id: uuid.UUID,
    role: WebUserRole,
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    enable: str | None = Form(default=None),
):
    """Aktiviert/deaktiviert eine Rolle. `enable=on` setzt sie, sonst entfernt sie."""
    toggle_role(
        session,
        actor=user,
        target_id=user_id,
        role=role,
        enable=enable is not None,
    )
    detail = get_user_detail(session, user_id)
    return templates.TemplateResponse(
        "admin/users/partials/drawer.html",
        {"request": request, "actor": user, "detail": detail},
    )


# ── Aktiv-Status ─────────────────────────────────────────────────────────────


@router.post("/{user_id}/active", response_class=HTMLResponse)
def update_active(
    user_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    is_active: str | None = Form(default=None),
):
    set_active(
        session,
        actor=user,
        target_id=user_id,
        is_active=is_active is not None,
    )
    detail = get_user_detail(session, user_id)
    return templates.TemplateResponse(
        "admin/users/partials/drawer.html",
        {"request": request, "actor": user, "detail": detail},
    )


# ── Person-Verknuepfung ──────────────────────────────────────────────────────


@router.get("/{user_id}/person-search", response_class=HTMLResponse)
def person_search(
    user_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = Query(default="", min_length=0),
):
    """Liefert Suchergebnis-Liste fuer die Person-Verknuepfung."""
    results = search_persons(session, query=q, limit=20, include_linked=False)
    return templates.TemplateResponse(
        "admin/users/partials/person_search_results.html",
        {
            "request": request,
            "results": results,
            "user_id": user_id,
            "query": q,
        },
    )


@router.post("/{user_id}/person", response_class=HTMLResponse)
def update_person_link(
    user_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    person_id: str | None = Form(default=None),
):
    """Setzt oder loescht die Person-Verknuepfung.

    Leeres `person_id` (oder fehlend) loest die Verknuepfung; sonst wird die
    angegebene Person verknuepft.
    """
    parsed: uuid.UUID | None = None
    if person_id:
        parsed = uuid.UUID(person_id)
    link_person(session, actor=user, target_id=user_id, person_id=parsed)
    detail = get_user_detail(session, user_id)
    return templates.TemplateResponse(
        "admin/users/partials/drawer.html",
        {"request": request, "actor": user, "detail": detail},
    )


# ── Einladungs-Flow ──────────────────────────────────────────────────────────


def _inviter_name(session: Session, actor: WebUser) -> str:
    """Liefert den fuer das Mail-Template angezeigten Inviter-Namen.

    Bevorzugt Person-Vorname/-Nachname, faellt sonst auf E-Mail-Prefix zurueck.
    """
    if actor.person_id:
        person = session.get(Person, actor.person_id)
        if person:
            return f"{person.f_name} {person.l_name}".strip()
    return actor.email.split("@")[0]


@router.get("/invite", response_class=HTMLResponse)
def invite_modal(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Liefert das Einladungs-Modal als HTMX-Partial."""
    return templates.TemplateResponse(
        "admin/users/partials/invite_modal.html",
        {"request": request, "actor": user, "error": None, "form": {}},
    )


@router.post("/invite", response_class=HTMLResponse)
def invite_submit(
    request: Request,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    email: str = Form(...),
    person_id: str | None = Form(default=None),
    role_admin: str | None = Form(default=None),
    role_dispatcher: str | None = Form(default=None),
    role_employee: str | None = Form(default=None),
    role_accountant: str | None = Form(default=None),
):
    """Legt einen neuen User an, erzeugt Setup-Token und verschickt die Setup-Mail."""
    roles: set[WebUserRole] = set()
    if role_admin:
        roles.add(WebUserRole.admin)
    if role_dispatcher:
        roles.add(WebUserRole.dispatcher)
    if role_employee:
        roles.add(WebUserRole.employee)
    if role_accountant:
        roles.add(WebUserRole.accountant)

    parsed_person: uuid.UUID | None = uuid.UUID(person_id) if person_id else None

    from fastapi import HTTPException

    try:
        new_user, token = create_invitation(
            session,
            actor=user,
            email=email,
            roles=roles,
            person_id=parsed_person,
        )
    except HTTPException as exc:
        # Modal mit Fehler-Banner neu rendern
        return templates.TemplateResponse(
            "admin/users/partials/invite_modal.html",
            {
                "request": request,
                "actor": user,
                "error": exc.detail,
                "form": {
                    "email": email,
                    "role_admin": role_admin,
                    "role_dispatcher": role_dispatcher,
                    "role_employee": role_employee,
                    "role_accountant": role_accountant,
                    "person_id": person_id,
                },
            },
            status_code=200,
        )

    payload = build_invitation_email(
        new_user, token, settings, inviter_name=_inviter_name(session, user)
    )
    schedule_emails(background_tasks, [payload], session)

    return templates.TemplateResponse(
        "admin/users/partials/invite_success.html",
        {"request": request, "new_user": new_user},
    )


@router.post("/{user_id}/resend-invite", response_class=HTMLResponse)
def resend_invite(
    user_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Schickt eine neue Setup-Mail; invalidiert vorher offene Tokens."""
    target, token = resend_invitation(session, actor=user, target_id=user_id)
    payload = build_invitation_email(
        target, token, settings, inviter_name=_inviter_name(session, user)
    )
    schedule_emails(background_tasks, [payload], session)

    detail = get_user_detail(session, user_id)
    return templates.TemplateResponse(
        "admin/users/partials/drawer.html",
        {"request": request, "actor": user, "detail": detail},
    )
