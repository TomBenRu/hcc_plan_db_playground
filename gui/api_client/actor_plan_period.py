"""Desktop-API-Client: ActorPlanPeriod-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(plan_period_id: uuid.UUID, person_id: uuid.UUID,
           actor_plan_period_id: uuid.UUID | None = None) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().post("/api/v1/actor-plan-periods", json={
        "plan_period_id": str(plan_period_id),
        "person_id": str(person_id),
        "actor_plan_period_id": str(actor_plan_period_id) if actor_plan_period_id else None,
    })
    return schemas.ActorPlanPeriodShow.model_validate(data)


def delete(app_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/actor-plan-periods/{app_id}")


def update(actor_plan_period: schemas.ActorPlanPeriodShow) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().put(f"/api/v1/actor-plan-periods/{actor_plan_period.id}",
                                json=actor_plan_period.model_dump(mode="json"))
    return schemas.ActorPlanPeriodShow.model_validate(data)


def update_notes(app_id: uuid.UUID, notes: str | None) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/actor-plan-periods/{app_id}/notes",
                                  json={"notes": notes})
    return schemas.ActorPlanPeriodShow.model_validate(data)


def update_requested_assignments(app_id: uuid.UUID, requested_assignments: int,
                                 required_assignments: bool) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/actor-plan-periods/{app_id}/requested-assignments", json={
        "requested_assignments": requested_assignments,
        "required_assignments": required_assignments,
    })
    return schemas.ActorPlanPeriodShow.model_validate(data)


def put_in_time_of_day(app_id: uuid.UUID,
                        time_of_day_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().post(
        f"/api/v1/actor-plan-periods/{app_id}/time-of-days/{time_of_day_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def remove_in_time_of_day(app_id: uuid.UUID,
                           time_of_day_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().delete(
        f"/api/v1/actor-plan-periods/{app_id}/time-of-days/{time_of_day_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def new_time_of_day_standard(app_id: uuid.UUID, time_of_day_id: uuid.UUID
                              ) -> tuple[schemas.ActorPlanPeriodShow, uuid.UUID | None]:
    data = get_api_client().post(
        f"/api/v1/actor-plan-periods/{app_id}/time-of-day-standards/{time_of_day_id}")
    old_id = uuid.UUID(data["old_standard_id"]) if data["old_standard_id"] else None
    return schemas.ActorPlanPeriodShow.model_validate(data["actor_plan_period"]), old_id


def remove_time_of_day_standard(app_id: uuid.UUID,
                                 time_of_day_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().delete(
        f"/api/v1/actor-plan-periods/{app_id}/time-of-day-standards/{time_of_day_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def put_in_comb_loc_possible(app_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/comb-loc-possibles/{clp_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def remove_comb_loc_possible(app_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().delete(f"/api/v1/actor-plan-periods/{app_id}/comb-loc-possibles/{clp_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def replace_comb_loc_possibles(
        app_id: uuid.UUID, person_id: uuid.UUID, original_ids: set[uuid.UUID],
        pending_creates: list[tuple[uuid.UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict[str, list[uuid.UUID]]:
    data = get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/comb-loc-possibles/replace", json={
        "person_id": str(person_id),
        "original_ids": [str(i) for i in original_ids],
        "pending_creates": [{"temp_id": str(tid), "data": d.model_dump(mode="json")}
                             for tid, d in pending_creates],
        "current_combs": [c.model_dump(mode="json") for c in current_combs],
    })
    return {k: [uuid.UUID(i) for i in v] for k, v in data.items()}


def restore_comb_loc_possibles(app_id: uuid.UUID, comb_ids_to_restore: list[uuid.UUID]) -> None:
    get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/comb-loc-possibles/restore",
                          json={"comb_ids_to_restore": [str(i) for i in comb_ids_to_restore]})


def put_in_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/location-prefs/{pref_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def remove_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().delete(f"/api/v1/actor-plan-periods/{app_id}/location-prefs/{pref_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def update_location_prefs_bulk(app_id: uuid.UUID,
                                location_id_to_score: dict[uuid.UUID, float],
                                ) -> dict[str, list[uuid.UUID]]:
    data = get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/location-prefs/bulk-update", json={
        "entries": [{"location_id": str(lid), "score": s}
                     for lid, s in location_id_to_score.items()],
    })
    return {k: [uuid.UUID(i) for i in v] for k, v in data.items()}


def restore_location_prefs_bulk(app_id: uuid.UUID, pref_ids_to_restore: list[uuid.UUID]) -> None:
    get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/location-prefs/bulk-restore",
                          json={"pref_ids_to_restore": [str(i) for i in pref_ids_to_restore]})


def put_in_partner_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/partner-location-prefs/{pref_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def remove_partner_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID) -> schemas.ActorPlanPeriodShow:
    data = get_api_client().delete(f"/api/v1/actor-plan-periods/{app_id}/partner-location-prefs/{pref_id}")
    return schemas.ActorPlanPeriodShow.model_validate(data)


def reset_avail_days_comb_loc_possibles_to_defaults(app_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/reset-defaults/comb-loc-possibles")


def reset_avail_days_location_prefs_to_defaults(app_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/reset-defaults/location-prefs")


def reset_avail_days_partner_location_prefs_to_defaults(app_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/actor-plan-periods/{app_id}/reset-defaults/partner-location-prefs")