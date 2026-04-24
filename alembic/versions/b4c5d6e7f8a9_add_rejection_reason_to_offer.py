"""add_rejection_reason_to_availability_offer

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-04-24 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, Sequence[str], None] = "a3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Optional-Text-Spalte `rejection_reason` auf `availability_offer`.
    Der Dispatcher kann bei Reject eine Begründung eingeben, die in der
    Offerer-Notification und im Detail-View sichtbar wird. Nullable, weil
    Reject auch ohne Begründung zulässig bleibt.
    """
    op.add_column(
        "availability_offer",
        sa.Column(
            "rejection_reason",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("availability_offer", "rejection_reason")