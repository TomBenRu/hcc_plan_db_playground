"""Cancellation-Service: Kernlogik für Absage-Workflow Phase 1."""

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    ActorPlanPeriodCombLocLink,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    CombinationLocationsPossible,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    LocOfWorkCombLocLink,
    Person,
    Plan,
    PlanPeriod,
    Team,
    TimeOfDay,
)
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    CancellationNotificationRecipient,
    CancellationRequest,
    CancellationStatus,
    InboxMessageType,
    LocationNotificationCircle,
    NotificationSource,
    WebUser,
)
from web_api.settings.service import get_effective_deadline
from web_api.templating import templates


# ── Datenklassen ──────────────────────────────────────────────────────────────


@dataclass
class NotificationRecipient:
    web_user_id: uuid.UUID
    email: str
    person_name: str
    source: NotificationSource


@dataclass
class CancellationDetail:
    id: uuid.UUID
    appointment_id: uuid.UUID
    employee_name: str
    location_name: str
    event_date: date
    time_of_day_name: str | None
    time_start: time | None
    time_end: time | None
    reason: str | None
    status: CancellationStatus
    created_at: datetime
    plan_period_id: uuid.UUID
    notification_recipients: list[NotificationRecipient]


@dataclass
class CancellationSummary:
    id: uuid.UUID
    employee_name: str
    location_name: str
    event_date: date
    time_of_day_name: str | None
    reason: str | None
    status: CancellationStatus
    created_at: datetime
    recipient_count: int


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _load_appointment_context(session: Session, appointment_id: uuid.UUID) -> dict:
    """Lädt alle für den Workflow benötigten Appointment-Daten in einem Query."""
    row = session.execute(
        sa_select(
            Appointment.id.label("appointment_id"),
            Appointment.plan_id,
            Event.id.label("event_id"),
            Event.date.label("event_date"),
            LocationOfWork.id.label("location_id"),
            LocationOfWork.name.label("location_name"),
            TimeOfDay.id.label("time_of_day_id"),
            TimeOfDay.name.label("time_of_day_name"),
            TimeOfDay.start.label("time_start"),
            TimeOfDay.end.label("time_end"),
            Plan.plan_period_id,
            Plan.is_binding,
            PlanPeriod.team_id,
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .where(Appointment.id == appointment_id)
        .where(Appointment.prep_delete.is_(None))
    ).mappings().first()

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")
    return dict(row)


def _verify_ownership(session: Session, appointment_id: uuid.UUID, person_id: uuid.UUID) -> None:
    """Stellt sicher, dass die Person via AvailDayAppointmentLink mit dem Appointment verknüpft ist."""
    exists = session.execute(
        sa_select(AvailDayAppointmentLink.appointment_id)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
        .where(ActorPlanPeriod.person_id == person_id)
    ).first()
    if exists is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff auf diesen Termin")


def _get_dispatcher_web_user(session: Session, team_id: uuid.UUID) -> WebUser | None:
    """Gibt den WebUser des Dispatchers zurück (wenn vorhanden)."""
    team = session.get(Team, team_id)
    if team is None or team.dispatcher_id is None:
        return None
    return session.execute(
        sa_select(WebUser).where(WebUser.person_id == team.dispatcher_id)
    ).scalars().first()


def _time_gap(t_from: time, t_to: time) -> timedelta:
    """Positiver Zeitabstand zwischen zwei time-Objekten (auch über Mitternacht)."""
    d = datetime.combine(date.today(), t_to) - datetime.combine(date.today(), t_from)
    if d.total_seconds() < 0:
        d += timedelta(days=1)
    return d


def _build_snapshot(ctx: dict, employee_name: str) -> dict:
    return {
        "employee_name": employee_name,
        "location_name": ctx["location_name"],
        "event_date": str(ctx["event_date"]),
        "time_of_day_name": ctx["time_of_day_name"],
        "time_start": str(ctx["time_start"]) if ctx["time_start"] else None,
        "time_end": str(ctx["time_end"]) if ctx["time_end"] else None,
    }


def _render_email(template_name: str, **ctx) -> str:
    return templates.get_template(f"emails/{template_name}").render(**ctx)


def _notify_recipients(
    session: Session,
    cr_id: uuid.UUID,
    recipients: list,
    dispatcher_user: WebUser | None,
    snapshot: dict,
    msg_type: InboxMessageType,
) -> tuple[list[str], set[uuid.UUID]]:
    """Erstellt Inbox-Messages für recipients + dispatcher. Gibt Email-Liste + recipient-IDs zurück."""
    notify_ids: set[uuid.UUID] = set()
    emails: list[str] = []

    for rec in recipients:
        notify_ids.add(rec.web_user_id)
        emails.append(rec.email)
        create_inbox_message(
            session,
            recipient_id=rec.web_user_id,
            msg_type=msg_type,
            reference_id=cr_id,
            reference_type="cancellation_request",
            snapshot_data=snapshot,
        )

    if dispatcher_user and dispatcher_user.id not in notify_ids:
        emails.insert(0, dispatcher_user.email)
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=msg_type,
            reference_id=cr_id,
            reference_type="cancellation_request",
            snapshot_data=snapshot,
        )

    return emails, notify_ids


