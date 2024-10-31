from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, skill_group: schemas.SkillGroupCreate):
        self.skill_group = skill_group
        self.created_skill_group: schemas.SkillGroupShow | None = None

    def execute(self):
        self.created_skill_group = db_services.SkillGroup.create(self.skill_group)

    def undo(self):
        if self.created_skill_group:
            db_services.SkillGroup.delete(self.created_skill_group.id)

    def redo(self):
        if self.created_skill_group:
            db_services.SkillGroup.create(self.skill_group, self.created_skill_group.id)