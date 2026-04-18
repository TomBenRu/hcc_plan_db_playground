"""Desktop-API: EmployeeEvent Category-Endpunkte (/api/v1/employee-event-categories)."""

import uuid

from fastapi import APIRouter, HTTPException, status

from employee_event.db_service import EmployeeEventService
from employee_event.schemas.common_schemas import ErrorResponseSchema, SuccessResponseSchema
from employee_event.schemas.employee_event_schemas import (
    Category, CategoryCreate, CategoryUpdate,
)
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/employee-event-categories",
                   tags=["desktop-employee-event-categories"])


def _check(result):
    if isinstance(result, ErrorResponseSchema):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result.message)
    return result


@router.post("", response_model=Category, status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, _: DesktopUser):
    return _check(EmployeeEventService().create_category(body))


@router.put("/{category_id}", response_model=Category)
def update_category(category_id: uuid.UUID, body: CategoryUpdate, _: DesktopUser):
    return _check(EmployeeEventService().update_category(body))


@router.delete("/{category_id}", response_model=SuccessResponseSchema)
def delete_category(category_id: uuid.UUID, _: DesktopUser):
    return _check(EmployeeEventService().delete_category(category_id, soft_delete=True))


@router.post("/{category_id}/undelete", response_model=SuccessResponseSchema)
def undelete_category(category_id: uuid.UUID, _: DesktopUser):
    return _check(EmployeeEventService().undelete_category(category_id))