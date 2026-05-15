"""Suppress-Notifications-Schalter (SUPPRESS_NOTIFICATIONS=true).

Verifiziert, dass beide Notification-Hubs den Env-Schalter respektieren:
- ``web_api.email.service._send_one_smtp`` (Choke-Point fuer Web- UND
  Scheduler-Pfad) versendet keine Mail.
- ``web_api.inbox.service.create_inbox_message`` legt keine DB-Zeile an,
  gibt ``None`` zurueck und der Aufrufer crasht nicht.
"""

from __future__ import annotations

import logging
import uuid

import pytest
from fastapi import BackgroundTasks
from sqlmodel import Session, select

from web_api.email.config_loader import SmtpConfig
from web_api.email.service import EmailPayload, _send_one_smtp, schedule_emails
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import InboxMessage, InboxMessageType, WebUser


# ── E-Mail-Versand ────────────────────────────────────────────────────────────


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


def test_send_one_smtp_suppressed_at_choke_point(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    """Regressionsschutz fuer Vorfall 2026-05-16: Der Scheduler-Pfad
    (`email_to_users.EmailService._send_one` → `_send_one_smtp`) umgeht
    `schedule_emails` komplett. Der Suppress-Check muss daher auf
    `_send_one_smtp`-Ebene sitzen, sonst rutscht jeder Catchup-/Reminder-
    Versand durch.

    Wir uebergeben eine offensichtlich kaputte SmtpConfig: wuerde der
    Suppress-Pfad versagen, riefe `_send_one_smtp` `smtplib.SMTP("invalid-host")`
    auf und wuerde mit gaierror crashen. Erfolgt stattdessen ein
    schmerzfreier early-return + WARNING-Log, war der Choke-Point aktiv.
    """
    monkeypatch.setenv("SUPPRESS_NOTIFICATIONS", "true")
    fake_config = SmtpConfig(
        host="invalid-host-does-not-exist.local",
        port=587,
        username="x",
        password="x",
        use_tls=False,
        use_ssl=False,
        email_from="a@b.de",
        email_from_name=None,
    )
    payload = EmailPayload(to=["recipient@example.de"], subject="ChokeTest", html_body="<p>x</p>")

    with caplog.at_level(logging.WARNING, logger="web_api.email.service"):
        _send_one_smtp(payload, fake_config)  # darf NICHT crashen

    assert any(
        "SUPPRESS_NOTIFICATIONS" in rec.message and "ChokeTest" in rec.message
        for rec in caplog.records
    )


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