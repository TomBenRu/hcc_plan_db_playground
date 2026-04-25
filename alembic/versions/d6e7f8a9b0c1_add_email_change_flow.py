"""add email_change_token + web_user.pending_email

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-04-25 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, Sequence[str], None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "web_user",
        sa.Column(
            "pending_email",
            sqlmodel.sql.sqltypes.AutoString(length=254),
            nullable=True,
        ),
    )

    op.create_table(
        "email_change_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("web_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "target_email",
            sqlmodel.sql.sqltypes.AutoString(length=254),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sqlmodel.sql.sqltypes.AutoString(length=64),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["web_user_id"], ["web_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_email_change_token_web_user_id",
        "email_change_token",
        ["web_user_id"],
    )
    op.create_index(
        "ix_email_change_token_token_hash",
        "email_change_token",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_change_token_token_hash", table_name="email_change_token"
    )
    op.drop_index(
        "ix_email_change_token_web_user_id", table_name="email_change_token"
    )
    op.drop_table("email_change_token")
    op.drop_column("web_user", "pending_email")