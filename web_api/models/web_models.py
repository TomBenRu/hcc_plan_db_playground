"""Web-spezifische DB-Modelle (nicht Teil des Desktop-Tool-Schemas)."""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Enum as SAEnum
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
