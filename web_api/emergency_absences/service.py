"""Service: Notfall-Absage-Workflow.

Im Unterschied zur regulären Absage:
 - greift NUR nach Ablauf der Absagefrist (invertierte Frist-Prüfung),
 - ist sofort terminal (Reporter wird sofort aus dem Cast genommen),
 - sendet eine personalisierte Bestätigungsmail mit Telefonliste der
   gefilterten Empfänger an den Reporter.

Wiederverwendet bestehende Cancellation-Bausteine:
 - `_load_appointment_context`, `_verify_ownership` aus cancellations/service.py
 - `compute_notification_circle(mode='emergency')`
 - `replace_cast_for_appointment` mit `exclude_cancellation_ids` und
   `additional_exclude_user_ids` für sofortige Cast-Removal ohne
   widersprüchliche Cast-Removed-Mail an den Reporter.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    AvailDay,
    AvailDayAppointmentLink,
    Person,
)
from web_api.cancellations.service import (
    CancellationDetail,
    _build_snapshot,
    _get_dispatcher_web_user,
    _load_appointment_context,
    _render_email,
    _verify_ownership,
    compute_notification_circle,
    is_person_in_appointment_cast,
)
from web_api.dispatcher.service import replace_cast_for_appointment
from web_api.email.recipient import (
    first_name_for_web_user,
    recipient_email_for_web_user,
)
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    CancellationKind,
    CancellationNotificationRecipient,
    CancellationRequest,
    CancellationStatus,
    InboxMessageType,
    NotificationSource,
    SwapRequest,
    SwapRequestStatus,
    WebUser,
    WebUserRole,
)
from web_api.settings.service import get_effective_deadline

_REASON_MIN_LEN = 3
_REASON_MAX_LEN = 500


def _load_current_person_ids(session: Session, appointment_id: uuid.UUID) -> list[uuid.UUID]:
    """Aktuelle Cast-Person-IDs des Appointments (für die spätere Cast-Removal)."""
    return list(session.execute(
        sa_select(ActorPlanPeriod.person_id)
        .join(AvailDay, AvailDay.actor_plan_period_id == ActorPlanPeriod.id)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().all())


def _build_phone_list(
    session: Session,
    recipient_web_user_ids: set[uuid.UUID],
) -> list[tuple[str, str]]:
    """Liefert (full_name, phone_nr) für Empfänger, deren Person.share_phone_in_emergency=True
    und phone_nr nicht leer ist.

    Reihenfolge: alphabetisch nach Nachname/Vorname.
    """
    if not recipient_web_user_ids:
        return []
    rows = session.execute(
        sa_select(Person.f_name, Person.l_name, Person.phone_nr)
        .join(WebUser, WebUser.person_id == Person.id)
        .where(WebUser.id.in_(recipient_web_user_ids))
        .where(Person.share_phone_in_emergency.is_(True))
        .where(Person.phone_nr.is_not(None))
        .order_by(Person.l_name.asc(), Person.f_name.asc())
    ).all()
    return [
        (f"{f_name} {l_name}".strip(), (phone or "").strip())
        for f_name, l_name, phone in rows
        if phone and phone.strip()
    ]


def create_emergency_absence(
    session: Session,
    web_user: WebUser,
    appointment_id: uuid.UUID,
    reason: str,
) -> tuple[CancellationDetail, list[EmailPayload]]:
    """BR-EA-01..06: Notfall-Absage erstellen.

    - Frist MUSS überschritten sein (invers zur regulären Absage).
    - Reason ist Pflicht (min 3, max 500 Zeichen).
    - Reporter wird SOFORT aus dem Cast entfernt; eigene EA-CR wird via
      `exclude_cancellation_ids` vor dem Superseded-Sweep geschützt.
    - Reporter erhält Bestätigungs-Mail mit Telefonliste der Empfänger.
    """
    if web_user.person_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Personenprofil verknüpft.")

    ctx = _load_appointment_context(session, appointment_id)

    if not ctx["is_binding"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nur Termine aus dem verbindlichen Plan können abgesagt werden.",
        )

    _verify_ownership(session, appointment_id, web_user.person_id)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if ctx["time_start"] is not None:
        appointment_start_dt = datetime.combine(ctx["event_date"], ctx["time_start"])
    else:
        # Termin ohne konkrete Startzeit: konservativ als Tagesbeginn werten.
        appointment_start_dt = datetime.combine(ctx["event_date"], datetime.min.time())
    if now >= appointment_start_dt:
        raise HTTPException(
            status.HTTP_410_GONE,
            detail=(
                "Notfall-Absage nicht mehr möglich: Termin hat bereits begonnen "
                "oder liegt in der Vergangenheit."
            ),
        )

    # Idempotenz: keine doppelten offenen Workflow-Items für denselben Termin
    existing_cr = session.execute(
        sa_select(CancellationRequest)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).scalars().first()
    if existing_cr is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Für diesen Termin existiert bereits eine offene Absage.",
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
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Für diesen Termin existiert bereits eine offene Tausch-Anfrage.",
        )

    # Frist-Check INVERTIERT: Notfall-Absage greift nur, wenn die reguläre Frist
    # überschritten ist. Innerhalb der Frist soll der reguläre Workflow genutzt
    # werden.
    settings = get_effective_deadline(session, ctx["team_id"])
    if settings.deadline_hours <= 0 or not ctx["time_start"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Notfall-Absage nicht anwendbar: kein gültiger Termin-Zeitpunkt.",
        )
    cutoff = appointment_start_dt - timedelta(hours=settings.deadline_hours)
    if now <= cutoff:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Reguläre Absage ist noch möglich (Frist von {settings.deadline_hours}h "
                f"noch nicht überschritten) – bitte normalen Absage-Workflow nutzen."
            ),
        )

    # Reason-Pflicht
    reason = (reason or "").strip()
    if len(reason) < _REASON_MIN_LEN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Bitte gib einen kurzen Grund ein (mindestens {_REASON_MIN_LEN} Zeichen).",
        )
    if len(reason) > _REASON_MAX_LEN:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Grund darf höchstens {_REASON_MAX_LEN} Zeichen lang sein.",
        )

    # CR erzeugen (kind=emergency, status=pending)
    cr = CancellationRequest(
        appointment_id=appointment_id,
        web_user_id=web_user.id,
        reason=reason,
        status=CancellationStatus.pending,
        kind=CancellationKind.emergency,
    )
    session.add(cr)
    session.flush()

    person = session.get(Person, web_user.person_id)
    employee_name = f"{person.f_name} {person.l_name}" if person else web_user.email

    # Sofortige Cast-Removal — Reporter raus, Reporter-CR vor Cascade schützen,
    # Reporter aus Direct-Notify ausschließen (er bekommt Workflow-spezifische
    # Bestätigungsmail).
    current_person_ids = _load_current_person_ids(session, appointment_id)
    remaining_person_ids = [pid for pid in current_person_ids if pid != web_user.person_id]
    cast_payloads = replace_cast_for_appointment(
        session,
        appointment_id,
        remaining_person_ids,
        exclude_cancellation_ids=frozenset({cr.id}),
        additional_exclude_user_ids=frozenset({web_user.id}),
    )

    # Notification-Circle (mode='emergency': Implicit-Whitelist)
    recipients = compute_notification_circle(
        session,
        exclude_web_user_id=web_user.id,
        location_id=ctx["location_id"],
        plan_period_id=ctx["plan_period_id"],
        event_date=ctx["event_date"],
        cancelled_time_start=ctx["time_start"],
        cancelled_time_end=ctx["time_end"],
        mode="emergency",
    )

    for rec in recipients:
        session.add(CancellationNotificationRecipient(
            cancellation_request_id=cr.id,
            web_user_id=rec.web_user_id,
            source=rec.source,
        ))

    snapshot = {**_build_snapshot(ctx, employee_name), "kind": "emergency", "reason": reason}
    dispatcher_user = _get_dispatcher_web_user(session, ctx["team_id"])

    # Dispatcher als Employee in den Kreis einreihen (mirror create_cancellation),
    # aber NICHT, wenn er bereits im Cast des Termins ist — sonst bekommt er einen
    # Uebernahme-Vorschlag fuer einen Termin, an dem er ohnehin eingeteilt ist.
    # In dem Fall faellt er stattdessen auf den Dispatcher-Pfad in `_notify_recipients`
    # zurueck und bekommt die `sent_as='dispatcher'`-Inbox-Message.
    if dispatcher_user is not None:
        in_auto_circle = any(r.web_user_id == dispatcher_user.id for r in recipients)
        dispatcher_in_cast = is_person_in_appointment_cast(
            session, appointment_id, dispatcher_user.person_id
        )
        if (
            not in_auto_circle
            and dispatcher_user.has_any_role(WebUserRole.employee)
            and not dispatcher_in_cast
        ):
            session.add(CancellationNotificationRecipient(
                cancellation_request_id=cr.id,
                web_user_id=dispatcher_user.id,
                source=NotificationSource.auto_computed,
            ))

    # Inbox-Messages für Empfänger + Dispatcher
    recipient_web_user_ids: set[uuid.UUID] = set()
    recipient_infos: list[tuple[str, str]] = []
    for rec in recipients:
        recipient_web_user_ids.add(rec.web_user_id)
        recipient_infos.append((rec.email, getattr(rec, "first_name", "") or ""))
        create_inbox_message(
            session,
            recipient_id=rec.web_user_id,
            msg_type=InboxMessageType.emergency_absence_new,
            reference_id=cr.id,
            reference_type="cancellation_request",
            snapshot_data={**snapshot, "sent_as": "employee"},
        )

    dispatcher_info: tuple[str, str] | None = None
    if dispatcher_user and dispatcher_user.id not in recipient_web_user_ids:
        dispatcher_info = (
            recipient_email_for_web_user(session, dispatcher_user),
            first_name_for_web_user(session, dispatcher_user),
        )
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.emergency_absence_new,
            reference_id=cr.id,
            reference_type="cancellation_request",
            snapshot_data={**snapshot, "sent_as": "dispatcher"},
        )

    # Bestätigungs-Inbox an den Reporter
    create_inbox_message(
        session,
        recipient_id=web_user.id,
        msg_type=InboxMessageType.emergency_absence_new,
        reference_id=cr.id,
        reference_type="cancellation_request",
        snapshot_data={**snapshot, "sent_as": "reporter"},
    )

    # Telefonliste für Reporter-Mail (Privacy-gefiltert)
    phone_list = _build_phone_list(session, recipient_web_user_ids)

    email_payloads: list[EmailPayload] = list(cast_payloads)

    # Broadcast-Mails an Notification-Circle
    for email, first_name in recipient_infos:
        html = _render_email(
            "emergency_absence_broadcast.html",
            employee_name=employee_name,
            snapshot=snapshot,
            reason=reason,
            cr_id=cr.id,
            recipient_first_name=first_name,
        )
        subject = f"Notfall-Absage: {ctx['location_name']}, {ctx['event_date']}"
        email_payloads.append(EmailPayload(to=[email], subject=subject, html_body=html))

    # Dispatcher-Mail (nur wenn nicht ohnehin im Kreis)
    if dispatcher_info is not None:
        email, first_name = dispatcher_info
        html = _render_email(
            "emergency_absence_dispatcher.html",
            employee_name=employee_name,
            snapshot=snapshot,
            reason=reason,
            cr_id=cr.id,
            recipient_count=len(recipient_web_user_ids),
            recipient_first_name=first_name,
        )
        email_payloads.append(EmailPayload(
            to=[email],
            subject="Notfall-Absage eingegangen",
            html_body=html,
        ))

    # Reporter-Bestätigungsmail (mit Telefonliste)
    reporter_email = recipient_email_for_web_user(session, web_user)
    reporter_first_name = first_name_for_web_user(session, web_user)
    if reporter_email:
        html = _render_email(
            "emergency_absence_reporter.html",
            employee_name=employee_name,
            snapshot=snapshot,
            reason=reason,
            phone_list=phone_list,
            recipient_count=len(recipient_web_user_ids),
            recipient_first_name=reporter_first_name,
        )
        email_payloads.append(EmailPayload(
            to=[reporter_email],
            subject="Notfall-Absage bestätigt",
            html_body=html,
        ))

    return CancellationDetail(
        id=cr.id,
        appointment_id=appointment_id,
        employee_name=employee_name,
        location_name=ctx["location_name"],
        event_date=ctx["event_date"],
        time_of_day_name=ctx["time_of_day_name"],
        time_start=ctx["time_start"],
        time_end=ctx["time_end"],
        reason=reason,
        status=CancellationStatus.pending,
        created_at=cr.created_at,
        plan_period_id=ctx["plan_period_id"],
        notification_recipients=recipients,
        kind=CancellationKind.emergency,
    ), email_payloads
