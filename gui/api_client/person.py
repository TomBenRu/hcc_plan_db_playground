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


def undelete(person_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/persons/{person_id}/undelete")


def update_admin_of_project(person_id: uuid.UUID, project_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().patch(f"/api/v1/persons/{person_id}/admin-of-project",
                                  json={"project_id": str(project_id)})
    return schemas.PersonShow.model_validate(data)


def clear_admin_of_project(person_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/admin-of-project")
    return schemas.PersonShow.model_validate(data)


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


def put_in_comb_loc_possible(person_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/comb-loc-possibles/{clp_id}")
    return schemas.PersonShow.model_validate(data)


def remove_comb_loc_possible(person_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/comb-loc-possibles/{clp_id}")
    return schemas.PersonShow.model_validate(data)


def replace_comb_loc_possibles(
        person_id: uuid.UUID, original_ids: set[uuid.UUID],
        pending_creates: list[tuple[uuid.UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict[str, list[uuid.UUID]]:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/comb-loc-possibles/replace", json={
        "original_ids": [str(i) for i in original_ids],
        "pending_creates": [{"temp_id": str(tid), "data": d.model_dump(mode="json")}
                             for tid, d in pending_creates],
        "current_combs": [c.model_dump(mode="json") for c in current_combs],
    })
    return {k: [uuid.UUID(i) for i in v] for k, v in data.items()}


def restore_comb_loc_possibles(person_id: uuid.UUID, comb_ids_to_restore: list[uuid.UUID]) -> None:
    get_api_client().post(f"/api/v1/persons/{person_id}/comb-loc-possibles/restore",
                          json={"comb_ids_to_restore": [str(i) for i in comb_ids_to_restore]})


def put_in_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/location-prefs/{pref_id}")
    return schemas.PersonShow.model_validate(data)


def remove_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/location-prefs/{pref_id}")
    return schemas.PersonShow.model_validate(data)


def update_location_prefs_bulk(person_id: uuid.UUID, project_id: uuid.UUID,
                                location_id_to_score: dict[uuid.UUID, float],
                                ) -> dict[str, list[uuid.UUID]]:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/location-prefs/bulk-update", json={
        "project_id": str(project_id),
        "entries": [{"location_id": str(lid), "score": s}
                     for lid, s in location_id_to_score.items()],
    })
    return {k: [uuid.UUID(i) for i in v] for k, v in data.items()}


def restore_location_prefs_bulk(person_id: uuid.UUID, pref_ids_to_restore: list[uuid.UUID]) -> None:
    get_api_client().post(f"/api/v1/persons/{person_id}/location-prefs/bulk-restore",
                          json={"pref_ids_to_restore": [str(i) for i in pref_ids_to_restore]})


def put_in_partner_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/partner-location-prefs/{pref_id}")
    return schemas.PersonShow.model_validate(data)


def remove_partner_location_pref(person_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/partner-location-prefs/{pref_id}")
    return schemas.PersonShow.model_validate(data)


def add_skill(person_id: uuid.UUID, skill_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/skills/{skill_id}")
    return schemas.PersonShow.model_validate(data)


def remove_skill(person_id: uuid.UUID, skill_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/skills/{skill_id}")
    return schemas.PersonShow.model_validate(data)


def put_in_flag(person_id: uuid.UUID, flag_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().post(f"/api/v1/persons/{person_id}/flags/{flag_id}")
    return schemas.PersonShow.model_validate(data)


def remove_flag(person_id: uuid.UUID, flag_id: uuid.UUID) -> schemas.PersonShow:
    data = get_api_client().delete(f"/api/v1/persons/{person_id}/flags/{flag_id}")
    return schemas.PersonShow.model_validate(data)