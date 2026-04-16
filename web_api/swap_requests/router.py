"""Router: Tausch-Anfragen-Endpoints (Phase 2)."""

import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select as sa_select
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole, require_role
from web_api.config import get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import send_emails_background
from web_api.models.web_models import CancellationRequest, CancellationStatus, WebUser

_SWAP_LIST_TEMPLATE = "swap_requests/partials/swap_list.html"
_ERROR_HEADERS = {"HX-Retarget": "#swap-action-area", "HX-Reswap": "innerHTML"}


def _parse_date(value: str | None) -> date | None:
    """Leere Strings (aus leeren HTML-Date-Inputs) werden als None behandelt."""
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
from web_api.swap_requests.service import (
    SwapCandidate,
    _load_appointment_context,
    accept_swap_request,
    confirm_swap_request,
    create_swap_request,
    get_filter_options_for_user,
    get_own_upcoming_appointments,
    get_swap_candidate_appointments,
    get_swap_requests_for_user,
    reject_swap_request,
    withdraw_swap_request,
)
from web_api.templating import templates

router = APIRouter(prefix="/swap-requests", tags=["swap-requests"])


@router.get("", response_class=HTMLResponse)
def list_swap_requests(
    request: Request,
    user: LoggedInUser,
    status_filter: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
):
    swaps = get_swap_requests_for_user(session, user.id)
    is_dispatcher = user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)

    # Status-Filter anwenden
    if status_filter:
        swaps = [s for s in swaps if s.status.value == status_filter]

    return templates.TemplateResponse(
        "swap_requests/index.html",
        {
            "request": request,
            "user": user,
            "swaps": swaps,
            "is_dispatcher": is_dispatcher,
            "from_dispatcher": False,
            "status_filter": status_filter or "",
        },
    )


