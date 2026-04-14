"""Router: Dispatcher-Endpoints."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import WebUserRole, require_role
from web_api.models.web_models import WebUser
from web_api.cancellations.service import get_cancellations_for_dispatcher
from web_api.dependencies import get_db_session
from web_api.templating import templates

router = APIRouter(prefix="/dispatcher", tags=["dispatcher"])


@router.get("/cancellations", response_class=HTMLResponse)
def dispatcher_cancellations(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    status_filter: str | None = None,
):
    cancellations = get_cancellations_for_dispatcher(session, user, status_filter)
    return templates.TemplateResponse(
        "dispatcher/cancellations.html",
        {
            "request": request,
            "user": user,
            "cancellations": cancellations,
            "status_filter": status_filter,
        },
    )
