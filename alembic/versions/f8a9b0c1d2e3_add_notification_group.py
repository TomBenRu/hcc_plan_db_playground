"""add_notification_group

Phase 0 (Schema): legt die Tabelle `notification_group` an und ergaenzt
`plan_period.notification_group_id` als zunaechst nullable Spalte. Der Backfill
mit 1er-Gruppen pro existierender PP und das anschliessende NOT-NULL-Setzen
erfolgen in der nachgelagerten Migration `f9b0c1d2e3f4_backfill_notification_groups`.

Hintergrund: Reminder-Stufen (T-7/T-3/T-1) werden nicht pro PlanPeriod, sondern
pro Notification-Group versendet. Mehrere PPs koennen sich eine gemeinsame
Deadline und damit einen gemeinsamen Reminder-Schedule teilen, damit Empfaenger
nicht je PP eine eigene Mail bekommen. Im Default-Fall ist jede Gruppe eine
1er-Gruppe (auto-erzeugt beim PP-Insert).

Revision ID: f8a9b0c1d2e3
Revises: 4e3571332c12
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, Sequence[str], None] = '4e3571332c12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tabelle anlegen + nullable FK auf plan_period."""
    op.create_table(
        'notification_group',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('team_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['team.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_notification_group_team_deadline',
        'notification_group',
        ['team_id', 'deadline'],
    )

    # Spalte zunaechst nullable; die Backfill-Migration macht sie NOT NULL,
    # nachdem fuer jede existierende PP eine 1er-Gruppe gesetzt ist.
    op.add_column(
        'plan_period',
        sa.Column('notification_group_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        'fk_plan_period_notification_group_id',
        'plan_period', 'notification_group',
        ['notification_group_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_plan_period_notification_group_id',
        'plan_period',
        type_='foreignkey',
    )
    op.drop_column('plan_period', 'notification_group_id')
    op.drop_index('idx_notification_group_team_deadline', table_name='notification_group')
    op.drop_table('notification_group')
