"""Swap-Request Service: Tausch-Anfragen zwischen Mitarbeitern."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    Event,
    Person,
    Plan,
    PlanPeriod,
    Team,
)
from web_api.cancellations.service import (
    _build_snapshot,
    _get_dispatcher_web_user,
    _load_appointment_context,
    _render_email,
)
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    InboxMessageType,
    SwapRequest,
    SwapRequestStatus,
    WebUser,
)
from web_api.plan_adjustment.service import swap_appointments


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SwapRequestSummary:
    id: uuid.UUID
    requester_web_user_id: uuid.UUID
    target_web_user_id: uuid.UUID
    requester_name: str
    target_name: str
    requester_event_date: str
    target_event_date: str
    requester_location: str
    target_location: str
    message: str | None
    status: SwapRequestStatus
    created_at: datetime


def _load_appointment_person(
    session: Session, appointment_id: uuid.UUID
) -> tuple[uuid.UUID, str, str]:
    """Lädt Location-Name + Event-Datum eines Appointments für Swap-Snapshots."""
    ctx = _load_appointment_context(session, appointment_id)
    return ctx["plan_period_id"], ctx["location_name"], str(ctx["event_date"])


def _find_person_for_appointment(
    session: Session, appointment_id: uuid.UUID
) -> WebUser | None:
    """Findet den WebUser, dem ein Appointment über AvailDayAppointmentLink zugeordnet ist."""
    row = session.execute(
        sa_select(WebUser)
        .select_from(AvailDayAppointmentLink)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(WebUser, WebUser.person_id == Person.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().first()
    return row


def create_swap_request(
    session: Session,
    requester_user: WebUser,
    requester_appt_id: uuid.UUID,
    target_appt_id: uuid.UUID,
    message: str | None,
) -> tuple[SwapRequest, list[EmailPayload]]:
    """BR-08: Beide Appointments müssen in derselben PlanPeriod liegen."""
    if requester_user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Kein Personenprofil verknüpft."
        )

    req_ctx = _load_appointment_context(session, requester_appt_id)
    tgt_ctx = _load_appointment_context(session, target_appt_id)

    # BR-08: gleiche PlanPeriod prüfen
    if req_ctx["plan_period_id"] != tgt_ctx["plan_period_id"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tausch ist nur innerhalb derselben Planperiode möglich.",
        )

    # Ziel-Person ermitteln
    target_user = _find_person_for_appointment(session, target_appt_id)
    if target_user is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Für den Ziel-Termin wurde kein Mitarbeiter-WebUser gefunden.",
        )

    swap = SwapRequest(
        requester_web_user_id=requester_user.id,
        requester_appointment_id=requester_appt_id,
        target_web_user_id=target_user.id,
        target_appointment_id=target_appt_id,
        message=message,
        status=SwapRequestStatus.pending,
    )
    session.add(swap)
    session.flush()

    # Snapshot
    req_person = session.get(Person, requester_user.person_id)
    requester_name = (
        f"{req_person.f_name} {req_person.l_name}" if req_person else requester_user.email
    )
    tgt_person = (
        session.get(Person, target_user.person_id) if target_user.person_id else None
    )
    target_name = f"{tgt_person.f_name} {tgt_person.l_name}" if tgt_person else target_user.email

    snapshot = {
        "requester_name": requester_name,
        "target_name": target_name,
        "requester_location": req_ctx["location_name"],
        "target_location": tgt_ctx["location_name"],
        "requester_event_date": str(req_ctx["event_date"]),
        "target_event_date": str(tgt_ctx["event_date"]),
    }

    # Inbox für Ziel + Dispatcher
    dispatcher_user = _get_dispatcher_web_user(session, req_ctx["team_id"])
    email_targets: list[str] = [target_user.email]
    inbox_users: list[tuple[uuid.UUID, str]] = [(target_user.id, target_user.email)]

    if dispatcher_user:
        inbox_users.append((dispatcher_user.id, dispatcher_user.email))
        email_targets.append(dispatcher_user.email)

    for uid, _umail in inbox_users:
        create_inbox_message(
            session,
            recipient_id=uid,
            msg_type=InboxMessageType.swap_request_received,
            reference_id=swap.id,
            reference_type="swap_request",
            snapshot_data=snapshot,
        )

    email_payloads: list[EmailPayload] = []
    if email_targets:
        html = _render_email(
            "swap_request_received.html",
            requester_name=requester_name,
            snapshot=snapshot,
            message=message,
        )
        email_payloads.append(
            EmailPayload(
                to=email_targets,
                subject="Tausch-Anfrage erhalten",
                html_body=html,
            )
        )

    return swap, email_payloads


def accept_swap_request(
    session: Session,
    swap_id: uuid.UUID,
    target_user: WebUser,
) -> list[EmailPayload]:
    """Ziel-Mitarbeiter akzeptiert Tausch-Anfrage."""
    swap = session.get(SwapRequest, swap_id)
    if swap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tausch-Anfrage nicht gefunden.")
    if swap.target_web_user_id != target_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")
    if swap.status != SwapRequestStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Diese Tausch-Anfrage kann nicht mehr akzeptiert werden.",
        )

    swap.status = SwapRequestStatus.accepted_by_target
    session.add(swap)
    session.flush()

    # Dispatcher benachrichtigen
    req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
    dispatcher_user = _get_dispatcher_web_user(session, req_ctx["team_id"])

    snapshot = _build_swap_snapshot(session, swap, req_ctx)
    email_payloads: list[EmailPayload] = []

    if dispatcher_user:
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.swap_accepted_by_target,
            reference_id=swap.id,
            reference_type="swap_request",
            snapshot_data=snapshot,
        )

    return email_payloads


def reject_swap_request(
    session: Session,
    swap_id: uuid.UUID,
    target_user: WebUser,
) -> list[EmailPayload]:
    """Ziel-Mitarbeiter lehnt Tausch-Anfrage ab."""
    swap = session.get(SwapRequest, swap_id)
    if swap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tausch-Anfrage nicht gefunden.")
    if swap.target_web_user_id != target_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")
    if swap.status != SwapRequestStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Diese Tausch-Anfrage kann nicht mehr abgelehnt werden.",
        )

    swap.status = SwapRequestStatus.rejected_by_target
    session.add(swap)
    session.flush()

    # Anfragenden benachrichtigen
    requester_user = session.get(WebUser, swap.requester_web_user_id)
    req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
    snapshot = _build_swap_snapshot(session, swap, req_ctx)

    email_payloads: list[EmailPayload] = []
    if requester_user:
        create_inbox_message(
            session,
            recipient_id=requester_user.id,
            msg_type=InboxMessageType.swap_rejected,
            reference_id=swap.id,
            reference_type="swap_request",
            snapshot_data=snapshot,
        )
        html = _render_email("swap_rejected.html", snapshot=snapshot)
        email_payloads.append(
            EmailPayload(
                to=[requester_user.email],
                subject="Tausch-Anfrage abgelehnt",
                html_body=html,
            )
        )

    return email_payloads


def confirm_swap_request(
    session: Session,
    swap_id: uuid.UUID,
    dispatcher_user: WebUser,
) -> list[EmailPayload]:
    """Dispatcher bestätigt Tausch: Plan-Anpassung + beide Partner benachrichtigen."""
    swap = session.get(SwapRequest, swap_id)
    if swap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tausch-Anfrage nicht gefunden.")
    if swap.status != SwapRequestStatus.accepted_by_target:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Tausch kann nur bestätigt werden, wenn das Ziel zugestimmt hat.",
        )

    # Dispatcher-Zugehörigkeit prüfen
    req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
    expected_dispatcher = _get_dispatcher_web_user(session, req_ctx["team_id"])
    if expected_dispatcher is None or expected_dispatcher.id != dispatcher_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Nur der zuständige Dispatcher kann Tausche bestätigen.",
        )

    requester_user = session.get(WebUser, swap.requester_web_user_id)
    target_user = session.get(WebUser, swap.target_web_user_id)

    if (
        requester_user is None
        or requester_user.person_id is None
        or target_user is None
        or target_user.person_id is None
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Person-Verknüpfung fehlt bei einem der Tauschpartner.",
        )

    # Plan-Anpassung
    swap_appointments(
        session,
        appt_a_id=swap.requester_appointment_id,
        person_a_id=requester_user.person_id,
        appt_b_id=swap.target_appointment_id,
        person_b_id=target_user.person_id,
    )

    swap.status = SwapRequestStatus.confirmed_by_dispatcher
    session.add(swap)
    session.flush()

    snapshot = _build_swap_snapshot(session, swap, req_ctx)

    # Beide Partner + Dispatcher benachrichtigen
    notify_users = [requester_user, target_user, dispatcher_user]
    notify_emails: list[str] = []
    notified_ids: set[uuid.UUID] = set()

    for u in notify_users:
        if u.id not in notified_ids:
            notified_ids.add(u.id)
            notify_emails.append(u.email)
            create_inbox_message(
                session,
                recipient_id=u.id,
                msg_type=InboxMessageType.swap_confirmed,
                reference_id=swap.id,
                reference_type="swap_request",
                snapshot_data=snapshot,
            )

    email_payloads: list[EmailPayload] = []
    if notify_emails:
        html = _render_email("swap_confirmed.html", snapshot=snapshot)
        email_payloads.append(
            EmailPayload(
                to=notify_emails,
                subject="Tausch bestätigt",
                html_body=html,
            )
        )

    return email_payloads


def withdraw_swap_request(
    session: Session,
    swap_id: uuid.UUID,
    requester_user: WebUser,
) -> None:
    """Anfragender zieht Tausch-Anfrage zurück."""
    swap = session.get(SwapRequest, swap_id)
    if swap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tausch-Anfrage nicht gefunden.")
    if swap.requester_web_user_id != requester_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")
    if swap.status not in (SwapRequestStatus.pending, SwapRequestStatus.accepted_by_target):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Diese Tausch-Anfrage kann nicht mehr zurückgezogen werden.",
        )

    swap.status = SwapRequestStatus.withdrawn
    session.add(swap)
    session.flush()


def get_swap_requests_for_user(
    session: Session,
    web_user_id: uuid.UUID,
) -> list[SwapRequestSummary]:
    """Gibt alle Tausch-Anfragen als Anfragender oder Ziel zurück."""
    rows = session.execute(
        sa_select(SwapRequest)
        .where(
            (SwapRequest.requester_web_user_id == web_user_id)
            | (SwapRequest.target_web_user_id == web_user_id)
        )
        .order_by(SwapRequest.created_at.desc())
    ).scalars().all()

    result = []
    for swap in rows:
        req_user = session.get(WebUser, swap.requester_web_user_id)
        tgt_user = session.get(WebUser, swap.target_web_user_id)
        req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
        tgt_ctx = _load_appointment_context(session, swap.target_appointment_id)

        req_person = session.get(Person, req_user.person_id) if req_user and req_user.person_id else None
        tgt_person = session.get(Person, tgt_user.person_id) if tgt_user and tgt_user.person_id else None

        result.append(SwapRequestSummary(
            id=swap.id,
            requester_web_user_id=swap.requester_web_user_id,
            target_web_user_id=swap.target_web_user_id,
            requester_name=f"{req_person.f_name} {req_person.l_name}" if req_person else (req_user.email if req_user else ""),
            target_name=f"{tgt_person.f_name} {tgt_person.l_name}" if tgt_person else (tgt_user.email if tgt_user else ""),
            requester_event_date=str(req_ctx["event_date"]),
            target_event_date=str(tgt_ctx["event_date"]),
            requester_location=req_ctx["location_name"],
            target_location=tgt_ctx["location_name"],
            message=swap.message,
            status=swap.status,
            created_at=swap.created_at,
        ))

    return result


def _build_swap_snapshot(session: Session, swap: SwapRequest, req_ctx: dict) -> dict:
    req_user = session.get(WebUser, swap.requester_web_user_id)
    tgt_user = session.get(WebUser, swap.target_web_user_id)
    tgt_ctx = _load_appointment_context(session, swap.target_appointment_id)

    req_person = session.get(Person, req_user.person_id) if req_user and req_user.person_id else None
    tgt_person = session.get(Person, tgt_user.person_id) if tgt_user and tgt_user.person_id else None

    return {
        "requester_name": f"{req_person.f_name} {req_person.l_name}" if req_person else (req_user.email if req_user else ""),
        "target_name": f"{tgt_person.f_name} {tgt_person.l_name}" if tgt_person else (tgt_user.email if tgt_user else ""),
        "requester_location": req_ctx["location_name"],
        "target_location": tgt_ctx["location_name"],
        "requester_event_date": str(req_ctx["event_date"]),
        "target_event_date": str(tgt_ctx["event_date"]),
    }
