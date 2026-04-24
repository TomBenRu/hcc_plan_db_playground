"""Router: Persönliche Einstellungen (aktuell nur Location-Farben)."""

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser
from web_api.dependencies import get_db_session
from web_api.palette import is_allowed_location_color
from web_api.templating import templates
from web_api.user_settings.service import (
    LocationColorRow,
    delete_location_color,
    get_visible_locations_with_colors,
    set_location_color,
)

router = APIRouter(prefix="/user/settings", tags=["user-settings"])


@router.get("", response_class=HTMLResponse)
def user_settings_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Einstellungs-Landing mit Farb-Liste."""
    locations = get_visible_locations_with_colors(session, user)
    return templates.TemplateResponse(
        "user_settings/index.html",
        {"request": request, "user": user, "locations": locations},
    )


@router.post("/colors/{location_id}", response_class=HTMLResponse)
def set_user_color(
    request: Request,
    location_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    color: str = Form(...),
):
    """Setzt den User-Override für eine Location auf die gewählte Palette-Farbe.

    Server-seitige Allowlist: nur Farben aus `LOCATION_PALETTE` werden akzeptiert.
    Row-Partial wird zurückgegeben — HTMX swapt die Zeile in-place.
    """
    if not is_allowed_location_color(color):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Farbe nicht in der erlaubten Palette",
        )
    set_location_color(session, user.id, location_id, color)
    session.commit()
    row = _build_row_for_location(session, user, location_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return templates.TemplateResponse(
        "user_settings/partials/location_row.html",
        {"request": request, "loc": row},
    )


@router.delete("/colors/{location_id}", response_class=HTMLResponse)
def reset_user_color(
    request: Request,
    location_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Löscht den Override — Rückfall auf den deterministischen Default."""
    delete_location_color(session, user.id, location_id)
    session.commit()
    row = _build_row_for_location(session, user, location_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    return templates.TemplateResponse(
        "user_settings/partials/location_row.html",
        {"request": request, "loc": row},
    )


def _build_row_for_location(
    session: Session,
    user,
    location_id: uuid.UUID,
) -> LocationColorRow | None:
    """Einzelne Zeile für HTMX-Swap nach Set/Reset zurückbauen."""
    for loc in get_visible_locations_with_colors(session, user):
        if loc.id == location_id:
            return loc
    # Fallback: Location außerhalb der sichtbaren Teams — sollte nicht auftreten,
    # aber Schutz gegen manipulierte Requests.
    return None
