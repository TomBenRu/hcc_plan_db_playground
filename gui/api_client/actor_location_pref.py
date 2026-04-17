"""Desktop-API-Client: ActorLocationPref-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(pref: schemas.ActorLocationPrefCreate) -> schemas.ActorLocationPrefShow:
    data = get_api_client().post("/api/v1/actor-location-prefs",
                                 json=pref.model_dump(mode="json"))
    return schemas.ActorLocationPrefShow.model_validate(data)


def delete(pref_id: uuid.UUID) -> schemas.ActorLocationPrefShow:
    data = get_api_client().delete(f"/api/v1/actor-location-prefs/{pref_id}")
    return schemas.ActorLocationPrefShow.model_validate(data)


def undelete(pref_id: uuid.UUID) -> schemas.ActorLocationPrefShow:
    data = get_api_client().post(f"/api/v1/actor-location-prefs/{pref_id}/undelete")
    return schemas.ActorLocationPrefShow.model_validate(data)