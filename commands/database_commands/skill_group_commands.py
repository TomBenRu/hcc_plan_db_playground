from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, skill_group: schemas.SkillGroupCreate):
        super().__init__()
        self.skill_group = skill_group
        self.created_skill_group: schemas.SkillGroupShow | None = None

    def execute(self):
        self.created_skill_group = db_services.SkillGroup.create(self.skill_group)

    def _undo(self):
        if self.created_skill_group:
            db_services.SkillGroup.delete(self.created_skill_group.id)

    def _redo(self):
        if self.created_skill_group:
            db_services.SkillGroup.create(self.skill_group, self.created_skill_group.id)


class Update(Command):
    def __init__(self, skill_group: schemas.SkillGroupUpdate):
        super().__init__()
        self.skill_group = skill_group
        self.original_skill_group: schemas.SkillGroupShow = db_services.SkillGroup.get(skill_group.id)
        self.updated_skill_group: schemas.SkillGroupShow | None = None

    def execute(self):
        self.updated_skill_group = db_services.SkillGroup.update(self.skill_group)

    def _undo(self):
        if self.updated_skill_group:
            db_services.SkillGroup.update(
                schemas.SkillGroupUpdate(id=self.original_skill_group.id, skill_id=self.original_skill_group.skill.id,
                                         nr_persons=self.original_skill_group.nr_actors))

    def _redo(self):
        if self.updated_skill_group:
            db_services.SkillGroup.update(self.skill_group)