"""add_superseded_by_cast_change_enum_values

Revision ID: d9e0f1a2b3c4
Revises: c7d8e9f0a1b2
Create Date: 2026-04-20 18:00:00.000000

Ergaenzt neue Enum-Werte fuer den Fall, dass eine Absage-/Tausch-/Uebernahme-
Anfrage durch eine Cast-Aenderung (Dispatcher entfernt User aus Appointment)
obsolet wird. Wird von web_api/plan_adjustment/service.py gesetzt.

Zusaetzlich neuer InboxMessageType fuer die Benachrichtigung der Betroffenen.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9e0f1a2b3c4"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE cancellationstatus "
            "ADD VALUE IF NOT EXISTS 'superseded_by_cast_change'"
        )
        op.execute(
            "ALTER TYPE takeoverofferstatus "
            "ADD VALUE IF NOT EXISTS 'superseded_by_cast_change'"
        )
        op.execute(
            "ALTER TYPE swaprequeststatus "
            "ADD VALUE IF NOT EXISTS 'superseded_by_cast_change'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype "
            "ADD VALUE IF NOT EXISTS 'dispatcher_removed_from_cast'"
        )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte.
    Der Downgrade ist bewusst ein No-Op; ein vollstaendiger Rollback
    wuerde Recreate-Typ + Table-Cast verlangen.
    """
    pass