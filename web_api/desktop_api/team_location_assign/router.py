"""Desktop-API: TeamLocationAssign-Endpunkte (/api/v1/team-location-assigns)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/team-location-assigns", tags=["desktop-team-location-assigns"])


class TeamLocationAssignCreateBody(BaseModel):
    location_of_work_id: uuid.UUID
    team_id: uuid.UUID
    start: datetime.date | None = None
    end: datetime.date | None = None
    assign_id: uuid.UUID | None = None


class EndDateBody(BaseModel):
    end_date: datetime.date | None = None


@router.post("", response_model=schemas.TeamLocationAssignShow, status_code=status.HTTP_201_CREATED)
def create_team_location_assign(body: TeamLocationAssignCreateBody, _: DesktopUser):
    location = db_services.LocationOfWork.get(body.location_of_work_id)
    team = db_services.Team.get(body.team_id)
    tla = schemas.TeamLocationAssignCreate(start=body.start, end=body.end,
                                           location_of_work=location, team=team)
    return db_services.TeamLocationAssign.create(tla, body.assign_id)


@router.patch("/{assign_id}/end-date", status_code=status.HTTP_204_NO_CONTENT)
def set_end_date(assign_id: uuid.UUID, body: EndDateBody, _: DesktopUser):
    db_services.TeamLocationAssign.set_end_date(assign_id, body.end_date)


@router.delete("/{assign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_location_assign(assign_id: uuid.UUID, _: DesktopUser):
    db_services.TeamLocationAssign.delete(assign_id)