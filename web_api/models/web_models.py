"""Web-spezifische DB-Modelle (nicht Teil des Desktop-Tool-Schemas)."""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy.types import JSON
from sqlmodel import Column, Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WebUserRole(str, enum.Enum):
    admin = "admin"
    dispatcher = "dispatcher"
    employee = "employee"
    accountant = "accountant"


class WebUserRoleLink(SQLModel, table=True):
    """M:N-Verknüpfung zwischen WebUser und WebUserRole."""

    __tablename__ = "web_user_role"

    web_user_id: uuid.UUID = Field(
        foreign_key="web_user.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    role: WebUserRole = Field(
        sa_column=Column(
            SAEnum(WebUserRole, name="webuserrole"),
            primary_key=True,
            nullable=False,
        )
    )

    user: Optional["WebUser"] = Relationship(back_populates="role_links")


class WebUser(SQLModel, table=True):
    """Verknüpft einen Web-Login (E-Mail + Passwort-Hash) mit einem Person-Eintrag."""

    __tablename__ = "web_user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    person_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="person.id",
        unique=True,
        nullable=True,
    )
    email: str = Field(unique=True, index=True, max_length=254)
    hashed_password: str
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utcnow)
    last_modified: datetime = Field(default_factory=_utcnow)

    role_links: list[WebUserRoleLink] = Relationship(back_populates="user")

    @property
    def roles(self) -> set[WebUserRole]:
        """Gibt alle Rollen des Users zurück (setzt voraus, dass role_links geladen sind)."""
        return {link.role for link in self.role_links}

    def has_any_role(self, *roles: WebUserRole) -> bool:
        return bool(self.roles & set(roles))


# ── Absage-Workflow — Enums ───────────────────────────────────────────────────


class CancellationStatus(str, enum.Enum):
    pending = "pending"
    resolved = "resolved"
    withdrawn = "withdrawn"


class NotificationSource(str, enum.Enum):
    auto_computed = "auto_computed"
    preconfigured = "preconfigured"
    both = "both"


class InboxMessageType(str, enum.Enum):
    cancellation_new = "cancellation_new"
    cancellation_withdrawn = "cancellation_withdrawn"
    cancellation_resolved = "cancellation_resolved"
    takeover_offer_received = "takeover_offer_received"
    takeover_accepted = "takeover_accepted"
    swap_request_received = "swap_request_received"
    swap_accepted_by_target = "swap_accepted_by_target"
    swap_confirmed = "swap_confirmed"
    swap_rejected = "swap_rejected"
    swap_withdrawn = "swap_withdrawn"


# ── Absage-Workflow — Modelle ─────────────────────────────────────────────────


class ProjectSettings(SQLModel, table=True):
    """Projekt-weite Einstellungen, insbesondere die Standard-Absagefrist."""

    __tablename__ = "project_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", unique=True, ondelete="CASCADE")
    cancellation_deadline_hours: int = Field(default=48, ge=0)
    created_at: datetime = Field(default_factory=_utcnow)
    last_modified: datetime = Field(default_factory=_utcnow)


class TeamNotificationSettings(SQLModel, table=True):
    """Team-spezifische Absagefrist (NULL = erbt von ProjectSettings)."""

    __tablename__ = "team_notification_settings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    team_id: uuid.UUID = Field(foreign_key="team.id", unique=True, ondelete="CASCADE")
    cancellation_deadline_hours: Optional[int] = Field(default=None, ge=0, nullable=True)
    created_at: datetime = Field(default_factory=_utcnow)
    last_modified: datetime = Field(default_factory=_utcnow)


class LocationNotificationCircle(SQLModel, table=True):
    """Vorab-konfigurierter Benachrichtigungs-Kreis pro Arbeitsort (durch Dispatcher)."""

    __tablename__ = "location_notification_circle"

    location_of_work_id: uuid.UUID = Field(
        foreign_key="location_of_work.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    web_user_id: uuid.UUID = Field(
        foreign_key="web_user.id",
        primary_key=True,
        ondelete="CASCADE",
    )
    added_by_id: uuid.UUID = Field(foreign_key="web_user.id", ondelete="CASCADE")
    created_at: datetime = Field(default_factory=_utcnow)


