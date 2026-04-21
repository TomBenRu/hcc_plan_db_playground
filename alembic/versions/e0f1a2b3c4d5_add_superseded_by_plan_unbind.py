"""add_superseded_by_plan_unbind_enum_values

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-04-20 20:00:00.000000

Ergänzt Enum-Werte für PRD Punkt 10: Plan wird auf nicht-verbindlich
gesetzt → offene Requests im Plan obsolet. Wird von
web_api/plan_adjustment/service.py gesetzt.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0f1a2b3c4d5"
down_revision: Union[str, Sequence[str], None] = "d9e0f1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE cancellationstatus "
            "ADD VALUE IF NOT EXISTS 'superseded_by_plan_unbind'"
        )
        op.execute(
            "ALTER TYPE takeoverofferstatus "
            "ADD VALUE IF NOT EXISTS 'superseded_by_plan_unbind'"
        )
        op.execute(
            "ALTER TYPE swaprequeststatus "
            "ADD VALUE IF NOT EXISTS 'superseded_by_plan_unbind'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype "
            "ADD VALUE IF NOT EXISTS 'plan_unbound'"
        )


def downgrade() -> None:
    """Downgrade schema.

    PostgreSQL erlaubt kein einfaches Entfernen einzelner Enum-Werte.
    Der Downgrade ist bewusst ein No-Op.
    """
    pass