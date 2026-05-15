"""Admin-Teams-Router: Read-Routes fuer Listen + Detail-Drawer.

Mutations sind in ``mutations.py`` (Stammdaten/Plan-Konfig/Lifecycle) und
``assignments.py`` (Personen-/Standort-Zuordnungen) ausgelagert und werden
in spaeteren Phasen registriert.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from datetime import date

from database import db_services
from database.models import (
    LocationOfWork,
    Person,
    PlanPeriod,
    Team,
    TeamActorAssign,
    TeamLocationAssign,
)
from web_api.admin.teams import assignments, guards, mutations, service
from web_api.auth.dependencies import require_role
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


async def _read_name_confirmation(request: Request) -> str:
    """Liest ``name_confirmation`` aus URL-Query ODER form-encoded Body.

    Hintergrund: HTMX (1.x) sendet bei ``hx-delete`` die Form-Werte als
    URL-Query-Parameter, nicht im Body. Die Tests/Tools (httpx ``data=``)
    schicken dagegen einen form-encoded Body. Damit beide Pfade laufen,
    pruefen wir beide Quellen.
    """
    val = request.query_params.get("name_confirmation", "") or ""
    if val:
        return val
    try:
        form = await request.form()
        return str(form.get("name_confirmation") or "")
    except Exception:
        return ""

router = APIRouter(prefix="/admin/teams", tags=["admin-teams"])


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────


_VALID_TABS = ("teams", "locations", "members")


def _normalize_tab(raw: str | None) -> str:
    return raw if raw in _VALID_TABS else "teams"


def _normalize_status(raw: str | None) -> str:
    return "inactive" if raw == "inactive" else "active"


def _parse_optional_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw or not raw.strip():
        return None
    try:
        return uuid.UUID(raw.strip())
    except (ValueError, AttributeError):
        return None


def _build_filters(
    tab: str | None,
    status: str | None,
    search: str | None,
    team: str | None,
) -> dict:
    return {
        "tab": _normalize_tab(tab),
        "status": _normalize_status(status),
        "search": (search or "").strip(),
        "team_filter_id": _parse_optional_uuid(team),
    }


def _build_view_context(
    request: Request,
    user: WebUser,
    session: Session,
    filters: dict,
) -> dict:
    project = service.get_session_project(session, user)
    only_inactive = filters["status"] == "inactive"
    team_filter_id = filters.get("team_filter_id")

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
        team_filter_id=team_filter_id if filters["tab"] == "locations" else None,
    )
    members_rows = service.list_members_view(
        session,
        project.id,
        only_inactive=only_inactive,
        search=filters["search"] if filters["tab"] == "members" else "",
        team_filter_id=team_filter_id if filters["tab"] == "members" else None,
    )

    sidebar_counts = {
        "teams_active": service.count_teams(session, project.id, only_inactive=False),
        "teams_inactive": service.count_teams(session, project.id, only_inactive=True),
        "locations_active": service.count_locations(
            session, project.id, only_inactive=False
        ),
        "locations_inactive": service.count_locations(
            session, project.id, only_inactive=True
        ),
        "members_active": service.count_members(
            session, project.id, only_inactive=False
        ),
        "members_inactive": service.count_members(
            session, project.id, only_inactive=True
        ),
    }

    # Wenn ein team_filter aktiv ist, brauchen wir den Team-Namen fuer den
    # Banner ueber der gefilterten Liste.
    filter_team_name: str | None = None
    if team_filter_id is not None:
        team_for_filter = session.get(Team, team_filter_id)
        if team_for_filter is not None:
            filter_team_name = team_for_filter.name

    return {
        "request": request,
        "user": user,
        "filters": filters,
        "teams_rows": teams_rows,
        "locations_rows": locations_rows,
        "members_rows": members_rows,
        "sidebar_counts": sidebar_counts,
        "filter_team_name": filter_team_name,
    }


# ─── Routen ───────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def teams_index(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    tab: str | None = None,
    status: str | None = None,
    search: str | None = None,
    team: str | None = None,
):
    """Hauptseite mit Sidebar + Tab-Switch Teams/Standorte/Mitglieder.

    Vollseiten-Render fuer GET ohne ``HX-Request``; OOB-Response-Partial
    fuer HTMX-Calls (Liste + Sidebar-Counts + Hidden-State austauschen).

    ``team``-Param: UUID eines Teams; wenn gesetzt, filtert die Standorte-
    bzw. Mitglieder-Liste auf aktive Zuordnungen zu diesem Team. Diese
    Links kommen aus dem Team-Drawer.
    """
    filters = _build_filters(tab, status, search, team)
    ctx = _build_view_context(request, user, session, filters)

    template_name = (
        "admin/teams/partials/htmx_response.html"
        if request.headers.get("HX-Request") == "true"
        else "admin/teams/index.html"
    )
    return templates.TemplateResponse(template_name, ctx)


@router.get("/teams/new", response_class=HTMLResponse)
def new_team_drawer(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
):
    """Liefert einen leeren Team-Drawer (Anlage-Form)."""
    return templates.TemplateResponse(
        "admin/teams/partials/team_drawer.html",
        {"request": request, "user": user, "team": None},
    )


@router.get("/locations/new", response_class=HTMLResponse)
def new_location_drawer(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
):
    """Liefert einen leeren Standort-Drawer (Anlage-Form)."""
    return templates.TemplateResponse(
        "admin/teams/partials/location_drawer.html",
        {"request": request, "user": user, "location": None},
    )


@router.get("/teams/{team_id}/drawer", response_class=HTMLResponse)
def team_drawer(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Detail-Drawer fuer ein Team — Stammdaten + Dispatcher + Counts/Links zu
    Mitglieder- und Standorte-Tabs."""
    team = db_services.team.get(team_id, include_deleted=True)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    return templates.TemplateResponse(
        "admin/teams/partials/team_drawer.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "active_member_count": len(assignments.list_active_team_members(session, team.id)),
            "active_location_count": len(assignments.list_active_team_locations(session, team.id)),
        },
    )


