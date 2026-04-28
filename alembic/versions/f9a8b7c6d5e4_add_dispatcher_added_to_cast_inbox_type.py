"""add_dispatcher_added_to_cast_inbox_type

Revision ID: f9a8b7c6d5e4
Revises: ea8ed809d887
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9a8b7c6d5e4"
down_revision: Union[str, Sequence[str], None] = "ea8ed809d887"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Erweitert den Postgres-Enum `inboxmessagetype` um `dispatcher_added_to_cast`.

    Symmetrie zu `dispatcher_removed_from_cast` — wird gefeuert, wenn der
    Dispatcher eine Person neu in den Cast eines Appointments aufnimmt.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'dispatcher_added_to_cast'"
        )


def downgrade() -> None:
    """Downgrade ist no-op.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte ohne
    vollständigen Typ-Recreate + Table-Cast. Der Wert bleibt nach Downgrade
    bestehen — ungenutzt, aber harmlos.
    """
    pass
