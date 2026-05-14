"""Admin-Teams-Router: Read-Routes fuer Listen + Detail-Drawer.

Mutations sind in ``mutations.py`` (Stammdaten/Plan-Konfig/Lifecycle) und
``assignments.py`` (Personen-/Standort-Zuordnungen) ausgelagert und werden
in spaeteren Phasen registriert.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database import db_services
from web_api.admin.teams import service
from web_api.auth.dependencies import LoggedInUser
from web_api.dependencies import get_db_session
from web_api.models.web_models import WebUserRole
from web_api.templating import templates

router = APIRouter(prefix="/admin/teams", tags=["admin-teams"])


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────


def _normalize_tab(raw: str | None) -> str:
    return "locations" if raw == "locations" else "teams"


def _normalize_status(raw: str | None) -> str:
    return "inactive" if raw == "inactive" else "active"


def _build_filters(tab: str | None, status: str | None, search: str | None) -> dict:
    return {
        "tab": _normalize_tab(tab),
        "status": _normalize_status(status),
        "search": (search or "").strip(),
    }


def _build_view_context(
    request: Request,
    user,  # WebUser, untyped fuer einfacheren Aufruf
    session: Session,
    filters: dict,
) -> dict:
    project = service.get_session_project(session, user)
    only_inactive = filters["status"] == "inactive"

    teams_rows = service.list_teams_view(
        session,
        project.id,
        only_inactive=only_inactive,
        search=filters["search"] if filters["tab"] == "teams" else "",
    )
    locations_rows = service.list_locations_view(
        session,
        project.id,
        only_inactive=only_inactive,
        search=filters["search"] if filters["tab"] == "locations" else "",
    )

    sidebar_counts = {
        "teams_active": service.count_teams(session, project.id, only_inactive=False),
        "teams_inactive": service.count_teams(session, project.id, only_inactive=True),
        "locations_active": service.count_locations(session, project.id, only_inactive=False),
        "locations_inactive": service.count_locations(session, project.id, only_inactive=True),
    }

    return {
        "request": request,
        "user": user,
        "filters": filters,
        "teams_rows": teams_rows,
        "locations_rows": locations_rows,
        "sidebar_counts": sidebar_counts,
        "is_admin": user.has_any_role(WebUserRole.admin),
        "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
    }


# ─── Routen ───────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def teams_index(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    tab: str | None = None,
    status: str | None = None,
    search: str | None = None,
):
    """Hauptseite mit Sidebar + Tab-Switch Teams/Standorte.

    Vollseiten-Render fuer GET ohne ``HX-Request``; OOB-Response-Partial
    fuer HTMX-Calls (Liste + Sidebar-Counts + Hidden-State austauschen).
    """
    service.require_admin_or_dispatcher(user)
    filters = _build_filters(tab, status, search)
    ctx = _build_view_context(request, user, session, filters)

    template_name = (
        "admin/teams/partials/htmx_response.html"
        if request.headers.get("HX-Request") == "true"
        else "admin/teams/index.html"
    )
    return templates.TemplateResponse(template_name, ctx)


@router.get("/teams/{team_id}/drawer", response_class=HTMLResponse)
def team_drawer(
    request: Request,
    team_id: uuid.UUID,
    user: LoggedInUser,
):
    """Detail-Drawer fuer ein Team (read-only in Phase 1.0).

    DB-Service oeffnet seine eigene Session via ``database.database.get_session()``
    — daher kein explizites ``session``-Argument. Engine ist via Test-Setup
    auf die Test-DB gepatcht.
    """
    service.require_admin_or_dispatcher(user)
    team = db_services.team.get(team_id, include_deleted=True)
    return templates.TemplateResponse(
        "admin/teams/partials/team_drawer.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "is_admin": user.has_any_role(WebUserRole.admin),
            "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
        },
    )


@router.get("/locations/{location_id}/drawer", response_class=HTMLResponse)
def location_drawer(
    request: Request,
    location_id: uuid.UUID,
    user: LoggedInUser,
):
    """Detail-Drawer fuer einen Standort (read-only in Phase 1.0)."""
    service.require_admin_or_dispatcher(user)
    location = db_services.location_of_work.get(location_id)
    return templates.TemplateResponse(
        "admin/teams/partials/location_drawer.html",
        {
            "request": request,
            "user": user,
            "location": location,
            "is_admin": user.has_any_role(WebUserRole.admin),
            "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
        },
    )
