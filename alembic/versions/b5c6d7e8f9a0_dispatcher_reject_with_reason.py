"""dispatcher_reject_with_reason

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-05-05 10:00:00.000000

Ergaenzt das Datenmodell fuer Dispatcher-Reject mit Pflicht-Begruendung
fuer Tausch-Anfragen und Uebernahme-Angebote:

  1. `swap_request.rejection_reason` (Optional[str]) — gespeichert wenn
     der Dispatcher mit Begruendung ablehnt. SwapRequestStatus.rejected_by_dispatcher
     existiert bereits, daher keine Enum-Aenderung noetig.

  2. `takeover_offer.rejection_reason` (Optional[str]).

  3. takeoverofferstatus: Recreate-Pattern. `rejected` wird in drei semantisch
     klare Werte aufgesplittet — `withdrawn` (Anbieter zog selbst zurueck),
     `rejected_by_dispatcher` (mit Begruendung) und `superseded` (durch andere
     Annahme oder durch Absage-Rueckzug obsolet, BR-09 + Cancellation-Withdraw).
     Bestehende `rejected`-Datensaetze werden heuristisch gemappt:
        - Schwester `accepted` existiert        → `superseded`
        - Cancellation ist `withdrawn`          → `superseded`
        - sonst                                  → `withdrawn` (best-guess)

     Recreate-Pattern (statt ADD VALUE) ist noetig, weil PG einen frisch
     hinzugefuegten Enum-Wert in derselben Transaktion nicht in einem UPDATE
     verwenden darf, und weil wir den toten `rejected`-Wert komplett
     eliminieren wollen.

  4. inboxmessagetype: ADD VALUE `takeover_offer_rejected` (sicher in
     derselben Transaktion, weil der Wert hier nicht verwendet wird).
"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, Sequence[str], None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_TAKEOVER_VALUES = (
    "pending",
    "accepted",
    "withdrawn",
    "rejected_by_dispatcher",
    "superseded",
    "superseded_by_cast_change",
    "superseded_by_plan_unbind",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.add_column(
        "swap_request",
        sa.Column("rejection_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "takeover_offer",
        sa.Column("rejection_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )

    if dialect == "postgresql":
        # 1) Daten-Mapping VOR dem Type-Recreate, solange `rejected` noch
        #    erlaubter Enum-Wert ist. Wir schreiben in eine temp-Text-Spalte,
        #    damit der ALTER COLUMN ... TYPE neu unten klar definiert ist.
        op.execute(
            """
            ALTER TABLE takeover_offer
            ALTER COLUMN status TYPE TEXT USING status::text
            """
        )

        op.execute(
            """
            UPDATE takeover_offer t
            SET status = 'superseded'
            WHERE status = 'rejected'
              AND EXISTS (
                  SELECT 1 FROM takeover_offer s
                  WHERE s.cancellation_request_id = t.cancellation_request_id
                    AND s.status = 'accepted'
              )
            """
        )
        op.execute(
            """
            UPDATE takeover_offer t
            SET status = 'superseded'
            WHERE status = 'rejected'
              AND EXISTS (
                  SELECT 1 FROM cancellation_request c
                  WHERE c.id = t.cancellation_request_id
                    AND c.status = 'withdrawn'
              )
            """
        )
        op.execute(
            """
            UPDATE takeover_offer
            SET status = 'withdrawn'
            WHERE status = 'rejected'
            """
        )

        # 2) Enum-Recreate: alten Typ raus, neuen mit finaler Werte-Liste rein.
        op.execute("DROP TYPE takeoverofferstatus")
        op.execute(
            "CREATE TYPE takeoverofferstatus AS ENUM ("
            + ", ".join(f"'{v}'" for v in _NEW_TAKEOVER_VALUES)
            + ")"
        )

        op.execute(
            """
            ALTER TABLE takeover_offer
            ALTER COLUMN status TYPE takeoverofferstatus
            USING status::takeoverofferstatus
            """
        )

        # 3) Inbox-Typ ergaenzen — sicher in derselben Tx, weil hier nicht verwendet.
        op.execute(
            "ALTER TYPE inboxmessagetype "
            "ADD VALUE IF NOT EXISTS 'takeover_offer_rejected'"
        )

    else:
        # SQLite: Status-Spalte ist TEXT, Enum-Beschraenkung nur via Python.
        # Datenwerte werden mit den gleichen Heuristiken umgemappt.
        op.execute(
            """
            UPDATE takeover_offer
            SET status = 'superseded'
            WHERE status = 'rejected'
              AND cancellation_request_id IN (
                  SELECT cancellation_request_id FROM takeover_offer
                  WHERE status = 'accepted'
              )
            """
        )
        op.execute(
            """
            UPDATE takeover_offer
            SET status = 'superseded'
            WHERE status = 'rejected'
              AND cancellation_request_id IN (
                  SELECT id FROM cancellation_request WHERE status = 'withdrawn'
              )
            """
        )
        op.execute(
            """
            UPDATE takeover_offer
            SET status = 'withdrawn'
            WHERE status = 'rejected'
            """
        )


def downgrade() -> None:
    """Downgrade schema.

    Setzt die neuen Status-Werte auf `rejected` zurueck (verlustig:
    drei Werte werden auf einen kollabiert) und droppt die rejection_reason-
    Spalten. Inbox-Type-Wert bleibt im Enum, weil PG kein einfaches
    Entfernen von Enum-Werten erlaubt.
    """
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "postgresql":
        op.execute(
            """
            ALTER TABLE takeover_offer
            ALTER COLUMN status TYPE TEXT USING status::text
            """
        )
        op.execute(
            """
            UPDATE takeover_offer
            SET status = 'rejected'
            WHERE status IN ('withdrawn', 'rejected_by_dispatcher', 'superseded')
            """
        )
        op.execute("DROP TYPE takeoverofferstatus")
        op.execute(
            "CREATE TYPE takeoverofferstatus AS ENUM ("
            "'pending', 'accepted', 'rejected', "
            "'superseded_by_cast_change', 'superseded_by_plan_unbind'"
            ")"
        )
        op.execute(
            """
            ALTER TABLE takeover_offer
            ALTER COLUMN status TYPE takeoverofferstatus
            USING status::takeoverofferstatus
            """
        )
    else:
        op.execute(
            """
            UPDATE takeover_offer
            SET status = 'rejected'
            WHERE status IN ('withdrawn', 'rejected_by_dispatcher', 'superseded')
            """
        )

    op.drop_column("takeover_offer", "rejection_reason")
    op.drop_column("swap_request", "rejection_reason")
