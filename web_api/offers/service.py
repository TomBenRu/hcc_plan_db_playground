"""AvailabilityOffer-Service: proaktive Angebote für unterbesetzte Termine.

Spiegelt das SwapRequest-Pattern, aber uni-partit: nur Offerer → Dispatcher.
Cast-Change-Integration via `replace_cast_for_appointment` aus dem Dispatcher-
Service — der Offerer wird zum bestehenden Cast hinzugefügt (additive Operation,
keine Remove-Semantik).
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    AvailDay,
    AvailDayAppointmentLink,
    Person,
    PlanPeriod,
)
from web_api.cancellations.service import (
    _get_dispatcher_web_user,
    _load_appointment_context,
    _render_email,
)
from web_api.dispatcher.service import (
    get_cast_status_for_appointment,
    replace_cast_for_appointment,
)
from web_api.email.service import EmailPayload
from web_api.inbox.service import create_inbox_message
from web_api.models.web_models import (
    AvailabilityOffer,
    AvailabilityOfferStatus,
    InboxMessageType,
    WebUser,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class AvailabilityOfferSummary:
    id: uuid.UUID
    offerer_web_user_id: uuid.UUID
    offerer_name: str
    appointment_id: uuid.UUID
    event_date: str
    location_name: str
    time_of_day_name: str | None
    message: str | None
    status: AvailabilityOfferStatus
    created_at: datetime


# ── Interne Helfer ───────────────────────────────────────────────────────────


def _get_current_cast_person_ids(
    session: Session, appointment_id: uuid.UUID
) -> set[uuid.UUID]:
    """Liefert die Menge aller Person-IDs, die aktuell dem Appointment zugeordnet sind."""
    return set(session.execute(
        sa_select(ActorPlanPeriod.person_id)
        .join(AvailDay, AvailDay.actor_plan_period_id == ActorPlanPeriod.id)
        .join(AvailDayAppointmentLink, AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().all())


def _person_has_actor_plan_period_in_team(
    session: Session,
    person_id: uuid.UUID,
    team_id: uuid.UUID,
    plan_period_id: uuid.UUID,
) -> bool:
    """Prüft, ob die Person einen ActorPlanPeriod in derselben Plan-Periode hat.

    Ohne diesen Check könnte `replace_cast_for_appointment` keine AvailDay-
    Zuordnung anlegen — dort wird ein existierender ActorPlanPeriod derselben
    PlanPeriod vorausgesetzt.
    """
    row = session.execute(
        sa_select(ActorPlanPeriod.id)
        .join(PlanPeriod, PlanPeriod.id == ActorPlanPeriod.plan_period_id)
        .where(ActorPlanPeriod.person_id == person_id)
        .where(PlanPeriod.id == plan_period_id)
        .where(PlanPeriod.team_id == team_id)
        .where(PlanPeriod.prep_delete.is_(None))
    ).first()
    return row is not None


def _build_offer_snapshot(ctx: dict, offerer_name: str) -> dict:
    """Struktur für Inbox-Snapshots + Email-Templates. Spiegelt Cancellation-Pattern."""
    return {
        "offerer_name": offerer_name,
        "location_name": ctx["location_name"],
        "event_date": str(ctx["event_date"]),
        "time_of_day_name": ctx["time_of_day_name"],
        "time_start": str(ctx["time_start"]) if ctx["time_start"] else None,
        "time_end": str(ctx["time_end"]) if ctx["time_end"] else None,
    }


def _format_offerer_name(offerer_user: WebUser, session: Session) -> str:
    if offerer_user.person_id is None:
        return offerer_user.email
    person = session.get(Person, offerer_user.person_id)
    return f"{person.f_name} {person.l_name}" if person else offerer_user.email


# ── State-Transitions ────────────────────────────────────────────────────────


def create_offer(
    session: Session,
    offerer_user: WebUser,
    appointment_id: uuid.UUID,
    message: str | None,
) -> tuple[AvailabilityOffer, list[EmailPayload]]:
    """Mitarbeiter bietet sich für einen unterbesetzten Termin an.

    Guards:
      1. Offerer hat Person-Verknüpfung
      2. Appointment existiert und ist unterbesetzt (cast_count < cast_required)
      3. Offerer ist **nicht** bereits diesem Appointment zugeordnet
      4. Offerer hat einen ActorPlanPeriod im Team desselben Plans
      5. Kein aktives Pending-Offer derselben Person auf denselben Appointment
    """
    if offerer_user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Kein Personenprofil verknüpft."
        )

    ctx = _load_appointment_context(session, appointment_id)

    if ctx["event_date"] < date.today():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Der Termin liegt in der Vergangenheit.",
        )

    cast_status = get_cast_status_for_appointment(session, appointment_id)
    if not cast_status["is_understaffed"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Der Termin ist nicht unterbesetzt.",
        )

    current_person_ids = _get_current_cast_person_ids(session, appointment_id)
    if offerer_user.person_id in current_person_ids:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Du bist bereits für diesen Termin eingeteilt.",
        )

    if not _person_has_actor_plan_period_in_team(
        session, offerer_user.person_id, ctx["team_id"], ctx["plan_period_id"]
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Du bist für diese Planperiode nicht als einsetzbar geführt.",
        )

    duplicate = session.execute(
        sa_select(AvailabilityOffer.id)
        .where(AvailabilityOffer.offerer_web_user_id == offerer_user.id)
        .where(AvailabilityOffer.appointment_id == appointment_id)
        .where(AvailabilityOffer.status == AvailabilityOfferStatus.pending)
    ).first()
    if duplicate is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Du hast bereits ein offenes Angebot für diesen Termin.",
        )

    offer = AvailabilityOffer(
        offerer_web_user_id=offerer_user.id,
        appointment_id=appointment_id,
        message=message,
        status=AvailabilityOfferStatus.pending,
    )
    session.add(offer)
    session.flush()

    offerer_name = _format_offerer_name(offerer_user, session)
    snapshot = _build_offer_snapshot(ctx, offerer_name)

    email_payloads: list[EmailPayload] = []
    dispatcher_user = _get_dispatcher_web_user(session, ctx["team_id"])
    if dispatcher_user:
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.availability_offer_received,
            reference_id=offer.id,
            reference_type="availability_offer",
            snapshot_data=snapshot,
        )
        html = _render_email(
            "availability_offer_received.html",
            offerer_name=offerer_name,
            snapshot=snapshot,
            message=message,
        )
        email_payloads.append(EmailPayload(
            to=[dispatcher_user.email],
            subject=f"Angebot: {offerer_name} möchte einspringen",
            html_body=html,
        ))

    return offer, email_payloads


def accept_offer(
    session: Session,
    offer_id: uuid.UUID,
    dispatcher_user: WebUser,
) -> list[EmailPayload]:
    """Dispatcher akzeptiert ein Angebot — fügt Offerer zum Cast hinzu.

    Additiv: bestehender Cast bleibt, Offerer kommt hinzu. `replace_cast_for_appointment`
    berechnet keinen Remove-Diff, weil `old_person_ids ⊂ new_person_ids`.
    """
    offer = session.get(AvailabilityOffer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Angebot nicht gefunden.")
    if offer.status != AvailabilityOfferStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Dieses Angebot kann nicht mehr akzeptiert werden.",
        )

    ctx = _load_appointment_context(session, offer.appointment_id)
    dispatcher_for_team = _get_dispatcher_web_user(session, ctx["team_id"])
    if dispatcher_for_team is None or dispatcher_for_team.id != dispatcher_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Nur der Dispatcher des Teams kann dieses Angebot akzeptieren.",
        )

    if ctx["event_date"] < date.today():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Der Termin liegt in der Vergangenheit.",
        )

    offerer_user = session.get(WebUser, offer.offerer_web_user_id)
    if offerer_user is None or offerer_user.person_id is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Offerer-Profil nicht mehr verfügbar.",
        )

    current_person_ids = _get_current_cast_person_ids(session, offer.appointment_id)
    new_person_ids = current_person_ids | {offerer_user.person_id}

    cast_change_payloads = replace_cast_for_appointment(
        session, offer.appointment_id, list(new_person_ids)
    )

    offer.status = AvailabilityOfferStatus.accepted_by_dispatcher
    session.add(offer)
    session.flush()

    offerer_name = _format_offerer_name(offerer_user, session)
    snapshot = _build_offer_snapshot(ctx, offerer_name)

    email_payloads: list[EmailPayload] = list(cast_change_payloads)
    create_inbox_message(
        session,
        recipient_id=offerer_user.id,
        msg_type=InboxMessageType.availability_offer_accepted,
        reference_id=offer.id,
        reference_type="availability_offer",
        snapshot_data=snapshot,
    )
    html = _render_email("availability_offer_accepted.html", snapshot=snapshot)
    email_payloads.append(EmailPayload(
        to=[offerer_user.email],
        subject="Dein Angebot wurde angenommen",
        html_body=html,
    ))
    return email_payloads


def reject_offer(
    session: Session,
    offer_id: uuid.UUID,
    dispatcher_user: WebUser,
) -> list[EmailPayload]:
    """Dispatcher lehnt Angebot ab."""
    offer = session.get(AvailabilityOffer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Angebot nicht gefunden.")
    if offer.status != AvailabilityOfferStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Dieses Angebot kann nicht mehr abgelehnt werden.",
        )

    ctx = _load_appointment_context(session, offer.appointment_id)
    dispatcher_for_team = _get_dispatcher_web_user(session, ctx["team_id"])
    if dispatcher_for_team is None or dispatcher_for_team.id != dispatcher_user.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Nur der Dispatcher des Teams kann dieses Angebot ablehnen.",
        )

    offer.status = AvailabilityOfferStatus.rejected_by_dispatcher
    session.add(offer)
    session.flush()

    offerer_user = session.get(WebUser, offer.offerer_web_user_id)
    email_payloads: list[EmailPayload] = []
    if offerer_user is not None:
        offerer_name = _format_offerer_name(offerer_user, session)
        snapshot = _build_offer_snapshot(ctx, offerer_name)
        create_inbox_message(
            session,
            recipient_id=offerer_user.id,
            msg_type=InboxMessageType.availability_offer_rejected,
            reference_id=offer.id,
            reference_type="availability_offer",
            snapshot_data=snapshot,
        )
        html = _render_email("availability_offer_rejected.html", snapshot=snapshot)
        email_payloads.append(EmailPayload(
            to=[offerer_user.email],
            subject="Dein Angebot wurde abgelehnt",
            html_body=html,
        ))
    return email_payloads


def withdraw_offer(
    session: Session,
    offer_id: uuid.UUID,
    offerer_user: WebUser,
) -> list[EmailPayload]:
    """Mitarbeiter zieht sein Angebot zurück (nur solange pending)."""
    offer = session.get(AvailabilityOffer, offer_id)
    if offer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Angebot nicht gefunden.")
    if offer.offerer_web_user_id != offerer_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Kein Zugriff.")
    if offer.status != AvailabilityOfferStatus.pending:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Dieses Angebot kann nicht mehr zurückgezogen werden.",
        )

    offer.status = AvailabilityOfferStatus.withdrawn
    session.add(offer)
    session.flush()

    ctx = _load_appointment_context(session, offer.appointment_id)
    dispatcher_user = _get_dispatcher_web_user(session, ctx["team_id"])
    email_payloads: list[EmailPayload] = []
    if dispatcher_user is not None:
        offerer_name = _format_offerer_name(offerer_user, session)
        snapshot = _build_offer_snapshot(ctx, offerer_name)
        create_inbox_message(
            session,
            recipient_id=dispatcher_user.id,
            msg_type=InboxMessageType.availability_offer_withdrawn,
            reference_id=offer.id,
            reference_type="availability_offer",
            snapshot_data=snapshot,
        )
        html = _render_email("availability_offer_withdrawn.html", snapshot=snapshot)
        email_payloads.append(EmailPayload(
            to=[dispatcher_user.email],
            subject=f"{offerer_name} hat das Angebot zurückgezogen",
            html_body=html,
        ))
    return email_payloads


# ── Lese-Funktionen ──────────────────────────────────────────────────────────


def _row_to_summary(row) -> AvailabilityOfferSummary:
    return AvailabilityOfferSummary(
        id=row["id"],
        offerer_web_user_id=row["offerer_web_user_id"],
        offerer_name=row["offerer_name"] or "",
        appointment_id=row["appointment_id"],
        event_date=str(row["event_date"]) if row["event_date"] else "",
        location_name=row["location_name"] or "",
        time_of_day_name=row["time_of_day_name"],
        message=row["message"],
        status=row["status"],
        created_at=row["created_at"],
    )


def get_offers_for_user(
    session: Session, web_user_id: uuid.UUID
) -> list[AvailabilityOfferSummary]:
    """Alle Angebote des Mitarbeiters (als Offerer)."""
    from database.models import Appointment, Event, LocationOfWork, LocationPlanPeriod, Plan, TimeOfDay
    stmt = (
        sa_select(
            AvailabilityOffer.id.label("id"),
            AvailabilityOffer.offerer_web_user_id.label("offerer_web_user_id"),
            AvailabilityOffer.appointment_id.label("appointment_id"),
            AvailabilityOffer.message.label("message"),
            AvailabilityOffer.status.label("status"),
            AvailabilityOffer.created_at.label("created_at"),
            (Person.f_name + " " + Person.l_name).label("offerer_name"),
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            TimeOfDay.name.label("time_of_day_name"),
        )
        .select_from(AvailabilityOffer)
        .join(WebUser, WebUser.id == AvailabilityOffer.offerer_web_user_id)
        .join(Person, Person.id == WebUser.person_id, isouter=True)
        .join(Appointment, Appointment.id == AvailabilityOffer.appointment_id)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .where(AvailabilityOffer.offerer_web_user_id == web_user_id)
        .order_by(AvailabilityOffer.created_at.desc())
    )
    rows = session.execute(stmt).mappings().all()
    return [_row_to_summary(r) for r in rows]


def get_offers_for_dispatcher(
    session: Session, dispatcher_user: WebUser
) -> list[AvailabilityOfferSummary]:
    """Alle Angebote in Teams, in denen der User als Dispatcher eingetragen ist.

    Ein Admin ohne Dispatcher-Zuweisung bekommt hier eine leere Liste zurück —
    konsistent mit dem SwapRequest-Scope.
    """
    from database.models import (
        Appointment,
        Event,
        LocationOfWork,
        LocationPlanPeriod,
        Plan,
        Team,
        TimeOfDay,
    )
    if dispatcher_user.person_id is None:
        return []
    my_team_ids = session.execute(
        sa_select(Team.id).where(Team.dispatcher_id == dispatcher_user.person_id)
    ).scalars().all()
    if not my_team_ids:
        return []

    stmt = (
        sa_select(
            AvailabilityOffer.id.label("id"),
            AvailabilityOffer.offerer_web_user_id.label("offerer_web_user_id"),
            AvailabilityOffer.appointment_id.label("appointment_id"),
            AvailabilityOffer.message.label("message"),
            AvailabilityOffer.status.label("status"),
            AvailabilityOffer.created_at.label("created_at"),
            (Person.f_name + " " + Person.l_name).label("offerer_name"),
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            TimeOfDay.name.label("time_of_day_name"),
        )
        .select_from(AvailabilityOffer)
        .join(WebUser, WebUser.id == AvailabilityOffer.offerer_web_user_id)
        .join(Person, Person.id == WebUser.person_id, isouter=True)
        .join(Appointment, Appointment.id == AvailabilityOffer.appointment_id)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .where(PlanPeriod.team_id.in_(my_team_ids))
        .order_by(AvailabilityOffer.created_at.desc())
    )
    rows = session.execute(stmt).mappings().all()
    return [_row_to_summary(r) for r in rows]