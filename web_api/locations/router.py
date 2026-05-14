"""Endpoints fuer die Einsatzort-Info-Card (Modal aus Termin-Detail)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser
from web_api.dependencies import get_db_session
from web_api.locations.service import get_info_card_data
from web_api.models.web_models import WebUserRole
from web_api.palette import location_color
from web_api.templating import templates
from web_api.user_settings.service import get_color_overrides

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("/{location_id}/info-card", response_class=HTMLResponse)
def location_info_card(
    request: Request,
    location_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    exclude: uuid.UUID | None = None,
    view: Literal["employee", "dispatcher"] = Query(default="employee"),
):
    """HTMX-Partial: read-only Detail-Modal eines Einsatzortes.

    Inhalt: Adresse + Notizen + naechste 5 Termine an diesem Ort.

    `view` bestimmt die Sicht (vom aufrufenden Template gesetzt):
    - `employee` (Default): nur eigene Termine, ohne Cast-Liste.
    - `dispatcher`: alle Termine + Cast-Namen — verlangt Dispatcher-, Admin-
      oder Viewer-Rolle. Der Name `dispatcher` beschreibt nur die Dichte der
      Anzeige (voll vs. nur-eigene), nicht die Berechtigung.

    Auf Dual-Rolle (Mitarbeiter+Dispatcher) wuerde eine Rolle-basierte
    Erkennung den User immer als Dispatcher behandeln, auch im Mitarbeiter-
    Kalender. Daher steuert der Caller den Mode.
    """
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknuepft",
        )

    is_dispatcher_view = view == "dispatcher"
    if is_dispatcher_view and not user.has_any_role(
        WebUserRole.dispatcher, WebUserRole.admin, WebUserRole.viewer
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    overrides = get_color_overrides(session, user.id)
    color = location_color(location_id, overrides)

    card = get_info_card_data(
        session,
        location_id=location_id,
        viewer_person_id=user.person_id,
        color=color,
        is_dispatcher=is_dispatcher_view,
        exclude_appointment_id=exclude,
    )
    if card is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    return templates.TemplateResponse(
        "locations/_info_modal.html",
        {"request": request, "card": card},
    )
