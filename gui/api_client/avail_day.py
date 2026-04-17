"""Desktop-API-Client: AvailDay-Operationen."""

import datetime
import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(date: datetime.date, actor_plan_period_id: uuid.UUID,
           time_of_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().post("/api/v1/avail-days", json={
        "date": date.isoformat(),
        "actor_plan_period_id": str(actor_plan_period_id),
        "time_of_day_id": str(time_of_day_id),
    })
    return schemas.AvailDayShow.model_validate(data)


def delete(avail_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}")
    return schemas.AvailDayShow.model_validate(data)


def update_time_of_day(avail_day_id: uuid.UUID, time_of_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().patch(f"/api/v1/avail-days/{avail_day_id}/time-of-day",
                                  json={"time_of_day_id": str(time_of_day_id)})
    return schemas.AvailDayShow.model_validate(data)


def update_time_of_days(avail_day_id: uuid.UUID,
                        time_of_days: list[schemas.TimeOfDay]) -> schemas.AvailDayShow:
    data = get_api_client().patch(f"/api/v1/avail-days/{avail_day_id}/time-of-days",
                                  json={"time_of_days": [t.model_dump(mode="json") for t in time_of_days]})
    return schemas.AvailDayShow.model_validate(data)