@router.get("/preflight/{appointment_id}", response_class=HTMLResponse)
def swap_preflight(
    request: Request,
    appointment_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Prüft Konflikte vor dem Öffnen der Browse-Seite; leitet bei OK per HX-Redirect weiter."""
    open_cancellation = session.execute(
        sa_select(CancellationRequest.id)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).first()
    if open_cancellation is not None:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": "Für diesen Termin existiert bereits eine offene Absage."},
        )
    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/swap-requests/browse?requester_appointment_id={appointment_id}"},
    )


@router.get("/browse", response_class=HTMLResponse)
def browse_swap_candidates(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    requester_appointment_id: uuid.UUID | None = Query(default=None),
):
    error_message = None
    if requester_appointment_id is not None:
        open_cancellation = session.execute(
            sa_select(CancellationRequest.id)
            .where(CancellationRequest.appointment_id == requester_appointment_id)
            .where(CancellationRequest.status == CancellationStatus.pending)
        ).first()
        if open_cancellation is not None:
            error_message = "Für diesen Termin existiert bereits eine offene Absage."

    locations, colleagues = get_filter_options_for_user(session, user, requester_appointment_id)
    requester_ctx = None
    if requester_appointment_id is not None and error_message is None:
        requester_ctx = _load_appointment_context(session, requester_appointment_id)
    return templates.TemplateResponse(
        "swap_requests/browse.html",
        {
            "request": request,
            "user": user,
            "locations": locations,
            "colleagues": colleagues,
            "requester_appointment_id": requester_appointment_id,
            "requester_ctx": requester_ctx,
            "error_message": error_message,
        },
    )


@router.get("/browse/results", response_class=HTMLResponse)
def browse_swap_results(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    location_id: list[uuid.UUID] = Query(default=[]),
    person_id: list[uuid.UUID] = Query(default=[]),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    requester_appointment_id: uuid.UUID | None = Query(default=None),
):
    candidates = get_swap_candidate_appointments(
        session,
        user,
        location_ids=location_id or None,
        person_ids=person_id or None,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
        requester_appointment_id=requester_appointment_id,
    )
    return templates.TemplateResponse(
        "swap_requests/partials/candidate_list.html",
        {"request": request, "candidates": candidates, "user": user,
         "requester_appointment_id": requester_appointment_id},
    )


@router.get("/form", response_class=HTMLResponse)
def swap_form(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    target_appointment_id: uuid.UUID | None = Query(default=None),
    target_web_user_id: uuid.UUID | None = Query(default=None),
    requester_appointment_id: uuid.UUID | None = Query(default=None),
):
    if requester_appointment_id is not None:
        open_cancellation = session.execute(
            sa_select(CancellationRequest.id)
            .where(CancellationRequest.appointment_id == requester_appointment_id)
            .where(CancellationRequest.status == CancellationStatus.pending)
        ).first()
        if open_cancellation is not None:
            return templates.TemplateResponse(
                "swap_requests/partials/error.html",
                {"request": request, "message": "Für diesen Termin existiert bereits eine offene Absage."},
                headers=_ERROR_HEADERS,
            )

    own_appointments = get_own_upcoming_appointments(session, user)
    requester_ctx = None
    if requester_appointment_id is not None:
        requester_ctx = _load_appointment_context(session, requester_appointment_id)
    return templates.TemplateResponse(
        "swap_requests/partials/swap_form.html",
        {
            "request": request,
            "user": user,
            "own_appointments": own_appointments,
            "prefilled_target_id": target_appointment_id,
            "prefilled_target_web_user_id": target_web_user_id,
            "prefilled_requester_id": requester_appointment_id,
            "requester_ctx": requester_ctx,
        },
    )


@router.get("/{swap_id}", response_class=HTMLResponse)
def swap_detail(
    request: Request,
    swap_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    from_dispatcher: bool = Query(default=False),
):
    from web_api.models.web_models import SwapRequest as SwapRequestModel
    from web_api.swap_requests.service import _load_appointment_context, _build_swap_snapshot

    swap = session.get(SwapRequestModel, swap_id)
    if swap is None:
        raise HTTPException(404, detail="Tausch-Anfrage nicht gefunden.")

    # Zugriff: Anfragender, Ziel oder Dispatcher
    is_dispatcher = user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)
    is_requester = swap.requester_web_user_id == user.id
    is_target = swap.target_web_user_id == user.id
    if not (is_requester or is_target or is_dispatcher):
        raise HTTPException(403, detail="Kein Zugriff.")

    req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
    tgt_ctx = _load_appointment_context(session, swap.target_appointment_id)
    snapshot = _build_swap_snapshot(session, swap, req_ctx)

    return templates.TemplateResponse(
        "swap_requests/detail.html",
        {
            "request": request,
            "user": user,
            "swap": swap,
            "req_ctx": req_ctx,
            "tgt_ctx": tgt_ctx,
            "snapshot": snapshot,
            "is_dispatcher": is_dispatcher,
            "is_requester": is_requester,
            "is_target": is_target,
            "from_dispatcher": from_dispatcher,
        },
    )


@router.post("", response_class=HTMLResponse)
def post_swap_request(
    request: Request,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
    requester_appointment_id: uuid.UUID = Form(...),
    target_appointment_ids: list[uuid.UUID] = Form(...),
    target_web_user_id: uuid.UUID | None = Form(default=None),
    message: str | None = Form(default=None),
):
    try:
        swaps, email_payloads = create_swap_request(
            session, user, requester_appointment_id, target_appointment_ids, message,
            target_web_user_id=target_web_user_id,
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": exc.detail},
            headers=_ERROR_HEADERS,
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    return templates.TemplateResponse(
        "swap_requests/partials/swap_submitted.html",
        {"request": request, "user": user, "swap_count": len(swaps), "swap_id": swaps[0].id if swaps else None},
    )


@router.post("/{swap_id}/accept", response_class=HTMLResponse)
def post_accept_swap(
    request: Request,
    swap_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    try:
        email_payloads = accept_swap_request(session, swap_id, user)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": exc.detail},
            headers=_ERROR_HEADERS,
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps,
         "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin),
         "from_dispatcher": False},
    )


@router.post("/{swap_id}/reject", response_class=HTMLResponse)
def post_reject_swap(
    request: Request,
    swap_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    try:
        email_payloads = reject_swap_request(session, swap_id, user)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": exc.detail},
            headers=_ERROR_HEADERS,
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps,
         "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin),
         "from_dispatcher": False},
    )


@router.post("/{swap_id}/confirm", response_class=HTMLResponse)
def post_confirm_swap(
    request: Request,
    swap_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    try:
        email_payloads = confirm_swap_request(session, swap_id, user)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": exc.detail},
            headers=_ERROR_HEADERS,
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps, "is_dispatcher": True, "from_dispatcher": True},
    )


@router.post("/{swap_id}/withdraw", response_class=HTMLResponse)
def post_withdraw_swap(
    request: Request,
    swap_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    try:
        withdraw_swap_request(session, swap_id, user)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": exc.detail},
            headers=_ERROR_HEADERS,
        )
    session.commit()

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps,
         "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin),
         "from_dispatcher": False},
    )