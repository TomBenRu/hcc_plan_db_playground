"""Desktop-API: Person-Endpunkte (/api/v1/persons)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/persons", tags=["desktop-persons"])


class PersonCreateBody(BaseModel):
    project_id: uuid.UUID
    person: schemas.PersonCreate
    person_id: uuid.UUID | None = None


@router.post("", response_model=schemas.Person, status_code=status.HTTP_201_CREATED)
def create_person(body: PersonCreateBody, _: DesktopUser):
    return db_services.Person.create(body.person, body.project_id, body.person_id)


@router.put("/{person_id}", response_model=schemas.Person)
def update_person(person_id: uuid.UUID, body: schemas.PersonShow, _: DesktopUser):
    return db_services.Person.update(body)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: uuid.UUID, _: DesktopUser):
    db_services.Person.delete(person_id)
