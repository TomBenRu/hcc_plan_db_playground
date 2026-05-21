"""Dispatcher-View: Notfall-Benachrichtigungs-Kreis pro Arbeitsort.

Eigene Whitelist parallel zum regulären `location_notification_circle`.
KEINE toggle-mode-Route — Aktivierung implicit über Member-Existenz.
"""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import LocationOfWork
from web_api.auth.dependencies import require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.emergency_notification_circles.service import (
    add_emergency_members,
    get_emergency_circle_members,
    list_emergency_locations_for_dispatcher,
    remove_emergency_member,
)
from web_api.dispatcher.notification_circles.service import (
    assert_dispatcher_owns_location,
    get_eligible_users_for_location,
)
from web_api.models.web_models import WebUser, WebUserRole
from web_api.templating import templates


router = APIRouter(
    prefix="/dispatcher/emergency-notification-circles",
    tags=["dispatcher-emergency-notification-circles"],
)


def _render_detail_pane(
    request: Request,
    session: Session,
    user: WebUser,
    location_id: uuid.UUID,
) -> HTMLResponse:
    """Re-rendert das #detail-pane nach jeder Mutation (Add/Remove)."""
    loc = session.get(LocationOfWork, location_id)
    if loc is None or loc.prep_delete is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")

    members = get_emergency_circle_members(session, location_id)
    eligible_count = len(get_eligible_users_for_location(session, location_id))

    return templates.TemplateResponse(
        "emergency_notification_circles/partials/_detail_pane.html",
        {
            "request": request,
            "loc": loc,
            "members": members,
            "eligible_count": eligible_count,
        },
    )


@router.get("", response_class=HTMLResponse)
def list_circles(
    request: Request,
    filter: str = "",
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Liste aller Arbeitsorte des Dispatchers mit Notfall-Member-Count.

    `filter`-Werte:
      - `""` (Default): alle Arbeitsorte.
      - `"configured"`: nur Orte mit mindestens einem Notfall-Member.
      - `"empty"`: nur Orte ohne Notfall-Member (Auto-Mode).
    """
    summaries = list_emergency_locations_for_dispatcher(session, user)

    if filter == "configured":
        summaries = [s for s in summaries if s.member_count > 0]
    elif filter == "empty":
        summaries = [s for s in summaries if s.member_count == 0]

    return templates.TemplateResponse(
        "emergency_notification_circles/index.html",
        {
            "request": request,
            "user": user,
            "summaries": summaries,
            "filter": filter,
            "filter_labels": {
                "": "Alle",
                "configured": "Konfiguriert",
                "empty": "Auto-Mode",
            },
        },
    )


@router.get("/{location_id}", response_class=HTMLResponse)
def detail(
    location_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Detail-View eines Arbeitsorts: Member-Liste + Hinweis-Banner."""
    assert_dispatcher_owns_location(session, user, location_id)

    loc = session.get(LocationOfWork, location_id)
    if loc is None or loc.prep_delete is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Arbeitsort nicht gefunden.")

    members = get_emergency_circle_members(session, location_id)
    eligible_count = len(get_eligible_users_for_location(session, location_id))

    return templates.TemplateResponse(
        "emergency_notification_circles/detail.html",
        {
            "request": request,
            "user": user,
            "loc": loc,
            "members": members,
            "eligible_count": eligible_count,
        },
    )


@router.get("/{location_id}/add-member", response_class=HTMLResponse)
def add_member_modal(
    location_id: uuid.UUID,
    request: Request,
    q: str = "",
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Pool-Auswahl-Modal mit optionaler Server-side-Suche."""
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
    current_member_ids = {m.web_user_id for m in get_emergency_circle_members(session, location_id)}

    return templates.TemplateResponse(
        "emergency_notification_circles/partials/add_member_modal.html",
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
    """Bulk-Add aus dem Modal."""
    assert_dispatcher_owns_location(session, user, location_id)
    add_emergency_members(session, location_id, web_user_ids, added_by=user)
    return _render_detail_pane(request, session, user, location_id)


@router.delete("/{location_id}/members/{web_user_id}", response_class=HTMLResponse)
def delete_member(
    location_id: uuid.UUID,
    web_user_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher),
    session: Session = Depends(get_db_session),
):
    """Entfernt einen Notfall-Whitelist-Member."""
    assert_dispatcher_owns_location(session, user, location_id)
    remove_emergency_member(session, location_id, web_user_id)
    return _render_detail_pane(request, session, user, location_id)
