"""Service-Funktionen für Address (Anschrift).

CRUD-Operationen für Adressen innerhalb eines Projekts. Unterstützt sowohl
Soft-Delete (setzt `prep_delete`-Timestamp) als auch hartes Löschen
(`soft_delete=False`).
"""
import datetime
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(address_id: UUID) -> schemas.Address:
    with get_session() as session:
        return schemas.Address.model_validate(session.get(models.Address, address_id))


def get_all_from__project(project_id: UUID, include_prep_delete: bool = False) -> list[schemas.Address]:
    with get_session() as session:
        stmt = select(models.Address).where(models.Address.project_id == project_id)
        if not include_prep_delete:
            stmt = stmt.where(models.Address.prep_delete.is_(None))
        return [schemas.Address.model_validate(a) for a in session.exec(stmt).all()]


def create(address: schemas.AddressCreate) -> schemas.Address:
    log_function_info()
    with get_session() as session:
        addr = models.Address(project=session.get(models.Project, address.project_id),
                              street=address.street, postal_code=address.postal_code,
                              city=address.city, name=address.name)
        session.add(addr)
        session.flush()
        return schemas.Address.model_validate(addr)


def update(address: schemas.Address) -> schemas.Address:
    log_function_info()
    with get_session() as session:
        addr = session.get(models.Address, address.id)
        for k, v in address.model_dump(include={'name', 'street', 'postal_code', 'city'}).items():
            setattr(addr, k, v)
        session.flush()
        return schemas.Address.model_validate(addr)


def delete(address_id: UUID, soft_delete: bool = True) -> schemas.Address | None:
    log_function_info()
    with get_session() as session:
        addr = session.get(models.Address, address_id)
        if soft_delete:
            addr.prep_delete = _utcnow()
            session.flush()
            return schemas.Address.model_validate(addr)
        session.delete(addr)
        return None


def undelete(address_id: UUID) -> schemas.Address:
    log_function_info()
    with get_session() as session:
        addr = session.get(models.Address, address_id)
        addr.prep_delete = None
        session.flush()
        return schemas.Address.model_validate(addr)