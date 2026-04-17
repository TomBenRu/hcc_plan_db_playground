"""Desktop-API: Team-Endpunkte (/api/v1/teams)."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/teams", tags=["desktop-teams"])


class TeamNotesBody(BaseModel):
    notes: str


@router.patch("/{team_id}/notes", response_model=schemas.TeamShow)
def update_team_notes(team_id: uuid.UUID, body: TeamNotesBody, _: DesktopUser):
    return db_services.Team.update_notes(team_id, body.notes)
