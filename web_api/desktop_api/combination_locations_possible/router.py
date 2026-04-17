"""Desktop-API: CombinationLocationsPossible-Endpunkte (/api/v1/combination-locations-possibles)."""

import uuid

from fastapi import APIRouter, status

from database import db_services, schemas
from web_api.desktop_api.auth import DesktopUser

router = APIRouter(prefix="/combination-locations-possibles",
                   tags=["desktop-combination-locations-possibles"])


@router.post("", response_model=schemas.CombinationLocationsPossibleShow,
             status_code=status.HTTP_201_CREATED)
def create_comb_loc(body: schemas.CombinationLocationsPossibleCreate, _: DesktopUser):
    return db_services.CombinationLocationsPossible.create(body)


@router.delete("/{clp_id}", response_model=schemas.CombinationLocationsPossibleShow)
def delete_comb_loc(clp_id: uuid.UUID, _: DesktopUser):
    return db_services.CombinationLocationsPossible.delete(clp_id)


@router.post("/{clp_id}/undelete", response_model=schemas.CombinationLocationsPossibleShow)
def undelete_comb_loc(clp_id: uuid.UUID, _: DesktopUser):
    return db_services.CombinationLocationsPossible.undelete(clp_id)