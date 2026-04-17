"""Desktop-API: MaxFairShiftsOfApp-Endpunkte (/api/v1/max-fair-shifts)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/max-fair-shifts", tags=["desktop-max-fair-shifts"])


class BulkCreateBody(BaseModel):
    entries: list[schemas.MaxFairShiftsOfAppCreate]


class BulkCreateResponse(BaseModel):
    ids: list[uuid.UUID]


class BulkDeleteBody(BaseModel):
    ids: list[uuid.UUID]


@router.post("", response_model=schemas.MaxFairShiftsOfAppShow,
             status_code=status.HTTP_201_CREATED)
def create_max_fair_shifts(body: schemas.MaxFairShiftsOfAppCreate, _: DesktopUser):
    return db_services.MaxFairShiftsOfApp.create(body)


@router.post("/bulk", response_model=BulkCreateResponse, status_code=status.HTTP_201_CREATED)
def create_max_fair_shifts_bulk(body: BulkCreateBody, _: DesktopUser):
    ids = db_services.MaxFairShiftsOfApp.create_bulk(body.entries)
    return BulkCreateResponse(ids=ids)


@router.delete("/{mfs_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_max_fair_shifts(mfs_id: uuid.UUID, _: DesktopUser):
    db_services.MaxFairShiftsOfApp.delete(mfs_id)


@router.delete("/bulk", status_code=status.HTTP_204_NO_CONTENT)
def delete_max_fair_shifts_bulk(body: BulkDeleteBody, _: DesktopUser):
    db_services.MaxFairShiftsOfApp.delete_bulk(body.ids)