# ── Benachrichtigungs-Kreis ───────────────────────────────────────────────────


def compute_notification_circle(
    session: Session,
    *,
    exclude_web_user_id: uuid.UUID,
    location_id: uuid.UUID,
    plan_period_id: uuid.UUID,
    event_date: date,
    cancelled_time_start: time | None,
    cancelled_time_end: time | None,
) -> list[NotificationRecipient]:
    """Berechnet den Benachrichtigungs-Kreis (vorab-konfiguriert + auto-berechnet)."""

    # ── Schritt A: vorab-konfiguriert ─────────────────────────────────────────
    preconfigured_rows = session.execute(
        sa_select(
            LocationNotificationCircle.web_user_id,
            WebUser.email,
            Person.f_name,
            Person.l_name,
        )
        .join(WebUser, WebUser.id == LocationNotificationCircle.web_user_id)
        .join(Person, Person.id == WebUser.person_id)
        .where(LocationNotificationCircle.location_of_work_id == location_id)
        .where(LocationNotificationCircle.web_user_id != exclude_web_user_id)
    ).mappings().all()

    preconfigured: dict[uuid.UUID, NotificationRecipient] = {
        r["web_user_id"]: NotificationRecipient(
            web_user_id=r["web_user_id"],
            email=r["email"],
            person_name=f"{r['f_name']} {r['l_name']}",
            source=NotificationSource.preconfigured,
        )
        for r in preconfigured_rows
    }

    # ── Schritt B: auto-berechnet ─────────────────────────────────────────────
    candidates_rows = session.execute(
        sa_select(
            ActorPlanPeriod.id.label("app_id"),
            ActorPlanPeriod.person_id,
            WebUser.id.label("web_user_id"),
            WebUser.email,
            Person.f_name,
            Person.l_name,
        )
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(WebUser, WebUser.person_id == Person.id)
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .where(WebUser.is_active.is_(True))
        .where(WebUser.id != exclude_web_user_id)
    ).mappings().all()

    auto_computed: dict[uuid.UUID, NotificationRecipient] = {}

    if candidates_rows:
        candidate_app_ids = [r["app_id"] for r in candidates_rows]

        # Binding-Appointments am Termin-Datum pro ActorPlanPeriod
        existing_apps_rows = session.execute(
            sa_select(
                AvailDay.actor_plan_period_id,
                TimeOfDay.start.label("tod_start"),
                TimeOfDay.end.label("tod_end"),
                LocationOfWork.id.label("loc_id"),
            )
            .select_from(AvailDayAppointmentLink)
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(Appointment, Appointment.id == AvailDayAppointmentLink.appointment_id)
            .join(Event, Event.id == Appointment.event_id)
            .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
            .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
            .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
            .join(Plan, Plan.id == Appointment.plan_id)
            .where(AvailDay.actor_plan_period_id.in_(candidate_app_ids))
            .where(Event.date == event_date)
            .where(Plan.is_binding.is_(True))
            .where(Plan.prep_delete.is_(None))
            .where(Appointment.prep_delete.is_(None))
        ).mappings().all()

        existing_by_app: dict[uuid.UUID, list[dict]] = {}
        for row in existing_apps_rows:
            existing_by_app.setdefault(row["actor_plan_period_id"], []).append(dict(row))

        # CombLoc-Daten für Kandidaten mit bestehenden Appointments
        combloc_candidates = [a for a in candidate_app_ids if a in existing_by_app]
        combloc_data: dict[uuid.UUID, list[dict]] = {}

        if combloc_candidates:
            clp_rows = session.execute(
                sa_select(
                    ActorPlanPeriodCombLocLink.actor_plan_period_id,
                    CombinationLocationsPossible.id.label("clp_id"),
                    CombinationLocationsPossible.time_span_between,
                )
                .join(
                    CombinationLocationsPossible,
                    CombinationLocationsPossible.id
                    == ActorPlanPeriodCombLocLink.combination_locations_possible_id,
                )
                .where(ActorPlanPeriodCombLocLink.actor_plan_period_id.in_(combloc_candidates))
                .where(CombinationLocationsPossible.prep_delete.is_(None))
            ).mappings().all()

            clp_ids = list({r["clp_id"] for r in clp_rows})
            loc_by_clp: dict[uuid.UUID, set[uuid.UUID]] = {}
            if clp_ids:
                loc_rows = session.execute(
                    sa_select(
                        LocOfWorkCombLocLink.combination_locations_possible_id,
                        LocOfWorkCombLocLink.location_of_work_id,
                    )
                    .where(
                        LocOfWorkCombLocLink.combination_locations_possible_id.in_(clp_ids)
                    )
                ).mappings().all()
                for lr in loc_rows:
                    loc_by_clp.setdefault(
                        lr["combination_locations_possible_id"], set()
                    ).add(lr["location_of_work_id"])

            for r in clp_rows:
                combloc_data.setdefault(r["actor_plan_period_id"], []).append({
                    "clp_id": r["clp_id"],
                    "time_span_between": r["time_span_between"],
                    "locations": loc_by_clp.get(r["clp_id"], set()),
                })

        for cand in candidates_rows:
            app_id = cand["app_id"]
            web_user_id = cand["web_user_id"]

            if app_id not in existing_by_app:
                auto_computed[web_user_id] = NotificationRecipient(
                    web_user_id=web_user_id,
                    email=cand["email"],
                    person_name=f"{cand['f_name']} {cand['l_name']}",
                    source=NotificationSource.auto_computed,
                )
                continue

            if app_id not in combloc_data:
                continue

            for existing_app in existing_by_app[app_id]:
                existing_loc = existing_app["loc_id"]
                existing_start: time = existing_app["tod_start"]
                existing_end: time = existing_app["tod_end"]
                eligible = False

                for clp in combloc_data[app_id]:
                    locs = clp["locations"]
                    if location_id not in locs or existing_loc not in locs:
                        continue
                    ts_between: timedelta = clp["time_span_between"]
                    if cancelled_time_start and existing_end:
                        if _time_gap(existing_end, cancelled_time_start) >= ts_between:
                            eligible = True
                            break
                    if cancelled_time_end and existing_start:
                        if _time_gap(cancelled_time_end, existing_start) >= ts_between:
                            eligible = True
                            break

                if eligible:
                    auto_computed[web_user_id] = NotificationRecipient(
                        web_user_id=web_user_id,
                        email=cand["email"],
                        person_name=f"{cand['f_name']} {cand['l_name']}",
                        source=NotificationSource.auto_computed,
                    )
                    break

    # ── Schritt C: Merge ──────────────────────────────────────────────────────
    result: dict[uuid.UUID, NotificationRecipient] = {}
    for uid, rec in preconfigured.items():
        result[uid] = rec
    for uid, rec in auto_computed.items():
        if uid in result:
            result[uid].source = NotificationSource.both
        else:
            result[uid] = rec

    return list(result.values())


