"""Command-Klassen für Address (Anschrift).

Enthält:
- `Create`: Legt eine neue Adresse an; Undo/Redo via Soft-Delete.
- `Update`: Aktualisiert Felder einer bestehenden Adresse; speichert Vorher-Zustand.
- `Delete`: Soft-löscht eine Adresse (setzt `prep_delete`); reversibel.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import address as api_address


class Create(Command):
    """Command to create a new address."""

    def __init__(self, address: schemas.AddressCreate):
        super().__init__()
        self.address = address
        self.created_address: schemas.Address | None = None

    def execute(self):
        self.created_address = db_services.Address.create(self.address)

    def _undo(self):
        if self.created_address:
            db_services.Address.delete(self.created_address.id)

    def _redo(self):
        if self.created_address:
            db_services.Address.undelete(self.created_address.id)


class Update(Command):
    """Command to update an existing address."""

    def __init__(self, address: schemas.Address):
        super().__init__()
        self.new_data = address.model_copy()
        self.old_data = db_services.Address.get(address.id)

    def execute(self):
        api_address.update(self.new_data)

    def _undo(self):
        api_address.update(self.old_data)

    def _redo(self):
        api_address.update(self.new_data)


class Delete(Command):
    """Command to soft delete an address (sets prep_delete)."""

    def __init__(self, address_id: UUID):
        super().__init__()
        self.address_id = address_id
        self.address_data = db_services.Address.get(address_id)

    def execute(self):
        db_services.Address.delete(self.address_id)

    def _undo(self):
        db_services.Address.undelete(self.address_id)

    def _redo(self):
        db_services.Address.delete(self.address_id)
