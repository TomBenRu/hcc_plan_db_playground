"""Desktop-API-Client: EmployeeEvent-Category-Operationen."""

import uuid

from employee_event.schemas.common_schemas import SuccessResponseSchema
from employee_event.schemas.employee_event_schemas import (
    Category, CategoryCreate, CategoryUpdate,
)
from gui.api_client.client import get_api_client


def create(category: CategoryCreate) -> Category:
    data = get_api_client().post("/api/v1/employee-event-categories",
                                 json=category.model_dump(mode="json"))
    return Category.model_validate(data)


def update(category: CategoryUpdate) -> Category:
    data = get_api_client().put(f"/api/v1/employee-event-categories/{category.id}",
                                json=category.model_dump(mode="json"))
    return Category.model_validate(data)


def delete(category_id: uuid.UUID) -> SuccessResponseSchema:
    data = get_api_client().delete(f"/api/v1/employee-event-categories/{category_id}")
    return SuccessResponseSchema.model_validate(data)


def undelete(category_id: uuid.UUID) -> SuccessResponseSchema:
    data = get_api_client().post(f"/api/v1/employee-event-categories/{category_id}/undelete")
    return SuccessResponseSchema.model_validate(data)