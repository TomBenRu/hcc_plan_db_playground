"""Router: Inbox-Endpoints."""

import uuid

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole
from web_api.dependencies import get_db_session
from web_api.inbox.service import get_inbox_grouped, get_unread_count, mark_as_read
from web_api.templating import templates

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("", response_class=HTMLResponse)
def inbox_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    type_filter: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    role_filter: str | None = Query(default=None),
):
    is_dispatcher = user.has_any_role(WebUserRole.dispatcher, WebUserRole.admin)
    is_employee = user.has_any_role(WebUserRole.employee)
    can_offer_takeover = is_employee
    groups = get_inbox_grouped(
        session, user.id,
        type_filter=type_filter,
        unread_only=unread_only,
        role_filter=role_filter,
        person_id=user.person_id,
    )
    return templates.TemplateResponse(
        "inbox/index.html",
        {
            "request": request,
            "user": user,
            "groups": groups,
            "type_filter": type_filter or "",
            "role_filter": role_filter or "",
            "unread_only": unread_only,
            "is_dispatcher": is_dispatcher,
            "can_offer_takeover": can_offer_takeover,
            "show_role_filter": is_dispatcher and is_employee,
        },
    )


@router.get("/badge", response_class=HTMLResponse)
def inbox_badge(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    count = get_unread_count(session, user.id)
    return templates.TemplateResponse(
        "inbox/partials/inbox_badge.html",
        {"request": request, "unread_count": count},
    )


@router.patch("/{message_id}/read", response_class=HTMLResponse)
def patch_mark_read(
    request: Request,
    message_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    mark_as_read(session, message_id, user.id)
    session.commit()
    count = get_unread_count(session, user.id)
    return templates.TemplateResponse(
        "inbox/partials/inbox_badge.html",
        {"request": request, "unread_count": count},
    )
