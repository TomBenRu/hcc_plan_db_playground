"""Desktop-API: Person-Endpunkte (/api/v1/persons)."""

import uuid

from fastapi import APIRouter, Response, status
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


class PendingCombLocCreate(BaseModel):
    temp_id: uuid.UUID
    data: schemas.CombinationLocationsPossibleCreate


class ReplaceCombLocPossiblesBody(BaseModel):
    original_ids: list[uuid.UUID]
    pending_creates: list[PendingCombLocCreate]
    current_combs: list[schemas.CombinationLocationsPossible]


class RestoreCombLocPossiblesBody(BaseModel):
    comb_ids_to_restore: list[uuid.UUID]


class LocationPrefEntry(BaseModel):
    location_id: uuid.UUID
    score: float


class UpdateLocationPrefsBulkBody(BaseModel):
    project_id: uuid.UUID
    entries: list[LocationPrefEntry]


class RestoreLocationPrefsBulkBody(BaseModel):
    pref_ids_to_restore: list[uuid.UUID]


class UpdateAdminOfProjectBody(BaseModel):
    project_id: uuid.UUID


class PersonNotesBody(BaseModel):
    notes: str


@router.post("", response_model=schemas.Person, status_code=status.HTTP_201_CREATED)
def create_person(body: PersonCreateBody, _: DesktopUser):
    return db_services.Person.create(body.person, body.project_id, body.person_id)


@router.put("/{person_id}", response_model=schemas.Person)
def update_person(person_id: uuid.UUID, body: schemas.PersonShow, _: DesktopUser):
    return db_services.Person.update(body)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: uuid.UUID, _: DesktopUser):
    db_services.Person.delete(person_id)


@router.post("/{person_id}/undelete", status_code=status.HTTP_204_NO_CONTENT)
def undelete_person(person_id: uuid.UUID, _: DesktopUser):
    db_services.Person.undelete(person_id)


@router.patch("/{person_id}/notes", status_code=204, response_class=Response)
def update_person_notes(person_id: uuid.UUID, body: PersonNotesBody, _: DesktopUser):
    """204 No Content — Client aktualisiert sein notes-Feld lokal."""
    db_services.Person.update_notes(person_id, body.notes)


@router.patch("/{person_id}/admin-of-project", response_model=schemas.PersonShow)
def update_admin_of_project(person_id: uuid.UUID, body: UpdateAdminOfProjectBody, _: DesktopUser):
    """Macht die Person zum Admin des angegebenen Projekts (Projekt-Seite ersetzt)."""
    return db_services.Person.update_project_of_admin(person_id, body.project_id)


@router.delete("/{person_id}/admin-of-project", response_model=schemas.PersonShow)
def clear_admin_of_project(person_id: uuid.UUID, _: DesktopUser):
    """Entfernt die Admin-Zuordnung der Person (Undo-Gegenstueck)."""
    return db_services.Person.clear_project_of_admin(person_id)


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


# Statische Pfade MUESSEN vor dynamischen {clp_id}/{pref_id}-Routen stehen,
# sonst matcht FastAPI "replace"/"bulk-update" als UUID-Parameter.
@router.post("/{person_id}/comb-loc-possibles/replace",
             response_model=dict[str, list[uuid.UUID]])
def replace_comb_loc_possibles(person_id: uuid.UUID, body: ReplaceCombLocPossiblesBody, _: DesktopUser):
    pending_tuples = [(p.temp_id, p.data) for p in body.pending_creates]
    return db_services.Person.replace_comb_loc_possibles(
        person_id, set(body.original_ids), pending_tuples, body.current_combs,
    )


@router.post("/{person_id}/comb-loc-possibles/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_comb_loc_possibles(person_id: uuid.UUID, body: RestoreCombLocPossiblesBody, _: DesktopUser):
    db_services.Person.restore_comb_loc_possibles(person_id, body.comb_ids_to_restore)


@router.post("/{person_id}/comb-loc-possibles/{clp_id}", response_model=schemas.PersonShow)
def put_in_comb_loc_possible(person_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.put_in_comb_loc_possible(person_id, clp_id)


@router.delete("/{person_id}/comb-loc-possibles/{clp_id}", response_model=schemas.PersonShow)
def remove_comb_loc_possible(person_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_comb_loc_possible(person_id, clp_id)


@router.post("/{person_id}/location-prefs/bulk-update",
             response_model=dict[str, list[uuid.UUID]])
def update_location_prefs_bulk(person_id: uuid.UUID, body: UpdateLocationPrefsBulkBody, _: DesktopUser):
    score_dict = {e.location_id: e.score for e in body.entries}
    return db_services.Person.update_location_prefs_bulk(person_id, body.project_id, score_dict)


@router.post("/{person_id}/location-prefs/bulk-restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_location_prefs_bulk(person_id: uuid.UUID, body: RestoreLocationPrefsBulkBody, _: DesktopUser):
    db_services.Person.restore_location_prefs_bulk(person_id, body.pref_ids_to_restore)


@router.post("/{person_id}/location-prefs/{pref_id}", response_model=schemas.PersonShow)
def put_in_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.put_in_location_pref(person_id, pref_id)


@router.delete("/{person_id}/location-prefs/{pref_id}", response_model=schemas.PersonShow)
def remove_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_location_pref(person_id, pref_id)


@router.post("/{person_id}/partner-location-prefs/{pref_id}", response_model=schemas.PersonShow)
def put_in_partner_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.put_in_partner_location_pref(person_id, pref_id)


@router.delete("/{person_id}/partner-location-prefs/{pref_id}", response_model=schemas.PersonShow)
def remove_partner_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_partner_location_pref(person_id, pref_id)


@router.post("/{person_id}/skills/{skill_id}", response_model=schemas.PersonShow)
def add_skill(person_id: uuid.UUID, skill_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.add_skill(person_id, skill_id)


@router.delete("/{person_id}/skills/{skill_id}", response_model=schemas.PersonShow)
def remove_skill(person_id: uuid.UUID, skill_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_skill(person_id, skill_id)


@router.post("/{person_id}/flags/{flag_id}", response_model=schemas.PersonShow)
def put_in_flag(person_id: uuid.UUID, flag_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.put_in_flag(person_id, flag_id)


@router.delete("/{person_id}/flags/{flag_id}", response_model=schemas.PersonShow)
def remove_flag(person_id: uuid.UUID, flag_id: uuid.UUID, _: DesktopUser):
    return db_services.Person.remove_flag(person_id, flag_id)
