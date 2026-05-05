"""Swap-Request Service: Tausch-Anfragen zwischen Mitarbeitern."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Address,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    Plan,
    PlanPeriod,
    Team,
    TimeOfDay,
)
from web_api.email.recipient import first_name_for_web_user, recipient_email_for_web_user
from web_api.cancellations.service import (
    _build_snapshot,
    _get_dispatcher_web_user,
    _load_appointment_context,
    _render_email,
)
from web_api.common import location_display_name
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    CancellationRequest,
    CancellationStatus,
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
    target_appt_ids: list[uuid.UUID],
    message: str | None,
    *,
    target_web_user_id: uuid.UUID | None = None,
) -> tuple[list[SwapRequest], list[EmailPayload]]:
    """Erstellt einen SwapRequest pro Ziel-Appointment. BR-08: Gleiches Team erforderlich.

    Jedes Ziel-Appointment bekommt eine eigene Inbox-Nachricht.
    Der Dispatcher erhält eine zusammengefasste Benachrichtigung.
    """
    if not target_appt_ids:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mindestens ein Ziel-Termin muss angegeben werden.",
        )
    if requester_user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Kein Personenprofil verknüpft."
        )

    req_ctx = _load_appointment_context(session, requester_appt_id)
    req_person = session.get(Person, requester_user.person_id)
    requester_name = (
        f"{req_person.f_name} {req_person.l_name}" if req_person else requester_user.email
    )

    dispatcher_user = _get_dispatcher_web_user(session, req_ctx["team_id"])

    swaps: list[SwapRequest] = []
    email_payloads: list[EmailPayload] = []
    target_names: list[str] = []

    for target_appt_id in target_appt_ids:
        tgt_ctx = _load_appointment_context(session, target_appt_id)

        # BR-08: gleiches Team prüfen
        if req_ctx["team_id"] != tgt_ctx["team_id"]:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tausch ist nur innerhalb desselben Teams möglich.",
            )

        # Konflikt: offene Absage für einen der Termine
        for appt_id in (requester_appt_id, target_appt_id):
            open_cancellation = session.execute(
                sa_select(CancellationRequest.id)
                .where(CancellationRequest.appointment_id == appt_id)
                .where(CancellationRequest.status == CancellationStatus.pending)
            ).first()
            if open_cancellation is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="Für einen der Termine existiert bereits eine offene Absage.",
                )

        duplicate_swap = session.execute(
            sa_select(SwapRequest.id)
            .where(SwapRequest.requester_appointment_id == requester_appt_id)
            .where(SwapRequest.target_appointment_id == target_appt_id)
            .where(SwapRequest.status.in_([SwapRequestStatus.pending, SwapRequestStatus.accepted_by_target]))
        ).first()
        if duplicate_swap is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Für diese Termin-Kombination existiert bereits eine offene Tausch-Anfrage.",
            )

        # Wenn eine konkrete target_web_user_id übergeben wurde (aus Browse-Formular),
        # direkt verwenden — verhindert Selbst-Tausch bei Gruppen-Appointments.
        if target_web_user_id is not None and len(target_appt_ids) == 1:
            target_user = session.get(WebUser, target_web_user_id)
        else:
            target_user = _find_person_for_appointment(session, target_appt_id)
        if target_user is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Für einen Ziel-Termin wurde kein Mitarbeiter-WebUser gefunden.",
            )
        if target_user.id == requester_user.id:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tausch mit sich selbst ist nicht möglich.",
            )

        tgt_person = (
            session.get(Person, target_user.person_id) if target_user.person_id else None
        )
        target_name = (
            f"{tgt_person.f_name} {tgt_person.l_name}" if tgt_person else target_user.email
        )
        target_names.append(target_name)

        snapshot = {
            "requester_name": requester_name,
            "target_name": target_name,
            "requester_location": req_ctx["location_name"],
            "target_location": tgt_ctx["location_name"],
            "requester_event_date": str(req_ctx["event_date"]),
            "target_event_date": str(tgt_ctx["event_date"]),
        }

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
        swaps.append(swap)

        # Inbox + E-Mail an Ziel-Mitarbeiter
        create_inbox_message(
            session,
            recipient_id=target_user.id,
            msg_type=InboxMessageType.swap_request_received,
            reference_id=swap.id,
            reference_type="swap_request",
            snapshot_data=snapshot,
        )
        html = _render_email(
            "swap_request_received.html",
            requester_name=requester_name,
            snapshot=snapshot,
            message=message,
            recipient_first_name=first_name_for_web_user(session, target_user),
        )
        email_payloads.append(
            EmailPayload(
                to=[recipient_email_for_web_user(session, target_user)],
                subject="Tausch-Anfrage erhalten",
                html_body=html,
            )
        )

    # Dispatcher erhält eine zusammengefasste Inbox-Nachricht (für den ersten Swap stellvertretend)
    if dispatcher_user and swaps:
        first_swap = swaps[0]
        first_tgt_ctx = _load_appointment_context(session, first_swap.target_appointment_id)
        dispatcher_snapshot = {
            "requester_name": requester_name,
            "target_name": ", ".join(target_names),
            "requester_location": req_ctx["location_name"],
            "target_location": first_tgt_ctx["location_name"],
            "requester_event_date": str(req_ctx["event_date"]),
            "target_event_date": str(first_tgt_ctx["event_date"]),
        }
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.swap_request_received,
            reference_id=first_swap.id,
            reference_type="swap_request",
            snapshot_data=dispatcher_snapshot,
        )

    return swaps, email_payloads


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
        requester_name = snapshot.get("requester_name", "")
        target_name = snapshot.get("target_name", "")
        html = _render_email(
            "swap_accepted_by_target.html",
            requester_name=requester_name,
            target_name=target_name,
            snapshot=snapshot,
            recipient_first_name=first_name_for_web_user(session, dispatcher_user),
        )
        email_payloads.append(
            EmailPayload(
                to=[recipient_email_for_web_user(session, dispatcher_user)],
                subject=f"{target_name} hat dem Tausch zugestimmt",
                html_body=html,
            )
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
        html = _render_email(
            "swap_rejected.html",
            snapshot=snapshot,
            recipient_first_name=first_name_for_web_user(session, requester_user),
        )
        email_payloads.append(
            EmailPayload(
                to=[recipient_email_for_web_user(session, requester_user)],
                subject="Tausch-Anfrage abgelehnt",
                html_body=html,
            )
        )

    return email_payloads


def dispatcher_reject_swap_request(
    session: Session,
    swap_id: uuid.UUID,
    dispatcher_user: WebUser,
    rejection_reason: str,
) -> list[EmailPayload]:
    """Dispatcher lehnt Tausch-Anfrage mit Pflicht-Begründung ab.

    Erlaubt im Status `pending` oder `accepted_by_target` — der Dispatcher hat
    operatives Vetorecht unabhängig davon, ob das Target bereits zugestimmt hat.
    Setzt `rejected_by_dispatcher` und benachrichtigt Anfragenden + Ziel.
    """
    cleaned_reason = (rejection_reason or "").strip()
    if not cleaned_reason:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Eine Begründung ist erforderlich.",
        )

    swap = session.get(SwapRequest, swap_id)
    if swap is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tausch-Anfrage nicht gefunden.")
    if swap.status not in (SwapRequestStatus.pending, SwapRequestStatus.accepted_by_target):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Diese Tausch-Anfrage kann nicht mehr abgelehnt werden.",
        )

    req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
    expected_dispatcher = _get_dispatcher_web_user(session, req_ctx["team_id"])
    if expected_dispatcher is None or expected_dispatcher.id != dispatcher_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Nur der zuständige Dispatcher kann Tausche ablehnen.",
        )

    swap.rejection_reason = cleaned_reason
    swap.status = SwapRequestStatus.rejected_by_dispatcher
    session.add(swap)
    session.flush()

    requester_user = session.get(WebUser, swap.requester_web_user_id)
    target_user = session.get(WebUser, swap.target_web_user_id)
    snapshot = _build_swap_snapshot(session, swap, req_ctx)
    snapshot["rejection_reason"] = cleaned_reason

    email_payloads: list[EmailPayload] = []
    notified_ids: set[uuid.UUID] = set()
    for u in (requester_user, target_user):
        if u is None or u.id in notified_ids:
            continue
        notified_ids.add(u.id)
        create_inbox_message(
            session,
            recipient_id=u.id,
            msg_type=InboxMessageType.swap_rejected,
            reference_id=swap.id,
            reference_type="swap_request",
            snapshot_data=snapshot,
        )
        html = _render_email(
            "swap_rejected_by_dispatcher.html",
            snapshot=snapshot,
            rejection_reason=cleaned_reason,
            recipient_first_name=first_name_for_web_user(session, u),
        )
        email_payloads.append(
            EmailPayload(
                to=[recipient_email_for_web_user(session, u)],
                subject="Tausch-Anfrage von Einsatzplanung abgelehnt",
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

    # Plan-Anpassung. Die aktive SwapRequest wird unten auf confirmed_by_dispatcher
    # gesetzt — exclude sie hier, damit der Helper sie nicht stumm auf superseded
    # flippt oder eine obsolet-Benachrichtigung an die Partner sendet.
    cast_removal_payloads = swap_appointments(
        session,
        appt_a_id=swap.requester_appointment_id,
        person_a_id=requester_user.person_id,
        appt_b_id=swap.target_appointment_id,
        person_b_id=target_user.person_id,
        exclude_swap_ids=frozenset({swap.id}),
    )

    swap.status = SwapRequestStatus.confirmed_by_dispatcher
    session.add(swap)
    session.flush()

    snapshot = _build_swap_snapshot(session, swap, req_ctx)

    # Beide Partner + Dispatcher benachrichtigen
    notify_users = [requester_user, target_user, dispatcher_user]
    recipient_infos: list[tuple[str, str]] = []  # (email, first_name) pro Empfänger
    notified_ids: set[uuid.UUID] = set()

    for u in notify_users:
        if u.id not in notified_ids:
            notified_ids.add(u.id)
            recipient_infos.append((
                recipient_email_for_web_user(session, u),
                first_name_for_web_user(session, u),
            ))
            create_inbox_message(
                session,
                recipient_id=u.id,
                msg_type=InboxMessageType.swap_confirmed,
                reference_id=swap.id,
                reference_type="swap_request",
                snapshot_data=snapshot,
            )

    email_payloads: list[EmailPayload] = list(cast_removal_payloads)
    for email, first_name in recipient_infos:
        html = _render_email(
            "swap_confirmed.html",
            snapshot=snapshot,
            recipient_first_name=first_name,
        )
        email_payloads.append(
            EmailPayload(
                to=[email],
                subject="Tausch bestätigt",
                html_body=html,
            )
        )

    return email_payloads


def withdraw_swap_request(
    session: Session,
    swap_id: uuid.UUID,
    requester_user: WebUser,
) -> list[EmailPayload]:
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

    target_user = session.get(WebUser, swap.target_web_user_id)
    req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
    snapshot = _build_swap_snapshot(session, swap, req_ctx)

    email_payloads: list[EmailPayload] = []
    if target_user:
        create_inbox_message(
            session,
            recipient_id=target_user.id,
            msg_type=InboxMessageType.swap_withdrawn,
            reference_id=swap.id,
            reference_type="swap_request",
            snapshot_data=snapshot,
        )
        html = _render_email(
            "swap_withdrawn.html",
            snapshot=snapshot,
            recipient_first_name=first_name_for_web_user(session, target_user),
        )
        email_payloads.append(
            EmailPayload(
                to=[recipient_email_for_web_user(session, target_user)],
                subject="Tausch-Anfrage zurückgezogen",
                html_body=html,
            )
        )

    return email_payloads


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
        try:
            req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
            tgt_ctx = _load_appointment_context(session, swap.target_appointment_id)
        except HTTPException:
            continue

        req_user = session.get(WebUser, swap.requester_web_user_id)
        tgt_user = session.get(WebUser, swap.target_web_user_id)
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


def get_swap_requests_for_dispatcher(
    session: Session,
    web_user: WebUser,
) -> list[SwapRequestSummary]:
    """Gibt alle Tausch-Anfragen zurück, die Teams des Dispatchers betreffen.

    Ein Dispatcher kann mehrere Teams verwalten. Daher werden alle team_ids
    gesammelt, dann alle zugehörigen Appointment-IDs bestimmt und schließlich
    alle SwapRequests gefiltert, bei denen mindestens ein Termin zu diesen
    Teams gehört.
    """
    if web_user.person_id is None:
        return []

    # Alle Teams, für die der Nutzer Dispatcher ist (kann mehrere sein)
    team_ids = session.execute(
        sa_select(Team.id)
        .where(Team.dispatcher_id == web_user.person_id)
        .where(Team.prep_delete.is_(None))
    ).scalars().all()

    if not team_ids:
        return []

    # Alle Appointment-IDs in diesen Teams (über Plan → PlanPeriod)
    appt_ids_subquery = (
        sa_select(Appointment.id)
        .join(Plan, Appointment.plan_id == Plan.id)
        .join(PlanPeriod, Plan.plan_period_id == PlanPeriod.id)
        .where(PlanPeriod.team_id.in_(team_ids))
    )

    rows = session.execute(
        sa_select(SwapRequest)
        .where(
            SwapRequest.requester_appointment_id.in_(appt_ids_subquery)
            | SwapRequest.target_appointment_id.in_(appt_ids_subquery)
        )
        .order_by(SwapRequest.created_at.desc())
    ).scalars().all()

    result = []
    for swap in rows:
        try:
            req_ctx = _load_appointment_context(session, swap.requester_appointment_id)
            tgt_ctx = _load_appointment_context(session, swap.target_appointment_id)
        except HTTPException:
            continue

        req_user = session.get(WebUser, swap.requester_web_user_id)
        tgt_user = session.get(WebUser, swap.target_web_user_id)
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


# ── Browse / Kandidaten-Suche ─────────────────────────────────────────────────


@dataclass
class SwapCandidate:
    appointment_id: uuid.UUID
    location_name: str
    event_date: date
    time_of_day_name: str | None
    holder_web_user_id: uuid.UUID
    holder_name: str
    already_requested: bool = False


def _get_requester_team_ids(session: Session, web_user: WebUser) -> list[uuid.UUID]:
    """Gibt alle Team-IDs zurück, in denen der Nutzer einen ActorPlanPeriod hat."""
    if web_user.person_id is None:
        return []
    rows = session.execute(
        sa_select(PlanPeriod.team_id)
        .select_from(ActorPlanPeriod)
        .join(PlanPeriod, PlanPeriod.id == ActorPlanPeriod.plan_period_id)
        .where(ActorPlanPeriod.person_id == web_user.person_id)
        .distinct()
    ).scalars().all()
    return list(rows)


def _get_team_id_for_appointment(session: Session, appointment_id: uuid.UUID) -> uuid.UUID | None:
    """Gibt die Team-ID zurück, zu der ein Appointment über Plan → PlanPeriod gehört."""
    return session.execute(
        sa_select(PlanPeriod.team_id)
        .select_from(Appointment)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .where(Appointment.id == appointment_id)
    ).scalar_one_or_none()


def get_swap_candidate_appointments(
    session: Session,
    requester_user: WebUser,
    *,
    location_ids: list[uuid.UUID] | None = None,
    person_ids: list[uuid.UUID] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    requester_appointment_id: uuid.UUID | None = None,
) -> list[SwapCandidate]:
    """Gibt Appointments anderer Personen zurück, die als Tausch-Ziel in Frage kommen.

    Wenn requester_appointment_id angegeben ist, werden nur Termine des Teams dieses
    Termins zurückgegeben — auch wenn der Nutzer mehreren Teams angehört.
    Schließt eigene Appointments aus; liefert nur zukünftige Termine.
    """
    if date_from is None:
        date_from = date.today()

    if requester_appointment_id is not None:
        team_id = _get_team_id_for_appointment(session, requester_appointment_id)
        team_ids = [team_id] if team_id else []
    else:
        team_ids = _get_requester_team_ids(session, requester_user)
    if not team_ids:
        return []

    query = (
        sa_select(
            Appointment.id.label("appointment_id"),
            LocationOfWork.name.label("location_name"),
            Address.city.label("location_city"),
            Event.date.label("event_date"),
            TimeOfDay.name.label("time_of_day_name"),
            WebUser.id.label("holder_web_user_id"),
            Person.f_name.label("f_name"),
            Person.l_name.label("l_name"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(Address, Address.id == LocationOfWork.address_id, isouter=True)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.appointment_id == Appointment.id)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(WebUser, WebUser.person_id == Person.id)
        .where(PlanPeriod.team_id.in_(team_ids))
        .where(Event.date >= date_from)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .where(Appointment.prep_delete.is_(None))
    )

    # Eigene Appointments ausschließen
    if requester_user.person_id is not None:
        query = query.where(Person.id != requester_user.person_id)

    # Doppelbuchung: Personen, die im Anfrager-Termin bereits besetzt sind, ausschließen
    if requester_appointment_id is not None:
        query = query.where(Person.id.notin_(
            sa_select(ActorPlanPeriod.person_id)
            .select_from(AvailDayAppointmentLink)
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
            .where(AvailDayAppointmentLink.appointment_id == requester_appointment_id)
        ))

    # Doppelbuchung: Termine, in denen der Anfrager bereits besetzt ist, ausschließen
    if requester_user.person_id is not None:
        query = query.where(Appointment.id.notin_(
            sa_select(AvailDayAppointmentLink.appointment_id)
            .select_from(AvailDayAppointmentLink)
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
            .where(ActorPlanPeriod.person_id == requester_user.person_id)
        ))

    if location_ids:
        query = query.where(LocationOfWork.id.in_(location_ids))
    if person_ids:
        query = query.where(WebUser.id.in_(person_ids))
    if date_to:
        query = query.where(Event.date <= date_to)

    query = query.order_by(Event.date.asc())

    rows = session.execute(query).mappings().all()

    # Termine, für die der Anfrager bereits eine offene SwapRequest hat → in der Liste als "Anfrage gestellt" anzeigen
    already_requested_query = (
        sa_select(SwapRequest.target_appointment_id)
        .where(SwapRequest.requester_web_user_id == requester_user.id)
        .where(SwapRequest.status.in_([SwapRequestStatus.pending, SwapRequestStatus.accepted_by_target]))
    )
    if requester_appointment_id is not None:
        already_requested_query = already_requested_query.where(
            SwapRequest.requester_appointment_id == requester_appointment_id
        )
    already_requested_ids = set(session.execute(already_requested_query).scalars().all())

    return [
        SwapCandidate(
            appointment_id=row["appointment_id"],
            location_name=location_display_name(row["location_name"], row["location_city"]),
            event_date=row["event_date"],
            time_of_day_name=row["time_of_day_name"],
            holder_web_user_id=row["holder_web_user_id"],
            holder_name=f"{row['f_name']} {row['l_name']}",
            already_requested=row["appointment_id"] in already_requested_ids,
        )
        for row in rows
    ]


def get_filter_options_for_user(
    session: Session,
    web_user: WebUser,
    requester_appointment_id: uuid.UUID | None = None,
) -> tuple[list[tuple[uuid.UUID, str, str | None]], list[tuple[uuid.UUID, str]]]:
    """Liefert (locations, colleagues) für die Filter-Sidebar.

    locations: Liste von (location_id, location_name, city) im Team des Nutzers.
    colleagues: Liste von (web_user_id, full_name) im Team des Nutzers (ohne den Nutzer selbst).

    Wenn requester_appointment_id angegeben ist, werden nur Daten des Teams dieses
    Termins zurückgegeben — auch wenn der Nutzer mehreren Teams angehört.
    """
    if requester_appointment_id is not None:
        team_id = _get_team_id_for_appointment(session, requester_appointment_id)
        team_ids = [team_id] if team_id else []
    else:
        team_ids = _get_requester_team_ids(session, web_user)
    if not team_ids:
        return [], []

    loc_rows = session.execute(
        sa_select(LocationOfWork.id, LocationOfWork.name, Address.city)
        .select_from(LocationPlanPeriod)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .outerjoin(Address, Address.id == LocationOfWork.address_id)
        .join(PlanPeriod, PlanPeriod.id == LocationPlanPeriod.plan_period_id)
        .where(PlanPeriod.team_id.in_(team_ids))
        .where(LocationOfWork.prep_delete.is_(None))
        .distinct()
        .order_by(LocationOfWork.name)
    ).all()
    locations = [(row[0], row[1], row[2]) for row in loc_rows]

    colleague_rows = session.execute(
        sa_select(WebUser.id, Person.f_name, Person.l_name)
        .select_from(ActorPlanPeriod)
        .join(PlanPeriod, PlanPeriod.id == ActorPlanPeriod.plan_period_id)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(WebUser, WebUser.person_id == Person.id)
        .where(PlanPeriod.team_id.in_(team_ids))
        .where(WebUser.id != web_user.id)
        .distinct()
        .order_by(Person.l_name, Person.f_name)
    ).all()
    colleagues = [(row[0], f"{row[1]} {row[2]}") for row in colleague_rows]

    return locations, colleagues


def get_own_upcoming_appointments(
    session: Session,
    web_user: WebUser,
) -> list[SwapCandidate]:
    """Liefert eigene zukünftige Appointments für das Tausch-Formular (Auswahl 'Mein Termin')."""
    if web_user.person_id is None:
        return []

    rows = session.execute(
        sa_select(
            Appointment.id.label("appointment_id"),
            LocationOfWork.name.label("location_name"),
            Address.city.label("location_city"),
            Event.date.label("event_date"),
            TimeOfDay.name.label("time_of_day_name"),
            WebUser.id.label("holder_web_user_id"),
            Person.f_name.label("f_name"),
            Person.l_name.label("l_name"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(Address, Address.id == LocationOfWork.address_id, isouter=True)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.appointment_id == Appointment.id)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(WebUser, WebUser.person_id == Person.id)
        .where(Person.id == web_user.person_id)
        .where(Event.date >= date.today())
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .where(Appointment.prep_delete.is_(None))
        .order_by(Event.date.asc())
    ).mappings().all()

    return [
        SwapCandidate(
            appointment_id=row["appointment_id"],
            location_name=location_display_name(row["location_name"], row["location_city"]),
            event_date=row["event_date"],
            time_of_day_name=row["time_of_day_name"],
            holder_web_user_id=row["holder_web_user_id"],
            holder_name=f"{row['f_name']} {row['l_name']}",
        )
        for row in rows
    ]


# ── Badge-Counts ─────────────────────────────────────────────────────────────


def count_active_swap_requests_for_user(
    session: Session, web_user_id: uuid.UUID
) -> int:
    """Badge-Count: aktionsrelevante Tauschanfragen für den User.

    Zählt Requests, bei denen der User Anfragender oder Ziel ist und der
    Status noch offen ist (`pending` oder `accepted_by_target`). Terminale
    Status werden ignoriert.
    """
    from sqlalchemy import func
    result = session.execute(
        sa_select(func.count(SwapRequest.id))
        .where(
            (SwapRequest.requester_web_user_id == web_user_id)
            | (SwapRequest.target_web_user_id == web_user_id)
        )
        .where(SwapRequest.status.in_(
            [SwapRequestStatus.pending, SwapRequestStatus.accepted_by_target]
        ))
    ).scalar()
    return result or 0


def count_swap_requests_pending_confirm_for_dispatcher(
    session: Session, web_user: WebUser
) -> int:
    """Badge-Count: Tauschanfragen im Status `accepted_by_target` in Teams
    des Dispatchers — warten auf die Dispatcher-Bestätigung.
    """
    from sqlalchemy import func
    if web_user.person_id is None:
        return 0
    team_ids = session.execute(
        sa_select(Team.id)
        .where(Team.dispatcher_id == web_user.person_id)
        .where(Team.prep_delete.is_(None))
    ).scalars().all()
    if not team_ids:
        return 0
    appt_ids_subquery = (
        sa_select(Appointment.id)
        .join(Plan, Appointment.plan_id == Plan.id)
        .join(PlanPeriod, Plan.plan_period_id == PlanPeriod.id)
        .where(PlanPeriod.team_id.in_(team_ids))
    )
    result = session.execute(
        sa_select(func.count(SwapRequest.id))
        .where(
            SwapRequest.requester_appointment_id.in_(appt_ids_subquery)
            | SwapRequest.target_appointment_id.in_(appt_ids_subquery)
        )
        .where(SwapRequest.status == SwapRequestStatus.accepted_by_target)
    ).scalar()
    return result or 0
