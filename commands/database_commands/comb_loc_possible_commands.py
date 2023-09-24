from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, comb_locations_poss: schemas.CombinationLocationsPossibleCreate):
        super().__init__()

        self.comb_loc_poss = comb_locations_poss
        self.created_comb_loc_poss: schemas.CombinationLocationsPossibleShow | None = None

    def execute(self):
        self.created_comb_loc_poss = db_services.CombinationLocationsPossible.create(self.comb_loc_poss)

    def undo(self):
        db_services.CombinationLocationsPossible.delete(self.created_comb_loc_poss.id)

    def redo(self):
        db_services.CombinationLocationsPossible.undelete(self.created_comb_loc_poss.id)


class Delete(Command):
    def __init__(self, comb_locations_poss_id: UUID):
        super().__init__()

        self.comb_loc_poss_id = comb_locations_poss_id

    def execute(self):
        db_services.CombinationLocationsPossible.delete(self.comb_loc_poss_id)

    def undo(self):
        db_services.CombinationLocationsPossible.undelete(self.comb_loc_poss_id)

    def redo(self):
        db_services.CombinationLocationsPossible.delete(self.comb_loc_poss_id)
