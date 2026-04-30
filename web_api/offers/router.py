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
    Query,
    Request,
)
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser, WebUserRole, require_role
from web_api.dependencies import get_db_session
from web_api.email.service import schedule_emails
from web_api.models.web_models import WebUser
from web_api.models.web_models import AvailabilityOfferStatus
from web_api.offers.service import (
    accept_offer,
    create_offer,
    get_offer_detail,
    get_offers_for_dispatcher,
    get_offers_for_user,
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


@router.get("/mine", response_class=HTMLResponse)
def list_my_offers(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Eigene Angebote des Offerers — aktiver Einstiegspunkt für Mitarbeiter.

    Zeigt alle eigenen Angebote (pending + abgeschlossen), nach Erstellung absteigend.
    Pending erscheinen oben, Terminals (accepted/rejected/withdrawn/superseded)
    darunter als Archiv.
    """
    offers = get_offers_for_user(session, user.id)
    pending_count = sum(
        1 for o in offers if o.status == AvailabilityOfferStatus.pending
    )
    return templates.TemplateResponse(
        "offers/mine_index.html",
        {
            "request": request,
            "user": user,
            "offers": offers,
            "pending_count": pending_count,
            "total_count": len(offers),
        },
    )


@router.get("/{offer_id}", response_class=HTMLResponse)
def get_offer_detail_page(
    request: Request,
    offer_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Rollen-sensitive Detail-Ansicht eines Angebots.

    Ziel für Inbox-Deep-Links (`reference_type == "availability_offer"`). Sichtbar
    für Offerer und Dispatcher des zuständigen Teams; sonst 403.
    """
    detail = get_offer_detail(session, offer_id, user)
    return templates.TemplateResponse(
        "offers/detail.html",
        {"request": request, "user": user, "offer": detail},
    )


@router.post("", response_class=HTMLResponse)
def post_create_offer(
    request: Request,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    appointment_id: uuid.UUID = Form(...),
    message: str | None = Form(default=None),
    session: Session = Depends(get_db_session),
):
    """Mitarbeiter stellt Angebot für einen unterbesetzten fremden Termin."""
    try:
        offer, payloads = create_offer(session, user, appointment_id, message)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    schedule_emails(background_tasks, payloads, session)
    return _success_response(request, "Angebot gesendet.")


@router.post("/{offer_id}/withdraw", response_class=HTMLResponse)
def post_withdraw_offer(
    request: Request,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Mitarbeiter zieht sein Angebot zurück (nur solange pending)."""
    try:
        payloads = withdraw_offer(session, offer_id, user)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    schedule_emails(background_tasks, payloads, session)
    return _success_response(request, "Angebot zurückgezogen.")


@router.post("/{offer_id}/accept", response_class=HTMLResponse)
def post_accept_offer(
    request: Request,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Dispatcher nimmt Angebot an — Offerer wird additiv zum Cast hinzugefügt."""
    try:
        payloads = accept_offer(session, offer_id, user)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    schedule_emails(background_tasks, payloads, session)
    return _success_response(request, "Angebot angenommen — Mitarbeiter eingeteilt.")


@router.get("/{offer_id}/actions", response_class=HTMLResponse)
def get_dispatcher_actions(
    request: Request,
    offer_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    edit: int = Query(default=0),
):
    """Dispatcher-Aktionspanel für ein Offer — Default- vs. Reject-Modus.

    Wird per HTMX vom Detail-Template aufgerufen, um zwischen
    „Annehmen/Ablehnen"-Buttons (edit=0) und dem Reject-Form mit Textarea
    (edit=1) umzuschalten. Beide Partials rendern denselben Wrapper
    `#dispatcher-actions` und ersetzen sich gegenseitig via `hx-swap="outerHTML"`.
    """
    detail = get_offer_detail(session, offer_id, user)
    if not detail.is_dispatcher_for_team:
        raise HTTPException(403, detail="Kein Zugriff.")
    if detail.status != AvailabilityOfferStatus.pending:
        raise HTTPException(409, detail="Dieses Angebot ist nicht mehr pending.")
    template = (
        "offers/partials/dispatcher_actions_reject.html"
        if edit
        else "offers/partials/dispatcher_actions.html"
    )
    return templates.TemplateResponse(
        template,
        {"request": request, "user": user, "offer": detail},
    )


@router.get("/{offer_id}/card", response_class=HTMLResponse)
def get_dispatcher_card(
    request: Request,
    offer_id: uuid.UUID,
    session: Session = Depends(get_db_session),
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    edit: int = Query(default=0),
):
    """Dispatcher-Listen-Card für ein Offer — Default- vs. Reject-Modus.

    Wird per HTMX aus der Listen-Ansicht aufgerufen, um die ganze Card
    zwischen „Accept + Ablehnen"-Buttons (edit=0) und dem Reject-Form mit
    Textarea (edit=1) umzuschalten. `hx-swap="outerHTML"` auf dem
    `.offer-card`-Container.
    """
    summaries = get_offers_for_dispatcher(session, user)
    summary = next((s for s in summaries if s.id == offer_id), None)
    if summary is None:
        raise HTTPException(404, detail="Angebot nicht gefunden oder nicht in deinem Zuständigkeitsbereich.")
    if summary.status != AvailabilityOfferStatus.pending:
        raise HTTPException(409, detail="Dieses Angebot ist nicht mehr pending.")
    template = (
        "offers/partials/offer_card_reject.html"
        if edit
        else "offers/partials/offer_card.html"
    )
    return templates.TemplateResponse(
        template,
        {"request": request, "user": user, "offer": summary},
    )


@router.post("/{offer_id}/reject", response_class=HTMLResponse)
def post_reject_offer(
    request: Request,
    offer_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    reason: str | None = Form(default=None),
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Dispatcher lehnt Angebot ab — optional mit schriftlicher Begründung."""
    try:
        payloads = reject_offer(session, offer_id, user, reason=reason)
    except HTTPException as exc:
        return _error_response(request, exc.detail)
    session.commit()
    schedule_emails(background_tasks, payloads, session)
    return _success_response(request, "Angebot abgelehnt.")