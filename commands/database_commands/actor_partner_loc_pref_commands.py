"""Command-Klassen für ActorPartnerLocationPref (Partner-Standortpräferenz).

Enthält:
- `Create`: Erstellt eine neue Partner-Standortpräferenz (Akteur + Partner + Ort);
  Undo/Redo via Soft-Delete (`prep_delete`).
- `DeleteUnused`: Bereinigt alle ungenutzten Partner-Präferenzen einer Person.
- `ReplaceAll`: Ersetzt alle APL-Verknüpfungen eines Modells in einer Transaktion.

Hinweis: Die auskommentierte `Modify`-Klasse ist derzeit nicht in Verwendung.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import actor_partner_location_pref as api_aplp


class Create(Command):
    def __init__(self, actor_partner_loc_pref: schemas.ActorPartnerLocationPrefCreate):
        super().__init__()
        self.actor_partner_loc_pref = actor_partner_loc_pref
        self.created_actor_partner_loc_pref: schemas.ActorPartnerLocationPrefShow | None = None

    def execute(self):
        self.created_actor_partner_loc_pref = api_aplp.create(self.actor_partner_loc_pref)

    def _undo(self):
        api_aplp.delete(self.created_actor_partner_loc_pref.id)

    def _redo(self):
        api_aplp.undelete(self.created_actor_partner_loc_pref.id)

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


class ReplaceAll(Command):
    """Ersetzt alle APL-Verknüpfungen eines Modells in einer einzigen Transaktion.

    Deutlich performanter als einzelne Remove/Create/PutIn-Commands:
    statt N×(Remove+Create+PutIn) Transaktionen → 1 Transaktion.
    """
    def __init__(self, model_class_name: str, model_id: UUID, person_id: UUID,
                 new_prefs: list[tuple[UUID, UUID, float]]):
        super().__init__()
        self.model_class_name = model_class_name
        self.model_id = model_id
        self.person_id = person_id
        self.new_prefs = new_prefs
        self.created_ids: list[UUID] = []
        self.old_apl_ids: list[UUID] = []

    def execute(self):
        self.created_ids, self.old_apl_ids = api_aplp.replace_all_for_model(
            self.model_class_name, self.model_id, self.person_id, self.new_prefs)

    def _undo(self):
        api_aplp.undo_replace_all_for_model(
            self.model_class_name, self.model_id, self.created_ids, self.old_apl_ids)

    def _redo(self):
        self.created_ids, self.old_apl_ids = api_aplp.replace_all_for_model(
            self.model_class_name, self.model_id, self.person_id, self.new_prefs)


class DeleteUnused(Command):
    def __init__(self, person_id):
        super().__init__()
        self.person_id = person_id
        self.deleted_pref_ids: list[UUID] = []

    def execute(self):
        self.deleted_pref_ids = api_aplp.delete_unused(self.person_id)

    def _undo(self):
        for pref_id in self.deleted_pref_ids:
            api_aplp.undelete(pref_id)

    def _redo(self):
        self.deleted_pref_ids = api_aplp.delete_unused(self.person_id)
