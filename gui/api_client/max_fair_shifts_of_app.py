"""Desktop-API-Client: MaxFairShiftsOfApp-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(entry: schemas.MaxFairShiftsOfAppCreate) -> schemas.MaxFairShiftsOfAppShow:
    data = get_api_client().post("/api/v1/max-fair-shifts",
                                 json=entry.model_dump(mode="json"))
    return schemas.MaxFairShiftsOfAppShow.model_validate(data)


def create_bulk(entries: list[schemas.MaxFairShiftsOfAppCreate]) -> list[uuid.UUID]:
    data = get_api_client().post("/api/v1/max-fair-shifts/bulk", json={
        "entries": [e.model_dump(mode="json") for e in entries],
    })
    return [uuid.UUID(i) for i in data["ids"]]


def delete(mfs_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/max-fair-shifts/{mfs_id}")


def delete_bulk(ids: list[uuid.UUID]) -> None:
    get_api_client().delete("/api/v1/max-fair-shifts/bulk",
                            json={"ids": [str(i) for i in ids]})