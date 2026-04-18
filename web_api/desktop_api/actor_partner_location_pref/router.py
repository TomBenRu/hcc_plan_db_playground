"""Desktop-API: ActorPartnerLocationPref-Endpunkte (/api/v1/actor-partner-location-prefs)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/actor-partner-location-prefs",
                   tags=["desktop-actor-partner-location-prefs"])


class NewPref(BaseModel):
    partner_id: uuid.UUID
    location_id: uuid.UUID
    score: float


class ReplaceAllForModelBody(BaseModel):
    model_class_name: str
    model_id: uuid.UUID
    person_id: uuid.UUID
    new_prefs: list[NewPref]


class ReplaceAllForModelResponse(BaseModel):
    created_ids: list[uuid.UUID]
    old_apl_ids: list[uuid.UUID]


class UndoReplaceAllForModelBody(BaseModel):
    model_class_name: str
    model_id: uuid.UUID
    created_ids: list[uuid.UUID]
    old_apl_ids: list[uuid.UUID]


class ReplaceAllForAvailDaysBody(BaseModel):
    avail_day_ids: list[uuid.UUID]
    person_id: uuid.UUID
    new_prefs: list[NewPref]


class ReplaceAllForAvailDaysResponse(BaseModel):
    created_ids: list[uuid.UUID]
    old_pref_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]


class UndoReplaceAllForAvailDaysBody(BaseModel):
    avail_day_ids: list[uuid.UUID]
    created_ids: list[uuid.UUID]
    old_pref_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]


@router.post("", response_model=schemas.ActorPartnerLocationPrefShow,
             status_code=status.HTTP_201_CREATED)
def create_pref(body: schemas.ActorPartnerLocationPrefCreate, _: DesktopUser):
    return db_services.ActorPartnerLocationPref.create(body)


@router.patch("/{pref_id}", response_model=schemas.ActorPartnerLocationPrefShow)
def modify_pref(pref_id: uuid.UUID, body: schemas.ActorPartnerLocationPrefShow, _: DesktopUser):
    return db_services.ActorPartnerLocationPref.modify(body)


@router.delete("/{pref_id}", response_model=schemas.ActorPartnerLocationPrefShow)
def delete_pref(pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPartnerLocationPref.delete(pref_id)


@router.post("/{pref_id}/undelete", response_model=schemas.ActorPartnerLocationPrefShow)
def undelete_pref(pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPartnerLocationPref.undelete(pref_id)


@router.post("/replace-all-for-model", response_model=ReplaceAllForModelResponse)
def replace_all_for_model(body: ReplaceAllForModelBody, _: DesktopUser):
    new_prefs_tuples = [(p.partner_id, p.location_id, p.score) for p in body.new_prefs]
    created_ids, old_apl_ids = db_services.ActorPartnerLocationPref.replace_all_for_model(
        body.model_class_name, body.model_id, body.person_id, new_prefs_tuples,
    )
    return ReplaceAllForModelResponse(created_ids=created_ids, old_apl_ids=old_apl_ids)


@router.post("/undo-replace-all-for-model", status_code=status.HTTP_204_NO_CONTENT)
def undo_replace_all_for_model(body: UndoReplaceAllForModelBody, _: DesktopUser):
    db_services.ActorPartnerLocationPref.undo_replace_all_for_model(
        body.model_class_name, body.model_id, body.created_ids, body.old_apl_ids,
    )


@router.post("/replace-all-for-avail-days", response_model=ReplaceAllForAvailDaysResponse)
def replace_all_for_avail_days(body: ReplaceAllForAvailDaysBody, _: DesktopUser):
    new_prefs_tuples = [(p.partner_id, p.location_id, p.score) for p in body.new_prefs]
    created_ids, old_pref_ids_per_avail_day = \
        db_services.ActorPartnerLocationPref.replace_all_for_avail_days(
            body.avail_day_ids, body.person_id, new_prefs_tuples,
        )
    return ReplaceAllForAvailDaysResponse(
        created_ids=created_ids, old_pref_ids_per_avail_day=old_pref_ids_per_avail_day,
    )


@router.post("/undo-replace-all-for-avail-days", status_code=status.HTTP_204_NO_CONTENT)
def undo_replace_all_for_avail_days(body: UndoReplaceAllForAvailDaysBody, _: DesktopUser):
    db_services.ActorPartnerLocationPref.undo_replace_all_for_avail_days(
        body.avail_day_ids, body.created_ids, body.old_pref_ids_per_avail_day,
    )


@router.post("/delete-unused-for-person/{person_id}", response_model=list[uuid.UUID])
def delete_unused(person_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPartnerLocationPref.delete_unused(person_id)