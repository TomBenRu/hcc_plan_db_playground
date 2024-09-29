import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, event: schemas.EventCreate):
        self.event = event.model_copy()
        self.created_event: schemas.EventShow | None = None

    def execute(self):
        self.created_event = db_services.Event.create(self.event)

    def undo(self):
        db_services.Event.delete(self.created_event.id)

    def redo(self):
        self.created_event = db_services.Event.create(self.event)


class UpdateTimeOfDay(Command):
    def __init__(self, event: schemas.EventShow, new_time_of_day_id: UUID):
        self.event = event
        self.old_time_of_day_id = self.event.time_of_day.id
        self.new_time_of_day_id = new_time_of_day_id

    def execute(self):
        db_services.Event.update_time_of_day_and_date(self.event.id, self.new_time_of_day_id)

    def undo(self):
        db_services.Event.update_time_of_day_and_date(self.event.id, self.old_time_of_day_id)

    def redo(self):
        db_services.Event.update_time_of_day_and_date(self.event.id, self.new_time_of_day_id)


class UpdateDateTimeOfDay(Command):
    def __init__(self, event: schemas.Event, new_date: datetime.date, new_time_of_day_id: UUID):
        self.event = event
        self.new_date = new_date
        self.new_time_of_day_id = new_time_of_day_id
        self.updated_event: schemas.EventShow | None = None

    def execute(self):
        self.updated_event = db_services.Event.update_time_of_day_and_date(
            self.event.id, self.new_time_of_day_id, self.new_date)

    def undo(self):
        self.updated_event = db_services.Event.update_time_of_day_and_date(
            self.event.id, self.event.time_of_day.id, self.event.date)

    def redo(self):
        self.updated_event = db_services.Event.update_time_of_day_and_date(
            self.event.id, self.new_time_of_day_id, self.new_date)


class UpdateNotes(Command):
    def __init__(self, event: schemas.EventShow, notes: str):
        self.event = event
        self.notes = notes
        self.updated_event: schemas.EventShow | None = None

    def execute(self):
        self.updated_event = db_services.Event.update_notes(self.event.id, self.notes)

    def undo(self):
        db_services.Event.update_notes(self.event.id, self.event.notes)

    def redo(self):
        db_services.Event.update_notes(self.event.id, self.notes)


class Delete(Command):
    def __init__(self, event_id):
        self.event_id = event_id
        self.event_to_delete = db_services.Event.get(event_id)
        self.containing_cast_groups = db_services.CastGroup.get(self.event_to_delete.cast_group.id).parent_groups

    def execute(self):
        db_services.Event.delete(self.event_id)

    def undo(self):
        self.event_id = db_services.Event.create(self.event_to_delete)

    def redo(self):
        db_services.Event.delete(self.event_id)


class PutInFlag(Command):
    def __init__(self, event_id: UUID, flag_id: UUID):
        self.event_id = event_id
        self.flag_id = flag_id

    def execute(self):
        db_services.Event.put_in_flag(self.event_id, self.flag_id)

    def undo(self):
        db_services.Event.remove_flag(self.event_id, self.flag_id)

    def redo(self):
        db_services.Event.put_in_flag(self.event_id, self.flag_id)


class RemoveFlag(Command):
    def __init__(self, event_id: UUID, flag_id: UUID):
        self.event_id = event_id
        self.flag_id = flag_id

    def execute(self):
        db_services.Event.remove_flag(self.event_id, self.flag_id)

    def undo(self):
        db_services.Event.put_in_flag(self.event_id, self.flag_id)

    def redo(self):
        db_services.Event.remove_flag(self.event_id, self.flag_id)
