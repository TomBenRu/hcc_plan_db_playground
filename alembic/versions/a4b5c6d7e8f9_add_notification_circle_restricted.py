"""add_notification_circle_restricted

Revision ID: a4b5c6d7e8f9
Revises: f3e4f5a6b7c8
Create Date: 2026-05-03 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, Sequence[str], None] = "f3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Fuegt das Modus-Bit fuer den Notification-Circle pro Arbeitsort hinzu.

    `False` (Default) = heutige Auto-Kreis-Logik unveraendert.
    `True`            = Tabelle `location_notification_circle` wird als
                        Whitelist interpretiert; Endergebnis ist
                        Auto-Kreis ∩ Whitelist.
    """
    op.add_column(
        "location_of_work",
        sa.Column(
            "notification_circle_restricted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column(
        "location_of_work",
        "notification_circle_restricted",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("location_of_work", "notification_circle_restricted")
