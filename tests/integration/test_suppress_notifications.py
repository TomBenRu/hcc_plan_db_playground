"""Suppress-Notifications-Schalter (SUPPRESS_NOTIFICATIONS=true).

Verifiziert, dass beide Notification-Hubs den Env-Schalter respektieren:
- ``web_api.email.service.schedule_emails`` plant keinen BackgroundTask.
- ``web_api.inbox.service.create_inbox_message`` legt keine DB-Zeile an,
  gibt ``None`` zurueck und der Aufrufer crasht nicht.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from web_api.email.service import EmailPayload, schedule_emails
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import InboxMessage, InboxMessageType, WebUser


# ── E-Mail-Versand ────────────────────────────────────────────────────────────


def test_schedule_emails_suppressed_when_flag_true(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    caplog: pytest.LogCaptureFixture,
):
    """Mit SUPPRESS_NOTIFICATIONS=true wird KEIN BackgroundTask geplant —
    selbst wenn payloads vorliegen. WARNING-Log wird emittiert."""
    monkeypatch.setenv("SUPPRESS_NOTIFICATIONS", "true")
    bg = BackgroundTasks()
    payloads = [EmailPayload(to=["a@b.de"], subject="Test", html_body="<p>x</p>")]

    with caplog.at_level(logging.WARNING, logger="web_api.email.service"):
        schedule_emails(bg, payloads, session)

    assert bg.tasks == []
    assert any("SUPPRESS_NOTIFICATIONS" in rec.message for rec in caplog.records)


def test_schedule_emails_sends_when_flag_false(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
):
    """Mit SUPPRESS_NOTIFICATIONS=false wird der Standardpfad genommen —
    bei fehlender SMTP-Config wirft das eine Exception, hier reicht uns,
    dass der Code den Suppress-Pfad NICHT genommen hat (Indikator: er kommt
    bis ``load_smtp_config`` durch)."""
    monkeypatch.setenv("SUPPRESS_NOTIFICATIONS", "false")
    bg = BackgroundTasks()
    payloads = [EmailPayload(to=["a@b.de"], subject="Test", html_body="<p>x</p>")]

    # Ohne SMTP-Settings in der DB schmeisst load_smtp_config einen Fehler
    # — genau das wollen wir hier zeigen (Suppress-Pfad wuerde frueh
    # zurueckgehen und nicht crashen).
    with pytest.raises(Exception):
        schedule_emails(bg, payloads, session)


def test_schedule_emails_empty_payloads_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
):
    """Leere Payload-Liste short-circuited VOR dem Suppress-Check —
    keine Logs noetig, keine Tasks."""
    monkeypatch.setenv("SUPPRESS_NOTIFICATIONS", "true")
    bg = BackgroundTasks()
    schedule_emails(bg, [], session)
    assert bg.tasks == []


# ── Inbox-Messages ────────────────────────────────────────────────────────────


def test_create_inbox_message_suppressed_when_flag_true(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    admin_user: WebUser,
    caplog: pytest.LogCaptureFixture,
):
    """Mit SUPPRESS_NOTIFICATIONS=true wird keine InboxMessage angelegt;
    Rueckgabewert ist None, WARNING-Log wird emittiert."""
    monkeypatch.setenv("SUPPRESS_NOTIFICATIONS", "true")

    with caplog.at_level(logging.WARNING, logger="web_api.inbox.service"):
        result = create_inbox_message(
            session,
            recipient_id=admin_user.id,
            msg_type=InboxMessageType.swap_request_received,
            reference_id=uuid.uuid4(),
            reference_type="swap_request",
            snapshot_data={"x": 1},
        )

    assert result is None
    session.commit()
    rows = session.exec(
        select(InboxMessage).where(InboxMessage.recipient_web_user_id == admin_user.id)
    ).all()
    assert rows == []
    assert any("SUPPRESS_NOTIFICATIONS" in rec.message for rec in caplog.records)


def test_create_inbox_message_creates_when_flag_false(
    monkeypatch: pytest.MonkeyPatch,
    session: Session,
    admin_user: WebUser,
):
    """Mit SUPPRESS_NOTIFICATIONS=false (default) wird die Message
    normal angelegt und session.add() wurde aufgerufen."""
    monkeypatch.setenv("SUPPRESS_NOTIFICATIONS", "false")

    result = create_inbox_message(
        session,
        recipient_id=admin_user.id,
        msg_type=InboxMessageType.swap_request_received,
        reference_id=uuid.uuid4(),
        reference_type="swap_request",
        snapshot_data={"x": 1},
    )

    assert result is not None
    session.commit()
    rows = session.exec(
        select(InboxMessage).where(InboxMessage.recipient_web_user_id == admin_user.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].id == result.id