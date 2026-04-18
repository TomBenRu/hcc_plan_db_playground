"""Desktop-API-Client: E-Mail-Versand.

Alle E-Mails werden ueber den Server versendet — der Desktop-Client
haelt keine SMTP-Credentials mehr.
"""

import uuid
from typing import Any

from gui.api_client.client import get_api_client


def send_plan_notification(plan_id: uuid.UUID,
                           recipient_ids: list[uuid.UUID] | None = None,
                           include_attachments: bool = True) -> dict[str, Any]:
    return get_api_client().post("/api/v1/email/plan-notification", json={
        "plan_id": str(plan_id),
        "recipient_ids": [str(i) for i in recipient_ids] if recipient_ids else None,
        "include_attachments": include_attachments,
    })


def send_availability_request(plan_period_id: uuid.UUID,
                              recipient_ids: list[uuid.UUID] | None = None,
                              url_base: str | None = None,
                              notes: str | None = None) -> dict[str, Any]:
    return get_api_client().post("/api/v1/email/availability-request", json={
        "plan_period_id": str(plan_period_id),
        "recipient_ids": [str(i) for i in recipient_ids] if recipient_ids else None,
        "url_base": url_base,
        "notes": notes,
    })


def send_custom_email(subject: str, text_content: str,
                      recipient_ids: list[uuid.UUID],
                      html_content: str | None = None) -> dict[str, Any]:
    return get_api_client().post("/api/v1/email/custom", json={
        "subject": subject,
        "text_content": text_content,
        "html_content": html_content,
        "recipient_ids": [str(i) for i in recipient_ids],
    })


def send_bulk_email(subject: str, text_content: str,
                    recipient_ids: list[uuid.UUID] | None = None,
                    cc_ids: list[uuid.UUID] | None = None,
                    bcc_ids: list[uuid.UUID] | None = None,
                    html_content: str | None = None) -> dict[str, Any]:
    return get_api_client().post("/api/v1/email/bulk", json={
        "subject": subject,
        "text_content": text_content,
        "html_content": html_content,
        "recipient_ids": [str(i) for i in (recipient_ids or [])],
        "cc_ids": [str(i) for i in (cc_ids or [])],
        "bcc_ids": [str(i) for i in (bcc_ids or [])],
    })