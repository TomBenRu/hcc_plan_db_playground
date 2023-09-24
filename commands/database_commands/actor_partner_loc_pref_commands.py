from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefCreate):
        self.actor_partner_loc_pref = actor_partner_loc_pref
        self.created_actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow | None = None

    def execute(self):
        self.created_actor_partner_loc_pref = db_services.ActorPartnerLocationPref.create(self.actor_partner_loc_pref)

    def undo(self):
        db_services.ActorPartnerLocationPref.delete(self.created_actor_partner_loc_pref.id)

    def redo(self):
        db_services.ActorPartnerLocationPref.undelete(self.created_actor_partner_loc_pref.id)

    def get_created_actor_partner_loc_pref(self) -> schemas.ActorPartnerLocationPrefShow:
        if not self.created_actor_partner_loc_pref:
            raise LookupError('Keine Einrichtungs-Partner-Präferenz erstellt.')
        else:
            return self.created_actor_partner_loc_pref


# class Modify(Command):
#     """Used to put in or pull out from ..._defaults"""
#     def __init__(self, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow):
#         self.actor_partner_loc_pref = actor_partner_loc_pref
#         self.old_actor_partner_loc_pref = db_services.ActorPartnerLocationPref.get(
#             actor_partner_loc_pref_id=actor_partner_loc_pref.id)
#
#     def execute(self):
#         db_services.ActorPartnerLocationPref.modify(self.actor_partner_loc_pref)
#
#     def undo(self):
#         db_services.ActorPartnerLocationPref.modify(self.old_actor_partner_loc_pref)
#
#     def redo(self):
#         db_services.ActorPartnerLocationPref.modify(self.actor_partner_loc_pref)


class DeleteUnused(Command):
    def __init__(self, person_id):
        self.person_id = person_id
        self.deleted_pref_ids: list[UUID] = []

    def execute(self):
        self.deleted_pref_ids = db_services.ActorPartnerLocationPref.delete_unused(self.person_id)

    def undo(self):
        for pref_id in self.deleted_pref_ids:
            db_services.ActorPartnerLocationPref.undelete(pref_id)

    def redo(self):
        self.deleted_pref_ids = db_services.ActorPartnerLocationPref.delete_unused(self.person_id)
