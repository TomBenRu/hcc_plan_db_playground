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


def put_in_time_of_day(person_id: uuid.UUID, time_of_day_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/time-of-days/{time_of_day_id}")
    return schemas.PersonShow.model_validate(data)


def remove_in_time_of_day(person_id: uuid.UUID, time_of_day_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/time-of-days/{time_of_day_id}")
    return schemas.PersonShow.model_validate(data)


def new_time_of_day_standard(person_id: uuid.UUID,
                              time_of_day_id: uuid.UUID) -> tuple[schemas.PersonShow, uuid.UUID | None]:
    data = get_api_client().post(
        f"/api/v1/persons/{person_id}/time-of-day-standards/{time_of_day_id}")
    old_id = uuid.UUID(data["old_standard_id"]) if data["old_standard_id"] else None
    return schemas.PersonShow.model_validate(data["person"]), old_id


def remove_time_of_day_standard(person_id: uuid.UUID,
                                 time_of_day_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(
        f"/api/v1/persons/{person_id}/time-of-day-standards/{time_of_day_id}")
    return schemas.PersonShow.model_validate(data)