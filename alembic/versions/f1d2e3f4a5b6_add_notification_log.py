"""add_notification_log

Phase 1.1: Audit-/Idempotenz-Tabelle fuer den Reminder-Versand. Pro
versendeter Mail eine Zeile mit (group_id, person_id, kind, sent_at,
success, error_detail). Vor jedem Versand liest der Mailer, ob fuer
`(group_id, person_id, kind)` heute bereits ein erfolgreicher Eintrag
existiert — sonst skip.

`kind` ist VARCHAR(32) (kein DB-Enum), weil neue Stufen (T-14,
final_warning) ohne weitere Migration ergaenzbar sein sollen.

Revision ID: f1d2e3f4a5b6
Revises: f0c1d2e3f4a5
Create Date: 2026-05-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'f1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'f0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_detail', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('notification_group_id', sa.Uuid(), nullable=False),
        sa.Column('person_id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ['notification_group_id'], ['notification_group.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['person_id'], ['person.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_log_kind', 'notification_log', ['kind'])
    op.create_index(
        'idx_notification_log_group_kind',
        'notification_log',
        ['notification_group_id', 'kind'],
    )
    op.create_index(
        'idx_notification_log_person_sent',
        'notification_log',
        ['person_id', 'sent_at'],
    )


def downgrade() -> None:
    op.drop_index('idx_notification_log_person_sent', table_name='notification_log')
    op.drop_index('idx_notification_log_group_kind', table_name='notification_log')
    op.drop_index('ix_notification_log_kind', table_name='notification_log')
    op.drop_table('notification_log')
