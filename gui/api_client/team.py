"""Desktop-API-Client: Team-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def update_notes(team_id: uuid.UUID, notes: str) -> schemas.TeamShow:
    data = get_api_client().patch(f"/api/v1/teams/{team_id}/notes",
                                  json={"notes": notes})
    return schemas.TeamShow.model_validate(data)


def put_in_comb_loc_possible(team_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.TeamShow:
    data = get_api_client().post(f"/api/v1/teams/{team_id}/comb-loc-possibles/{clp_id}")
    return schemas.TeamShow.model_validate(data)


def remove_comb_loc_possible(team_id: uuid.UUID, clp_id: uuid.UUID) -> schemas.TeamShow:
    data = get_api_client().delete(f"/api/v1/teams/{team_id}/comb-loc-possibles/{clp_id}")
    return schemas.TeamShow.model_validate(data)


def replace_comb_loc_possibles(
        team_id: uuid.UUID, original_ids: set[uuid.UUID],
        pending_creates: list[tuple[uuid.UUID, schemas.CombinationLocationsPossibleCreate]],
        current_combs: list[schemas.CombinationLocationsPossible],
) -> dict[str, list[uuid.UUID]]:
    data = get_api_client().post(f"/api/v1/teams/{team_id}/comb-loc-possibles/replace", json={
        "original_ids": [str(i) for i in original_ids],
        "pending_creates": [{"temp_id": str(tid), "data": d.model_dump(mode="json")}
                             for tid, d in pending_creates],
        "current_combs": [c.model_dump(mode="json") for c in current_combs],
    })
    return {k: [uuid.UUID(i) for i in v] for k, v in data.items()}


def restore_comb_loc_possibles(team_id: uuid.UUID, comb_ids_to_restore: list[uuid.UUID]) -> None:
    get_api_client().post(f"/api/v1/teams/{team_id}/comb-loc-possibles/restore",
                          json={"comb_ids_to_restore": [str(i) for i in comb_ids_to_restore]})


def put_in_excel_settings(team_id: uuid.UUID, excel_settings_id: uuid.UUID) -> schemas.TeamShow:
    data = get_api_client().put(f"/api/v1/teams/{team_id}/excel-settings/{excel_settings_id}")
    return schemas.TeamShow.model_validate(data)