# ── Haupt-Aktionen ────────────────────────────────────────────────────────────


def create_cancellation(
    session: Session,
    web_user: WebUser,
    appointment_id: uuid.UUID,
    reason: str | None,
) -> tuple[CancellationDetail, list[EmailPayload]]:
    """BR-01..04: Validierung → CancellationRequest + Kreis + Inbox + EmailPayloads."""
    ctx = _load_appointment_context(session, appointment_id)

    if not ctx["is_binding"]:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nur Termine aus dem verbindlichen Plan können abgesagt werden.",
        )

    if web_user.person_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Personenprofil verknüpft.")
    _verify_ownership(session, appointment_id, web_user.person_id)

    existing = session.execute(
        sa_select(CancellationRequest)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Für diesen Termin existiert bereits eine offene Absage.",
        )

    settings = get_effective_deadline(session, ctx["team_id"])
    if settings.deadline_hours > 0 and ctx["time_start"]:
        appointment_dt = datetime.combine(ctx["event_date"], ctx["time_start"])
        cutoff = appointment_dt - timedelta(hours=settings.deadline_hours)
        if datetime.now(timezone.utc).replace(tzinfo=None) > cutoff:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Absage nicht mehr möglich: Frist von {settings.deadline_hours}h überschritten.",
            )

    cr = CancellationRequest(
        appointment_id=appointment_id,
        web_user_id=web_user.id,
        reason=reason,
        status=CancellationStatus.pending,
    )
    session.add(cr)
    session.flush()

    person = session.get(Person, web_user.person_id)
    employee_name = f"{person.f_name} {person.l_name}" if person else web_user.email

    recipients = compute_notification_circle(
        session,
        exclude_web_user_id=web_user.id,
        location_id=ctx["location_id"],
        plan_period_id=ctx["plan_period_id"],
        event_date=ctx["event_date"],
        cancelled_time_start=ctx["time_start"],
        cancelled_time_end=ctx["time_end"],
    )

    for rec in recipients:
        session.add(CancellationNotificationRecipient(
            cancellation_request_id=cr.id,
            web_user_id=rec.web_user_id,
            source=rec.source,
        ))

    snapshot = _build_snapshot(ctx, employee_name)
    dispatcher_user = _get_dispatcher_web_user(session, ctx["team_id"])

    emails, _ = _notify_recipients(
        session, cr.id, recipients, dispatcher_user, snapshot, InboxMessageType.cancellation_new
    )

    email_payloads: list[EmailPayload] = []
    if emails:
        html = _render_email("cancellation_new.html",
                             employee_name=employee_name, snapshot=snapshot, reason=reason)
        email_payloads.append(EmailPayload(to=emails, subject="Termin abgesagt", html_body=html))

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
    ), email_payloads


