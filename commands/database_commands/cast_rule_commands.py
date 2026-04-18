"""Command-Klassen für CastRule (Besetzungsregel).

Enthält:
- `Create`: Erstellt eine benannte Regel mit Regel-String; Undo löscht hart,
  Redo übergibt die Original-ID für referenzielle Stabilität.
- `Update`: Ändert Name und/oder Regel-String; speichert Vorher-Zustand.
- `SetPrepDelete`: Soft-löscht eine CastRule; Undo hebt die Markierung auf.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import cast_rule as api_cast_rule


class Create(Command):
    def __init__(self, project_id: UUID, name: str, rule: str):
        super().__init__()
        self.project_id = project_id
        self.name = name
        self.rule = rule
        self.created_cast_rule: schemas.CastRuleShow | None = None

    def execute(self):
        self.created_cast_rule = api_cast_rule.create(self.project_id, self.name, self.rule)

    def _undo(self):
        api_cast_rule.delete(self.created_cast_rule.id)

    def _redo(self):
        api_cast_rule.create(self.project_id, self.name, self.rule, self.created_cast_rule.id)


class Update(Command):
    def __init__(self, cast_rule_id: UUID, name: str, rule: str):
        super().__init__()
        self.cast_rule_id = cast_rule_id
        self.cast_rule: schemas.CastRuleShow = db_services.CastRule.get(cast_rule_id)
        self.name = name
        self.rule = rule
        self.updated_cast_rule: schemas.CastRuleShow | None = None

    def execute(self):
        self.updated_cast_rule = api_cast_rule.update(self.cast_rule_id, self.name, self.rule)

    def _undo(self):
        api_cast_rule.update(self.cast_rule_id, self.cast_rule.name, self.cast_rule.rule)

    def _redo(self):
        api_cast_rule.update(self.cast_rule_id, self.name, self.rule)

class SetPrepDelete(Command):
    def __init__(self, cast_rule_id: UUID):
        super().__init__()
        self.cast_rule_id = cast_rule_id
        self.updated_cast_rule: schemas.CastRuleShow | None = None

    def execute(self):
        self.updated_cast_rule = api_cast_rule.set_prep_delete(self.cast_rule_id)

    def _undo(self):
        api_cast_rule.undelete(self.cast_rule_id)

    def _redo(self):
        api_cast_rule.set_prep_delete(self.cast_rule_id)


