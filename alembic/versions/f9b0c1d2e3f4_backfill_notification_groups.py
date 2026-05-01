"""backfill_notification_groups

Phase 0 (Daten): legt fuer jede existierende PlanPeriod eine 1er-Notification-
Group an, traegt sie in `plan_period.notification_group_id` ein und macht die
Spalte anschliessend NOT NULL.

Strategie: Python-Loop (kein CTE), weil PG die Reihenfolge von Side-Effects in
Multi-Statement-CTEs nicht garantiert (https://www.postgresql.org/docs/current/queries-with.html).
Bei < 10k PPs in Production unproblematisch.

Mit dem Insert kopiert die Migration `team_id` und `deadline` aus der jeweiligen
PlanPeriod direkt in die neue Group, sodass `pp.deadline == pp.notification_group.deadline`
nach Migration garantiert ist (dual-write-Invariante in Phase 0).

Revision ID: f9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-05-01

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b0c1d2e3f4'
down_revision: Union[str, Sequence[str], None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Pro existierender PP eine 1er-Group anlegen + verknuepfen, dann NOT NULL."""
    conn = op.get_bind()
    pps = list(conn.execute(
        sa.text("SELECT id, team_id, deadline FROM plan_period")
    ))

    for pp_id, team_id, deadline in pps:
        new_group_id = uuid.uuid4()
        conn.execute(
            sa.text(
                """
                INSERT INTO notification_group (id, team_id, deadline, name, created_at)
                VALUES (:gid, :tid, :dl, NULL, now())
                """
            ),
            {"gid": new_group_id, "tid": team_id, "dl": deadline},
        )
        conn.execute(
            sa.text(
                "UPDATE plan_period SET notification_group_id = :gid WHERE id = :pid"
            ),
            {"gid": new_group_id, "pid": pp_id},
        )

    # Spalte auf NOT NULL setzen — alle existierenden Zeilen sind jetzt verknuepft.
    op.alter_column('plan_period', 'notification_group_id', nullable=False)


def downgrade() -> None:
    """Spalte wieder nullable + alle Werte ausnullen + Gruppen entfernen.

    Hartloeschen aller Gruppen-Zeilen (kein Erkennungsmerkmal "wurde von dieser
    Migration angelegt vs. spaeter manuell" — in Phase 0 ist das aber sauber,
    weil noch kein anderer Code Gruppen anlegt). Nach Phase 0.5/0.9 ist ein
    Downgrade aufwendiger; daher empfiehlt sich vor jedem Phase-Wechsel ein
    Snapshot.
    """
    op.alter_column('plan_period', 'notification_group_id', nullable=True)
    op.execute("UPDATE plan_period SET notification_group_id = NULL")
    op.execute("DELETE FROM notification_group")
