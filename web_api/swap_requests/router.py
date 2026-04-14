"""Router: Tausch-Anfragen-Endpoints (Phase 2)."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole, require_role
from web_api.models.web_models import WebUser
from web_api.config import get_settings

_SWAP_LIST_TEMPLATE = "swap_requests/partials/swap_list.html"
from web_api.dependencies import get_db_session
from web_api.email.service import send_emails_background
from web_api.swap_requests.service import (
    accept_swap_request,
    confirm_swap_request,
    create_swap_request,
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
    session: Session = Depends(get_db_session),
):
    swaps = get_swap_requests_for_user(session, user.id)
    is_dispatcher = user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)
    return templates.TemplateResponse(
        "swap_requests/index.html",
        {"request": request, "user": user, "swaps": swaps, "is_dispatcher": is_dispatcher},
    )


@router.post("", response_class=HTMLResponse)
def post_swap_request(
    request: Request,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
    requester_appointment_id: uuid.UUID = Form(...),
    target_appointment_id: uuid.UUID = Form(...),
    message: str | None = Form(default=None),
):
    try:
        swap, email_payloads = create_swap_request(
            session, user, requester_appointment_id, target_appointment_id, message
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            "swap_requests/partials/error.html",
            {"request": request, "message": exc.detail},
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    return templates.TemplateResponse(
        "swap_requests/partials/swap_submitted.html",
        {"request": request, "user": user, "swap_id": swap.id},
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
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps,
         "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)},
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
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps,
         "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)},
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
        )
    session.commit()
    background_tasks.add_task(send_emails_background, email_payloads, settings)

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps, "is_dispatcher": True},
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
        )
    session.commit()

    swaps = get_swap_requests_for_user(session, user.id)
    return templates.TemplateResponse(
        _SWAP_LIST_TEMPLATE,
        {"request": request, "user": user, "swaps": swaps,
         "is_dispatcher": user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)},
    )
