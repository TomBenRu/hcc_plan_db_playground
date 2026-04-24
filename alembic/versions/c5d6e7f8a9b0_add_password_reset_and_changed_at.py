"""add password_reset_token + web_user.password_changed_at

Revision ID: c5d6e7f8a9b0
Revises: b328fdd08f2b
Create Date: 2026-04-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, Sequence[str], None] = "b328fdd08f2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "web_user",
        sa.Column(
            "password_changed_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.alter_column("web_user", "password_changed_at", server_default=None)

    op.create_table(
        "password_reset_token",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("web_user_id", sa.Uuid(), nullable=False),
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
        "ix_password_reset_token_web_user_id",
        "password_reset_token",
        ["web_user_id"],
    )
    op.create_index(
        "ix_password_reset_token_token_hash",
        "password_reset_token",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_token_token_hash", table_name="password_reset_token"
    )
    op.drop_index(
        "ix_password_reset_token_web_user_id", table_name="password_reset_token"
    )
    op.drop_table("password_reset_token")
    op.drop_column("web_user", "password_changed_at")