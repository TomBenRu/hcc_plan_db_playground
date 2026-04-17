"""Desktop-API-Client: Team-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def update_notes(team_id: uuid.UUID, notes: str) -> schemas.TeamShow:
    data = get_api_client().patch(f"/api/v1/teams/{team_id}/notes",
                                  json={"notes": notes})
    return schemas.TeamShow.model_validate(data)