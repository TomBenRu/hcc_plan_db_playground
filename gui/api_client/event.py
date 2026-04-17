"""Desktop-API-Client: Event-Operationen."""

import datetime
import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(date: datetime.date, location_plan_period_id: uuid.UUID,
           time_of_day_id: uuid.UUID) -> schemas.EventShow:
    data = get_api_client().post("/api/v1/events", json={
        "location_plan_period_id": str(location_plan_period_id),
        "date": date.isoformat(),
        "time_of_day_id": str(time_of_day_id),
    })
    return schemas.EventShow.model_validate(data)


def delete(event_id: uuid.UUID) -> schemas.EventShow:
    data = get_api_client().delete(f"/api/v1/events/{event_id}")
    return schemas.EventShow.model_validate(data)


def update_time_of_day_and_date(event_id: uuid.UUID, time_of_day_id: uuid.UUID,
                                 date: datetime.date | None = None) -> None:
    get_api_client().patch(f"/api/v1/events/{event_id}/time-of-day-date", json={
        "time_of_day_id": str(time_of_day_id),
        "date": date.isoformat() if date else None,
    })


def update_notes(event_id: uuid.UUID, notes: str) -> None:
    get_api_client().patch(f"/api/v1/events/{event_id}/notes", json={"notes": notes})


def update_time_of_days(event_id: uuid.UUID,
                        time_of_days: list[schemas.TimeOfDay]) -> schemas.EventShow:
    data = get_api_client().patch(f"/api/v1/events/{event_id}/time-of-days",
                                  json={"time_of_days": [t.model_dump(mode="json") for t in time_of_days]})
    return schemas.EventShow.model_validate(data)


def put_in_flag(event_id: uuid.UUID, flag_id: uuid.UUID) -> schemas.EventShow:
    data = get_api_client().post(f"/api/v1/events/{event_id}/flags/{flag_id}")
    return schemas.EventShow.model_validate(data)


def remove_flag(event_id: uuid.UUID, flag_id: uuid.UUID) -> schemas.EventShow:
    data = get_api_client().delete(f"/api/v1/events/{event_id}/flags/{flag_id}")
    return schemas.EventShow.model_validate(data)


def add_skill_group(event_id: uuid.UUID, skill_group_id: uuid.UUID) -> schemas.EventShow:
    data = get_api_client().post(f"/api/v1/events/{event_id}/skill-groups/{skill_group_id}")
    return schemas.EventShow.model_validate(data)


def remove_skill_group(event_id: uuid.UUID, skill_group_id: uuid.UUID) -> schemas.EventShow:
    data = get_api_client().delete(f"/api/v1/events/{event_id}/skill-groups/{skill_group_id}")
    return schemas.EventShow.model_validate(data)