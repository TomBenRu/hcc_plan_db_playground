"""Inbox-Service: InboxMessages erstellen, lesen, als gelesen markieren."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from web_api.models.web_models import InboxMessage, InboxMessageType


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
    messages: list[InboxItem] = field(default_factory=list)
    has_unread: bool = False


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
) -> list[InboxItem]:
    stmt = (
        sa_select(InboxMessage)
        .where(InboxMessage.recipient_web_user_id == web_user_id)
        .order_by(InboxMessage.created_at.desc())
    )
    if unread_only:
        stmt = stmt.where(InboxMessage.is_read.is_(False))
    if type_filter:
        stmt = stmt.where(InboxMessage.type == type_filter)
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
) -> list[InboxGroup]:
    items = get_inbox_for_user(
        session, web_user_id, type_filter=type_filter, unread_only=unread_only
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
            )
        groups[key].messages.append(item)
        if not item.is_read:
            groups[key].has_unread = True
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
