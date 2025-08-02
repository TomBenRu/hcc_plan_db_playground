from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    """Command to create a new address."""
    
    def __init__(self, address: schemas.AddressCreate):
        self.address = address
        self.created_address: schemas.Address | None = None

    def execute(self):
        self.created_address = db_services.Address.create(self.address)

    def undo(self):
        if self.created_address:
            db_services.Address.delete(self.created_address.id)

    def redo(self):
        if self.created_address:
            db_services.Address.undelete(self.created_address.id)


class Update(Command):
    """Command to update an existing address."""
    
    def __init__(self, address: schemas.Address):
        self.new_data = address.model_copy()
        self.old_data = db_services.Address.get(address.id)

    def execute(self):
        db_services.Address.update(self.new_data)

    def undo(self):
        db_services.Address.update(self.old_data)

    def redo(self):
        db_services.Address.update(self.new_data)


class Delete(Command):
    """Command to soft delete an address (sets prep_delete)."""
    
    def __init__(self, address_id: UUID):
        self.address_id = address_id
        self.address_data = db_services.Address.get(address_id)

    def execute(self):
        db_services.Address.delete(self.address_id)

    def undo(self):
        db_services.Address.undelete(self.address_id)

    def redo(self):
        db_services.Address.delete(self.address_id)
