"""Desktop-API: TeamActorAssign-Endpunkte (/api/v1/team-actor-assigns)."""

import datetime
import uuid

from fastapi import APIRouter, status
from pydantic import BaseModel

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/team-actor-assigns", tags=["desktop-team-actor-assigns"])


class TeamActorAssignCreateBody(BaseModel):
    person_id: uuid.UUID
    team_id: uuid.UUID
    start: datetime.date | None = None
    end: datetime.date | None = None
    assign_id: uuid.UUID | None = None


class EndDateBody(BaseModel):
    end_date: datetime.date | None = None


@router.post("", response_model=schemas.TeamActorAssignShow, status_code=status.HTTP_201_CREATED)
def create_team_actor_assign(body: TeamActorAssignCreateBody, _: DesktopUser):
    person = db_services.Person.get(body.person_id)
    team = db_services.Team.get(body.team_id)
    taa = schemas.TeamActorAssignCreate(start=body.start, end=body.end, person=person, team=team)
    return db_services.TeamActorAssign.create(taa, body.assign_id)


@router.patch("/{assign_id}/end-date", status_code=status.HTTP_204_NO_CONTENT)
def set_end_date(assign_id: uuid.UUID, body: EndDateBody, _: DesktopUser):
    db_services.TeamActorAssign.set_end_date(assign_id, body.end_date)


@router.delete("/{assign_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_actor_assign(assign_id: uuid.UUID, _: DesktopUser):
    db_services.TeamActorAssign.delete(assign_id)