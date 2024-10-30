from uuid import UUID

from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, skill: schemas.SkillCreate):
        self.skill = skill
        self.created_skill: schemas.Skill | None = None

    def execute(self):
        self.created_skill = db_services.Skills.create(self.skill)

    def undo(self):
        if self.created_skill:
            db_services.Skills.delete(self.created_skill.id)

    def redo(self):
        if self.created_skill:
            db_services.Skills.create(self.skill, self.created_skill.id)


class Update(Command):
    def __init__(self, skill: schemas.SkillUpdate):
        self.skill_to_update = skill
        self.skill_original = db_services.Skills.get(skill.id)
        self.updated_skill: schemas.Skill | None = None

    def execute(self):
        self.updated_skill = db_services.Skills.update(self.skill_to_update)

    def undo(self):
        if self.updated_skill:
            db_services.Skills.update(self.skill_original)

    def redo(self):
        if self.updated_skill:
            db_services.Skills.update(self.skill_to_update)


class Delete(Command):
    def __init__(self, skill_id: UUID):
        self.skill_id = skill_id
        self.skill_deleted: schemas.Skill | None = None

    def execute(self):
        self.skill_deleted = db_services.Skills.prep_delete(self.skill_id)

    def undo(self):
        db_services.Skills.undelete(self.skill_id)

    def redo(self):
        self.skill_deleted = db_services.Skills.prep_delete(self.skill_id)