"""Desktop-API-Client: ActorPartnerLocationPref-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(pref: schemas.ActorPartnerLocationPrefCreate) -> schemas.ActorPartnerLocationPrefShow:
    data = get_api_client().post("/api/v1/actor-partner-location-prefs",
                                 json=pref.model_dump(mode="json"))
    return schemas.ActorPartnerLocationPrefShow.model_validate(data)


def modify(pref: schemas.ActorPartnerLocationPrefShow) -> schemas.ActorPartnerLocationPrefShow:
    data = get_api_client().patch(f"/api/v1/actor-partner-location-prefs/{pref.id}",
                                  json=pref.model_dump(mode="json"))
    return schemas.ActorPartnerLocationPrefShow.model_validate(data)


def delete(pref_id: uuid.UUID) -> schemas.ActorPartnerLocationPrefShow:
    data = get_api_client().delete(f"/api/v1/actor-partner-location-prefs/{pref_id}")
    return schemas.ActorPartnerLocationPrefShow.model_validate(data)


def undelete(pref_id: uuid.UUID) -> schemas.ActorPartnerLocationPrefShow:
    data = get_api_client().post(f"/api/v1/actor-partner-location-prefs/{pref_id}/undelete")
    return schemas.ActorPartnerLocationPrefShow.model_validate(data)


def replace_all_for_model(
        model_class_name: str, model_id: uuid.UUID, person_id: uuid.UUID,
        new_prefs: list[tuple[uuid.UUID, uuid.UUID, float]],
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    data = get_api_client().post("/api/v1/actor-partner-location-prefs/replace-all-for-model", json={
        "model_class_name": model_class_name,
        "model_id": str(model_id),
        "person_id": str(person_id),
        "new_prefs": [{"partner_id": str(p), "location_id": str(l), "score": s}
                      for p, l, s in new_prefs],
    })
    return ([uuid.UUID(i) for i in data["created_ids"]],
            [uuid.UUID(i) for i in data["old_apl_ids"]])


def undo_replace_all_for_model(model_class_name: str, model_id: uuid.UUID,
                                created_ids: list[uuid.UUID],
                                old_apl_ids: list[uuid.UUID]) -> None:
    get_api_client().post("/api/v1/actor-partner-location-prefs/undo-replace-all-for-model", json={
        "model_class_name": model_class_name,
        "model_id": str(model_id),
        "created_ids": [str(i) for i in created_ids],
        "old_apl_ids": [str(i) for i in old_apl_ids],
    })


def replace_all_for_avail_days(
        avail_day_ids: list[uuid.UUID], person_id: uuid.UUID,
        new_prefs: list[tuple[uuid.UUID, uuid.UUID, float]],
) -> tuple[list[uuid.UUID], dict[uuid.UUID, list[uuid.UUID]]]:
    data = get_api_client().post("/api/v1/actor-partner-location-prefs/replace-all-for-avail-days", json={
        "avail_day_ids": [str(i) for i in avail_day_ids],
        "person_id": str(person_id),
        "new_prefs": [{"partner_id": str(p), "location_id": str(l), "score": s}
                      for p, l, s in new_prefs],
    })
    return (
        [uuid.UUID(i) for i in data["created_ids"]],
        {uuid.UUID(k): [uuid.UUID(i) for i in v]
         for k, v in data["old_pref_ids_per_avail_day"].items()},
    )


def undo_replace_all_for_avail_days(avail_day_ids: list[uuid.UUID],
                                     created_ids: list[uuid.UUID],
                                     old_pref_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]) -> None:
    get_api_client().post("/api/v1/actor-partner-location-prefs/undo-replace-all-for-avail-days", json={
        "avail_day_ids": [str(i) for i in avail_day_ids],
        "created_ids": [str(i) for i in created_ids],
        "old_pref_ids_per_avail_day": {str(k): [str(i) for i in v]
                                        for k, v in old_pref_ids_per_avail_day.items()},
    })


def delete_unused(person_id: uuid.UUID) -> list[uuid.UUID]:
    data = get_api_client().post(
        f"/api/v1/actor-partner-location-prefs/delete-unused-for-person/{person_id}")
    return [uuid.UUID(i) for i in data]