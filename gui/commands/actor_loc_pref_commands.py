from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, actor_loc_pref: schemas.ActorLocationPrefCreate):
        self.actor_loc_pref = actor_loc_pref
        self.created_actor_loc_pref: schemas.ActorLocationPrefShow | None = None

    def execute(self):
        self.created_actor_loc_pref = db_services.ActorLocationPref.create(self.actor_loc_pref)

    def undo(self):
        db_services.ActorLocationPref.delete(self.created_actor_loc_pref.id)

    def redo(self):
        db_services.ActorLocationPref.undelete(self.created_actor_loc_pref.id)
