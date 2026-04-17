"""Desktop-API-Client: LocationPlanPeriod-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(plan_period_id: uuid.UUID, location_id: uuid.UUID,
           location_plan_period_id: uuid.UUID | None = None) -> schemas.LocationPlanPeriodShow:
    data = get_api_client().post("/api/v1/location-plan-periods", json={
        "plan_period_id": str(plan_period_id),
        "location_id": str(location_id),
        "location_plan_period_id": str(location_plan_period_id) if location_plan_period_id else None,
    })
    return schemas.LocationPlanPeriodShow.model_validate(data)


def delete(lpp_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/location-plan-periods/{lpp_id}")


def update_notes(lpp_id: uuid.UUID, notes: str) -> schemas.LocationPlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/location-plan-periods/{lpp_id}/notes",
                                  json={"notes": notes})
    return schemas.LocationPlanPeriodShow.model_validate(data)


def update_fixed_cast(lpp_id: uuid.UUID, fixed_cast: str,
                      fixed_cast_only_if_available: bool) -> schemas.LocationPlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/location-plan-periods/{lpp_id}/fixed-cast", json={
        "fixed_cast": fixed_cast,
        "fixed_cast_only_if_available": fixed_cast_only_if_available,
    })
    return schemas.LocationPlanPeriodShow.model_validate(data)


def update_num_actors(lpp_id: uuid.UUID, num_actors: int) -> schemas.LocationPlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/location-plan-periods/{lpp_id}/num-actors",
                                  json={"num_actors": num_actors})
    return schemas.LocationPlanPeriodShow.model_validate(data)