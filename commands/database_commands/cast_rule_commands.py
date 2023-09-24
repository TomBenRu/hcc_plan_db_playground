from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, project_id: UUID, name: str, rule: str):
        self.project_id = project_id
        self.name = name
        self.rule = rule
        self.created_cast_rule: schemas.CastRuleShow | None = None

    def execute(self):
        self.created_cast_rule = db_services.CastRule.create(self.project_id, self.name, self.rule)

    def undo(self):
        db_services.CastRule.delete(self.created_cast_rule.id)

    def redo(self):
        db_services.CastRule.create(self.project_id, self.name, self.rule, self.created_cast_rule.id)
