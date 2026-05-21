"""add swap_deadline_hours to project_settings + team_notification_settings

Revision ID: cd34ef56ab78
Revises: ab12cd34ef56
Create Date: 2026-05-21 18:00:00.000000

Eigene Tausch-Frist analog zur Absagefrist:

1.  `project_settings.swap_deadline_hours INT NOT NULL DEFAULT 48` —
    projektweiter Default, identisch zur Absagefrist-Logik.
2.  `team_notification_settings.swap_deadline_hours INT NULL` —
    optionaler Team-Override (NULL = erbt von ProjectSettings).

Bestandsdaten bekommen den Default 48 (entspricht dem bisherigen Verhalten,
das die Cancellation-Frist als implizite Tausch-Frist mitnutzte).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd34ef56ab78"
down_revision: Union[str, Sequence[str], None] = "ab12cd34ef56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_settings",
        sa.Column(
            "swap_deadline_hours",
            sa.Integer(),
            nullable=False,
            server_default="48",
        ),
    )
    op.add_column(
        "team_notification_settings",
        sa.Column(
            "swap_deadline_hours",
            sa.Integer(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("team_notification_settings", "swap_deadline_hours")
    op.drop_column("project_settings", "swap_deadline_hours")