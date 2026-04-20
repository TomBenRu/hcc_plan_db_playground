"""add_swap_withdrawn_inbox_type

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-04-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'swap_withdrawn'")


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte.
    Der Downgrade ist bewusst ein No-Op; ein vollständiger Rollback
    würde Recreate-Typ + Table-Cast verlangen.
    """
    pass