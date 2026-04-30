"""Desktop-API: E-Mail-Versand (/api/v1/email).

Zentrale SMTP-Dispatch: alle E-Mails gehen über den Server — der Desktop-Client
hält keine SMTP-Credentials mehr. SMTP-Konfiguration wird pro Request aus der
DB geladen (web_api.email.config_loader.load_smtp_config) und an den
EmailService weitergegeben. Damit gibt es genau eine Konfigurationsquelle für
alle E-Mail-versendenden Subsysteme.
"""

import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlmodel import Session

from database import db_services
from email_to_users.service import EmailService
from web_api.dependencies import get_db_session
from web_api.desktop_api.auth import DesktopUser
from web_api.email.config_loader import load_smtp_config

router = APIRouter(prefix="/email", tags=["desktop-email"])


class PlanNotificationBody(BaseModel):
    plan_id: uuid.UUID
    recipient_ids: list[uuid.UUID] | None = None
    include_attachments: bool = True


class AvailabilityRequestBody(BaseModel):
    plan_period_id: uuid.UUID
    recipient_ids: list[uuid.UUID] | None = None
    url_base: str | None = None
    notes: str | None = None


class CustomEmailBody(BaseModel):
    subject: str
    text_content: str
    html_content: str | None = None
    recipient_ids: list[uuid.UUID]


class BulkEmailBody(BaseModel):
    subject: str
    text_content: str
    html_content: str | None = None
    recipient_ids: list[uuid.UUID] = []
    cc_ids: list[uuid.UUID] = []
    bcc_ids: list[uuid.UUID] = []


class SendStats(BaseModel):
    success: int = 0
    failed: int = 0
    error: str | None = None


def _fetch_persons(ids: list[uuid.UUID] | None):
    if not ids:
        return None
    return db_services.Person.get_batch(ids)


def _build_service(session: Session) -> EmailService:
    """Lädt die SMTP-Config aus der DB und instantiiert den Service.

    EmailNotConfiguredError propagiert in den Handler, falls die Tabelle leer
    oder unvollständig ist — der Admin sieht den Fehler-Text im Response statt
    eines stillen Wegschluckens im Background-Task.
    """
    return EmailService(load_smtp_config(session))


@router.post("/plan-notification", response_model=SendStats, status_code=status.HTTP_200_OK)
def send_plan_notification(
    body: PlanNotificationBody,
    _: DesktopUser,
    session: Session = Depends(get_db_session),
):
    recipient_id_strs = [str(i) for i in body.recipient_ids] if body.recipient_ids else None
    stats = _build_service(session).send_plan_notification(
        str(body.plan_id),
        recipient_ids=recipient_id_strs,
        include_attachments=body.include_attachments,
    )
    return SendStats(**stats)


@router.post("/availability-request", response_model=SendStats)
def send_availability_request(
    body: AvailabilityRequestBody,
    _: DesktopUser,
    session: Session = Depends(get_db_session),
):
    recipient_id_strs = [str(i) for i in body.recipient_ids] if body.recipient_ids else None
    stats = _build_service(session).send_availability_request(
        str(body.plan_period_id),
        recipient_ids=recipient_id_strs,
        url_base=body.url_base,
        notes=body.notes,
    )
    return SendStats(**stats)


@router.post("/custom", response_model=SendStats)
def send_custom_email(
    body: CustomEmailBody,
    _: DesktopUser,
    session: Session = Depends(get_db_session),
):
    recipients = _fetch_persons(body.recipient_ids)
    stats = _build_service(session).send_custom_email(
        subject=body.subject,
        text_content=body.text_content,
        html_content=body.html_content,
        recipients=recipients,
    )
    return SendStats(**stats)


@router.post("/bulk", response_model=SendStats)
def send_bulk_email(
    body: BulkEmailBody,
    _: DesktopUser,
    session: Session = Depends(get_db_session),
):
    stats = _build_service(session).send_bulk_email(
        subject=body.subject,
        text_content=body.text_content,
        html_content=body.html_content,
        recipients=_fetch_persons(body.recipient_ids),
        cc=_fetch_persons(body.cc_ids),
        bcc=_fetch_persons(body.bcc_ids),
    )
    return SendStats(**stats)