from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore


def create_scheduler(db_url: str) -> AsyncIOScheduler:
    jobstores = {"default": SQLAlchemyJobStore(url=db_url)}
    return AsyncIOScheduler(jobstores=jobstores)
