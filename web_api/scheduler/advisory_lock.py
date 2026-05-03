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
- **Geister-Connection-Cleanup**: Beim Acquire werden zuerst alle anderen
  Sessions mit `application_name=APPLICATION_NAME` terminiert. Hintergrund:
  Render macht Zero-Downtime-Deploys, der alte Container kann via SIGKILL
  enden ohne sauberen Lifespan-Shutdown. Die TCP-Connection bleibt aus
  PG-Sicht offen (bis `tcp_keepalives_idle` greift, oft 2h+), und damit
  der Lock haengen. Wir raeumen daher bei jedem Start eigene alte
  Sessions ab — Kollateralschaden ausgeschlossen, weil nur die Lock-
  Connections diesen `application_name` setzen (Pool-Connections fuer
  Requests haben den nicht).
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

# Application-Name auf der Lock-Connection. Wir terminieren beim Start
# Geister-Sessions mit DIESEM Namen (s. Modul-Docstring).
APPLICATION_NAME: str = "hcc-plan-scheduler"


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

    Setzt `application_name=APPLICATION_NAME` auf der Connection und
    terminiert vor dem Lock-Versuch alle anderen Sessions mit demselben
    `application_name` (Geister-Connection-Cleanup, s. Modul-Docstring).

    Auch im Misserfolgsfall wird der Handle zurueckgegeben (mit
    `acquired=False`), damit `release_scheduler_lock` einheitlich gerufen
    werden kann — das vereinfacht den Lifespan-Code.
    """
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"application_name": APPLICATION_NAME},
    )
    connection = engine.connect()
    acquired = False
    try:
        # Geister-Sessions desselben app_name terminieren. pg_terminate_backend
        # wirkt async — wir warten hier nicht explizit, weil PG den Lock im
        # selben Moment freigibt, in dem die Session terminiert. Der nachfolgende
        # try_advisory_lock greift typischerweise im selben Roundtrip.
        terminated = connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE application_name = :app_name "
                "  AND pid <> pg_backend_pid()"
            ),
            {"app_name": APPLICATION_NAME},
        ).fetchall()
        if terminated:
            logger.info(
                "Geister-Lock-Sessions terminiert: %d (alte Worker / Deploy-Reste).",
                len(terminated),
            )

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
