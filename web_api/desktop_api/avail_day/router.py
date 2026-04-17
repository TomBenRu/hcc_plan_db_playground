"""Desktop-API: AvailDay-Endpunkte (/api/v1/avail-days)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/avail-days", tags=["desktop-avail-days"])


class AvailDayCreateBody(BaseModel):
    date: datetime.date
    actor_plan_period_id: uuid.UUID
    time_of_day_id: uuid.UUID


class AvailDayTimeOfDayBody(BaseModel):
    time_of_day_id: uuid.UUID


class AvailDayTimeOfDaysBody(BaseModel):
    time_of_days: list[schemas.TimeOfDay]


class IdsBody(BaseModel):
    ids: list[uuid.UUID]


class PendingCombLocCreate(BaseModel):
    temp_id: uuid.UUID
    data: schemas.CombinationLocationsPossibleCreate


class ReplaceCombLocForAvailDaysBody(BaseModel):
    avail_day_ids: list[uuid.UUID]
    person_id: uuid.UUID
    original_ids: list[uuid.UUID]
    pending_creates: list[PendingCombLocCreate]
    current_combs: list[schemas.CombinationLocationsPossible]


class RestoreCombLocForAvailDaysBody(BaseModel):
    target_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]


class LocationPrefEntry(BaseModel):
    location_id: uuid.UUID
    score: float


class ReplaceLocationPrefsForAvailDaysBody(BaseModel):
    avail_day_ids: list[uuid.UUID]
    person_id: uuid.UUID
    project_id: uuid.UUID
    entries: list[LocationPrefEntry]


class RestoreLocationPrefsForAvailDaysBody(BaseModel):
    target_ids_per_avail_day: dict[uuid.UUID, list[uuid.UUID]]


@router.post("", response_model=schemas.AvailDayShow, status_code=status.HTTP_201_CREATED)
def create_avail_day(body: AvailDayCreateBody, _: DesktopUser):
    actor_plan_period = db_services.ActorPlanPeriod.get(body.actor_plan_period_id)
    time_of_day = db_services.TimeOfDay.get(body.time_of_day_id)
    avail_day_create = schemas.AvailDayCreate(
        date=body.date, actor_plan_period=actor_plan_period, time_of_day=time_of_day
    )
    return db_services.AvailDay.create(avail_day_create)


@router.delete("/{avail_day_id}", response_model=schemas.AvailDayShow)
def delete_avail_day(avail_day_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.delete(avail_day_id)


@router.patch("/{avail_day_id}/time-of-day", response_model=schemas.AvailDayShow)
def update_time_of_day(avail_day_id: uuid.UUID, body: AvailDayTimeOfDayBody, _: DesktopUser):
    return db_services.AvailDay.update_time_of_day(avail_day_id, body.time_of_day_id)


@router.patch("/{avail_day_id}/time-of-days", response_model=schemas.AvailDayShow)
def update_time_of_days(avail_day_id: uuid.UUID, body: AvailDayTimeOfDaysBody, _: DesktopUser):
    return db_services.AvailDay.update_time_of_days(avail_day_id, body.time_of_days)


# Statische Pfade vor dynamischen Routen (FastAPI-Reihenfolge).
# Wichtig: /batch/... muss vor /{avail_day_id}/... stehen (sonst matcht "batch" als UUID).

# ── batch ops (mehrere avail_days) ────────────────────────────────────────────

@router.post("/batch/comb-loc-possibles/replace")
def replace_comb_loc_possibles_for_avail_days(body: ReplaceCombLocForAvailDaysBody, _: DesktopUser):
    pending_tuples = [(p.temp_id, p.data) for p in body.pending_creates]
    return db_services.AvailDay.replace_comb_loc_possibles_for_avail_days(
        body.avail_day_ids, body.person_id, set(body.original_ids),
        pending_tuples, body.current_combs,
    )


@router.post("/batch/comb-loc-possibles/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_comb_loc_possibles_for_avail_days(body: RestoreCombLocForAvailDaysBody, _: DesktopUser):
    db_services.AvailDay.restore_comb_loc_possibles_for_avail_days(body.target_ids_per_avail_day)


@router.post("/batch/location-prefs/replace")
def replace_location_prefs_for_avail_days(body: ReplaceLocationPrefsForAvailDaysBody, _: DesktopUser):
    score_dict = {e.location_id: e.score for e in body.entries}
    return db_services.AvailDay.replace_location_prefs_for_avail_days(
        body.avail_day_ids, body.person_id, body.project_id, score_dict,
    )


@router.post("/batch/location-prefs/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_location_prefs_for_avail_days(body: RestoreLocationPrefsForAvailDaysBody, _: DesktopUser):
    db_services.AvailDay.restore_location_prefs_for_avail_days(body.target_ids_per_avail_day)


# ── comb-loc-possibles ────────────────────────────────────────────────────────

@router.post("/{avail_day_id}/comb-loc-possibles/bulk", response_model=schemas.AvailDayShow)
def put_in_comb_loc_possibles(avail_day_id: uuid.UUID, body: IdsBody, _: DesktopUser):
    return db_services.AvailDay.put_in_comb_loc_possibles(avail_day_id, body.ids)


@router.delete("/{avail_day_id}/comb-loc-possibles", response_model=schemas.AvailDayShow)
def clear_comb_loc_possibles(avail_day_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.clear_comb_loc_possibles(avail_day_id)


@router.post("/{avail_day_id}/comb-loc-possibles/{clp_id}", response_model=schemas.AvailDayShow)
def put_in_comb_loc_possible(avail_day_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.put_in_comb_loc_possible(avail_day_id, clp_id)


@router.delete("/{avail_day_id}/comb-loc-possibles/{clp_id}", response_model=schemas.AvailDayShow)
def remove_comb_loc_possible(avail_day_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.remove_comb_loc_possible(avail_day_id, clp_id)


# ── location-prefs ────────────────────────────────────────────────────────────

@router.post("/{avail_day_id}/location-prefs/bulk", response_model=schemas.AvailDayShow)
def put_in_location_prefs(avail_day_id: uuid.UUID, body: IdsBody, _: DesktopUser):
    return db_services.AvailDay.put_in_location_prefs(avail_day_id, body.ids)


@router.delete("/{avail_day_id}/location-prefs", response_model=schemas.AvailDayShow)
def clear_location_prefs(avail_day_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.clear_location_prefs(avail_day_id)


@router.post("/{avail_day_id}/location-prefs/{pref_id}", response_model=schemas.AvailDayShow)
def put_in_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.put_in_location_pref(avail_day_id, pref_id)


@router.delete("/{avail_day_id}/location-prefs/{pref_id}", response_model=schemas.AvailDayShow)
def remove_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.remove_location_pref(avail_day_id, pref_id)


# ── partner-location-prefs ────────────────────────────────────────────────────

@router.post("/{avail_day_id}/partner-location-prefs/bulk", response_model=schemas.AvailDayShow)
def put_in_partner_location_prefs(avail_day_id: uuid.UUID, body: IdsBody, _: DesktopUser):
    return db_services.AvailDay.put_in_partner_location_prefs(avail_day_id, body.ids)


@router.delete("/{avail_day_id}/partner-location-prefs", response_model=schemas.AvailDayShow)
def clear_partner_location_prefs(avail_day_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.clear_partner_location_prefs(avail_day_id)


@router.post("/{avail_day_id}/partner-location-prefs/{pref_id}", response_model=schemas.AvailDayShow)
def put_in_partner_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.put_in_partner_location_pref(avail_day_id, pref_id)


@router.delete("/{avail_day_id}/partner-location-prefs/{pref_id}", response_model=schemas.AvailDayShow)
def remove_partner_location_pref(avail_day_id: uuid.UUID, pref_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.remove_partner_location_pref(avail_day_id, pref_id)


# ── skills ────────────────────────────────────────────────────────────────────
# Statische Pfade vor dynamischen {skill_id}.

@router.post("/{avail_day_id}/skills/bulk", response_model=schemas.AvailDayShow)
def put_in_skills(avail_day_id: uuid.UUID, body: IdsBody, _: DesktopUser):
    return db_services.AvailDay.put_in_skills(avail_day_id, body.ids)


@router.delete("/{avail_day_id}/skills", response_model=schemas.AvailDayShow)
def clear_skills(avail_day_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.clear_skills(avail_day_id)


@router.post("/{avail_day_id}/skills/{skill_id}", response_model=schemas.AvailDayShow)
def add_skill(avail_day_id: uuid.UUID, skill_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.add_skill(avail_day_id, skill_id)


@router.delete("/{avail_day_id}/skills/{skill_id}", response_model=schemas.AvailDayShow)
def remove_skill(avail_day_id: uuid.UUID, skill_id: uuid.UUID, _: DesktopUser):
    return db_services.AvailDay.remove_skill(avail_day_id, skill_id)