from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class PutInCombLocPossible(Command):
    def __init__(self, team_id: UUID, comb_loc_poss_id: UUID):

        self.team_id = team_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.Team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.Team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, team_id: UUID, comb_loc_poss_id: UUID):

        self.team_id = team_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.Team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.Team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)
