"""Desktop-API: ActorPlanPeriod-Endpunkte (/api/v1/actor-plan-periods)."""

import uuid

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/actor-plan-periods", tags=["desktop-actor-plan-periods"])


class ActorPlanPeriodCreateBody(BaseModel):
    plan_period_id: uuid.UUID
    person_id: uuid.UUID
    actor_plan_period_id: uuid.UUID | None = None


class AppNotesBody(BaseModel):
    notes: str | None = None


class AppRequestedAssignmentsBody(BaseModel):
    requested_assignments: int
    required_assignments: bool


class NewTimeOfDayStandardResponse(BaseModel):
    actor_plan_period: schemas.ActorPlanPeriodShow
    old_standard_id: uuid.UUID | None


class PendingCombLocCreate(BaseModel):
    temp_id: uuid.UUID
    data: schemas.CombinationLocationsPossibleCreate


class ReplaceCombLocPossiblesBody(BaseModel):
    person_id: uuid.UUID
    original_ids: list[uuid.UUID]
    pending_creates: list[PendingCombLocCreate]
    current_combs: list[schemas.CombinationLocationsPossible]


class RestoreCombLocPossiblesBody(BaseModel):
    comb_ids_to_restore: list[uuid.UUID]


class LocationPrefEntry(BaseModel):
    location_id: uuid.UUID
    score: float


class UpdateLocationPrefsBulkBody(BaseModel):
    entries: list[LocationPrefEntry]


class RestoreLocationPrefsBulkBody(BaseModel):
    pref_ids_to_restore: list[uuid.UUID]


@router.post("", response_model=schemas.ActorPlanPeriodShow, status_code=status.HTTP_201_CREATED)
def create_actor_plan_period(body: ActorPlanPeriodCreateBody, _: DesktopUser):
    return db_services.ActorPlanPeriod.create(
        body.plan_period_id, body.person_id, body.actor_plan_period_id
    )


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_actor_plan_period(app_id: uuid.UUID, _: DesktopUser):
    db_services.ActorPlanPeriod.delete(app_id)


@router.put("/{app_id}", response_model=schemas.ActorPlanPeriodShow)
def update_actor_plan_period(app_id: uuid.UUID, body: schemas.ActorPlanPeriodShow, _: DesktopUser):
    return db_services.ActorPlanPeriod.update(body)


@router.patch("/{app_id}/notes", status_code=204, response_class=Response)
def update_app_notes(app_id: uuid.UUID, body: AppNotesBody, _: DesktopUser):
    """204 No Content — Client aktualisiert sein Notes-Feld lokal und
    braucht keine Server-Antwort."""
    update_data = schemas.ActorPlanPeriodUpdateNotes(id=app_id, notes=body.notes)
    db_services.ActorPlanPeriod.update_notes(update_data)


@router.patch("/{app_id}/requested-assignments", response_model=schemas.ActorPlanPeriodShow)
def update_requested_assignments(app_id: uuid.UUID, body: AppRequestedAssignmentsBody, _: DesktopUser):
    return db_services.ActorPlanPeriod.update_requested_assignments(
        app_id, body.requested_assignments, body.required_assignments
    )


