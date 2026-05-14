"""add viewer role to webuserrole enum

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
Create Date: 2026-05-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "e9f0a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Erweitert das webuserrole-Enum um den Wert 'viewer'."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE webuserrole ADD VALUE IF NOT EXISTS 'viewer'"
        )


def downgrade() -> None:
    """Downgrade als No-Op.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte.
    Ein vollstaendiger Rollback wuerde Type-Recreate + Table-Cast verlangen.
    """
    pass