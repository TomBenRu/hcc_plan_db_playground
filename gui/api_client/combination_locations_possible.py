"""Desktop-API-Client: CombinationLocationsPossible-Operationen."""

import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(clp: schemas.CombinationLocationsPossibleCreate
           ) -> schemas.CombinationLocationsPossibleShow:
    data = get_api_client().post("/api/v1/combination-locations-possibles",
                                 json=clp.model_dump(mode="json"))
    return schemas.CombinationLocationsPossibleShow.model_validate(data)


def delete(clp_id: uuid.UUID) -> schemas.CombinationLocationsPossibleShow:
    data = get_api_client().delete(f"/api/v1/combination-locations-possibles/{clp_id}")
    return schemas.CombinationLocationsPossibleShow.model_validate(data)


def undelete(clp_id: uuid.UUID) -> schemas.CombinationLocationsPossibleShow:
    data = get_api_client().post(f"/api/v1/combination-locations-possibles/{clp_id}/undelete")
    return schemas.CombinationLocationsPossibleShow.model_validate(data)