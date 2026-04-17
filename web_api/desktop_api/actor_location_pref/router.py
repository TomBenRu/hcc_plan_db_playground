"""Desktop-API: ActorLocationPref-Endpunkte (/api/v1/actor-location-prefs)."""

import uuid

from fastapi import APIRouter, status

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/actor-location-prefs", tags=["desktop-actor-location-prefs"])


@router.post("", response_model=schemas.ActorLocationPrefShow,
             status_code=status.HTTP_201_CREATED)
def create_actor_location_pref(body: schemas.ActorLocationPrefCreate, _: DesktopUser):
    return db_services.ActorLocationPref.create(body)


@router.delete("/{pref_id}", response_model=schemas.ActorLocationPrefShow)
def delete_actor_location_pref(pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorLocationPref.delete(pref_id)


@router.post("/{pref_id}/undelete", response_model=schemas.ActorLocationPrefShow)
def undelete_actor_location_pref(pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorLocationPref.undelete(pref_id)