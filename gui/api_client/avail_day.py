"""Desktop-API-Client: AvailDay-Operationen."""

import datetime
import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(date: datetime.date, actor_plan_period_id: uuid.UUID,
           time_of_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().post("/api/v1/avail-days", json={
        "date": date.isoformat(),
        "actor_plan_period_id": str(actor_plan_period_id),
        "time_of_day_id": str(time_of_day_id),
    })
    return schemas.AvailDayShow.model_validate(data)


def delete(avail_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}")
    return schemas.AvailDayShow.model_validate(data)


def update_time_of_day(avail_day_id: uuid.UUID, time_of_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().patch(f"/api/v1/avail-days/{avail_day_id}/time-of-day",
                                  json={"time_of_day_id": str(time_of_day_id)})
    return schemas.AvailDayShow.model_validate(data)


def update_time_of_days(avail_day_id: uuid.UUID,
                        time_of_days: list[schemas.TimeOfDay]) -> schemas.AvailDayShow:
    data = get_api_client().patch(f"/api/v1/avail-days/{avail_day_id}/time-of-days",
                                  json={"time_of_days": [t.model_dump(mode="json") for t in time_of_days]})
    return schemas.AvailDayShow.model_validate(data)


# ── comb-loc-possibles ────────────────────────────────────────────────────────

def put_in_comb_loc_possible(avail_day_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().post(f"/api/v1/avail-days/{avail_day_id}/comb-loc-possibles/{clp_id}")
    return schemas.AvailDayShow.model_validate(data)


def put_in_comb_loc_possibles(avail_day_id: uuid.UUID,
                               clp_ids: list[uuid.UUID]) -> schemas.AvailDayShow:
    data = get_api_client().post(f"/api/v1/avail-days/{avail_day_id}/comb-loc-possibles/bulk",
                                  json={"ids": [str(i) for i in clp_ids]})
    return schemas.AvailDayShow.model_validate(data)


def remove_comb_loc_possible(avail_day_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}/comb-loc-possibles/{clp_id}")
    return schemas.AvailDayShow.model_validate(data)


def clear_comb_loc_possibles(avail_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}/comb-loc-possibles")
    return schemas.AvailDayShow.model_validate(data)


def replace_comb_loc_possibles_for_avail_days(
        avail_day_ids: list[uuid.UUID], person_id: uuid.UUID, original_ids: set[uuid.UUID],
        pending_creates: list[tuple[uuid.UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict:
    return get_api_client().post("/api/v1/avail-days/batch/comb-loc-possibles/replace", json={
        "avail_day_ids": [str(i) for i in avail_day_ids],
        "person_id": str(person_id),
        "original_ids": [str(i) for i in original_ids],
        "pending_creates": [{"temp_id": str(tid), "data": d.model_dump(mode="json")}
                             for tid, d in pending_creates],
        "current_combs": [c.model_dump(mode="json") for c in current_combs],
    })


def restore_comb_loc_possibles_for_avail_days(
        target_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]) -> None:
    get_api_client().post("/api/v1/avail-days/batch/comb-loc-possibles/restore", json={
        "target_ids_per_avail_day": {str(k): [str(i) for i in v]
                                      for k, v in target_ids_per_avail_day.items()},
    })


# ── location-prefs ────────────────────────────────────────────────────────────

def put_in_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().post(f"/api/v1/avail-days/{avail_day_id}/location-prefs/{pref_id}")
    return schemas.AvailDayShow.model_validate(data)


def put_in_location_prefs(avail_day_id: uuid.UUID,
                           pref_ids: list[uuid.UUID]) -> schemas.AvailDayShow:
    data = get_api_client().post(f"/api/v1/avail-days/{avail_day_id}/location-prefs/bulk",
                                  json={"ids": [str(i) for i in pref_ids]})
    return schemas.AvailDayShow.model_validate(data)


def remove_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}/location-prefs/{pref_id}")
    return schemas.AvailDayShow.model_validate(data)


def clear_location_prefs(avail_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}/location-prefs")
    return schemas.AvailDayShow.model_validate(data)


def replace_location_prefs_for_avail_days(
        avail_day_ids: list[uuid.UUID], person_id: uuid.UUID, project_id: uuid.UUID,
        location_id_to_score: dict[uuid.UUID, float]) -> dict:
    return get_api_client().post("/api/v1/avail-days/batch/location-prefs/replace", json={
        "avail_day_ids": [str(i) for i in avail_day_ids],
        "person_id": str(person_id),
        "project_id": str(project_id),
        "entries": [{"location_id": str(lid), "score": s}
                     for lid, s in location_id_to_score.items()],
    })


def restore_location_prefs_for_avail_days(
        target_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]) -> None:
    get_api_client().post("/api/v1/avail-days/batch/location-prefs/restore", json={
        "target_ids_per_avail_day": {str(k): [str(i) for i in v]
                                      for k, v in target_ids_per_avail_day.items()},
    })


# ── partner-location-prefs ────────────────────────────────────────────────────

def put_in_partner_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().post(f"/api/v1/avail-days/{avail_day_id}/partner-location-prefs/{pref_id}")
    return schemas.AvailDayShow.model_validate(data)


def put_in_partner_location_prefs(avail_day_id: uuid.UUID,
                                   pref_ids: list[uuid.UUID]) -> schemas.AvailDayShow:
    data = get_api_client().post(f"/api/v1/avail-days/{avail_day_id}/partner-location-prefs/bulk",
                                  json={"ids": [str(i) for i in pref_ids]})
    return schemas.AvailDayShow.model_validate(data)


def remove_partner_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}/partner-location-prefs/{pref_id}")
    return schemas.AvailDayShow.model_validate(data)


def clear_partner_location_prefs(avail_day_id: uuid.UUID) -> schemas.AvailDayShow:
    data = get_api_client().delete(f"/api/v1/avail-days/{avail_day_id}/partner-location-prefs")
    return schemas.AvailDayShow.model_validate(data)