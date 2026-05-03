"""add_availability_reminder_inbox_types

Revision ID: f3e4f5a6b7c8
Revises: f2e3f4a5b6c7
Create Date: 2026-05-03 12:50:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "f2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Erweitert den Postgres-Enum `inboxmessagetype` um die vier
    Verfuegbarkeits-Reminder-Stufen.

    Schliesst die Luecke zwischen Mail-Versand (E-Mail) und Inbox: Pro
    erfolgreich versendetem Reminder wird zusaetzlich eine InboxMessage
    angelegt — falls die Person einen WebUser-Account hat (Best-Effort).
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_reminder_t7'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_reminder_t3'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_reminder_t1'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_reminder_catchup'"
        )


def downgrade() -> None:
    """Downgrade ist no-op.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte ohne
    vollstaendigen Typ-Recreate + Table-Cast. Die Werte bleiben nach
    Downgrade bestehen — ungenutzt, aber harmlos.
    """
    pass