@router.post("/{app_id}/time-of-days/{time_of_day_id}", response_model=schemas.ActorPlanPeriodShow)
def put_in_time_of_day(app_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.put_in_time_of_day(app_id, time_of_day_id)


@router.delete("/{app_id}/time-of-days/{time_of_day_id}", response_model=schemas.ActorPlanPeriodShow)
def remove_in_time_of_day(app_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.remove_in_time_of_day(app_id, time_of_day_id)


@router.post("/{app_id}/time-of-day-standards/{time_of_day_id}",
             response_model=NewTimeOfDayStandardResponse)
def new_time_of_day_standard(app_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    app, old_id = db_services.ActorPlanPeriod.new_time_of_day_standard(app_id, time_of_day_id)
    return NewTimeOfDayStandardResponse(actor_plan_period=app, old_standard_id=old_id)


@router.delete("/{app_id}/time-of-day-standards/{time_of_day_id}",
               response_model=schemas.ActorPlanPeriodShow)
def remove_time_of_day_standard(app_id: uuid.UUID, time_of_day_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.remove_time_of_day_standard(app_id, time_of_day_id)


# Statische Pfade vor dynamischen {clp_id}/{pref_id}-Routen (FastAPI-Reihenfolge).
@router.post("/{app_id}/comb-loc-possibles/replace",
             response_model=dict[str, list[uuid.UUID]])
def replace_comb_loc_possibles(app_id: uuid.UUID, body: ReplaceCombLocPossiblesBody, _: DesktopUser):
    pending_tuples = [(p.temp_id, p.data) for p in body.pending_creates]
    return db_services.ActorPlanPeriod.replace_comb_loc_possibles(
        app_id, body.person_id, set(body.original_ids), pending_tuples, body.current_combs,
    )


@router.post("/{app_id}/comb-loc-possibles/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_comb_loc_possibles(app_id: uuid.UUID, body: RestoreCombLocPossiblesBody, _: DesktopUser):
    db_services.ActorPlanPeriod.restore_comb_loc_possibles(app_id, body.comb_ids_to_restore)


@router.post("/{app_id}/comb-loc-possibles/{clp_id}", response_model=schemas.ActorPlanPeriodShow)
def put_in_comb_loc_possible(app_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.put_in_comb_loc_possible(app_id, clp_id)


@router.delete("/{app_id}/comb-loc-possibles/{clp_id}", response_model=schemas.ActorPlanPeriodShow)
def remove_comb_loc_possible(app_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.remove_comb_loc_possible(app_id, clp_id)


@router.post("/{app_id}/location-prefs/bulk-update",
             response_model=dict[str, list[uuid.UUID]])
def update_location_prefs_bulk(app_id: uuid.UUID, body: UpdateLocationPrefsBulkBody, _: DesktopUser):
    score_dict = {e.location_id: e.score for e in body.entries}
    return db_services.ActorPlanPeriod.update_location_prefs_bulk(app_id, score_dict)


@router.post("/{app_id}/location-prefs/bulk-restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_location_prefs_bulk(app_id: uuid.UUID, body: RestoreLocationPrefsBulkBody, _: DesktopUser):
    db_services.ActorPlanPeriod.restore_location_prefs_bulk(app_id, body.pref_ids_to_restore)


@router.post("/{app_id}/location-prefs/{pref_id}", response_model=schemas.ActorPlanPeriodShow)
def put_in_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.put_in_location_pref(app_id, pref_id)


@router.delete("/{app_id}/location-prefs/{pref_id}", response_model=schemas.ActorPlanPeriodShow)
def remove_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.remove_location_pref(app_id, pref_id)


@router.post("/{app_id}/partner-location-prefs/{pref_id}", response_model=schemas.ActorPlanPeriodShow)
def put_in_partner_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.put_in_partner_location_pref(app_id, pref_id)


@router.delete("/{app_id}/partner-location-prefs/{pref_id}", response_model=schemas.ActorPlanPeriodShow)
def remove_partner_location_pref(app_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.ActorPlanPeriod.remove_partner_location_pref(app_id, pref_id)


@router.post("/{app_id}/reset-defaults/comb-loc-possibles", status_code=status.HTTP_204_NO_CONTENT)
def reset_avail_days_comb_loc_possibles(app_id: uuid.UUID, _: DesktopUser):
    db_services.AvailDay.reset_all_avail_days_comb_loc_possibles_of_actor_plan_period_to_defaults(app_id)


@router.post("/{app_id}/reset-defaults/location-prefs", status_code=status.HTTP_204_NO_CONTENT)
def reset_avail_days_location_prefs(app_id: uuid.UUID, _: DesktopUser):
    db_services.AvailDay.reset_all_avail_days_location_prefs_of_actor_plan_period_to_defaults(app_id)


@router.post("/{app_id}/reset-defaults/partner-location-prefs", status_code=status.HTTP_204_NO_CONTENT)
def reset_avail_days_partner_location_prefs(app_id: uuid.UUID, _: DesktopUser):
    db_services.AvailDay.reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(app_id)


@router.post("/{app_id}/skills/clear-all", status_code=status.HTTP_204_NO_CONTENT)
def clear_all_skills(app_id: uuid.UUID, _: DesktopUser):
    db_services.AvailDay.clear_all_skills_of_actor_plan_period(app_id)


@router.post("/{app_id}/skills/reset-to-person-defaults", status_code=status.HTTP_204_NO_CONTENT)
def reset_all_skills_to_person_defaults(app_id: uuid.UUID, _: DesktopUser):
    db_services.AvailDay.reset_all_skills_of_actor_plan_period_to_person_defaults(app_id)