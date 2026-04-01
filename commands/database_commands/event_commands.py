"""Command-Klassen für Event (Veranstaltungstermin).

Verwaltet alle Änderungen an Events: Erstellen (legt automatisch EventGroup und
CastGroup an), Löschen (bereinigt beide), Datum-/Tageszeit-Änderungen, Notizen,
Flags und SkillGroups.

`Delete` speichert die komplette Event-Instanz, da beim Undo ein neues Event mit
denselben Daten neu erstellt werden muss (EventGroup und CastGroup werden separat
gelöscht und können nicht direkt wiederhergestellt werden).
"""
import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, event: schemas.EventCreate):
        super().__init__()
        self.event = event.model_copy()
        self.created_event: schemas.EventShow | None = None

    def execute(self):
        self.created_event = db_services.Event.create(self.event)

    def _undo(self):
        db_services.Event.delete(self.created_event.id)

    def _redo(self):
        self.created_event = db_services.Event.create(self.event)


class UpdateTimeOfDay(Command):
    def __init__(self, event: schemas.Event, new_time_of_day_id: UUID):
        super().__init__()
        self.event = event
        self.old_time_of_day_id = self.event.time_of_day.id
        self.new_time_of_day_id = new_time_of_day_id

    def execute(self):
        db_services.Event.update_time_of_day_and_date(self.event.id, self.new_time_of_day_id)

    def _undo(self):
        db_services.Event.update_time_of_day_and_date(self.event.id, self.old_time_of_day_id)

    def _redo(self):
        db_services.Event.update_time_of_day_and_date(self.event.id, self.new_time_of_day_id)


class UpdateTimeOfDays(Command):
    def __init__(self, event_id: UUID, time_of_days: list[schemas.TimeOfDay]):
        super().__init__()
        self.event_id = event_id
        self.new_time_of_days = time_of_days
        self.old_time_of_days = db_services.TimeOfDay.get_time_of_days_from__event(event_id)

    def execute(self):
        db_services.Event.update_time_of_days(self.event_id, self.new_time_of_days)

    def _undo(self):
        db_services.AvailDay.update_time_of_days(self.event_id, self.old_time_of_days)

    def _redo(self):
        db_services.AvailDay.update_time_of_days(self.event_id, self.new_time_of_days)


class UpdateDateTimeOfDay(Command):
    def __init__(self, event: schemas.Event, new_date: datetime.date, new_time_of_day_id: UUID):
        super().__init__()
        self.event = event
        self.new_date = new_date
        self.new_time_of_day_id = new_time_of_day_id
    def execute(self):
        db_services.Event.update_time_of_day_and_date(
            self.event.id, self.new_time_of_day_id, self.new_date)

    def _undo(self):
        db_services.Event.update_time_of_day_and_date(
            self.event.id, self.event.time_of_day.id, self.event.date)

    def _redo(self):
        db_services.Event.update_time_of_day_and_date(
            self.event.id, self.new_time_of_day_id, self.new_date)


class UpdateNotes(Command):
    def __init__(self, event: schemas.EventShow, notes: str):
        super().__init__()
        self.event = event
        self.notes = notes

    def execute(self):
        db_services.Event.update_notes(self.event.id, self.notes)

    def _undo(self):
        db_services.Event.update_notes(self.event.id, self.event.notes)

    def _redo(self):
        db_services.Event.update_notes(self.event.id, self.notes)


class Delete(Command):
    def __init__(self, event_id):
        super().__init__()
        self.event_id = event_id
        self.event_to_delete = db_services.Event.get(event_id)
        self.containing_cast_groups = db_services.CastGroup.get(self.event_to_delete.cast_group.id).parent_groups

    def execute(self):
        db_services.Event.delete(self.event_id)

    def _undo(self):
        self.event_id = db_services.Event.create(self.event_to_delete)

    def _redo(self):
        db_services.Event.delete(self.event_id)


class PutInFlag(Command):
    def __init__(self, event_id: UUID, flag_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.flag_id = flag_id

    def execute(self):
        db_services.Event.put_in_flag(self.event_id, self.flag_id)

    def _undo(self):
        db_services.Event.remove_flag(self.event_id, self.flag_id)

    def _redo(self):
        db_services.Event.put_in_flag(self.event_id, self.flag_id)


class RemoveFlag(Command):
    def __init__(self, event_id: UUID, flag_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.flag_id = flag_id

    def execute(self):
        db_services.Event.remove_flag(self.event_id, self.flag_id)

    def _undo(self):
        db_services.Event.put_in_flag(self.event_id, self.flag_id)

    def _redo(self):
        db_services.Event.remove_flag(self.event_id, self.flag_id)


class AddSkillGroup(Command):
    def __init__(self, event_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.skill_group_id = skill_group_id
        self.event: schemas.EventShow | None = None

    def execute(self):
        self.event = db_services.Event.add_skill_group(self.event_id, self.skill_group_id)

    def _undo(self):
        self.event = db_services.Event.remove_skill_group(self.event_id, self.skill_group_id)

    def _redo(self):
        self.event = db_services.Event.add_skill_group(self.event_id, self.skill_group_id)

class RemoveSkillGroup(Command):
    def __init__(self, event_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.event_id = event_id
        self.skill_group_id = skill_group_id
        self.event: schemas.EventShow | None = None

    def execute(self):
        self.event = db_services.Event.remove_skill_group(self.event_id, self.skill_group_id)

    def _undo(self):
        self.event = db_services.Event.add_skill_group(self.event_id, self.skill_group_id)

    def _redo(self):
        self.event = db_services.Event.remove_skill_group(self.event_id, self.skill_group_id)
