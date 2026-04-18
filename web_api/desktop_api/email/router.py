"""Desktop-API: E-Mail-Versand (/api/v1/email).

Zentrale SMTP-Dispatch: alle E-Mails gehen ueber den Server — der Desktop-Client
haelt keine SMTP-Credentials mehr. Anders als andere Phase-6-Endpunkte sind
diese Operationen stateless (fire-and-forget, kein Undo).
"""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services
from email_to_users.service import EmailService
from web_api.desktop_api.auth import DesktopUser

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


@router.post("/plan-notification", response_model=SendStats, status_code=status.HTTP_200_OK)
def send_plan_notification(body: PlanNotificationBody, _: DesktopUser):
    recipient_id_strs = [str(i) for i in body.recipient_ids] if body.recipient_ids else None
    stats = EmailService().send_plan_notification(
        str(body.plan_id), recipient_ids=recipient_id_strs,
        include_attachments=body.include_attachments,
    )
    return SendStats(**stats)


@router.post("/availability-request", response_model=SendStats)
def send_availability_request(body: AvailabilityRequestBody, _: DesktopUser):
    recipient_id_strs = [str(i) for i in body.recipient_ids] if body.recipient_ids else None
    stats = EmailService().send_availability_request(
        str(body.plan_period_id), recipient_ids=recipient_id_strs,
        url_base=body.url_base, notes=body.notes,
    )
    return SendStats(**stats)


@router.post("/custom", response_model=SendStats)
def send_custom_email(body: CustomEmailBody, _: DesktopUser):
    recipients = _fetch_persons(body.recipient_ids)
    stats = EmailService().send_custom_email(
        subject=body.subject, text_content=body.text_content,
        html_content=body.html_content, recipients=recipients,
    )
    return SendStats(**stats)


@router.post("/bulk", response_model=SendStats)
def send_bulk_email(body: BulkEmailBody, _: DesktopUser):
    stats = EmailService().send_bulk_email(
        subject=body.subject, text_content=body.text_content,
        html_content=body.html_content,
        recipients=_fetch_persons(body.recipient_ids),
        cc=_fetch_persons(body.cc_ids),
        bcc=_fetch_persons(body.bcc_ids),
    )
    return SendStats(**stats)