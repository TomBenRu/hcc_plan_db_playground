from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


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

    def get_created_actor_loc_pref(self):
        if not self.created_actor_loc_pref:
            raise LookupError('Keine Einrichtungspräferenz erstellt.')
        else:
            return self.created_actor_loc_pref.id


class DeleteUnused(Command):
    def __init__(self, project_id):
        self.project_id = project_id
        self.deleted_pref_ids: list[UUID] = []

    def execute(self):
        self.deleted_pref_ids = db_services.ActorLocationPref.delete_unused(self.project_id)

    def undo(self):
        for pref_id in self.deleted_pref_ids:
            db_services.ActorLocationPref.undelete(pref_id)

    def redo(self):
        self.deleted_pref_ids = db_services.ActorLocationPref.delete_unused(self.project_id)
