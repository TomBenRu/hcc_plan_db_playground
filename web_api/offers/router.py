"""Router: AvailabilityOffer-Mutations-Endpoints.

List- und Detail-Views gehören zu den UI-Scheiben E2c/E2d; hier nur die
State-Transitions (Create/Accept/Reject/Withdraw) plus Email-/Inbox-Hook.
"""

import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole, require_role
from web_api.config import get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import send_emails_background
from web_api.models.web_models import WebUser
from web_api.models.web_models import AvailabilityOfferStatus
from web_api.offers.service import (
    accept_offer,
    create_offer,
    get_offers_for_dispatcher,
    reject_offer,
    withdraw_offer,
)
from web_api.templating import templates

router = APIRouter(prefix="/offers", tags=["offers"])

_ERROR_HEADERS = {"HX-Retarget": "#offer-action-area", "HX-Reswap": "innerHTML"}


def _error_response(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        "offers/partials/error.html",
        {"request": request, "message": message},
        headers=_ERROR_HEADERS,
    )


def _success_response(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        "offers/partials/action_result.html",
        {"request": request, "message": message},
    )


@router.get("/dispatcher", response_class=HTMLResponse)
def list_dispatcher_offers(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Dispatcher-Übersicht: alle Pending-Angebote in den Teams des Dispatchers."""
    all_offers = get_offers_for_dispatcher(session, user)
    pending_offers = [o for o in all_offers if o.status == AvailabilityOfferStatus.pending]
    return templates.TemplateResponse(
        "offers/dispatcher_index.html",
        {
            "request": request,
            "user": user,
            "offers": pending_offers,
            "total_count": len(pending_offers),
        },
    )


@router.post("", response_class=HTMLResponse)
def post_create_offer(
    request: Request,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    appointment_id: uuid.UUID = Form(...),
    message: str | None = Form(default=None),
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    """Mitarbeiter stellt Angebot für einen unterbesetzten fremden Termin."""
    try:
        offer, payloads = create_offer(session, user, appointment_id, message)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    background_tasks.add_task(send_emails_background, payloads, settings)
    return _success_response(request, "Angebot gesendet.")


@router.post("/{offer_id}/withdraw", response_class=HTMLResponse)
def post_withdraw_offer(
    request: Request,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    """Mitarbeiter zieht sein Angebot zurück (nur solange pending)."""
    try:
        payloads = withdraw_offer(session, offer_id, user)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    background_tasks.add_task(send_emails_background, payloads, settings)
    return _success_response(request, "Angebot zurückgezogen.")


@router.post("/{offer_id}/accept", response_class=HTMLResponse)
def post_accept_offer(
    request: Request,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    """Dispatcher nimmt Angebot an — Offerer wird additiv zum Cast hinzugefügt."""
    try:
        payloads = accept_offer(session, offer_id, user)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    background_tasks.add_task(send_emails_background, payloads, settings)
    return _success_response(request, "Angebot angenommen — Mitarbeiter eingeteilt.")


@router.post("/{offer_id}/reject", response_class=HTMLResponse)
def post_reject_offer(
    request: Request,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    """Dispatcher lehnt Angebot ab."""
    try:
        payloads = reject_offer(session, offer_id, user)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    background_tasks.add_task(send_emails_background, payloads, settings)
    return _success_response(request, "Angebot abgelehnt.")