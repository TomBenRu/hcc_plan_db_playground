"""Disponenten-UI: Verwaltung von Planungsperioden unter `/dispatcher/periods`.

Spiegelt die Hauptfunktionen des Desktop-Dialogs `DlgPlanPeriodCreate` /
`DlgPlanPeriodEdit` ins Web-UI: Anlegen (atomar), Bearbeiten (Datum/Notes),
Schließen/Wiedereröffnen, Inline-Notes-Edit, Take-Over.

Routen sind ausschließlich für Disponenten/Admins zugänglich; Re-Open zusätzlich
nur für Admins. Layout-Vorbild: `web_api/templates/cancellations/index.html`.
"""

import datetime
import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session

from database import db_services, schemas
from database.db_services.plan_period import (
    PlanPeriodClosedError,
    PlanPeriodPermissionError,
)
from web_api.auth.dependencies import LoggedInUser, require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.service import get_teams_for_dispatcher
from web_api.dispatcher_periods.service import filter_periods, validate_period_dates
from web_api.models.web_models import WebUser, WebUserRole
from web_api.templating import templates


router = APIRouter(prefix="/dispatcher/periods", tags=["dispatcher-periods"])


def _is_admin(user: WebUser) -> bool:
    return user.has_any_role(WebUserRole.admin)


def _get_active_team_or_404(team_id: uuid.UUID) -> schemas.TeamShow:
    """Lädt das Team, gibt 404 zurück wenn es nicht existiert oder soft-deleted ist.

    `db_services.Team.get` filtert per Default soft-deleted Teams aus und wirft
    `NoResultFound` für nicht existente UND soft-deletete IDs — beide Fälle
    werden hier zu einer sauberen 404 gemappt, sonst kommt es als HTTP 500
    raus."""
    try:
        return db_services.Team.get(team_id)
    except NoResultFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} nicht gefunden oder gelöscht.",
        )


def _resolve_team_choices(session: Session, user: WebUser):
    """Teams, die in der Sidebar als Filter zur Auswahl stehen."""
    if not user.person_id:
        return []
    return get_teams_for_dispatcher(session, user.person_id)


def _today() -> datetime.date:
    return datetime.date.today()