def withdraw_cancellation(
    session: Session,
    cancellation_id: uuid.UUID,
    web_user: WebUser,
) -> tuple[CancellationDetail, list[EmailPayload]]:
    """BR-04: Rückzug nur bei status=pending."""
    cr = session.get(CancellationRequest, cancellation_id)
    if cr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Absage nicht gefunden.")
    if cr.web_user_id != web_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")
    if cr.status != CancellationStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Rückzug nur möglich, solange die Absage offen ist.",
        )

    cr.status = CancellationStatus.withdrawn
    session.add(cr)
    session.flush()

    ctx = _load_appointment_context(session, cr.appointment_id)
    person = session.get(Person, web_user.person_id) if web_user.person_id else None
    employee_name = f"{person.f_name} {person.l_name}" if person else web_user.email
    snapshot = _build_snapshot(ctx, employee_name)

    saved_recipients = session.execute(
        sa_select(CancellationNotificationRecipient)
        .where(CancellationNotificationRecipient.cancellation_request_id == cancellation_id)
    ).scalars().all()

    saved_ids = {r.web_user_id for r in saved_recipients}
    recipients_dc: list[NotificationRecipient] = []
    recipient_emails: list[str] = []

    for rec in saved_recipients:
        ru = session.get(WebUser, rec.web_user_id)
        if ru:
            recipient_emails.append(ru.email)
            create_inbox_message(
                session,
                recipient_id=rec.web_user_id,
                msg_type=InboxMessageType.cancellation_withdrawn,
                reference_id=cr.id,
                reference_type="cancellation_request",
                snapshot_data=snapshot,
            )
        p = session.get(Person, ru.person_id) if ru and ru.person_id else None
        recipients_dc.append(NotificationRecipient(
            web_user_id=rec.web_user_id,
            email=ru.email if ru else "",
            person_name=f"{p.f_name} {p.l_name}" if p else (ru.email if ru else ""),
            source=rec.source,
        ))

    dispatcher_user = _get_dispatcher_web_user(session, ctx["team_id"])
    if dispatcher_user and dispatcher_user.id not in saved_ids:
        recipient_emails.insert(0, dispatcher_user.email)
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.cancellation_withdrawn,
            reference_id=cr.id,
            reference_type="cancellation_request",
            snapshot_data=snapshot,
        )

    email_payloads: list[EmailPayload] = []
    if recipient_emails:
        html = _render_email("cancellation_withdrawn.html",
                             employee_name=employee_name, snapshot=snapshot)
        email_payloads.append(EmailPayload(
            to=recipient_emails, subject="Absage zurückgezogen", html_body=html
        ))

    return CancellationDetail(
        id=cr.id,
        appointment_id=cr.appointment_id,
        employee_name=employee_name,
        location_name=ctx["location_name"],
        event_date=ctx["event_date"],
        time_of_day_name=ctx["time_of_day_name"],
        time_start=ctx["time_start"],
        time_end=ctx["time_end"],
        reason=cr.reason,
        status=CancellationStatus.withdrawn,
        created_at=cr.created_at,
        plan_period_id=ctx["plan_period_id"],
        notification_recipients=recipients_dc,
    ), email_payloads


