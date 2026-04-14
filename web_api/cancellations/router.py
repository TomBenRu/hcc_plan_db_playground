"""Router: Absage-Endpoints (Phase 1 + Phase 2 Takeover)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole, require_role
from web_api.models.web_models import WebUser
from web_api.cancellations.takeover_service import (
    accept_takeover_offer,
    create_takeover_offer,
)
from web_api.cancellations.service import (
    create_cancellation,
    get_cancellation_detail,
    get_circle_cancellations,
    get_my_cancellations,
    withdraw_cancellation,
)
from web_api.models.web_models import CancellationRequest, CancellationStatus
from sqlalchemy import select as sa_select
from web_api.config import get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import send_emails_background
from web_api.templating import templates

router = APIRouter(prefix="/cancellations", tags=["cancellations"])


@router.get("/form/{appointment_id}", response_class=HTMLResponse)
def get_cancel_form(
    request: Request,
    appointment_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    existing = session.execute(
        sa_select(CancellationRequest.id)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).first()
    if existing is not None:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": "Für diesen Termin existiert bereits eine offene Absage."},
            headers={"HX-Retarget": "#cancellation-action-area", "HX-Reswap": "innerHTML"},
        )
    return templates.TemplateResponse(
        "cancellations/partials/cancel_form.html",
        {"request": request, "user": user, "appointment_id": appointment_id},
    )


@router.get("", response_class=HTMLResponse)
def list_cancellations(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    status_filter: str | None = None,
):
    cancellations = get_my_cancellations(session, user.id, status_filter)
    circle_cancellations = get_circle_cancellations(session, user.id, status_filter)

    return templates.TemplateResponse(
        "cancellations/index.html",
        {
            "request": request,
            "user": user,
            "cancellations": cancellations,
            "circle_cancellations": circle_cancellations,
            "is_dispatcher": False,
            "status_filter": status_filter,
        },
    )


@router.post("", response_class=HTMLResponse)
def post_cancellation(
    request: Request,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
    appointment_id: uuid.UUID = Form(...),
    reason: str | None = Form(default=None),
):
    _retarget = {"HX-Retarget": "#cancellation-action-area", "HX-Reswap": "innerHTML"}
    try:
        detail, email_payloads = create_cancellation(session, user, appointment_id, reason)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": exc.detail},
            headers=_retarget,
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    return templates.TemplateResponse(
        "cancellations/partials/cancel_success.html",
        {"request": request, "user": user, "detail": detail},
        headers=_retarget,
    )


@router.get("/cancel-button/{appointment_id}", response_class=HTMLResponse)
def get_cancel_button(
    request: Request,
    appointment_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Gibt Button oder 'bereits gestellt'-Badge zurück (nach Abbrechen im Formular)."""
    existing = session.execute(
        sa_select(CancellationRequest.id)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).first()
    return templates.TemplateResponse(
        "cancellations/partials/cancel_button.html",
        {"request": request, "appointment_id": appointment_id, "has_pending": existing is not None},
    )


@router.get("/{cancellation_id}", response_class=HTMLResponse)
def get_detail(
    request: Request,
    cancellation_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    from_dispatcher: bool = Query(default=False),
):
    detail = get_cancellation_detail(session, cancellation_id, user)
    return templates.TemplateResponse(
        "cancellations/detail.html",
        {
            "request": request,
            "user": user,
            "detail": detail,
            "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin),
            "can_offer_takeover": user.has_any_role(WebUserRole.employee) and not from_dispatcher,
            "back_url": "/dispatcher/cancellations" if from_dispatcher else "/cancellations",
            "from_dispatcher": from_dispatcher,
            "is_own": detail.requester_web_user_id == user.id,
        },
    )


@router.patch("/{cancellation_id}/withdraw", response_class=HTMLResponse)
def patch_withdraw(
    request: Request,
    cancellation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    try:
        detail, email_payloads = withdraw_cancellation(session, cancellation_id, user)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": exc.detail},
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    return templates.TemplateResponse(
        "cancellations/partials/withdraw_success.html",
        {"request": request},
    )


# ── Phase 2: Takeover-Offer-Endpoints ────────────────────────────────────────


@router.post("/{cancellation_id}/takeover-offers", response_class=HTMLResponse)
def post_takeover_offer(
    request: Request,
    cancellation_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
    message: str | None = Form(default=None),
):
    try:
        offer, email_payloads = create_takeover_offer(session, cancellation_id, user, message)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": exc.detail},
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    detail = get_cancellation_detail(session, cancellation_id, user)
    return templates.TemplateResponse(
        "cancellations/partials/takeover_offer_submitted.html",
        {"request": request, "user": user, "detail": detail},
    )


@router.post(
    "/{cancellation_id}/takeover-offers/{offer_id}/accept",
    response_class=HTMLResponse,
)
def post_accept_takeover_offer(
    request: Request,
    cancellation_id: uuid.UUID,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    try:
        email_payloads = accept_takeover_offer(session, cancellation_id, offer_id, user)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": exc.detail},
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/cancellations/{cancellation_id}"},
    )
