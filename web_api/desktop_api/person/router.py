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


class NewTimeOfDayStandardResponse(BaseModel):
    person: schemas.PersonShow
    old_standard_id: uuid.UUID | None


@router.post("", response_model=schemas.Person, status_code=status.HTTP_201_CREATED)
def create_person(body: PersonCreateBody, _: DesktopUser):
    return db_services.Person.create(body.person, body.project_id, body.person_id)


@router.put("/{person_id}", response_model=schemas.Person)
def update_person(person_id: uuid.UUID, body: schemas.PersonShow, _: DesktopUser):
    return db_services.Person.update(body)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: uuid.UUID, _: DesktopUser):
    db_services.Person.delete(person_id)


@router.post("/{person_id}/time-of-days/{time_of_day_id}", response_model=schemas.PersonShow)
def put_in_time_of_day(person_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.put_in_time_of_day(person_id, time_of_day_id)


@router.delete("/{person_id}/time-of-days/{time_of_day_id}", response_model=schemas.PersonShow)
def remove_in_time_of_day(person_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_in_time_of_day(person_id, time_of_day_id)


@router.post("/{person_id}/time-of-day-standards/{time_of_day_id}",
             response_model=NewTimeOfDayStandardResponse)
def new_time_of_day_standard(person_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    person, old_id = db_services.Person.new_time_of_day_standard(person_id, time_of_day_id)
    return NewTimeOfDayStandardResponse(person=person, old_standard_id=old_id)


@router.delete("/{person_id}/time-of-day-standards/{time_of_day_id}",
               response_model=schemas.PersonShow)
def remove_time_of_day_standard(person_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_time_of_day_standard(person_id, time_of_day_id)