@router.get("", response_class=HTMLResponse)
def index(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """Listenseite mit Sidebar-Team-Filter."""
    teams = _resolve_team_choices(session, user)
    if team_id is not None:
        # Per URL übergebene team_id muss aktiv sein — sonst 404 statt
        # heimlich softdeleted Inhalte zeigen.
        _get_active_team_or_404(team_id)
        selected_team_id = team_id
    elif teams:
        # Default-Auswahl beim Erstaufruf: erstes aktives Team aus der Sidebar.
        # _resolve_team_choices filtert bereits soft-deleted aus, also kein
        # zusätzlicher 404-Check nötig.
        selected_team_id = teams[0].id
    else:
        selected_team_id = None
    if selected_team_id:
        # include_deleted=True, weil _filter_periods('papierkorb') die soft-deleted
        # PPs anzeigen können muss; aktive Filter werden Python-seitig gemacht.
        periods = db_services.PlanPeriod.get_all_from__team_minimal(
            selected_team_id, include_deleted=True,
        )
    else:
        periods = []
    periods = filter_periods(periods, status_filter)
    periods = sorted(periods, key=lambda p: p.start, reverse=True)

    return templates.TemplateResponse(
        "dispatcher/periods/index.html",
        {
            "request": request,
            "user": user,
            "teams": teams,
            "selected_team_id": selected_team_id,
            "status_filter": status_filter,
            "periods": periods,
            "is_admin": _is_admin(user),
            "today": _today(),
        },
    )


@router.get("/list", response_class=HTMLResponse)
def list_partial(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """HTMX-Partial: nur die Liste, nach Filter-Wechsel."""
    if team_id:
        _get_active_team_or_404(team_id)
        periods = db_services.PlanPeriod.get_all_from__team_minimal(
            team_id, include_deleted=True,
        )
    else:
        periods = []
    periods = filter_periods(periods, status_filter)
    periods = sorted(periods, key=lambda p: p.start, reverse=True)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/list.html",
        {
            "request": request,
            "user": user,
            "periods": periods,
            "is_admin": _is_admin(user),
            "today": _today(),
            "status_filter": status_filter,
        },
    )


def _create_form_context(
    request: Request,
    team_id: uuid.UUID,
    *,
    start: datetime.date,
    end: datetime.date,
    notes: str,
    notes_for_employees: str,
    earliest_start: datetime.date,
    latest_end: datetime.date | None,
    error_message: str | None = None,
) -> dict:
    """Bündelt alle Werte für `create_form.html` — sowohl Initial-Render
    (smart Defaults) als auch Re-Render bei Validierungsfehler (übermittelte
    User-Werte werden zurück ins Formular gespiegelt).

    Phase C der NG-Verwaltung: Deadline + Reminder-Toggle wandern in die
    Notification-Groups-View; PP-Form fragt nur noch Datum + Notizen ab.
    """
    return {
        "request": request,
        "team_id": team_id,
        "today": _today(),
        "earliest_start": earliest_start,
        "latest_end": latest_end,
        "default_start": start,
        "default_end": end,
        "default_notes": notes,
        "default_notes_for_employees": notes_for_employees,
        "error_message": error_message,
    }


@router.get("/new", response_class=HTMLResponse)
def new_form(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Modal: Anlage-Formular für eine neue Periode mit smart Defaults
    (Notizen aus Team, Start ab Tag nach jüngster bestehender PP)."""
    today = _today()
    team = _get_active_team_or_404(team_id)
    latest_end = db_services.PlanPeriod.get_latest_end_for_team(team_id)
    earliest_start = max(
        today + datetime.timedelta(days=1),
        (latest_end + datetime.timedelta(days=1)) if latest_end else today + datetime.timedelta(days=1),
    )
    default_start = earliest_start
    default_end = default_start + datetime.timedelta(days=29)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/create_form.html",
        _create_form_context(
            request, team_id,
            start=default_start, end=default_end,
            notes=team.notes or "",
            notes_for_employees="",
            earliest_start=earliest_start,
            latest_end=latest_end,
        ),
    )


@router.post("", response_class=HTMLResponse)
def create_with_children(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Form(...),
    start: datetime.date = Form(...),
    end: datetime.date = Form(...),
    notes: str = Form(default=""),
    notes_for_employees: str = Form(default=""),
):
    """Atomarer Create-Submit. Bei Erfolg: Take-Over-Modal oder Liste-Refresh
    mit Reminder-Banner. Bei Validierungsfehler: Form mit Banner re-rendern,
    Eingaben bleiben.

    Phase C: PP entsteht ohne Reminder-Group; der Dispatcher richtet
    Reminder anschliessend in der NG-View ein. `remainder=False` ist hardcoded
    bis zum spaeteren Removal des Feldes (siehe TODO).
    """
    error = validate_period_dates(team_id, start, end)
    if error:
        latest_end = db_services.PlanPeriod.get_latest_end_for_team(team_id)
        earliest_start = max(
            _today() + datetime.timedelta(days=1),
            (latest_end + datetime.timedelta(days=1)) if latest_end else _today() + datetime.timedelta(days=1),
        )
        return templates.TemplateResponse(
            "dispatcher/periods/partials/create_form.html",
            _create_form_context(
                request, team_id,
                start=start, end=end,
                notes=notes, notes_for_employees=notes_for_employees,
                earliest_start=earliest_start,
                latest_end=latest_end,
                error_message=error,
            ),
        )

    team = _get_active_team_or_404(team_id)
    create_schema = schemas.PlanPeriodCreate(
        start=start, end=end, deadline=None,
        notes=notes or None, notes_for_employees=notes_for_employees or None,
        remainder=False, team=team,
    )
    new_pp = db_services.PlanPeriod.create_with_children(create_schema)

    # Take-Over-Vorschau prüfen — falls Kandidaten existieren, Modal zeigen.
    # Sobald der Dispatcher die Vorschau bestaetigt/abbricht, fliesst er auch
    # in den Banner-Pfad (`execute_takeover` ruft ebenfalls `_redirect_to_list`).
    preview = db_services.PlanPeriod.find_takeover_candidates(new_pp.id)
    if preview.total_avail_days > 0 or preview.total_events > 0:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/takeover_modal.html",
            {
                "request": request,
                "preview": preview,
                "plan_period_id": new_pp.id,
            },
            headers={"HX-Retarget": "#modal-root", "HX-Reswap": "innerHTML"},
        )

    # Direkt: Liste neu laden + Reminder-Banner einblenden.
    return _redirect_to_list(team_id, just_created_pp_id=new_pp.id)


def _edit_form_context(
    request: Request,
    pp,
    *,
    start: datetime.date,
    end: datetime.date,
    notes: str,
    notes_for_employees: str,
    is_admin: bool,
    error_message: str | None = None,
) -> dict:
    """Bündelt alle Werte für `edit_form.html`.

    `min_start` ist None, wenn es keine andere non-deleted PP im Team gibt —
    das Template lässt das `min`-Attribut dann weg, damit ältere Perioden
    (die vor allen anderen liegen) editierbar bleiben.

    Phase C: Deadline + Group-Verwaltung sind raus, PP-Edit fokussiert auf
    Datum + Notizen + Status.
    """
    latest_end_other = db_services.PlanPeriod.get_latest_end_for_team(
        pp.team.id, exclude_id=pp.id
    )
    min_start = (latest_end_other + datetime.timedelta(days=1)) if latest_end_other else None
    return {
        "request": request,
        "pp": pp,
        "is_admin": is_admin,
        "today": _today(),
        "min_start": min_start,
        "default_start": start,
        "default_end": end,
        "default_notes": notes,
        "default_notes_for_employees": notes_for_employees,
        "error_message": error_message,
    }


@router.get("/{plan_period_id}/edit", response_class=HTMLResponse)
def edit_form(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    pp = db_services.PlanPeriod.get(plan_period_id)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/edit_form.html",
        _edit_form_context(
            request, pp,
            start=pp.start, end=pp.end,
            notes=pp.notes or "",
            notes_for_employees=pp.notes_for_employees or "",
            is_admin=_is_admin(user),
        ),
    )


@router.patch("/{plan_period_id}", response_class=HTMLResponse)
def patch_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    start: datetime.date = Form(...),
    end: datetime.date = Form(...),
    notes: str = Form(default=""),
    notes_for_employees: str = Form(default=""),
):
    current = db_services.PlanPeriod.get(plan_period_id)

    error = validate_period_dates(
        current.team.id, start, end, exclude_id=plan_period_id
    )
    if error:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/edit_form.html",
            _edit_form_context(
                request, current,
                start=start, end=end,
                notes=notes, notes_for_employees=notes_for_employees,
                is_admin=_is_admin(user),
                error_message=error,
            ),
        )

    # deadline=None signalisiert dem Service "Group nicht touchen" (Phase B
    # update-Branch 1) — Reminder-Verwaltung laeuft ausschliesslich in der
    # NG-View. remainder bleibt aus dem ORM-Stand erhalten.
    update_schema = schemas.PlanPeriod(
        id=plan_period_id,
        start=start, end=end, deadline=None,
        notes=notes or None, notes_for_employees=notes_for_employees or None,
        remainder=current.remainder, team=current.team,
        closed=current.closed,
        prep_delete=current.prep_delete,
    )
    try:
        db_services.PlanPeriod.update(update_schema)
    except PlanPeriodClosedError as e:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/error.html",
            {"request": request, "message": str(e)},
            status_code=status.HTTP_409_CONFLICT,
        )
    return _redirect_to_list(current.team.id)


@router.get("/{plan_period_id}/notes-display", response_class=HTMLResponse)
def notes_display(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    # include_deleted=True: notes_display.html rendert den Notes-Edit-Button auch
    # für Papierkorb-PPs (siehe Template Z.16-22). Ohne den Override wirft der
    # Default-Filter NoResultFound → 404 → Papierkorb-Notes wären unzugänglich.
    pp = db_services.PlanPeriod.get(plan_period_id, include_deleted=True)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/notes_display.html",
        {"request": request, "pp": pp},
    )


@router.get("/{plan_period_id}/notes-edit", response_class=HTMLResponse)
def notes_edit(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    pp = db_services.PlanPeriod.get(plan_period_id, include_deleted=True)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/notes_edit.html",
        {"request": request, "pp": pp},
    )


@router.patch("/{plan_period_id}/notes", response_class=HTMLResponse)
def patch_notes(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    notes: str = Form(default=""),
):
    db_services.PlanPeriod.update_notes(plan_period_id, notes)
    pp = db_services.PlanPeriod.get(plan_period_id, include_deleted=True)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/notes_display.html",
        {"request": request, "pp": pp},
    )


@router.post("/{plan_period_id}/close", response_class=HTMLResponse)
def close_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    pp = db_services.PlanPeriod.set_closed(
        plan_period_id, True, is_admin=_is_admin(user)
    )
    return _redirect_to_list(pp.team_id)


@router.post("/{plan_period_id}/reopen", response_class=HTMLResponse)
def reopen_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    if not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Re-Open requires admin role")
    try:
        pp = db_services.PlanPeriod.set_closed(plan_period_id, False, is_admin=True)
    except PlanPeriodPermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return _redirect_to_list(pp.team_id)


@router.post("/{plan_period_id}/takeover", response_class=HTMLResponse)
def execute_takeover(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    accepted: str = Form(default="no"),
):
    # team_id schlank über minimal=True holen — kein PlanPeriodShow-Bloat
    pp_min = db_services.PlanPeriod.get(plan_period_id, minimal=True)
    if accepted == "yes":
        db_services.PlanPeriod.execute_takeover(plan_period_id)
    # Take-Over haengt immer am frisch erstellten PP — also auch hier den
    # Reminder-Banner triggern, sonst ginge er bei Take-Over-PPs verloren.
    return _redirect_to_list(pp_min.team.id, just_created_pp_id=plan_period_id)


@router.delete("/{plan_period_id}", response_class=HTMLResponse)
def delete_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    try:
        deleted = db_services.PlanPeriod.delete(plan_period_id)
    except PlanPeriodClosedError as e:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/error.html",
            {"request": request, "message": str(e)},
            status_code=status.HTTP_409_CONFLICT,
        )
    return _redirect_to_list(deleted.team_id)


def _redirect_to_list(
    team_id: uuid.UUID,
    *,
    just_created_pp_id: uuid.UUID | None = None,
) -> Response:
    """HTMX-Trigger zum Liste-Reload + Modal-Close.

    Status 200 mit leerem Body (NICHT 204): bei `hx-target="#modal-root"
    hx-swap="innerHTML"` wird der Modal-Root mit "" ersetzt → Modal verschwindet.
    Bei `hx-swap="none"` (Card-Buttons) bleibt der Swap aus, nur der Trigger
    feuert. Bei 204 würde HTMX laut Spec *gar keinen* Swap ausführen, das
    Modal bliebe stehen.

    Optionaler `just_created_pp_id` triggert zusaetzlich `pp-just-created`
    fuer den Reminder-Banner in `index.html` — Phase C der NG-Verwaltung.
    """
    triggers: dict[str, dict[str, str]] = {
        "periods-changed": {"team_id": str(team_id)},
    }
    if just_created_pp_id is not None:
        triggers["pp-just-created"] = {
            "pp_id": str(just_created_pp_id),
            "team_id": str(team_id),
        }
    payload = json.dumps(triggers)
    return Response(
        content="",
        media_type="text/html",
        status_code=status.HTTP_200_OK,
        headers={"HX-Trigger": payload},
    )
