"""PostgreSQL Advisory-Lock fuer den APScheduler-Singleton.

Hintergrund: APScheduler wird im FastAPI-`lifespan` jedes uvicorn-Workers
gestartet. Bei `--workers >1` (Horizontal-Scaling) wuerde jeder Worker die
persistierten Reminder-Jobs feuern → Doppelversand. Loesung: Vor
`scheduler.start()` einen PG-Advisory-Lock akquirieren; nur der Worker
mit dem Lock startet den Scheduler tatsaechlich.

Wichtige Eigenschaften:
- **Session-Scope**: `pg_try_advisory_lock` ist an die DB-Connection
  gebunden, nicht an Transaktionen. Wir halten daher eine eigene,
  persistente Connection ausserhalb des Request-Pools.
- **Auto-Release bei Connection-Drop**: Wenn die Lock-Connection abreisst
  (PG-Restart, Netzwerkfehler), gibt PG den Lock automatisch frei und ein
  anderer Worker kann ihn beim naechsten Lifespan-Tick uebernehmen. Das
  ist akzeptierter Trade-Off — kurze Doppel-Reminder-Lücken sind besser
  als Komplett-Stillstand.
- **Non-Blocking**: `pg_try_advisory_lock` blockt nicht; Worker ohne Lock
  laeuft als reiner HTTP-Worker weiter.

Lock-ID: 0x48434350 ("HCCP" als ASCII-Hex, 1_212_367_696). Bewusst
ungewoehnliche Konstante, um Kollisionen mit anderen Apps in derselben
Datenbank auszuschliessen.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger(__name__)

# "HCCP" als ASCII-Hex. Reicht in 32 bit, fits in PG bigint.
SCHEDULER_LOCK_ID: int = 0x48434350


@dataclass
class SchedulerLockHandle:
    """Haelt die persistente Connection + Engine, sodass der Lifespan-Code
    sie beim Shutdown sauber freigeben kann."""

    engine: Engine
    connection: Connection
    acquired: bool


def acquire_scheduler_lock(database_url: str) -> SchedulerLockHandle:
    """Versucht den Advisory-Lock zu holen. Gibt einen Handle zurueck;
    `handle.acquired` zeigt an, ob dieser Worker den Scheduler starten darf.

    Auch im Misserfolgsfall wird der Handle zurueckgegeben (mit
    `acquired=False`), damit `release_scheduler_lock` einheitlich gerufen
    werden kann — das vereinfacht den Lifespan-Code.
    """
    engine = create_engine(database_url, pool_pre_ping=True)
    connection = engine.connect()
    try:
        result = connection.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": SCHEDULER_LOCK_ID},
        ).scalar()
        # Implicit Transaction explizit committen, damit der Connection-State
        # sauber ist (Lock selbst ist session-scoped, der commit beeinflusst
        # ihn nicht).
        connection.commit()
        acquired = bool(result)
    except Exception:
        logger.exception("PG-Advisory-Lock-Akquise scheiterte.")
        acquired = False

    if acquired:
        logger.info(
            "PG-Advisory-Lock %s akquiriert — dieser Worker startet den Scheduler.",
            SCHEDULER_LOCK_ID,
        )
    else:
        logger.info(
            "PG-Advisory-Lock %s nicht akquiriert — anderer Worker hält ihn, "
            "Scheduler bleibt in diesem Worker aus.",
            SCHEDULER_LOCK_ID,
        )

    return SchedulerLockHandle(
        engine=engine, connection=connection, acquired=acquired,
    )


def release_scheduler_lock(handle: SchedulerLockHandle) -> None:
    """Gibt den Lock frei (falls gehalten) und schliesst die Connection.
    Idempotent — kann beim Shutdown immer gerufen werden."""
    if handle.acquired:
        try:
            handle.connection.execute(
                text("SELECT pg_advisory_unlock(:lock_id)"),
                {"lock_id": SCHEDULER_LOCK_ID},
            )
            handle.connection.commit()
            logger.info("PG-Advisory-Lock %s freigegeben.", SCHEDULER_LOCK_ID)
        except Exception:
            # Connection ist evtl. tot — kein Drama, PG gibt den Lock dann
            # selber frei sobald die Session geclosed wird.
            logger.exception(
                "PG-Advisory-Lock-Release scheiterte (Connection vermutlich tot)."
            )
    try:
        handle.connection.close()
    except Exception:
        logger.exception("Lock-Connection-Close scheiterte.")
    handle.engine.dispose()