class CancellationRequest(SQLModel, table=True):
    """Absage-Antrag eines Mitarbeiters für einen Appointment."""

    __tablename__ = "cancellation_request"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    appointment_id: uuid.UUID = Field(foreign_key="appointment.id", ondelete="CASCADE")
    web_user_id: uuid.UUID = Field(foreign_key="web_user.id", ondelete="CASCADE")
    reason: Optional[str] = Field(default=None)
    status: CancellationStatus = Field(
        sa_column=Column(
            SAEnum(CancellationStatus, name="cancellationstatus"),
            nullable=False,
        )
    )
    created_at: datetime = Field(default_factory=_utcnow)
    resolved_at: Optional[datetime] = Field(default=None, nullable=True)
    resolved_by_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="web_user.id", nullable=True, ondelete="SET NULL"
    )

    notification_recipients: list["CancellationNotificationRecipient"] = Relationship(
        back_populates="cancellation_request"
    )
    takeover_offers: list["TakeoverOffer"] = Relationship()


class CancellationNotificationRecipient(SQLModel, table=True):
    """Audit-Snapshot: wer bei dieser Absage benachrichtigt wurde und warum."""

    __tablename__ = "cancellation_notification_recipient"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cancellation_request_id: uuid.UUID = Field(
        foreign_key="cancellation_request.id", ondelete="CASCADE"
    )
    web_user_id: uuid.UUID = Field(foreign_key="web_user.id", ondelete="CASCADE")
    source: NotificationSource = Field(
        sa_column=Column(
            SAEnum(NotificationSource, name="notificationsource"),
            nullable=False,
        )
    )

    cancellation_request: CancellationRequest = Relationship(
        back_populates="notification_recipients"
    )


# ── Phase 2: Übernahme-Angebote + Tausch-Anfragen ────────────────────────────


class TakeoverOfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class SwapRequestStatus(str, enum.Enum):
    pending = "pending"
    accepted_by_target = "accepted_by_target"
    rejected_by_target = "rejected_by_target"
    confirmed_by_dispatcher = "confirmed_by_dispatcher"
    rejected_by_dispatcher = "rejected_by_dispatcher"
    withdrawn = "withdrawn"


class TakeoverOffer(SQLModel, table=True):
    __tablename__ = "takeover_offer"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cancellation_request_id: uuid.UUID = Field(
        foreign_key="cancellation_request.id", ondelete="CASCADE"
    )
    web_user_id: uuid.UUID = Field(foreign_key="web_user.id", ondelete="CASCADE")
    message: Optional[str] = Field(default=None)
    status: TakeoverOfferStatus = Field(
        sa_column=Column(
            SAEnum(TakeoverOfferStatus, name="takeoverofferstatus"),
            nullable=False,
        )
    )
    created_at: datetime = Field(default_factory=_utcnow)


class SwapRequest(SQLModel, table=True):
    __tablename__ = "swap_request"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    requester_web_user_id: uuid.UUID = Field(
        foreign_key="web_user.id", ondelete="CASCADE"
    )
    requester_appointment_id: uuid.UUID = Field(
        foreign_key="appointment.id", ondelete="CASCADE"
    )
    target_web_user_id: uuid.UUID = Field(
        foreign_key="web_user.id", ondelete="CASCADE"
    )
    target_appointment_id: uuid.UUID = Field(
        foreign_key="appointment.id", ondelete="CASCADE"
    )
    message: Optional[str] = Field(default=None)
    status: SwapRequestStatus = Field(
        sa_column=Column(
            SAEnum(SwapRequestStatus, name="swaprequeststatus"),
            nullable=False,
        )
    )
    created_at: datetime = Field(default_factory=_utcnow)


class InboxMessage(SQLModel, table=True):
    """Inbox-Nachricht für einen WebUser."""

    __tablename__ = "inbox_message"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipient_web_user_id: uuid.UUID = Field(
        foreign_key="web_user.id", ondelete="CASCADE"
    )
    type: InboxMessageType = Field(
        sa_column=Column(
            SAEnum(InboxMessageType, name="inboxmessagetype"),
            nullable=False,
        )
    )
    reference_id: uuid.UUID
    reference_type: str = Field(max_length=50)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_utcnow)
    snapshot_data: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default="{}"),
    )
