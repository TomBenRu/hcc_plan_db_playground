"""Router: Absage-Endpoints (Phase 1)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole, require_role
from web_api.cancellations.service import (
    create_cancellation,
    get_cancellation_detail,
    get_cancellations_for_dispatcher,
    get_my_cancellations,
    withdraw_cancellation,
)
from web_api.config import get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import send_email
from web_api.templating import templates

router = APIRouter(prefix="/cancellations", tags=["cancellations"])


def _send_emails_bg(payloads, settings):
    for payload in payloads:
        send_email(
            payload,
            backend=settings.EMAIL_BACKEND,
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            email_from=settings.EMAIL_FROM,
        )


@router.get("/form/{appointment_id}", response_class=HTMLResponse)
def get_cancel_form(
    request: Request,
    appointment_id: uuid.UUID,
    user: LoggedInUser,
):
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
    if user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin):
        cancellations = get_cancellations_for_dispatcher(session, user, status_filter)
        is_dispatcher = True
    else:
        cancellations = get_my_cancellations(session, user.id, status_filter)
        is_dispatcher = False

    return templates.TemplateResponse(
        "cancellations/index.html",
        {
            "request": request,
            "user": user,
            "cancellations": cancellations,
            "is_dispatcher": is_dispatcher,
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
    try:
        detail, email_payloads = create_cancellation(session, user, appointment_id, reason)
    except HTTPException as exc:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": exc.detail},
        )
    session.commit()
    background_tasks.add_task(_send_emails_bg, email_payloads, settings)

    return templates.TemplateResponse(
        "cancellations/partials/cancel_success.html",
        {"request": request, "user": user, "detail": detail},
    )


@router.get("/{cancellation_id}", response_class=HTMLResponse)
def get_detail(
    request: Request,
    cancellation_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    detail = get_cancellation_detail(session, cancellation_id, user)
    return templates.TemplateResponse(
        "cancellations/detail.html",
        {"request": request, "user": user, "detail": detail},
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
    background_tasks.add_task(_send_emails_bg, email_payloads, settings)

    return templates.TemplateResponse(
        "cancellations/partials/cancel_success.html",
        {"request": request, "user": user, "detail": detail},
    )
