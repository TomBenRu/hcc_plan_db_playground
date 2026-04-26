"""backfill_plan_period_closed

Backfill für PlanPeriod.closed: alle PlanPerioden mit end<today() und einem
existierenden binding-Plan werden auf closed=TRUE gesetzt. Damit erhält der
neue closed-Lifecycle (vergibt Schreibschutz für PP-Strukturmutationen) den
korrekten Anfangszustand für historische Daten.

Reine Daten-Migration — keine Schema-Änderung. Das Feld `closed` existiert
seit Initial-Schema (models.py:786, default=False).

Revision ID: ea8ed809d887
Revises: d6e7f8a9b0c1
Create Date: 2026-04-26 16:45:35.551844

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ea8ed809d887'
down_revision: Union[str, Sequence[str], None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Setze closed=TRUE auf historischen abgeschlossenen Perioden."""
    op.execute(
        """
        UPDATE plan_period AS pp
        SET closed = TRUE
        WHERE closed = FALSE
          AND pp.end < CURRENT_DATE
          AND EXISTS (
              SELECT 1 FROM plan p
              WHERE p.plan_period_id = pp.id
                AND p.is_binding = TRUE
          )
        """
    )


def downgrade() -> None:
    """No-op: wir können nicht wissen, welche Zeilen durch Upgrade gesetzt wurden.

    Falls ein Rollback nötig wäre, müsste der Operateur manuell die betroffenen
    Perioden auf closed=FALSE zurücksetzen — z. B. via:
        UPDATE plan_period SET closed = FALSE WHERE end < CURRENT_DATE;
    """
    pass
