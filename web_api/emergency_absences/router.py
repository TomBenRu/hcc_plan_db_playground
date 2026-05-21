"""Router: Notfall-Absage-Endpoints.

URL-Struktur:
  GET  /emergency-absences/form/{appointment_id}   HTMX-Modal-Form
  POST /emergency-absences/                         Erstellt EA + Cast-Removal
  GET  /emergency-absences/                         Liste eigener EAs (optional Listenview)

Die Detail-Ansicht einer Notfall-Absage läuft über die bestehende
Cancellation-Detail-Page `/cancellations/{cr_id}` (Variant B des Datenmodells).
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select as sa_select
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser
from web_api.dependencies import get_db_session
from web_api.email.service import schedule_emails
from web_api.emergency_absences.service import create_emergency_absence
from web_api.models.web_models import (
    CancellationKind,
    CancellationRequest,
    CancellationStatus,
    SwapRequest,
    SwapRequestStatus,
)
from web_api.templating import templates

router = APIRouter(prefix="/emergency-absences", tags=["emergency-absences"])


@router.get("/form/{appointment_id}", response_class=HTMLResponse)
def get_emergency_absence_form(
    request: Request,
    appointment_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """HTMX-Form für die Notfall-Absage (Pflicht-Reason).

    Pre-Checks (User-freundliche Fehler statt 500):
      - keine doppelte offene Cancellation auf dem Appointment
      - kein offener Swap auf dem Appointment
    """
    _retarget = {"HX-Retarget": "#cancellation-action-area", "HX-Reswap": "innerHTML"}

    existing = session.execute(
        sa_select(CancellationRequest.id)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).first()
    if existing is not None:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": "Für diesen Termin existiert bereits eine offene Absage."},
            headers=_retarget,
        )

    open_swap = session.execute(
        sa_select(SwapRequest.id)
        .where(
            (SwapRequest.requester_appointment_id == appointment_id)
            | (SwapRequest.target_appointment_id == appointment_id)
        )
        .where(SwapRequest.status.in_([
            SwapRequestStatus.pending,
            SwapRequestStatus.accepted_by_target,
        ]))
    ).first()
    if open_swap is not None:
        return templates.TemplateResponse(
            "cancellations/partials/cancel_error.html",
            {"request": request, "message": "Für diesen Termin existiert bereits eine offene Tausch-Anfrage."},
            headers=_retarget,
        )

    return templates.TemplateResponse(
        "emergency_absences/partials/emergency_form.html",
        {"request": request, "user": user, "appointment_id": appointment_id},
    )


@router.post("", response_class=HTMLResponse)
def post_emergency_absence(
    request: Request,
    user: LoggedInUser,
    background_tasks: BackgroundTasks,
    appointment_id: uuid.UUID = Form(...),
    reason: str = Form(...),
    session: Session = Depends(get_db_session),
):
    """Erstellt die Notfall-Absage und triggert Cast-Removal + Broadcast.

    Bei Erfolg: HX-Redirect auf die Cancellation-Detail-Page (gleiche URL wie
    reguläre Cancellations, weil dasselbe Backing-Modell). Bei Fehlern: 409/422
    werden vom FastAPI-Layer zu HTMX-konsumierbaren Responses (siehe
    feedback_htmx_4xx_response_handling).
    """
    detail, payloads = create_emergency_absence(session, user, appointment_id, reason)
    session.commit()

    if payloads:
        schedule_emails(background_tasks, payloads, session)

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["HX-Redirect"] = f"/cancellations/{detail.id}"
    return response


@router.get("", response_class=HTMLResponse)
def list_emergency_absences(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Listet alle Notfall-Absagen des aktuellen Users (eigene Reporter-Rolle).

    Für Dispatcher: die Dispatcher-Übersicht läuft weiterhin über
    `/cancellations/` mit Filter `kind=emergency`. Diese Route bedient
    primär den Mitarbeiter-Self-Service.
    """
    rows = session.execute(
        sa_select(CancellationRequest)
        .where(CancellationRequest.web_user_id == user.id)
        .where(CancellationRequest.kind == CancellationKind.emergency)
        .order_by(CancellationRequest.created_at.desc())
    ).scalars().all()

    return templates.TemplateResponse(
        "emergency_absences/index.html",
        {"request": request, "user": user, "emergency_absences": rows},
    )
