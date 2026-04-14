"""add_takeover_and_swap_tables

Revision ID: a1b2c3d4e5f6
Revises: 6e9afef81aa1
Create Date: 2026-04-14 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "6e9afef81aa1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "takeover_offer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cancellation_request_id", sa.Uuid(), nullable=False),
        sa.Column("web_user_id", sa.Uuid(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "rejected", name="takeoverofferstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["cancellation_request_id"],
            ["cancellation_request.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["web_user_id"], ["web_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "swap_request",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requester_web_user_id", sa.Uuid(), nullable=False),
        sa.Column("requester_appointment_id", sa.Uuid(), nullable=False),
        sa.Column("target_web_user_id", sa.Uuid(), nullable=False),
        sa.Column("target_appointment_id", sa.Uuid(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted_by_target",
                "rejected_by_target",
                "confirmed_by_dispatcher",
                "rejected_by_dispatcher",
                "withdrawn",
                name="swaprequeststatus",
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["requester_web_user_id"], ["web_user.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["requester_appointment_id"], ["appointment.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_web_user_id"], ["web_user.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_appointment_id"], ["appointment.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("swap_request")
    op.drop_table("takeover_offer")
    op.execute("DROP TYPE IF EXISTS swaprequeststatus")
    op.execute("DROP TYPE IF EXISTS takeoverofferstatus")
