"""Desktop-API-Client: Address-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(address: schemas.AddressCreate) -> schemas.Address:
    data = get_api_client().post("/api/v1/addresses",
                                 json=address.model_dump(mode="json"))
    return schemas.Address.model_validate(data)


def update(address: schemas.Address) -> schemas.Address:
    data = get_api_client().put(f"/api/v1/addresses/{address.id}",
                                json=address.model_dump(mode="json"))
    return schemas.Address.model_validate(data)


def delete(address_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/addresses/{address_id}")


def undelete(address_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/addresses/{address_id}/undelete")