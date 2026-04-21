"""Plan-Anpassungs-Service: AvailDay-Reassignment für Übernahme und Tausch."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    CastGroup,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    Plan,
    TimeOfDay,
)
from web_api.availability.service import create_avail_day, find_avail_day
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    CancellationRequest,
    CancellationStatus,
    InboxMessageType,
    SwapRequest,
    SwapRequestStatus,
    TakeoverOffer,
    TakeoverOfferStatus,
    WebUser,
)
from web_api.templating import templates


# ── Notification-Helfer ───────────────────────────────────────────────


def _render_cast_removal_email(snapshot: dict) -> str:
    return templates.get_template("emails/cast_member_removed.html").render(snapshot=snapshot)


def _render_plan_unbound_email(snapshot: dict) -> str:
    return templates.get_template("emails/plan_unbound.html").render(snapshot=snapshot)


def _load_cast_removal_context(session: Session, appointment_id: uuid.UUID) -> dict:
    """Lädt Termin-Kontext (Datum, Ort, Zeitfenster) für die Snapshot-Anzeige."""
    row = session.execute(
        sa_select(
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            TimeOfDay.name.label("time_of_day_name"),
            TimeOfDay.start.label("time_start"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    return dict(row) if row else {}


def _build_snapshot(
    ctx: dict,
    *,
    request_type: str,
    recipient_role: str,
    removed_person_name: str,
    partner_name: str = "",
) -> dict:
    return {
        "event_date": str(ctx.get("event_date", "")),
        "location_name": ctx.get("location_name", ""),
        "time_of_day_name": ctx.get("time_of_day_name", ""),
        "request_type": request_type,
        "recipient_role": recipient_role,
        "removed_person_name": removed_person_name,
        "partner_name": partner_name,
    }


def _cancel_open_requests_for_removed_persons(
    session: Session,
    appointment_id: uuid.UUID,
    removed_person_ids: set[uuid.UUID],
    *,
    exclude_cancellation_ids: frozenset[uuid.UUID] = frozenset(),
    exclude_swap_ids: frozenset[uuid.UUID] = frozenset(),
) -> list[EmailPayload]:
    """Setzt pending Cancel-/Swap-/Takeover-Requests der entfernten Personen
    auf superseded_by_cast_change und erzeugt Inbox-Messages + Email-Payloads
    für alle Betroffenen.

    Empfänger:
    - CancellationRequest → die entfernte Person (Antragstellerin).
    - Pending TakeoverOffer zu dieser Cancellation → der Anbieter.
    - SwapRequest mit entfernter Person → entfernte Person UND die Gegenseite.

    exclude_*_ids: Workflow-Pfade (accept_takeover_offer / confirm_swap_request)
    verwalten ihre aktive Request selbst und setzen den finalen Status
    (resolved / confirmed_by_dispatcher) anschließend — diese IDs können
    übergeben werden, damit der Helper sie weder auf superseded flippt noch
    Benachrichtigungen erzeugt.
    """
    payloads: list[EmailPayload] = []
    if not removed_person_ids:
        return payloads

    removed_web_users = list(session.execute(
        sa_select(WebUser).where(WebUser.person_id.in_(removed_person_ids))
    ).scalars().all())
    if not removed_web_users:
        return payloads

    removed_wu_ids = {u.id for u in removed_web_users}

    # Betroffene Requests und Offers vorab laden (für Batch-Empfänger-Load)
    cancel_reqs = list(session.execute(
        sa_select(CancellationRequest)
        .where(CancellationRequest.appointment_id == appointment_id)
        .where(CancellationRequest.web_user_id.in_(removed_wu_ids))
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).scalars().all())
    cancel_reqs = [cr for cr in cancel_reqs if cr.id not in exclude_cancellation_ids]

    cr_ids = [cr.id for cr in cancel_reqs]
    offers_by_cr: dict[uuid.UUID, list[TakeoverOffer]] = {}
    if cr_ids:
        all_offers = list(session.execute(
            sa_select(TakeoverOffer)
            .where(TakeoverOffer.cancellation_request_id.in_(cr_ids))
            .where(TakeoverOffer.status == TakeoverOfferStatus.pending)
        ).scalars().all())
        for o in all_offers:
            offers_by_cr.setdefault(o.cancellation_request_id, []).append(o)

    swap_reqs_raw = list(session.execute(
        sa_select(SwapRequest)
        .where(
            (
                (SwapRequest.requester_appointment_id == appointment_id)
                & (SwapRequest.requester_web_user_id.in_(removed_wu_ids))
            )
            | (
                (SwapRequest.target_appointment_id == appointment_id)
                & (SwapRequest.target_web_user_id.in_(removed_wu_ids))
            )
        )
        .where(SwapRequest.status.in_([
            SwapRequestStatus.pending,
            SwapRequestStatus.accepted_by_target,
        ]))
    ).scalars().all())
    swap_reqs = [sw for sw in swap_reqs_raw if sw.id not in exclude_swap_ids]

    if not cancel_reqs and not swap_reqs:
        return payloads

    # Batch-Load aller benötigten WebUser + Person (statt N+1 im Loop)
    relevant_wu_ids: set[uuid.UUID] = set(removed_wu_ids)
    for cr in cancel_reqs:
        for o in offers_by_cr.get(cr.id, []):
            relevant_wu_ids.add(o.web_user_id)
    for sw in swap_reqs:
        relevant_wu_ids.add(sw.requester_web_user_id)
        relevant_wu_ids.add(sw.target_web_user_id)

    all_users = list(session.execute(
        sa_select(WebUser).where(WebUser.id.in_(relevant_wu_ids))
    ).scalars().all())
    users_by_id = {u.id: u for u in all_users}
    person_ids = {u.person_id for u in all_users if u.person_id}
    persons_by_id: dict[uuid.UUID, Person] = {}
    if person_ids:
        all_persons = list(session.execute(
            sa_select(Person).where(Person.id.in_(person_ids))
        ).scalars().all())
        persons_by_id = {p.id: p for p in all_persons}

    def _name(wu_id: uuid.UUID | None) -> str:
        if wu_id is None:
            return "?"
        user = users_by_id.get(wu_id)
        if user is None:
            return "?"
        if user.person_id:
            p = persons_by_id.get(user.person_id)
            if p is not None:
                return f"{p.f_name} {p.l_name}"
        return user.email or "?"

    ctx = _load_cast_removal_context(session, appointment_id)

    # ── 1. CancellationRequests + Takeover-Kaskade ────────────────────
    for cr in cancel_reqs:
        cr.status = CancellationStatus.superseded_by_cast_change
        user = users_by_id.get(cr.web_user_id)
        removed_name = _name(cr.web_user_id)

        if user is not None:
            snapshot = _build_snapshot(
                ctx,
                request_type="cancellation",
                recipient_role="affected_self",
                removed_person_name=removed_name,
            )
            create_inbox_message(
                session,
                recipient_id=user.id,
                msg_type=InboxMessageType.dispatcher_removed_from_cast,
                reference_id=cr.id,
                reference_type="cancellation_request",
                snapshot_data=snapshot,
            )
            if user.email:
                payloads.append(EmailPayload(
                    to=[user.email],
                    subject="Cast-Änderung: Deine Absage-Anfrage ist obsolet",
                    html_body=_render_cast_removal_email(snapshot),
                ))

        for offer in offers_by_cr.get(cr.id, []):
            offer.status = TakeoverOfferStatus.superseded_by_cast_change
            offerer = users_by_id.get(offer.web_user_id)
            if offerer is None:
                continue
            offerer_snapshot = _build_snapshot(
                ctx,
                request_type="takeover_offer",
                recipient_role="offerer",
                removed_person_name=removed_name,
            )
            create_inbox_message(
                session,
                recipient_id=offerer.id,
                msg_type=InboxMessageType.dispatcher_removed_from_cast,
                reference_id=offer.id,
                reference_type="takeover_offer",
                snapshot_data=offerer_snapshot,
            )
            if offerer.email:
                payloads.append(EmailPayload(
                    to=[offerer.email],
                    subject="Cast-Änderung: Dein Übernahme-Angebot ist obsolet",
                    html_body=_render_cast_removal_email(offerer_snapshot),
                ))

    # ── 2. SwapRequests: beide Seiten benachrichtigen ─────────────────
    for swap in swap_reqs:
        swap.status = SwapRequestStatus.superseded_by_cast_change
        removed_is_requester = (
            swap.requester_appointment_id == appointment_id
            and swap.requester_web_user_id in removed_wu_ids
        )
        removed_is_target = (
            swap.target_appointment_id == appointment_id
            and swap.target_web_user_id in removed_wu_ids
        )
        requester_name = _name(swap.requester_web_user_id)
        target_name = _name(swap.target_web_user_id)
        removed_name = requester_name if removed_is_requester else target_name

        for wu_id, is_removed, partner in [
            (swap.requester_web_user_id, removed_is_requester, target_name),
            (swap.target_web_user_id, removed_is_target, requester_name),
        ]:
            user = users_by_id.get(wu_id)
            if user is None:
                continue
            role = "affected_self" if is_removed else "affected_partner"
            snapshot = _build_snapshot(
                ctx,
                request_type="swap_request",
                recipient_role=role,
                removed_person_name=removed_name,
                partner_name=partner,
            )
            create_inbox_message(
                session,
                recipient_id=user.id,
                msg_type=InboxMessageType.dispatcher_removed_from_cast,
                reference_id=swap.id,
                reference_type="swap_request",
                snapshot_data=snapshot,
            )
            if user.email:
                subject = (
                    "Cast-Änderung: Deine Tausch-Anfrage ist obsolet"
                    if is_removed
                    else "Cast-Änderung: Dein Tausch-Partner wurde entfernt"
                )
                payloads.append(EmailPayload(
                    to=[user.email],
                    subject=subject,
                    html_body=_render_cast_removal_email(snapshot),
                ))

    session.flush()
    return payloads


def update_appointment_avail_days(
    session: Session,
    appointment_id: uuid.UUID,
    new_avail_day_ids: list[uuid.UUID],
) -> list[EmailPayload]:
    """Ändert die AvailDay-Liste eines Appointments + cleant Requests entfernter User.

    Ermittelt vorab, welche Personen das Appointment verlieren, schreibt die
    neue M:N-Zuordnung direkt auf der übergebenen Session und flippt offene
    Requests der entfernten User auf superseded_by_cast_change — alles in
    einer Transaktion. Gibt die Liste der zu versendenden Email-Payloads
    zurück (Caller dispatched via BackgroundTasks).
    """
    old_person_ids = set(session.execute(
        sa_select(ActorPlanPeriod.person_id)
        .join(AvailDay, AvailDay.actor_plan_period_id == ActorPlanPeriod.id)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().all())

    new_person_ids: set[uuid.UUID] = set()
    avds_by_id: dict[uuid.UUID, AvailDay] = {}
    if new_avail_day_ids:
        new_person_ids = set(session.execute(
            sa_select(ActorPlanPeriod.person_id)
            .join(AvailDay, AvailDay.actor_plan_period_id == ActorPlanPeriod.id)
            .where(AvailDay.id.in_(new_avail_day_ids))
        ).scalars().all())
        avds_by_id = {
            ad.id: ad for ad in session.execute(
                sa_select(AvailDay).where(AvailDay.id.in_(new_avail_day_ids))
            ).scalars().all()
        }

    removed_person_ids = old_person_ids - new_person_ids

    appointment = session.get(Appointment, appointment_id)
    appointment.avail_days.clear()
    appointment.avail_days.extend(avds_by_id[aid] for aid in new_avail_day_ids)
    session.flush()

    return _cancel_open_requests_for_removed_persons(
        session, appointment_id, removed_person_ids
    )


def reassign_appointment(
    session: Session,
    appointment_id: uuid.UUID,
    old_person_id: uuid.UUID,
    new_person_id: uuid.UUID,
    *,
    exclude_cancellation_ids: frozenset[uuid.UUID] = frozenset(),
    exclude_swap_ids: frozenset[uuid.UUID] = frozenset(),
) -> list[EmailPayload]:
    """Verschiebt einen Appointment von old_person zu new_person via AvailDay-Reassignment.

    Ablauf:
    1. Offene Cancel-/Swap-/Takeover-Requests der old_person auf
       superseded_by_cast_change flippen + Benachrichtigungen erzeugen
       (Workflow-Pfade können ihre aktive Request via exclude_*_ids
       ausklammern — sie setzen den finalen Status selbst).
    2. Alten AvailDayAppointmentLink der old_person finden und löschen.
    3. ActorPlanPeriod der new_person in der selben PlanPeriod laden.
    4. Bestehenden AvailDay suchen oder neuen anlegen.
    5. Neuen AvailDayAppointmentLink erstellen.
    6. fixed_cast der CastGroup löschen (manuelle Zuweisung überschreibt
       den Constraint).

    Gibt die Liste der zu versendenden Email-Payloads zurück.
    """
    email_payloads = _cancel_open_requests_for_removed_persons(
        session,
        appointment_id,
        {old_person_id},
        exclude_cancellation_ids=exclude_cancellation_ids,
        exclude_swap_ids=exclude_swap_ids,
    )

    # 1. Alten Link + AvailDay der old_person finden
    old_link_row = session.execute(
        sa_select(AvailDayAppointmentLink, AvailDay)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
        .where(ActorPlanPeriod.person_id == old_person_id)
    ).first()

    if old_link_row is not None:
        old_link, old_avail_day = old_link_row
        session.delete(old_link)
        session.flush()

    # 2. Appointment-Kontext laden (Event-Datum + TimeOfDay + CastGroup)
    appt_row = session.execute(
        sa_select(
            Appointment.plan_id,
            Event.date.label("event_date"),
            Event.time_of_day_id,
            Event.cast_group_id,
            Plan.plan_period_id,
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()

    if appt_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")

    plan_period_id: uuid.UUID = appt_row["plan_period_id"]
    event_date = appt_row["event_date"]
    time_of_day_id: uuid.UUID = appt_row["time_of_day_id"]
    cast_group_id: uuid.UUID = appt_row["cast_group_id"]

    # 3. ActorPlanPeriod der new_person in derselben PlanPeriod finden
    new_app = session.execute(
        sa_select(ActorPlanPeriod)
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .where(ActorPlanPeriod.person_id == new_person_id)
    ).scalars().first()

    if new_app is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Neue Person hat keine Verfügbarkeitsperiode in dieser Planperiode.",
        )

    # 4. Bestehenden AvailDay suchen oder neuen anlegen
    avail_day = find_avail_day(session, new_app.id, event_date, time_of_day_id)
    if avail_day is None:
        avail_day = create_avail_day(session, new_app.id, event_date, time_of_day_id)

    # 5. Neuen Link anlegen
    new_link = AvailDayAppointmentLink(
        avail_day_id=avail_day.id,
        appointment_id=appointment_id,
    )
    session.add(new_link)
    session.flush()

    # 6. fixed_cast der CastGroup löschen
    cast_group = session.get(CastGroup, cast_group_id)
    if cast_group is not None and cast_group.fixed_cast is not None:
        cast_group.fixed_cast = None
        session.flush()

    return email_payloads


def _build_plan_unbind_snapshot(ctx: dict, *, request_type: str) -> dict:
    return {
        "event_date": str(ctx.get("event_date", "")),
        "location_name": ctx.get("location_name", ""),
        "time_of_day_name": ctx.get("time_of_day_name", ""),
        "request_type": request_type,
    }


def cancel_open_requests_for_unbound_plan(
    session: Session,
    plan_id: uuid.UUID,
) -> list[EmailPayload]:
    """Plan wurde auf nicht-verbindlich zurückgesetzt → alle offenen Requests
    für Appointments in diesem Plan auf superseded_by_plan_unbind setzen.

    Empfänger (eine Inbox-Message + E-Mail pro Request):
    - CancellationRequest → Antragstellerin.
    - Pending TakeoverOffer zu dieser Cancellation → Anbieter (Kaskade).
    - SwapRequest → beide Seiten (requester + target, auch bei
      Cross-Plan-Swaps, wo nur eine Seite im unbound Plan liegt).

    Kein exclude_*_ids-Parameter: der Toggle-Endpoint selbst setzt keinen
    nachgelagerten finalen Status, also gibt es nichts auszuschließen.
    """
    payloads: list[EmailPayload] = []

    appointment_ids = list(session.execute(
        sa_select(Appointment.id).where(Appointment.plan_id == plan_id)
    ).scalars().all())
    if not appointment_ids:
        return payloads

    cancel_reqs = list(session.execute(
        sa_select(CancellationRequest)
        .where(CancellationRequest.appointment_id.in_(appointment_ids))
        .where(CancellationRequest.status == CancellationStatus.pending)
    ).scalars().all())

    swap_reqs = list(session.execute(
        sa_select(SwapRequest)
        .where(
            SwapRequest.requester_appointment_id.in_(appointment_ids)
            | SwapRequest.target_appointment_id.in_(appointment_ids)
        )
        .where(SwapRequest.status.in_([
            SwapRequestStatus.pending,
            SwapRequestStatus.accepted_by_target,
        ]))
    ).scalars().all())

    cr_ids = [cr.id for cr in cancel_reqs]
    offers_by_cr: dict[uuid.UUID, list[TakeoverOffer]] = {}
    if cr_ids:
        all_offers = list(session.execute(
            sa_select(TakeoverOffer)
            .where(TakeoverOffer.cancellation_request_id.in_(cr_ids))
            .where(TakeoverOffer.status == TakeoverOfferStatus.pending)
        ).scalars().all())
        for o in all_offers:
            offers_by_cr.setdefault(o.cancellation_request_id, []).append(o)

    if not cancel_reqs and not swap_reqs:
        return payloads

    # Relevante WebUser-IDs sammeln und batch-laden
    relevant_wu_ids: set[uuid.UUID] = set()
    for cr in cancel_reqs:
        relevant_wu_ids.add(cr.web_user_id)
        for o in offers_by_cr.get(cr.id, []):
            relevant_wu_ids.add(o.web_user_id)
    for sw in swap_reqs:
        relevant_wu_ids.add(sw.requester_web_user_id)
        relevant_wu_ids.add(sw.target_web_user_id)

    all_users = list(session.execute(
        sa_select(WebUser).where(WebUser.id.in_(relevant_wu_ids))
    ).scalars().all())
    users_by_id = {u.id: u for u in all_users}

    # Termin-Kontext pro unique appointment_id vorladen (über Cancel-, Swap- und
    # beide Swap-Seiten, auch Cross-Plan)
    unique_appt_ids: set[uuid.UUID] = set()
    for cr in cancel_reqs:
        unique_appt_ids.add(cr.appointment_id)
    for sw in swap_reqs:
        unique_appt_ids.add(sw.requester_appointment_id)
        unique_appt_ids.add(sw.target_appointment_id)
    ctxs_by_appt_id: dict[uuid.UUID, dict] = {
        aid: _load_cast_removal_context(session, aid) for aid in unique_appt_ids
    }

    # 1. CancellationRequests + Takeover-Kaskade
    for cr in cancel_reqs:
        cr.status = CancellationStatus.superseded_by_plan_unbind
        ctx = ctxs_by_appt_id.get(cr.appointment_id, {})
        snapshot = _build_plan_unbind_snapshot(ctx, request_type="cancellation")
        user = users_by_id.get(cr.web_user_id)
        if user is not None:
            create_inbox_message(
                session,
                recipient_id=user.id,
                msg_type=InboxMessageType.plan_unbound,
                reference_id=cr.id,
                reference_type="cancellation_request",
                snapshot_data=snapshot,
            )
            if user.email:
                payloads.append(EmailPayload(
                    to=[user.email],
                    subject="Plan nicht mehr aktuell: Deine Absage-Anfrage ist obsolet",
                    html_body=_render_plan_unbound_email(snapshot),
                ))

        for offer in offers_by_cr.get(cr.id, []):
            offer.status = TakeoverOfferStatus.superseded_by_plan_unbind
            offerer = users_by_id.get(offer.web_user_id)
            if offerer is None:
                continue
            offerer_snapshot = _build_plan_unbind_snapshot(ctx, request_type="takeover_offer")
            create_inbox_message(
                session,
                recipient_id=offerer.id,
                msg_type=InboxMessageType.plan_unbound,
                reference_id=offer.id,
                reference_type="takeover_offer",
                snapshot_data=offerer_snapshot,
            )
            if offerer.email:
                payloads.append(EmailPayload(
                    to=[offerer.email],
                    subject="Plan nicht mehr aktuell: Dein Übernahme-Angebot ist obsolet",
                    html_body=_render_plan_unbound_email(offerer_snapshot),
                ))

    # 2. SwapRequests — beide Seiten benachrichtigen (jede Seite mit ihrem
    #    eigenen Termin-Kontext, auch bei Cross-Plan-Swaps)
    for swap in swap_reqs:
        swap.status = SwapRequestStatus.superseded_by_plan_unbind
        for wu_id, appt_id in [
            (swap.requester_web_user_id, swap.requester_appointment_id),
            (swap.target_web_user_id, swap.target_appointment_id),
        ]:
            user = users_by_id.get(wu_id)
            if user is None:
                continue
            ctx = ctxs_by_appt_id.get(appt_id, {})
            snapshot = _build_plan_unbind_snapshot(ctx, request_type="swap_request")
            create_inbox_message(
                session,
                recipient_id=user.id,
                msg_type=InboxMessageType.plan_unbound,
                reference_id=swap.id,
                reference_type="swap_request",
                snapshot_data=snapshot,
            )
            if user.email:
                payloads.append(EmailPayload(
                    to=[user.email],
                    subject="Plan nicht mehr aktuell: Deine Tausch-Anfrage ist obsolet",
                    html_body=_render_plan_unbound_email(snapshot),
                ))

    session.flush()
    return payloads


def swap_appointments(
    session: Session,
    appt_a_id: uuid.UUID,
    person_a_id: uuid.UUID,
    appt_b_id: uuid.UUID,
    person_b_id: uuid.UUID,
    *,
    exclude_swap_ids: frozenset[uuid.UUID] = frozenset(),
) -> list[EmailPayload]:
    """Tauscht zwei Appointments zwischen zwei Personen.

    Löscht beide alten Links zuerst (flush), dann legt neue an — verhindert
    UniqueConstraint-Konflikte falls beide AvailDays identisch wären.
    """
    def _find_link(appointment_id: uuid.UUID, person_id: uuid.UUID):
        return session.execute(
            sa_select(AvailDayAppointmentLink)
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
            .where(AvailDayAppointmentLink.appointment_id == appointment_id)
            .where(ActorPlanPeriod.person_id == person_id)
        ).scalars().first()

    link_a = _find_link(appt_a_id, person_a_id)
    link_b = _find_link(appt_b_id, person_b_id)

    if link_a is not None:
        session.delete(link_a)
    if link_b is not None:
        session.delete(link_b)
    session.flush()

    payloads = reassign_appointment(
        session, appt_a_id, person_a_id, person_b_id,
        exclude_swap_ids=exclude_swap_ids,
    )
    payloads += reassign_appointment(
        session, appt_b_id, person_b_id, person_a_id,
        exclude_swap_ids=exclude_swap_ids,
    )
    return payloads