def get_my_cancellations(
    session: Session,
    web_user_id: uuid.UUID,
    status_filter: str | None = None,
) -> list[CancellationSummary]:
    stmt = (
        sa_select(
            CancellationRequest.id,
            CancellationRequest.reason,
            CancellationRequest.status,
            CancellationRequest.created_at,
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            TimeOfDay.name.label("time_of_day_name"),
        )
        .select_from(CancellationRequest)
        .join(Appointment, Appointment.id == CancellationRequest.appointment_id)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .where(CancellationRequest.web_user_id == web_user_id)
        .order_by(Event.date.asc())
    )
    if status_filter:
        stmt = stmt.where(CancellationRequest.status == status_filter)
    rows = session.execute(stmt).mappings().all()

    return [
        CancellationSummary(
            id=r["id"],
            employee_name="",
            location_name=r["location_name"],
            event_date=r["event_date"],
            time_of_day_name=r["time_of_day_name"],
            reason=r["reason"],
            status=r["status"],
            created_at=r["created_at"],
            recipient_count=0,
        )
        for r in rows
    ]


def get_cancellations_for_dispatcher(
    session: Session,
    web_user: WebUser,
    status_filter: str | None = None,
) -> list[CancellationSummary]:
    """Gibt alle Absagen des Teams zurück, dessen Dispatcher der User ist."""
    if web_user.person_id is None:
        return []

    team_ids = session.execute(
        sa_select(Team.id).where(Team.dispatcher_id == web_user.person_id)
    ).scalars().all()
    if not team_ids:
        return []

    stmt = (
        sa_select(
            CancellationRequest.id,
            CancellationRequest.reason,
            CancellationRequest.status,
            CancellationRequest.created_at,
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            TimeOfDay.name.label("time_of_day_name"),
            Person.f_name,
            Person.l_name,
        )
        .select_from(CancellationRequest)
        .join(Appointment, Appointment.id == CancellationRequest.appointment_id)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(WebUser, WebUser.id == CancellationRequest.web_user_id)
        .join(Person, Person.id == WebUser.person_id)
        .where(PlanPeriod.team_id.in_(team_ids))
        .order_by(Event.date.asc())
    )
    if status_filter:
        stmt = stmt.where(CancellationRequest.status == status_filter)

    rows = session.execute(stmt).mappings().all()
    return [
        CancellationSummary(
            id=r["id"],
            employee_name=f"{r['f_name']} {r['l_name']}",
            location_name=r["location_name"],
            event_date=r["event_date"],
            time_of_day_name=r["time_of_day_name"],
            reason=r["reason"],
            status=r["status"],
            created_at=r["created_at"],
            recipient_count=0,
        )
        for r in rows
    ]


def get_cancellation_detail(
    session: Session, cancellation_id: uuid.UUID, web_user: WebUser
) -> CancellationDetail:
    cr = session.get(CancellationRequest, cancellation_id)
    if cr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Absage nicht gefunden.")

    is_own = cr.web_user_id == web_user.id
    is_dispatcher = web_user.person_id and session.execute(
        sa_select(Team.id).where(Team.dispatcher_id == web_user.person_id)
    ).first() is not None

    if not is_own and not is_dispatcher:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")

    ctx = _load_appointment_context(session, cr.appointment_id)

    requester_user = session.get(WebUser, cr.web_user_id)
    person = (
        session.get(Person, requester_user.person_id)
        if requester_user and requester_user.person_id
        else None
    )
    employee_name = (
        f"{person.f_name} {person.l_name}"
        if person
        else (requester_user.email if requester_user else "")
    )

    saved_recipients = session.execute(
        sa_select(CancellationNotificationRecipient)
        .where(CancellationNotificationRecipient.cancellation_request_id == cancellation_id)
    ).scalars().all()

    recipients_dc = []
    for rec in saved_recipients:
        ru = session.get(WebUser, rec.web_user_id)
        p = session.get(Person, ru.person_id) if ru and ru.person_id else None
        recipients_dc.append(NotificationRecipient(
            web_user_id=rec.web_user_id,
            email=ru.email if ru else "",
            person_name=f"{p.f_name} {p.l_name}" if p else (ru.email if ru else ""),
            source=rec.source,
        ))

    return CancellationDetail(
        id=cr.id,
        appointment_id=cr.appointment_id,
        employee_name=employee_name,
        location_name=ctx["location_name"],
        event_date=ctx["event_date"],
        time_of_day_name=ctx["time_of_day_name"],
        time_start=ctx["time_start"],
        time_end=ctx["time_end"],
        reason=cr.reason,
        status=cr.status,
        created_at=cr.created_at,
        plan_period_id=ctx["plan_period_id"],
        notification_recipients=recipients_dc,
    )
