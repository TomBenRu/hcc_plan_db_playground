"""Disponenten-View: Notification-Circles pro Arbeitsort.

Liefert einen optionalen Whitelist-Filter zum Auto-Benachrichtigungs-
Kreis bei Absagen — pro Arbeitsort konfigurierbar. Phase 3: nur
Lese-Endpoints (Liste + Detail). Mutationen folgen in Phase 4.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import LocationOfWork
from web_api.auth.dependencies import require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.notification_circles.service import (
    assert_dispatcher_owns_location,
    get_circle_members,
    get_eligible_users_for_location,
    list_locations_for_dispatcher,
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