@router.get("/locations/{location_id}/drawer", response_class=HTMLResponse)
def location_drawer(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Detail-Drawer fuer einen Standort."""
    location = db_services.location_of_work.get(location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    return templates.TemplateResponse(
        "admin/teams/partials/location_drawer.html",
        {
            "request": request,
            "user": user,
            "location": location,
            "active_team_assigns": assignments.list_active_location_teams(session, location.id),
            "future_team_assigns": assignments.list_future_location_teams(session, location.id),
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
    session: Session,
    saved: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    """Drawer fuer ein ``Team`` rendern. Hilfsfunktion, weil mehrere Mutations
    denselben Render-Pfad teilen.

    Seit 2026-05-15 zeigt der Team-Drawer nur Counts + Links zu den
    Mitglieder-/Standorte-Tabs (gefiltert auf das Team). Die Detail-Pflege
    erfolgt in den jeweiligen Tabs. ``session`` ist trotzdem noetig fuer die
    Counts.
    """
    active_member_count = len(assignments.list_active_team_members(session, team.id))
    active_location_count = len(assignments.list_active_team_locations(session, team.id))
    response = templates.TemplateResponse(
        "admin/teams/partials/team_drawer.html",
        {
            "request": request,
            "user": user,
            "team": team,
            "active_member_count": active_member_count,
            "active_location_count": active_location_count,
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
    session: Session,
    saved: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    """Standort-Drawer rendern inkl. Team-Zuordnungen.

    ``session`` ist zwingend, weil aktive und zukuenftige Team-Zuordnungen
    pro Render frisch geladen werden — Lazy-Load ueber die ORM-Relation wuerde
    historische Eintraege miteinschleppen und das Filtern ins Template verlagern.
    """
    active_team_assigns = assignments.list_active_location_teams(session, location.id)
    future_team_assigns = assignments.list_future_location_teams(session, location.id)
    response = templates.TemplateResponse(
        "admin/teams/partials/location_drawer.html",
        {
            "request": request,
            "user": user,
            "location": location,
            "active_team_assigns": active_team_assigns,
            "future_team_assigns": future_team_assigns,
            "saved": saved,
            "error": error,
        },
    )
    response.headers["HX-Trigger"] = "locations-list-changed"
    return response


def _render_member_drawer(
    request: Request,
    person: Person,
    user: WebUser,
    *,
    session: Session,
    saved: bool = False,
    error: str | None = None,
) -> HTMLResponse:
    """Mitglieder-Drawer rendern inkl. Team-Mitgliedschaften.

    Stammdaten der Person sind im Web read-only (Desktop ist die Wahrheit).
    Pflegbar sind nur die TAA-Zuordnungen.
    """
    active_team_assigns = assignments.list_active_person_teams(session, person.id)
    future_team_assigns = assignments.list_future_person_teams(session, person.id)
    response = templates.TemplateResponse(
        "admin/teams/partials/member_drawer.html",
        {
            "request": request,
            "user": user,
            "person": person,
            "active_team_assigns": active_team_assigns,
            "future_team_assigns": future_team_assigns,
            "saved": saved,
            "error": error,
        },
    )
    response.headers["HX-Trigger"] = "members-list-changed"
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
                    "saved": False,
                    "error": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
            return response
        raise
    return _render_team_drawer(request, team, user, session=session, saved=True)


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
            return _render_team_drawer(request, team, user, session=session, error=exc.detail)
        raise
    return _render_team_drawer(request, team, user, session=session, saved=True)


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
    return _render_team_drawer(request, team, user, session=session, saved=True)


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
                    "saved": False,
                    "error": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
            return response
        raise
    return _render_location_drawer(request, loc, user, session=session, saved=True)


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
        taa = assignments.add_team_member(
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
    # Folge-Frage: gibt's offene PPs, die sich mit der TAA ueberschneiden und
    # noch kein APP der Person tragen? Dann den APP-Dialog statt Drawer rendern.
    overlap_pps = assignments.list_open_overlapping_plan_periods_for_taa(session, taa=taa)
    if overlap_pps:
        return templates.TemplateResponse(
            "admin/teams/partials/apply_apps_dialog.html",
            {
                "request": request,
                "taa": taa,
                "plan_periods": overlap_pps,
                "drawer_target": "team-drawer",
                "drawer_reload_url": f"/admin/teams/teams/{team_id}/drawer",
                "return_drawer": "team",
            },
        )
    return _render_team_drawer(request, team, user, session=session, saved=True)


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
    return _render_team_drawer(request, team, user, session=session, saved=True)


@router.delete("/members/{assign_id}", response_class=HTMLResponse)
def delete_team_member_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Future-TAA physisch loeschen — nur erlaubt fuer ``start > today``."""
    assign = session.get(TeamActorAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mitgliedschaft nicht gefunden")
    team_id = assign.team_id
    assignments.delete_future_team_actor_assign(session, assign=assign, actor=user)
    team = session.get(Team, team_id)
    return _render_team_drawer(request, team, user, session=session, saved=True)


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
    return _render_team_drawer(request, team, user, session=session, saved=True)


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
    return _render_team_drawer(request, team, user, session=session, saved=True)


@router.delete("/team-locations/{assign_id}", response_class=HTMLResponse)
def delete_team_location_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Future-TLA physisch loeschen — Spiegel zu DELETE /location-teams/{id},
    rendert aber den Team-Drawer (URL-Konvention zeigt die Drawer-Richtung)."""
    assign = session.get(TeamLocationAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden")
    team_id = assign.team_id
    assignments.delete_future_team_location(session, assign=assign, actor=user)
    team = session.get(Team, team_id)
    return _render_team_drawer(request, team, user, session=session, saved=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1.3b — Team-Zuordnung von der Standort-Seite (Spiegel zu /teams/.../locations)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/locations/{location_id}/team-search", response_class=HTMLResponse)
def team_search_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = "",
):
    project = service.get_session_project(session, user)
    candidates = assignments.search_teams_for_location(
        session, project_id=project.id, q=q
    )
    return templates.TemplateResponse(
        "admin/teams/partials/team_search_results.html",
        {"request": request, "location_id": location_id, "candidates": candidates},
    )


@router.post("/locations/{location_id}/teams", response_class=HTMLResponse)
def add_location_team_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Form(...),
    start: str | None = Form(default=None),
):
    location = session.get(LocationOfWork, location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    team = session.get(Team, team_id)
    if team is None or team.project_id != location.project_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Team nicht gefunden")
    parsed_start = _parse_optional_date(start)
    try:
        assignments.add_team_location(
            session, team=team, location_id=location.id, start=parsed_start, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT and isinstance(
            exc.detail, assignments.AssignConflict
        ):
            return templates.TemplateResponse(
                "admin/teams/partials/conflict_dialog.html",
                {
                    "request": request,
                    "kind": "team",
                    "drawer_target": "location-drawer",
                    "drawer_reload_url": f"/admin/teams/locations/{location_id}/drawer",
                    "conflict": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
        raise
    return _render_location_drawer(request, location, user, session=session, saved=True)


@router.patch("/location-teams/{assign_id}", response_class=HTMLResponse)
def update_location_team_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    end: str | None = Form(default=None),
):
    """End-Datum einer Standort↔Team-Zuordnung setzen oder revertieren. Spiegel
    zu ``update_team_location_endpoint``, rendert aber den Standort-Drawer."""
    assign = session.get(TeamLocationAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden")
    parsed_end = _parse_optional_date(end)
    assign = assignments.set_team_location_end(
        session, assign=assign, end=parsed_end, actor=user
    )
    location = session.get(LocationOfWork, assign.location_of_work_id)
    return _render_location_drawer(request, location, user, session=session, saved=True)


@router.delete("/location-teams/{assign_id}", response_class=HTMLResponse)
def delete_location_team_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Future-TLA physisch loeschen — nur erlaubt fuer ``start > today``."""
    assign = session.get(TeamLocationAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden")
    location_id = assign.location_of_work_id
    assignments.delete_future_team_location(session, assign=assign, actor=user)
    location = session.get(LocationOfWork, location_id)
    return _render_location_drawer(request, location, user, session=session, saved=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1.3c — Mitglieder-Tab: Person-Drawer + Team-Zuordnung von der Person-Seite
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/persons/new", response_class=HTMLResponse)
def new_member_drawer(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
):
    """Liefert einen leeren Mitglieder-Drawer (Anlage-Form). Pflichtfelder
    Vorname/Nachname/E-Mail; ``gender`` ist optional."""
    return templates.TemplateResponse(
        "admin/teams/partials/member_drawer.html",
        {"request": request, "user": user, "person": None},
    )


@router.post("/persons", response_class=HTMLResponse)
def create_person_endpoint(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    f_name: str = Form(...),
    l_name: str = Form(...),
    email: str = Form(...),
    gender: str | None = Form(default=None),
):
    from database.models import Gender as _Gender

    project = service.get_session_project(session, user)
    parsed_gender: _Gender | None = None
    if gender and gender.strip():
        try:
            parsed_gender = _Gender(gender.strip())
        except ValueError:
            parsed_gender = None  # ungueltige Werte still ignorieren
    try:
        person = mutations.create_person(
            session,
            project=project,
            f_name=f_name,
            l_name=l_name,
            email=email,
            gender=parsed_gender,
            actor=user,
        )
    except mutations.DuplicateNameError as exc:
        return templates.TemplateResponse(
            "admin/teams/partials/member_drawer.html",
            {
                "request": request,
                "user": user,
                "person": None,
                "saved": False,
                "error": exc.detail,
                # Form-Vorbelegung, damit der Nutzer nicht neu tippen muss
                "form_f_name": f_name,
                "form_l_name": l_name,
                "form_email": email,
                "form_gender": gender,
            },
            status_code=status.HTTP_409_CONFLICT,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            return templates.TemplateResponse(
                "admin/teams/partials/member_drawer.html",
                {
                    "request": request,
                    "user": user,
                    "person": None,
                    "saved": False,
                    "error": exc.detail,
                    "form_f_name": f_name,
                    "form_l_name": l_name,
                    "form_email": email,
                    "form_gender": gender,
                },
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        raise
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.get("/persons/{person_id}/drawer", response_class=HTMLResponse)
def member_drawer_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Detail-Drawer fuer eine Person. Stammdaten sind read-only (Desktop-
    pflege); editierbar sind nur die Team-Mitgliedschaften."""
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")
    return _render_member_drawer(request, person, user, session=session)


@router.get("/persons/{person_id}/team-search", response_class=HTMLResponse)
def person_team_search_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = "",
):
    project = service.get_session_project(session, user)
    candidates = assignments.search_teams_for_person(
        session, project_id=project.id, q=q
    )
    return templates.TemplateResponse(
        "admin/teams/partials/person_team_search_results.html",
        {"request": request, "person_id": person_id, "candidates": candidates},
    )


@router.post("/persons/{person_id}/teams", response_class=HTMLResponse)
def add_person_team_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Form(...),
    start: str | None = Form(default=None),
):
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")
    team = session.get(Team, team_id)
    if team is None or team.project_id != person.project_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Team nicht gefunden")
    parsed_start = _parse_optional_date(start)
    try:
        taa = assignments.add_team_member(
            session, team=team, person_id=person.id, start=parsed_start, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT and isinstance(
            exc.detail, assignments.AssignConflict
        ):
            return templates.TemplateResponse(
                "admin/teams/partials/conflict_dialog.html",
                {
                    "request": request,
                    "kind": "person",
                    "drawer_target": "member-drawer",
                    "drawer_reload_url": f"/admin/teams/persons/{person_id}/drawer",
                    "conflict": exc.detail,
                },
                status_code=status.HTTP_409_CONFLICT,
            )
        raise
    # Symmetrisch zu add_team_member_endpoint: offene PPs → APP-Dialog.
    overlap_pps = assignments.list_open_overlapping_plan_periods_for_taa(session, taa=taa)
    if overlap_pps:
        return templates.TemplateResponse(
            "admin/teams/partials/apply_apps_dialog.html",
            {
                "request": request,
                "taa": taa,
                "plan_periods": overlap_pps,
                "drawer_target": "member-drawer",
                "drawer_reload_url": f"/admin/teams/persons/{person_id}/drawer",
                "return_drawer": "member",
            },
        )
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.patch("/person-teams/{assign_id}", response_class=HTMLResponse)
def update_person_team_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    end: str | None = Form(default=None),
):
    """End-Datum einer Person↔Team-Zuordnung setzen oder revertieren. Spiegel
    zu ``update_team_member_endpoint``, rendert aber den Mitglieder-Drawer."""
    assign = session.get(TeamActorAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mitgliedschaft nicht gefunden")
    parsed_end = _parse_optional_date(end)
    assign = assignments.set_team_member_end(
        session, assign=assign, end=parsed_end, actor=user
    )
    person = session.get(Person, assign.person_id)
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.delete("/person-teams/{assign_id}", response_class=HTMLResponse)
def delete_person_team_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Future-TAA von der Person-Seite physisch loeschen."""
    assign = session.get(TeamActorAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mitgliedschaft nicht gefunden")
    person_id = assign.person_id
    assignments.delete_future_team_actor_assign(session, assign=assign, actor=user)
    person = session.get(Person, person_id)
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.post("/members/{assign_id}/apply-apps", response_class=HTMLResponse)
def apply_actor_plan_periods_endpoint(
    request: Request,
    assign_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    plan_period_ids: list[uuid.UUID] = Form(default=[]),
    return_drawer: str = Form(default="team"),
):
    """Verarbeitet die Auswahl aus ``apply_apps_dialog.html``: erzeugt APPs
    fuer die ausgewaehlten offenen PPs und rendert den Quell-Drawer
    (``return_drawer`` = 'team' oder 'member')."""
    assign = session.get(TeamActorAssign, assign_id)
    if assign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mitgliedschaft nicht gefunden")
    person = session.get(Person, assign.person_id)
    team = session.get(Team, assign.team_id)
    if person is None or team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person oder Team nicht gefunden")

    # PPs laden + Project-Match-Filter (Mutation prueft nochmal, aber wir wollen
    # auch fremde IDs aus manipulierten Forms hier abfangen).
    plan_periods: list[PlanPeriod] = []
    if plan_period_ids:
        plan_periods = list(
            session.exec(
                select(PlanPeriod).where(
                    PlanPeriod.id.in_(plan_period_ids),  # type: ignore[union-attr]
                    PlanPeriod.team_id == team.id,
                )
            ).all()
        )
    mutations.create_actor_plan_periods(
        session, person=person, plan_periods=plan_periods, actor=user
    )

    if return_drawer == "member":
        return _render_member_drawer(request, person, user, session=session, saved=True)
    return _render_team_drawer(request, team, user, session=session, saved=True)


@router.patch("/persons/{person_id}/name", response_class=HTMLResponse)
def update_person_name_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    f_name: str = Form(...),
    l_name: str = Form(...),
):
    """Aendert Vor- und Nachname einer Person. Restliche Stammdaten (E-Mail,
    Telefon, Gender, etc.) bleiben Desktop-Pflege — bewusste Begrenzung des
    Web-Scopes auf das, was im Web haeufig zu korrigieren ist."""
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")
    try:
        person = mutations.update_person_names(
            session, person=person, f_name=f_name, l_name=l_name, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            return _render_member_drawer(
                request, person, user, session=session, error=exc.detail
            )
        raise
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.post("/persons/{person_id}/soft-delete", response_class=HTMLResponse)
def soft_delete_person_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")
    try:
        person = mutations.soft_delete_person(session, person=person, actor=user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return _render_member_drawer(
                request, person, user, session=session, error=exc.detail
            )
        raise
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.post("/persons/{person_id}/restore", response_class=HTMLResponse)
def restore_person_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")
    person = mutations.restore_person(session, person=person, actor=user)
    return _render_member_drawer(request, person, user, session=session, saved=True)


@router.delete("/persons/{person_id}", response_class=HTMLResponse)
async def hard_delete_person_endpoint(
    request: Request,
    person_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    name_confirmation = await _read_name_confirmation(request)
    person = session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person nicht gefunden")
    try:
        mutations.hard_delete_person(
            session, person=person, name_confirmation=name_confirmation, actor=user
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
            return _render_member_drawer(
                request, person, user, session=session, error=exc.detail
            )
        raise
    from fastapi.responses import Response

    resp = Response(status_code=status.HTTP_200_OK)
    resp.headers["HX-Trigger"] = "members-list-changed"
    return resp


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1.5 — Soft-Delete + Hard-Delete-Pfad
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/teams/{team_id}/soft-delete", response_class=HTMLResponse)
def soft_delete_team_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    try:
        team = mutations.soft_delete_team(session, team=team, actor=user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return _render_team_drawer(request, team, user, session=session, error=exc.detail)
        raise
    return _render_team_drawer(request, team, user, session=session, saved=True)


@router.post("/teams/{team_id}/restore", response_class=HTMLResponse)
def restore_team_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    team = mutations.restore_team(session, team=team, actor=user)
    return _render_team_drawer(request, team, user, session=session, saved=True)


@router.delete("/teams/{team_id}", response_class=HTMLResponse)
async def hard_delete_team_endpoint(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    name_confirmation = await _read_name_confirmation(request)
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Team nicht gefunden")
    mutations.hard_delete_team(
        session, team=team, name_confirmation=name_confirmation, actor=user
    )
    # Nach Hard-Delete: leerer Response mit HX-Trigger
    from fastapi.responses import Response

    resp = Response(status_code=status.HTTP_200_OK)
    resp.headers["HX-Trigger"] = "teams-list-changed"
    return resp


@router.post("/locations/{location_id}/soft-delete", response_class=HTMLResponse)
def soft_delete_location_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    location = session.get(LocationOfWork, location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    try:
        location = mutations.soft_delete_location(session, location=location, actor=user)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return _render_location_drawer(request, location, user, session=session, error=exc.detail)
        raise
    return _render_location_drawer(request, location, user, session=session, saved=True)


@router.post("/locations/{location_id}/restore", response_class=HTMLResponse)
def restore_location_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    location = session.get(LocationOfWork, location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    location = mutations.restore_location(session, location=location, actor=user)
    return _render_location_drawer(request, location, user, session=session, saved=True)


@router.delete("/locations/{location_id}", response_class=HTMLResponse)
async def hard_delete_location_endpoint(
    request: Request,
    location_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    name_confirmation = await _read_name_confirmation(request)
    location = session.get(LocationOfWork, location_id)
    if location is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Standort nicht gefunden")
    mutations.hard_delete_location(
        session, location=location, name_confirmation=name_confirmation, actor=user
    )
    from fastapi.responses import Response

    resp = Response(status_code=status.HTTP_200_OK)
    resp.headers["HX-Trigger"] = "locations-list-changed"
    return resp


@router.get("/addresses/suggest", response_class=HTMLResponse)
def address_suggest_endpoint(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    q: str = "",
):
    """Live-Suche fuer Adress-Vorschlaege im Standort-Drawer.

    Frontend-Pattern: Klick auf einen Vorschlag fuellt die Adress-Felder
    vor, laesst aber ``address_id`` unveraendert — beim Speichern wird
    immer eine **neue** Address-Zeile erzeugt (siehe PRD US-08).
    """
    project = service.get_session_project(session, user)
    suggestions = service.address_suggest(session, project.id, q)
    return templates.TemplateResponse(
        "admin/teams/partials/address_suggest_results.html",
        {"request": request, "suggestions": suggestions},
    )


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
            return _render_location_drawer(request, location, user, session=session, error=exc.detail)
        raise
    return _render_location_drawer(request, location, user, session=session, saved=True)
