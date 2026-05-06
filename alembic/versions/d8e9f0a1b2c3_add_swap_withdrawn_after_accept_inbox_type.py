"""add_swap_withdrawn_after_accept_inbox_type

Revision ID: d8e9f0a1b2c3
Revises: b5c6d7e8f9a0
Create Date: 2026-05-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE inboxmessagetype "
            "ADD VALUE IF NOT EXISTS 'swap_withdrawn_after_accept'"
        )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte.
    Der Downgrade ist bewusst ein No-Op; ein vollständiger Rollback
    würde Recreate-Typ + Table-Cast verlangen.
    """
    pass