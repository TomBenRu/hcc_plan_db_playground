"""Takeover-Offer Service: Übernahme-Angebote für den Absage-Workflow."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select, update as sa_update
from sqlmodel import Session

from database.models import Person
from web_api.cancellations.service import (
    _build_snapshot,
    _get_dispatcher_web_user,
    _load_appointment_context,
    _notify_recipients,
    _render_email,
)
from web_api.email.recipient import recipient_email_for_web_user
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    CancellationNotificationRecipient,
    CancellationRequest,
    CancellationStatus,
    InboxMessageType,
    TakeoverOffer,
    TakeoverOfferStatus,
    WebUser,
)
from web_api.plan_adjustment.service import reassign_appointment


@dataclass
class TakeoverOfferSummary:
    id: uuid.UUID
    offerer_name: str
    offerer_web_user_id: uuid.UUID
    message: str | None
    status: TakeoverOfferStatus
    created_at: datetime


def create_takeover_offer(
    session: Session,
    cancellation_id: uuid.UUID,
    web_user: WebUser,
    message: str | None,
) -> tuple[TakeoverOffer, list[EmailPayload]]:
    """BR-07: Nur Mitglieder des Benachrichtigungskreises dürfen Übernahme anbieten."""
    cr = session.get(CancellationRequest, cancellation_id)
    if cr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Absage nicht gefunden.")
    if cr.status != CancellationStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Übernahme-Angebote sind nur bei offenen Absagen möglich.",
        )

    # BR-07: Nutzer muss im Benachrichtigungskreis sein
    in_circle = session.execute(
        sa_select(CancellationNotificationRecipient.id)
        .where(CancellationNotificationRecipient.cancellation_request_id == cancellation_id)
        .where(CancellationNotificationRecipient.web_user_id == web_user.id)
    ).first()
    if in_circle is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Nur Mitglieder des Benachrichtigungskreises können eine Übernahme anbieten.",
        )

    duplicate = session.execute(
        sa_select(TakeoverOffer.id)
        .where(TakeoverOffer.cancellation_request_id == cancellation_id)
        .where(TakeoverOffer.web_user_id == web_user.id)
        .where(TakeoverOffer.status == TakeoverOfferStatus.pending)
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Sie haben bereits ein offenes Übernahme-Angebot für diese Absage.",
        )

    offer = TakeoverOffer(
        cancellation_request_id=cancellation_id,
        web_user_id=web_user.id,
        message=message,
        status=TakeoverOfferStatus.pending,
    )
    session.add(offer)
    session.flush()

    # Snapshot für Inbox + E-Mail
    ctx = _load_appointment_context(session, cr.appointment_id)
    person = session.get(Person, web_user.person_id) if web_user.person_id else None
    offerer_name = f"{person.f_name} {person.l_name}" if person else web_user.email
    snapshot = _build_snapshot(ctx, offerer_name)

    # Dispatcher benachrichtigen
    dispatcher_user = _get_dispatcher_web_user(session, ctx["team_id"])
    email_payloads: list[EmailPayload] = []

    if dispatcher_user:
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.takeover_offer_received,
            reference_id=cancellation_id,
            reference_type="cancellation_request",
            snapshot_data={**snapshot, "offerer_name": offerer_name, "sent_as": "dispatcher"},
        )
        html = _render_email(
            "takeover_offer_received.html",
            offerer_name=offerer_name,
            snapshot=snapshot,
            message=message,
        )
        email_payloads.append(
            EmailPayload(
                to=[recipient_email_for_web_user(session, dispatcher_user)],
                subject="Übernahme-Angebot eingegangen",
                html_body=html,
            )
        )

    return offer, email_payloads


def accept_takeover_offer(
    session: Session,
    cancellation_id: uuid.UUID,
    offer_id: uuid.UUID,
    dispatcher_user: WebUser,
) -> list[EmailPayload]:
    """Dispatcher akzeptiert ein Übernahme-Angebot: Plan neu zuordnen, andere Offers ablehnen."""
    cr = session.get(CancellationRequest, cancellation_id)
    if cr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Absage nicht gefunden.")

    offer = session.get(TakeoverOffer, offer_id)
    if offer is None or offer.cancellation_request_id != cancellation_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Übernahme-Angebot nicht gefunden.")
    if offer.status != TakeoverOfferStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Dieses Übernahme-Angebot ist nicht mehr offen.",
        )

    # Dispatcher-Zugehörigkeit prüfen
    ctx = _load_appointment_context(session, cr.appointment_id)
    expected_dispatcher = _get_dispatcher_web_user(session, ctx["team_id"])
    if expected_dispatcher is None or expected_dispatcher.id != dispatcher_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Nur der zuständige Dispatcher kann Übernahmen akzeptieren.",
        )

    # Person des Absagenden ermitteln
    requester_user = session.get(WebUser, cr.web_user_id)
    if requester_user is None or requester_user.person_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Person des Absagenden nicht gefunden.",
        )

    # Person des Übernehmenden ermitteln
    offerer_user = session.get(WebUser, offer.web_user_id)
    if offerer_user is None or offerer_user.person_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Person des Anbieters nicht gefunden.",
        )

    # Plan-Anpassung: alten AvailDay-Link entfernen, neuen erstellen.
    # Die aktive Cancellation wird unten explizit auf resolved gesetzt —
    # exclude sie hier, damit der Helper sie nicht stumm auf superseded flippt
    # oder eine obsolet-Benachrichtigung an den Absagenden sendet.
    cast_removal_payloads = reassign_appointment(
        session,
        appointment_id=cr.appointment_id,
        old_person_id=requester_user.person_id,
        new_person_id=offerer_user.person_id,
        exclude_cancellation_ids=frozenset({cancellation_id}),
    )

    # Angebot akzeptieren
    offer.status = TakeoverOfferStatus.accepted
    session.add(offer)
    session.flush()

    # BR-09: alle anderen pending Offers ablehnen
    other_pending = session.execute(
        sa_select(TakeoverOffer)
        .where(TakeoverOffer.cancellation_request_id == cancellation_id)
        .where(TakeoverOffer.id != offer_id)
        .where(TakeoverOffer.status == TakeoverOfferStatus.pending)
    ).scalars().all()
    for other in other_pending:
        other.status = TakeoverOfferStatus.rejected
        session.add(other)
    session.flush()

    # Absage als gelöst markieren
    cr.status = CancellationStatus.resolved
    cr.resolved_at = _utcnow()
    cr.resolved_by_id = dispatcher_user.id
    session.add(cr)
    session.flush()

    # Snapshot erstellen
    offerer_person = session.get(Person, offerer_user.person_id)
    offerer_name = (
        f"{offerer_person.f_name} {offerer_person.l_name}"
        if offerer_person else offerer_user.email
    )
    requester_person = session.get(Person, requester_user.person_id)
    employee_name = (
        f"{requester_person.f_name} {requester_person.l_name}"
        if requester_person else requester_user.email
    )
    snapshot = _build_snapshot(ctx, employee_name)
    full_snapshot = {**snapshot, "offerer_name": offerer_name}

    # Benachrichtigungskreis laden
    saved_recipients = session.execute(
        sa_select(CancellationNotificationRecipient)
        .where(CancellationNotificationRecipient.cancellation_request_id == cancellation_id)
    ).scalars().all()

    notify_emails: list[str] = []
    notified_ids: set[uuid.UUID] = set()

    tagged_snapshot = {**full_snapshot, "sent_as": "employee"}

    for rec in saved_recipients:
        ru = session.get(WebUser, rec.web_user_id)
        if ru:
            notified_ids.add(ru.id)
            notify_emails.append(recipient_email_for_web_user(session, ru))
            create_inbox_message(
                session,
                recipient_id=ru.id,
                msg_type=InboxMessageType.takeover_accepted,
                reference_id=cancellation_id,
                reference_type="cancellation_request",
                snapshot_data=tagged_snapshot,
            )

    # Auch den Anbieter und Absagenden benachrichtigen falls nicht im Kreis
    for extra_user in [offerer_user, requester_user]:
        if extra_user.id not in notified_ids:
            notified_ids.add(extra_user.id)
            notify_emails.append(recipient_email_for_web_user(session, extra_user))
            create_inbox_message(
                session,
                recipient_id=extra_user.id,
                msg_type=InboxMessageType.takeover_accepted,
                reference_id=cancellation_id,
                reference_type="cancellation_request",
                snapshot_data=tagged_snapshot,
            )

    email_payloads: list[EmailPayload] = list(cast_removal_payloads)
    if notify_emails:
        html = _render_email(
            "takeover_accepted.html",
            offerer_name=offerer_name,
            employee_name=employee_name,
            snapshot=snapshot,
        )
        email_payloads.append(
            EmailPayload(
                to=notify_emails,
                subject="Übernahme akzeptiert",
                html_body=html,
            )
        )

    return email_payloads


def get_takeover_offers_for_cancellation(
    session: Session,
    cancellation_id: uuid.UUID,
) -> list[TakeoverOfferSummary]:
    """Gibt alle TakeoverOffers einer Absage als Summary-Liste zurück."""
    rows = session.execute(
        sa_select(
            TakeoverOffer.id,
            TakeoverOffer.web_user_id,
            TakeoverOffer.message,
            TakeoverOffer.status,
            TakeoverOffer.created_at,
            Person.f_name,
            Person.l_name,
            WebUser.email,
        )
        .select_from(TakeoverOffer)
        .join(WebUser, WebUser.id == TakeoverOffer.web_user_id)
        .outerjoin(Person, Person.id == WebUser.person_id)
        .where(TakeoverOffer.cancellation_request_id == cancellation_id)
        .order_by(TakeoverOffer.created_at.asc())
    ).mappings().all()

    return [
        TakeoverOfferSummary(
            id=r["id"],
            offerer_name=(
                f"{r['f_name']} {r['l_name']}" if r["f_name"] else r["email"]
            ),
            offerer_web_user_id=r["web_user_id"],
            message=r["message"],
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


def withdraw_takeover_offer(
    session: Session,
    cancellation_id: uuid.UUID,
    offer_id: uuid.UUID,
    web_user: WebUser,
) -> None:
    """Anbieter zieht eigenes Übernahme-Angebot zurück."""
    offer = session.get(TakeoverOffer, offer_id)
    if offer is None or offer.cancellation_request_id != cancellation_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Übernahme-Angebot nicht gefunden.")
    if offer.web_user_id != web_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")
    if offer.status != TakeoverOfferStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Dieses Übernahme-Angebot kann nicht mehr zurückgezogen werden.",
        )

    offer.status = TakeoverOfferStatus.rejected
    session.add(offer)
    session.flush()


def _utcnow():
    from datetime import timezone
    return datetime.now(timezone.utc)
