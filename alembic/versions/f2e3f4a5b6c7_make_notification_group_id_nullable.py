"""make_notification_group_id_nullable

Phase A der Notification-Groups-Verwaltungs-View: trennt PlanPeriod und
NotificationGroup konzeptionell. PPs sollen ohne Reminder-Group existieren
koennen — der Default beim PP-Insert wird kein Auto-1er-Group mehr sein,
und Dispatcher koennen PPs in der NG-View aktiv aus einer Group entfernen.

Migration ist non-destruktiv: bestehende PPs behalten ihre Group-Verknuepfung,
weil die Spalte nur ihre NOT-NULL-Constraint verliert. Bestehende Reminder-
Jobs feuern unveraendert weiter.

Revision ID: f2e3f4a5b6c7
Revises: f1d2e3f4a5b6
Create Date: 2026-05-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2e3f4a5b6c7'
down_revision: Union[str, Sequence[str], None] = 'f1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """notification_group_id darf NULL sein (PP ohne Reminder-Group)."""
    op.alter_column('plan_period', 'notification_group_id', nullable=True)


def downgrade() -> None:
    """Re-add NOT NULL — nur sicher, wenn keine NULL-Werte existieren.

    Wenn nach dem Phase-A-Deploy bereits PPs ohne Group angelegt wurden
    (Web-Pfad mit `deadline=None`), schlaegt dieses Downgrade mit einer
    klaren Fehlermeldung fehl. Recovery: vor dem Downgrade entweder die
    NULL-PPs einer Group zuordnen oder loeschen.
    """
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text(
            "SELECT count(*) FROM plan_period WHERE notification_group_id IS NULL"
        )
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            f"Downgrade blocked: {null_count} plan_period rows have NULL "
            "notification_group_id. Assign them to a group or delete the "
            "rows before downgrading."
        )
    op.alter_column('plan_period', 'notification_group_id', nullable=False)
