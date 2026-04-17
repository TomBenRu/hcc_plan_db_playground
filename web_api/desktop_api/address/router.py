"""Desktop-API: Address-Endpunkte (/api/v1/addresses)."""

import uuid

from fastapi import APIRouter, status

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/addresses", tags=["desktop-addresses"])


@router.post("", response_model=schemas.Address, status_code=status.HTTP_201_CREATED)
def create_address(body: schemas.AddressCreate, _: DesktopUser):
    return db_services.Address.create(body)


@router.put("/{address_id}", response_model=schemas.Address)
def update_address(address_id: uuid.UUID, body: schemas.Address, _: DesktopUser):
    return db_services.Address.update(body)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: uuid.UUID, _: DesktopUser):
    db_services.Address.delete(address_id)


@router.post("/{address_id}/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_address(address_id: uuid.UUID, _: DesktopUser):
    db_services.Address.undelete(address_id)