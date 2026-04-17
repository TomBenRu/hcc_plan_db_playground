"""Desktop-API-Client: Person-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(person: schemas.PersonCreate, project_id: uuid.UUID,
           person_id: uuid.UUID | None = None) -> schemas.Person:
    data = get_api_client().post("/api/v1/persons", json={
        "project_id": str(project_id),
        "person": person.model_dump(mode="json"),
        "person_id": str(person_id) if person_id else None,
    })
    return schemas.Person.model_validate(data)


def update(person: schemas.PersonShow) -> schemas.Person:
    data = get_api_client().put(f"/api/v1/persons/{person.id}",
                                json=person.model_dump(mode="json"))
    return schemas.Person.model_validate(data)


def delete(person_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/persons/{person_id}")