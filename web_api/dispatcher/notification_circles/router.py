"""Disponenten-View: Notification-Circles pro Arbeitsort.

Liefert einen optionalen Whitelist-Filter zum Auto-Benachrichtigungs-
Kreis bei Absagen — pro Arbeitsort konfigurierbar. Phase 3: nur
Lese-Endpoints (Liste + Detail). Mutationen folgen in Phase 4.
"""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from database.models import LocationOfWork
from web_api.auth.dependencies import require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.notification_circles.service import (
    add_members,
    assert_dispatcher_owns_location,
    get_circle_members,
    get_eligible_users_for_location,
    list_locations_for_dispatcher,
    remove_member,
    set_location_restriction_mode,
)
from web_api.models.web_models import WebUser, WebUserRole
from web_api.templating import templates


router = APIRouter(
    prefix="/dispatcher/notification-circles",
    tags=["dispatcher-notification-circles"],
)


_FILTER_LABELS = {
    "": "Alle",
    "restricted": "Eingeschränkt",
    "open": "Offen",
}


def _render_detail_pane(
    request: Request,
    session: Session,
    user: WebUser,
    location_id: uuid.UUID,
) -> HTMLResponse:
    """Re-rendert das #detail-pane als HTML-Fragment mit aktuellem State.

    Wird nach jeder Mutation (Toggle / Add / Remove) zurueckgegeben, plus
    `HX-Trigger: notification-circle-changed` damit die Index-Liste auf
    der anderen Browser-Tab-Seite oder Sidebar live nachzieht.
    """
    loc = session.get(LocationOfWork, location_id)
    if loc is None or loc.prep_delete is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")

    members = get_circle_members(session, location_id)
    eligible_count = len(get_eligible_users_for_location(session, location_id))

    response = templates.TemplateResponse(
        "notification_circles/partials/_detail_pane.html",
        {
            "request": request,
            "loc": loc,
            "members": members,
            "eligible_count": eligible_count,
        },
    )
    response.headers["HX-Trigger"] = "notification-circle-changed"
    return response


@router.get("", response_class=HTMLResponse)
def list_circles(
    request: Request,
    filter: str = "",
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Liste aller Arbeitsorte des Dispatchers mit Modus-Status + Member-Count.

    `filter`-Werte:
      - `""` (Default): alle Arbeitsorte.
      - `"restricted"`: nur Orte mit aktivem Whitelist-Modus.
      - `"open"`: nur Orte ohne Whitelist (Default-Verhalten).
    """
    summaries = list_locations_for_dispatcher(session, user)

    if filter == "restricted":
        summaries = [s for s in summaries if s.restricted]
    elif filter == "open":
        summaries = [s for s in summaries if not s.restricted]

    return templates.TemplateResponse(
        "notification_circles/index.html",
        {
            "request": request,
            "user": user,
            "summaries": summaries,
            "filter": filter,
            "filter_labels": _FILTER_LABELS,
        },
    )


@router.get("/{location_id}", response_class=HTMLResponse)
def detail(
    location_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Detail-View eines Arbeitsorts: Mode-Status + Member-Liste."""
    assert_dispatcher_owns_location(session, user, location_id)

    loc = session.get(LocationOfWork, location_id)
    if loc is None or loc.prep_delete is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")

    members = get_circle_members(session, location_id)
    eligible_count = len(get_eligible_users_for_location(session, location_id))

    return templates.TemplateResponse(
        "notification_circles/detail.html",
        {
            "request": request,
            "user": user,
            "loc": loc,
            "members": members,
            "eligible_count": eligible_count,
        },
    )


# ── Mutationen ───────────────────────────────────────────────────────────────


@router.post("/{location_id}/toggle-mode", response_class=HTMLResponse)
def toggle_mode(
    location_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Flippt `notification_circle_restricted` und gibt das #detail-pane neu zurueck."""
    assert_dispatcher_owns_location(session, user, location_id)

    loc = session.get(LocationOfWork, location_id)
    if loc is None or loc.prep_delete is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")

    set_location_restriction_mode(session, location_id, not loc.notification_circle_restricted, user)
    return _render_detail_pane(request, session, user, location_id)


@router.get("/{location_id}/add-member", response_class=HTMLResponse)
def add_member_modal(
    location_id: uuid.UUID,
    request: Request,
    q: str = "",
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Rendert das Pool-Auswahl-Modal. Mit `?q=` server-seitig filterbar."""
    assert_dispatcher_owns_location(session, user, location_id)

    loc = session.get(LocationOfWork, location_id)
    if loc is None or loc.prep_delete is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")

    eligible = get_eligible_users_for_location(session, location_id)
    if q:
        q_lower = q.lower()
        eligible = [
            u for u in eligible
            if q_lower in u.person_name.lower() or q_lower in u.email.lower()
        ]
    current_member_ids = {m.web_user_id for m in get_circle_members(session, location_id)}

    return templates.TemplateResponse(
        "notification_circles/partials/add_member_modal.html",
        {
            "request": request,
            "loc": loc,
            "eligible": eligible,
            "current_member_ids": current_member_ids,
            "q": q,
        },
    )


@router.post("/{location_id}/members", response_class=HTMLResponse)
def post_members(
    location_id: uuid.UUID,
    request: Request,
    web_user_ids: list[uuid.UUID] = Form(default=[]),
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Bulk-Add aus dem Modal. Pool-Validierung im Service-Layer."""
    assert_dispatcher_owns_location(session, user, location_id)
    add_members(session, location_id, web_user_ids, added_by=user)
    return _render_detail_pane(request, session, user, location_id)


@router.delete("/{location_id}/members/{web_user_id}", response_class=HTMLResponse)
def delete_member(
    location_id: uuid.UUID,
    web_user_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Entfernt einen Whitelist-Member."""
    assert_dispatcher_owns_location(session, user, location_id)
    remove_member(session, location_id, web_user_id)
    return _render_detail_pane(request, session, user, location_id)
