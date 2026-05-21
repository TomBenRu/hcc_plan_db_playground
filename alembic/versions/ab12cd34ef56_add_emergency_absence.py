"""add emergency_absence workflow

Revision ID: ab12cd34ef56
Revises: f0a1b2c3d4e5
Create Date: 2026-05-20 14:00:00.000000

Erstellt die Schema-Erweiterungen für den Notfall-Absage-Workflow
(emergency_absence). Schema-Änderungen:

1.  Neuer Enum `cancellationkind` (regular, emergency).
2.  Spalte `cancellation_request.kind` mit Default 'regular'.
3.  Drei neue InboxMessageType-Werte (Notfall-Absage Lifecycle).
4.  Neue Tabelle `location_emergency_notification_circle`
    (eigene Whitelist pro Standort; Aktivierung implicit über
    Member-Existenz, kein Boolean-Toggle).
5.  Spalte `person.share_phone_in_emergency` (Privacy-Opt-out für
    Telefonliste in Bestätigungsmail). Default `true` für Bestandsdaten.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ab12cd34ef56"
down_revision: Union[str, Sequence[str], None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1) CancellationKind-Enum + 2) Spalte cancellation_request.kind
    if bind.dialect.name == "postgresql":
        op.execute("CREATE TYPE cancellationkind AS ENUM ('regular', 'emergency')")
        op.add_column(
            "cancellation_request",
            sa.Column(
                "kind",
                sa.Enum("regular", "emergency", name="cancellationkind", create_type=False),
                nullable=False,
                server_default="regular",
            ),
        )
    else:
        # SQLite-Fallback (lokale Dev): Enum als CHECK-Constraint serialisiert
        op.add_column(
            "cancellation_request",
            sa.Column(
                "kind",
                sa.Enum("regular", "emergency", name="cancellationkind"),
                nullable=False,
                server_default="regular",
            ),
        )

    # 3) InboxMessageType-Enum um 3 Werte erweitern
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'emergency_absence_new'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'emergency_absence_takeover_accepted'"
        )
        op.execute(
            "ALTER TYPE inboxmessagetype ADD VALUE IF NOT EXISTS 'emergency_absence_resolved'"
        )

    # 4) Neue Whitelist-Tabelle (Spiegel von location_notification_circle)
    op.create_table(
        "location_emergency_notification_circle",
        sa.Column("location_of_work_id", sa.Uuid(), nullable=False),
        sa.Column("web_user_id", sa.Uuid(), nullable=False),
        sa.Column("added_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["added_by_id"], ["web_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["location_of_work_id"], ["location_of_work.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["web_user_id"], ["web_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("location_of_work_id", "web_user_id"),
    )

    # 5) Privacy-Opt-out: Person.share_phone_in_emergency
    op.add_column(
        "person",
        sa.Column(
            "share_phone_in_emergency",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("person", "share_phone_in_emergency")
    op.drop_table("location_emergency_notification_circle")
    # Enum-Werte können in Postgres nicht entfernt werden — bewusst No-Op
    # (Wer einen vollständigen Rollback braucht: Enum-Recreate + Table-Cast,
    # siehe c7d8e9f0a1b2_add_swap_withdrawn_inbox_type.py).
    op.drop_column("cancellation_request", "kind")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS cancellationkind")
