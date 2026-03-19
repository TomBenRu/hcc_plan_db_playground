"""Command-Klassen für Skill (Qualifikation).

Enthält den vollständigen Skill-Lebenszyklus:
- `Create`: Hartes Löschen im Undo; Redo übergibt die Original-ID.
- `Update`: Name und Notizen; speichert Vorher-Zustand.
- `Delete`: Hartes Löschen; Undo re-erstellt inkl. eventuell vorhandenem
  `prep_delete`-Timestamp (für den Fall, dass der Skill bereits als gelöscht
  markiert war).
- `PrepDelete` / `Undelete`: Soft-Delete-Zyklus für den zweistufigen Löschvorgang.
"""
from uuid import UUID

from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, skill: schemas.SkillCreate):
        super().__init__()
        self.skill = skill
        self.created_skill: schemas.Skill | None = None

    def execute(self):
        self.created_skill = db_services.Skill.create(self.skill)

    def _undo(self):
        if self.created_skill:
            db_services.Skill.delete(self.created_skill.id)

    def _redo(self):
        if self.created_skill:
            db_services.Skill.create(self.skill, self.created_skill.id)


class Update(Command):
    def __init__(self, skill: schemas.SkillUpdate):
        super().__init__()
        self.skill_to_update = skill
        self.skill_original = db_services.Skill.get(skill.id)
        self.updated_skill: schemas.Skill | None = None

    def execute(self):
        self.updated_skill = db_services.Skill.update(self.skill_to_update)

    def _undo(self):
        if self.updated_skill:
            db_services.Skill.update(self.skill_original)

    def _redo(self):
        if self.updated_skill:
            db_services.Skill.update(self.skill_to_update)


class Delete(Command):
    def __init__(self, skill_id: UUID, project_id: UUID):
        super().__init__()
        self.skill_id = skill_id
        self.project_id = project_id
        self.skill_to_delete = db_services.Skill.get(skill_id)

    def execute(self):
        db_services.Skill.delete(self.skill_id)

    def _undo(self):
        db_services.Skill.create(
            schemas.SkillCreate(
                name=self.skill_to_delete.name, notes=self.skill_to_delete.notes, project_id=self.project_id),
            self.skill_id)
        if self.skill_to_delete.prep_delete:
            db_services.Skill.prep_delete(self.skill_id, self.skill_to_delete.prep_delete)

    def _redo(self):
        db_services.Skill.delete(self.skill_id)


class PrepDelete(Command):
    def __init__(self, skill_id: UUID):
        super().__init__()
        self.skill_id = skill_id
        self.skill_deleted: schemas.Skill | None = None

    def execute(self):
        self.skill_deleted = db_services.Skill.prep_delete(self.skill_id)

    def _undo(self):
        db_services.Skill.undelete(self.skill_id)

    def _redo(self):
        self.skill_deleted = db_services.Skill.prep_delete(self.skill_id)


class Undelete(Command):
    def __init__(self, skill_id: UUID):
        super().__init__()
        self.skill_id = skill_id
        self.skill_to_undelete = db_services.Skill.get(skill_id)
        self.skill_undeleted: schemas.Skill | None = None

    def execute(self):
        self.skill_undeleted = db_services.Skill.undelete(self.skill_id)

    def _undo(self):
        db_services.Skill.prep_delete(self.skill_id, self.skill_to_undelete.prep_delete)

    def _redo(self):
        self.skill_undeleted = db_services.Skill.undelete(self.skill_id)
