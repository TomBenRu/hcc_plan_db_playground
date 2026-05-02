"""Reminder-Jobs fuer den APScheduler — Phase 1.4.

Job-Function `reminder_job(group_id, kind)` ist als Top-Level-Funktion
deklariert (kein Closure), damit `SQLAlchemyJobStore` sie pickeln und
zwischen Scheduler-Restarts persistieren kann.

**Signatur-Stabilitaet:** Die Argument-Liste `(group_id: UUID, kind: str)`
ist eingefroren. Persistierte Jobs in der DB referenzieren diese Signatur
ueber Pickle — eine Aenderung der Arity oder Reihenfolge wuerde alle
existierenden Jobs beim naechsten Feuern crashen lassen. Erweiterungen
laufen ueber neue `kind`-Werte (`"t14"`, `"final_warning"`, ...), nie
ueber zusaetzliche Parameter.

**Single-Worker-Voraussetzung:** Der `AsyncIOScheduler` wird im
`lifespan` der FastAPI-App in *jedem* Uvicorn-Worker gestartet. Solange
auf Render mit Default = 1 Worker gefahren wird, ist das ok; ein
horizontal skaliertes Setup wuerde Reminder doppeln. TODO Phase 2:
PG-Advisory-Lock, sodass nur ein Lock-Holder `scheduler.start()` aufruft.

Zeitzone: Alle Reminder feuern um 08:00 Europe/Berlin am Stichtag, ueber
`DateTrigger` mit `ZoneInfo`. Sommerzeit unkritisch, weil DateTrigger
absolute Zeitpunkte verwendet.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from apscheduler.triggers.date import DateTrigger

if TYPE_CHECKING:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from database.models import NotificationGroup


logger = logging.getLogger(__name__)


_REMINDER_KINDS: tuple[tuple[int, str], ...] = (
    (7, "t7"),
    (3, "t3"),
    (1, "t1"),
)
_TZ = ZoneInfo("Europe/Berlin")
_FIRE_TIME = time(8, 0)
_MISFIRE_GRACE_SECONDS = 3600


def reminder_job(group_id: uuid.UUID | str, kind: str) -> None:
    """Top-Level-Job-Funktion — wird von APScheduler aus dem JobStore aufgerufen.

    Laedt die SMTP-Config aus der DB, instantiiert den `EmailService` und
    delegiert an `send_availability_reminder(group_id, kind, url_base)`. Beim
    Aufruf aus dem JobStore kommt `group_id` als String zurueck (UUID wird
    re-serialisiert) — wir konvertieren explizit zu UUID.

    `url_base` wird *innerhalb* des Jobs aus den Settings gelesen, nicht als
    Parameter durchgereicht — die persistierte Job-Signatur muss stabil
    bleiben (siehe Modul-Docstring).
    """
    from database.database import get_session
    from email_to_users.service import EmailService
    from web_api.config import get_settings
    from web_api.email.config_loader import load_smtp_config

    if isinstance(group_id, str):
        group_id = uuid.UUID(group_id)

    try:
        with get_session() as session:
            smtp_config = load_smtp_config(session)
    except Exception:
        logger.exception("Reminder-Job: SMTP-Config konnte nicht geladen werden, skip")
        return

    url_base = get_settings().BASE_URL or None

    service = EmailService(smtp_config)
    stats = service.send_availability_reminder(group_id, kind, url_base=url_base)
    logger.info(
        "Reminder-Job %s/%s versendet: success=%d failed=%d skipped=%d",
        group_id, kind, stats.get("success", 0), stats.get("failed", 0),
        stats.get("skipped", 0),
    )


def register_jobs_for_group(
    scheduler: "AsyncIOScheduler",
    group: "NotificationGroup",
) -> None:
    """Registriert (oder ersetzt) die drei Reminder-Jobs fuer eine Gruppe.

    Stabile Job-IDs `reminder:{group.id}:{kind}` mit `replace_existing=True`
    machen die Operation idempotent — bei Deadline-Aenderung einfach
    nochmal aufrufen. Liegt der Stichtag in der Vergangenheit (z.B.
    weil die Gruppe knapp vor Deadline angelegt wurde), greift
    `misfire_grace_time` und der Job feuert beim Scheduler-Tick einmalig
    nach.
    """
    for days, kind in _REMINDER_KINDS:
        run_date = datetime.combine(
            group.deadline - timedelta(days=days), _FIRE_TIME, tzinfo=_TZ,
        )
        scheduler.add_job(
            reminder_job,
            trigger=DateTrigger(run_date=run_date),
            args=[str(group.id), kind],
            id=f"reminder:{group.id}:{kind}",
            replace_existing=True,
            misfire_grace_time=_MISFIRE_GRACE_SECONDS,
            coalesce=True,
            max_instances=1,
        )


def unregister_jobs_for_group(
    scheduler: "AsyncIOScheduler",
    group_id: uuid.UUID,
) -> None:
    """Entfernt alle Reminder-Jobs fuer eine Gruppe — idempotent."""
    for _, kind in _REMINDER_KINDS:
        job_id = f"reminder:{group_id}:{kind}"
        try:
            scheduler.remove_job(job_id, jobstore="default")
        except Exception:
            # remove_job wirft bei nicht-existentem Job — wir ignorieren bewusst.
            logger.debug("Reminder-Job %s nicht entfernt (existiert nicht?)", job_id)


def trigger_catchup(group: "NotificationGroup") -> None:
    """Synchroner Catch-Up-Versand fuer alle Empfaenger einer Gruppe.

    Wird aufgerufen, wenn eine PP nachtraeglich zu einer existierenden
    Gruppe hinzugefuegt wird (siehe Phase 1.5). Nutzt den selben Mailer,
    aber laeuft ohne Scheduler-Persistenz — direkter Funktionsaufruf.
    """
    reminder_job(group.id, "catchup")
