"""Admin-Teams-Router: Read-Routes fuer Listen + Detail-Drawer.

Mutations sind in ``mutations.py`` (Stammdaten/Plan-Konfig/Lifecycle) und
``assignments.py`` (Personen-/Standort-Zuordnungen) ausgelagert und werden
in spaeteren Phasen registriert.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from datetime import date

from database import db_services
from database.models import LocationOfWork, Team, TeamActorAssign, TeamLocationAssign
from web_api.admin.teams import assignments, mutations, service
from web_api.auth.dependencies import LoggedInUser, require_role
from web_api.dependencies import get_db_session
from web_api.models.web_models import WebUser, WebUserRole
from web_api.templating import templates


def _parse_optional_date(raw: str | None) -> date | None:
    """Form-Date-Helper: leere Strings als None, sonst ``YYYY-MM-DD`` parsen."""
    if not raw or not raw.strip():
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Ungültiges Datum: {raw}"
        ) from exc

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


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1.1 — Stammdaten-Mutations (Admin)
# ═══════════════════════════════════════════════════════════════════════════════


def _render_team_drawer(
    request: Request,
    team: Team,
    user: WebUser,
    *,
    saved: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    """Drawer fuer ein ``Team`` rendern. Hilfsfunktion, weil mehrere Mutations
    denselben Render-Pfad teilen."""
    response = templates.TemplateResponse(
        "admin/teams/partials/team_drawer.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "is_admin": user.has_any_role(WebUserRole.admin),
            "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
            "saved": saved,
            "error": error,
        },
    )
    response.headers["HX-Trigger"] = "teams-list-changed"
    return response


def _render_location_drawer(
    request: Request,
    location: LocationOfWork,
    user: WebUser,
    *,
    saved: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        "admin/teams/partials/location_drawer.html",
        {
            "request": request,
            "user": user,
            "location": location,
            "is_admin": user.has_any_role(WebUserRole.admin),
            "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
            "saved": saved,
            "error": error,
        },
    )
    response.headers["HX-Trigger"] = "locations-list-changed"
    return response


@router.post("/teams", response_class=HTMLResponse)
def create_team_endpoint(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    name: str = Form(...),
    notes: str | None = Form(default=None),
    dispatcher_id: str | None = Form(default=None),
):
    project = service.get_session_project(session, user)
    dispatcher_uuid = uuid.UUID(dispatcher_id) if dispatcher_id else None
    try:
        team = mutations.create_team(
            session,
            project=project,
            name=name,
            dispatcher_id=dispatcher_uuid,
            notes=notes,
            actor=user,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            # Empty-Drawer mit Fehler-Banner rendern — kein separates Form-Card-Partial,
            # damit es nur EINEN Drawer-Inhalt zu warten gibt.
            response = templates.TemplateResponse(
                "admin/teams/partials/team_drawer.html",
                {
                    "request": request,
                    "user": user,
                    "team": None,
                    "is_admin": user.has_any_role(WebUserRole.admin),
                    "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
                    "saved": False,
                    "error": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
            return response
        raise
    return _render_team_drawer(request, team, user, saved=True)


@router.patch("/teams/{team_id}", response_class=HTMLResponse)
def update_team_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    name: str = Form(...),
    notes: str | None = Form(default=None),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    try:
        team = mutations.update_team_stammdaten(
            session, team=team, name=name, notes=notes, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return _render_team_drawer(request, team, user, error=exc.detail)
        raise
    return _render_team_drawer(request, team, user, saved=True)


@router.post("/teams/{team_id}/dispatcher", response_class=HTMLResponse)
def update_team_dispatcher_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    dispatcher_id: str | None = Form(default=None),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    dispatcher_uuid = uuid.UUID(dispatcher_id) if dispatcher_id else None
    team = mutations.update_team_dispatcher(
        session, team=team, dispatcher_id=dispatcher_uuid, actor=user
    )
    return _render_team_drawer(request, team, user, saved=True)


@router.get("/teams/{team_id}/dispatcher-search", response_class=HTMLResponse)
def dispatcher_search_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = "",
):
    project = service.get_session_project(session, user)
    candidates = mutations.search_dispatcher_pool(session, project.id, q)
    return templates.TemplateResponse(
        "admin/teams/partials/dispatcher_search_results.html",
        {"request": request, "team_id": team_id, "candidates": candidates},
    )


@router.post("/locations", response_class=HTMLResponse)
def create_location_endpoint(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    name: str = Form(...),
    nr_actors: int = Form(default=2, ge=0, le=255),
    address_name: str | None = Form(default=None),
    address_street: str | None = Form(default=None),
    address_postal_code: str | None = Form(default=None),
    address_city: str | None = Form(default=None),
):
    project = service.get_session_project(session, user)
    fields = mutations.address_fields_from_form(
        address_name, address_street, address_postal_code, address_city
    )
    try:
        loc = mutations.create_location(
            session,
            project=project,
            name=name,
            address_fields=fields,
            nr_actors=nr_actors,
            actor=user,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            response = templates.TemplateResponse(
                "admin/teams/partials/location_drawer.html",
                {
                    "request": request,
                    "user": user,
                    "location": None,
                    "is_admin": user.has_any_role(WebUserRole.admin),
                    "is_dispatcher": user.has_any_role(WebUserRole.dispatcher),
                    "saved": False,
                    "error": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
            return response
        raise
    return _render_location_drawer(request, loc, user, saved=True)


@router.patch("/locations/{location_id}/plan-konfig", response_class=HTMLResponse)
def update_location_plan_config_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    nr_actors: int = Form(default=2, ge=0, le=255),
    fixed_cast: str | None = Form(default=None),
    fixed_cast_only_if_available: str | None = Form(default=None),
    notes: str | None = Form(default=None),
):
    """Dispatcher-Felder am Standort. Admin darf ebenfalls; Stammdaten bleiben Admin-only.

    ``fixed_cast_only_if_available`` kommt als Checkbox — Formularkonvention: vorhanden
    (egal welcher Wert) = True, fehlend = False.
    """
    location = session.get(LocationOfWork, location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    location = mutations.update_location_plan_config(
        session,
        location=location,
        nr_actors=nr_actors,
        fixed_cast=fixed_cast,
        fixed_cast_only_if_available=fixed_cast_only_if_available is not None,
        notes=notes,
        actor=user,
    )
    return _render_location_drawer(request, location, user, saved=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1.3 — Zuordnungen (Mitglieder + Standorte zum Team)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/teams/{team_id}/member-search", response_class=HTMLResponse)
def member_search_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = "",
):
    project = service.get_session_project(session, user)
    candidates = assignments.search_persons_for_team(
        session, project_id=project.id, q=q
    )
    return templates.TemplateResponse(
        "admin/teams/partials/member_search_results.html",
        {"request": request, "team_id": team_id, "candidates": candidates},
    )


@router.post("/teams/{team_id}/members", response_class=HTMLResponse)
def add_team_member_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    person_id: uuid.UUID = Form(...),
    start: str | None = Form(default=None),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    parsed_start = _parse_optional_date(start)
    try:
        assignments.add_team_member(
            session, team=team, person_id=person_id, start=parsed_start, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT and isinstance(
            exc.detail, assignments.AssignConflict
        ):
            return templates.TemplateResponse(
                "admin/teams/partials/conflict_dialog.html",
                {
                    "request": request,
                    "kind": "member",
                    "team_id": team_id,
                    "person_id": person_id,
                    "start": parsed_start,
                    "conflict": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
        raise
    return _render_team_drawer(request, team, user, saved=True)


@router.patch("/members/{assign_id}", response_class=HTMLResponse)
def update_team_member_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    end: str | None = Form(default=None),
):
    """End-Datum setzen oder revertieren. ``end=""`` revertiert auf NULL."""
    assign = session.get(TeamActorAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mitgliedschaft nicht gefunden")
    parsed_end = _parse_optional_date(end)
    assign = assignments.set_team_member_end(
        session, assign=assign, end=parsed_end, actor=user
    )
    team = session.get(Team, assign.team_id)
    return _render_team_drawer(request, team, user, saved=True)


@router.get("/teams/{team_id}/location-search", response_class=HTMLResponse)
def location_search_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = "",
):
    project = service.get_session_project(session, user)
    candidates = assignments.search_locations_for_team(
        session, project_id=project.id, q=q
    )
    return templates.TemplateResponse(
        "admin/teams/partials/location_search_results.html",
        {"request": request, "team_id": team_id, "candidates": candidates},
    )


@router.post("/teams/{team_id}/locations", response_class=HTMLResponse)
def add_team_location_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    location_id: uuid.UUID = Form(...),
    start: str | None = Form(default=None),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    parsed_start = _parse_optional_date(start)
    try:
        assignments.add_team_location(
            session, team=team, location_id=location_id, start=parsed_start, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT and isinstance(
            exc.detail, assignments.AssignConflict
        ):
            return templates.TemplateResponse(
                "admin/teams/partials/conflict_dialog.html",
                {
                    "request": request,
                    "kind": "location",
                    "team_id": team_id,
                    "location_id": location_id,
                    "start": parsed_start,
                    "conflict": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
        raise
    return _render_team_drawer(request, team, user, saved=True)


@router.patch("/team-locations/{assign_id}", response_class=HTMLResponse)
def update_team_location_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    end: str | None = Form(default=None),
):
    assign = session.get(TeamLocationAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden")
    parsed_end = _parse_optional_date(end)
    assign = assignments.set_team_location_end(
        session, assign=assign, end=parsed_end, actor=user
    )
    team = session.get(Team, assign.team_id)
    return _render_team_drawer(request, team, user, saved=True)


@router.patch("/locations/{location_id}/stammdaten", response_class=HTMLResponse)
def update_location_stammdaten_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    name: str = Form(...),
    address_name: str | None = Form(default=None),
    address_street: str | None = Form(default=None),
    address_postal_code: str | None = Form(default=None),
    address_city: str | None = Form(default=None),
):
    location = session.get(LocationOfWork, location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    fields = mutations.address_fields_from_form(
        address_name, address_street, address_postal_code, address_city
    )
    try:
        location = mutations.update_location_admin_fields(
            session,
            location=location,
            name=name,
            address_fields=fields,
            actor=user,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return _render_location_drawer(request, location, user, error=exc.detail)
        raise
    return _render_location_drawer(request, location, user, saved=True)
