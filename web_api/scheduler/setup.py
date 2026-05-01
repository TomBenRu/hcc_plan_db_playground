from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore


# Modul-globaler Scheduler — wird im FastAPI-`lifespan` ueber create_scheduler()
# gesetzt und via get_scheduler() von db_services-Hooks erreicht. None solange
# `lifespan` nicht durchgelaufen ist (z.B. Desktop-Run, oder vor App-Start).
_scheduler: AsyncIOScheduler | None = None


def create_scheduler(db_url: str) -> AsyncIOScheduler:
    global _scheduler
    jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
    _scheduler = AsyncIOScheduler(jobstores=jobstores)
    return _scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    """Liefert den prozesslokalen Scheduler — None wenn nicht initialisiert.

    Hooks in `db_services/plan_period.py` rufen das auf; bei `None` (Desktop-
    Run, Tests ohne lifespan) wird die Job-Registrierung still uebersprungen.
    """
    return _scheduler
