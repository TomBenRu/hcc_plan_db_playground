"""Desktop-API: Team-Endpunkte (/api/v1/teams)."""

import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/teams", tags=["desktop-teams"])


class TeamNotesBody(BaseModel):
    notes: str


class PendingCombLocCreate(BaseModel):
    temp_id: uuid.UUID
    data: schemas.CombinationLocationsPossibleCreate


class ReplaceCombLocPossiblesBody(BaseModel):
    original_ids: list[uuid.UUID]
    pending_creates: list[PendingCombLocCreate]
    current_combs: list[schemas.CombinationLocationsPossible]


class RestoreCombLocPossiblesBody(BaseModel):
    comb_ids_to_restore: list[uuid.UUID]


@router.patch("/{team_id}/notes", response_model=schemas.TeamShow)
def update_team_notes(team_id: uuid.UUID, body: TeamNotesBody, _: DesktopUser):
    return db_services.Team.update_notes(team_id, body.notes)


@router.post("/{team_id}/comb-loc-possibles/{clp_id}", response_model=schemas.TeamShow)
def put_in_comb_loc_possible(team_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.Team.put_in_comb_loc_possible(team_id, clp_id)


@router.delete("/{team_id}/comb-loc-possibles/{clp_id}", response_model=schemas.TeamShow)
def remove_comb_loc_possible(team_id: uuid.UUID, clp_id: uuid.UUID, _: DesktopUser):
    return db_services.Team.remove_comb_loc_possible(team_id, clp_id)


@router.post("/{team_id}/comb-loc-possibles/replace",
             response_model=dict[str, list[uuid.UUID]])
def replace_comb_loc_possibles(team_id: uuid.UUID, body: ReplaceCombLocPossiblesBody, _: DesktopUser):
    pending_tuples = [(p.temp_id, p.data) for p in body.pending_creates]
    return db_services.Team.replace_comb_loc_possibles(
        team_id, set(body.original_ids), pending_tuples, body.current_combs,
    )


@router.post("/{team_id}/comb-loc-possibles/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_comb_loc_possibles(team_id: uuid.UUID, body: RestoreCombLocPossiblesBody, _: DesktopUser):
    db_services.Team.restore_comb_loc_possibles(team_id, body.comb_ids_to_restore)


@router.put("/{team_id}/excel-settings/{excel_settings_id}", response_model=schemas.TeamShow)
def put_in_excel_settings(team_id: uuid.UUID, excel_settings_id: uuid.UUID, _: DesktopUser):
    return db_services.Team.put_in_excel_settings(team_id, excel_settings_id)
