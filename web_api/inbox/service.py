"""Inbox-Service: InboxMessages erstellen, lesen, als gelesen markieren."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import or_, select as sa_select
from sqlmodel import Session

from database.models import ActorPlanPeriod, Appointment, Plan, PlanPeriod
from web_api.models.web_models import (
    CancellationRequest,
    CancellationStatus,
    InboxMessage,
    InboxMessageType,
)


# Zusammengesetzte Filter-Gruppen (mehrere Types hinter einem Filter-Key)
_TYPE_GROUPS: dict[str, set[str]] = {
    "resolved": {"cancellation_resolved", "takeover_accepted"},
}

# Welche Message-Types sind für welche Rolle relevant?
_ROLE_TYPES: dict[str, set[str]] = {
    "dispatcher": {
        "cancellation_new",
        "cancellation_withdrawn",
        "cancellation_resolved",
        "takeover_offer_received",
        "takeover_accepted",
        "availability_offer_received",
        "availability_offer_withdrawn",
    },
    "employee": {
        "cancellation_new",
        "cancellation_withdrawn",
        "cancellation_resolved",
        "takeover_accepted",
        "swap_request_received",
        "swap_accepted_by_target",
        "swap_confirmed",
        "swap_rejected",
        "swap_withdrawn",
        "availability_offer_accepted",
        "availability_offer_rejected",
        "availability_reminder_t7",
        "availability_reminder_t3",
        "availability_reminder_t1",
        "availability_reminder_catchup",
    },
}


@dataclass
class InboxItem:
    id: uuid.UUID
    type: InboxMessageType
    is_read: bool
    created_at: datetime
    snapshot_data: dict
    reference_id: uuid.UUID
    reference_type: str


@dataclass
class InboxGroup:
    reference_id: uuid.UUID
    reference_type: str
    location_name: str
    event_date: str
    employee_name: str
    time_of_day_name: str = ""
    time_start: str = ""
    time_end: str = ""
    messages: list[InboxItem] = field(default_factory=list)
    has_unread: bool = False
    cancellation_open: bool = False
    requester_web_user_id: uuid.UUID | None = None


def create_inbox_message(
    session: Session,
    *,
    recipient_id: uuid.UUID,
    msg_type: InboxMessageType,
    reference_id: uuid.UUID,
    reference_type: str,
    snapshot_data: dict,
) -> InboxMessage:
    msg = InboxMessage(
        recipient_web_user_id=recipient_id,
        type=msg_type,
        reference_id=reference_id,
        reference_type=reference_type,
        is_read=False,
        snapshot_data=snapshot_data,
    )
    session.add(msg)
    return msg


def get_inbox_for_user(
    session: Session,
    web_user_id: uuid.UUID,
    *,
    type_filter: str | None = None,
    unread_only: bool = False,
    role_filter: str | None = None,
    person_id: uuid.UUID | None = None,
) -> list[InboxItem]:
    stmt = (
        sa_select(InboxMessage)
        .where(InboxMessage.recipient_web_user_id == web_user_id)
        .order_by(InboxMessage.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(InboxMessage.is_read.is_(False))
    if type_filter:
        if type_filter in _TYPE_GROUPS:
            stmt = stmt.where(InboxMessage.type.in_(_TYPE_GROUPS[type_filter]))
        else:
            stmt = stmt.where(InboxMessage.type == type_filter)
    elif role_filter and role_filter in _ROLE_TYPES:
        stmt = stmt.where(InboxMessage.type.in_(_ROLE_TYPES[role_filter]))

        # Für cancellation_request-Nachrichten: Kontext über ActorPlanPeriod prüfen.
        # Hat der Nutzer (person_id) einen ActorPlanPeriod in der Planperiode des abgesagten
        # Termins → employee-Kontext; andernfalls → dispatcher-Kontext.
        if person_id:
            employee_cr_subq = (
                sa_select(CancellationRequest.id)
                .join(Appointment, Appointment.id == CancellationRequest.appointment_id)
                .join(Plan, Plan.id == Appointment.plan_id)
                .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
                .join(ActorPlanPeriod,
                      (ActorPlanPeriod.plan_period_id == PlanPeriod.id) &
                      (ActorPlanPeriod.person_id == person_id))
            )
            if role_filter == "employee":
                stmt = stmt.where(
                    or_(
                        InboxMessage.reference_type != "cancellation_request",
                        InboxMessage.reference_id.in_(employee_cr_subq),
                    )
                )
            elif role_filter == "dispatcher":
                stmt = stmt.where(
                    or_(
                        InboxMessage.reference_type != "cancellation_request",
                        InboxMessage.reference_id.not_in(employee_cr_subq),
                    )
                )
    rows = session.execute(stmt).scalars().all()

    return [
        InboxItem(
            id=m.id,
            type=m.type,
            is_read=m.is_read,
            created_at=m.created_at,
            snapshot_data=m.snapshot_data or {},
            reference_id=m.reference_id,
            reference_type=m.reference_type,
        )
        for m in rows
    ]


def get_inbox_grouped(
    session: Session,
    web_user_id: uuid.UUID,
    *,
    type_filter: str | None = None,
    unread_only: bool = False,
    role_filter: str | None = None,
    person_id: uuid.UUID | None = None,
) -> list[InboxGroup]:
    items = get_inbox_for_user(
        session, web_user_id,
        type_filter=type_filter,
        unread_only=unread_only,
        role_filter=role_filter,
        person_id=person_id,
    )
    groups: dict[uuid.UUID | None, InboxGroup] = {}
    ungrouped_key = uuid.UUID("00000000-0000-0000-0000-000000000000")
    for item in items:
        key = item.reference_id if item.reference_id else ungrouped_key
        if key not in groups:
            snap = item.snapshot_data or {}
            groups[key] = InboxGroup(
                reference_id=item.reference_id,
                reference_type=item.reference_type,
                location_name=snap.get("location_name", ""),
                event_date=snap.get("event_date", ""),
                employee_name=snap.get("employee_name", ""),
                time_of_day_name=snap.get("time_of_day_name") or "",
                time_start=snap.get("time_start") or "",
                time_end=snap.get("time_end") or "",
            )
        groups[key].messages.append(item)
        if not item.is_read:
            groups[key].has_unread = True
    # Batch-Lookup: Status + Antragsteller aller Cancellation-Referenzen
    cancellation_ref_ids = [
        g.reference_id
        for g in groups.values()
        if g.reference_type == "cancellation_request" and g.reference_id
    ]
    if cancellation_ref_ids:
        cr_rows = session.execute(
            sa_select(CancellationRequest.id, CancellationRequest.web_user_id, CancellationRequest.status)
            .where(CancellationRequest.id.in_(cancellation_ref_ids))
        ).mappings().all()
        cr_info: dict[uuid.UUID, dict] = {r["id"]: dict(r) for r in cr_rows}
        for g in groups.values():
            if g.reference_type == "cancellation_request" and g.reference_id in cr_info:
                info = cr_info[g.reference_id]
                g.cancellation_open = info["status"] == CancellationStatus.pending
                g.requester_web_user_id = info["web_user_id"]

    return list(groups.values())


def get_unread_count(session: Session, web_user_id: uuid.UUID) -> int:
    from sqlalchemy import func
    result = session.execute(
        sa_select(func.count(InboxMessage.id))
        .where(InboxMessage.recipient_web_user_id == web_user_id)
        .where(InboxMessage.is_read.is_(False))
    ).scalar()
    return result or 0


def mark_as_read(session: Session, message_id: uuid.UUID, web_user_id: uuid.UUID) -> None:
    msg = session.get(InboxMessage, message_id)
    if msg is None or msg.recipient_web_user_id != web_user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Nachricht nicht gefunden")
    msg.is_read = True
    session.add(msg)
