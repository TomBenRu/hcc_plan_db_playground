"""add_availability_offer

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-04-23 14:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    1. Neue Tabelle `availability_offer` + Enum `availabilityofferstatus`.
    2. Postgres: bestehender Enum `inboxmessagetype` um vier Werte erweitert.
    """
    op.create_table(
        "availability_offer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("offerer_web_user_id", sa.Uuid(), nullable=False),
        sa.Column("appointment_id", sa.Uuid(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted_by_dispatcher",
                "rejected_by_dispatcher",
                "withdrawn",
                "superseded_by_cast_change",
                "superseded_by_plan_unbind",
                name="availabilityofferstatus",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["offerer_web_user_id"], ["web_user.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["appointment_id"], ["appointment.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_offer_received'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_offer_accepted'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_offer_rejected'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'availability_offer_withdrawn'"
        )


def downgrade() -> None:
    """Downgrade schema.

    Entfernt die Tabelle + den neuen Enum-Typ. Die vier `inboxmessagetype`-
    Werte bleiben bestehen — PostgreSQL erlaubt kein einfaches Entfernen
    einzelner Enum-Werte ohne vollständigen Typ-Recreate + Table-Cast.
    """
    op.drop_table("availability_offer")
    op.execute("DROP TYPE IF EXISTS availabilityofferstatus")