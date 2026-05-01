"""drop_plan_period_deadline

Phase 0.9: Entfernt die jetzt redundante `plan_period.deadline`-Spalte.
Authoritative Quelle ist seit Phase 0.5 die `notification_group.deadline`,
gelesen ueber das ORM-Property `PlanPeriod.effective_deadline` und in
Pydantic-Schemas via `validation_alias='effective_deadline'`.

Voraussetzung: Phase-0.5-Code ist deployed (Service-Layer schreibt nicht
mehr in `pp.deadline`, Caller lesen ueber `effective_deadline`). Wenn ein
alter Worker ohne Phase-0.5-Code laeuft, scheitern dessen INSERTs/UPDATEs
auf `plan_period`, weil sie `deadline` setzen wollen, das nicht mehr
existiert. Daher: Phase 0.5 muss vor Phase 0.9 in Production baken.

Downgrade: Spalte als nullable wieder anlegen, aus `notification_group`
backfillen, dann NOT NULL — exakt der Weg, der in den Phase-0-Migrationen
beschritten wurde, nur in umgekehrter Richtung. Falls die Gruppen
zwischenzeitlich Mehrfach-PPs enthalten, bekommt jede PP weiterhin den
Group-Wert (das ist nach dual-write-Aufgabe in Phase 0.9 nicht mehr
unter unserer Kontrolle, aber semantisch korrekt).

Revision ID: f0c1d2e3f4a5
Revises: f9b0c1d2e3f4
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f0c1d2e3f4a5'
down_revision: Union[str, Sequence[str], None] = 'f9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Spalte droppen — Authority liegt seit Phase 0.5 auf notification_group.deadline."""
    op.drop_column('plan_period', 'deadline')


def downgrade() -> None:
    """Spalte als nullable wieder anlegen, aus notification_group backfillen, NOT NULL."""
    op.add_column(
        'plan_period',
        sa.Column('deadline', sa.Date(), nullable=True),
    )
    op.execute(
        """
        UPDATE plan_period AS pp
        SET deadline = ng.deadline
        FROM notification_group AS ng
        WHERE pp.notification_group_id = ng.id
        """
    )
    op.alter_column('plan_period', 'deadline', nullable=False)
