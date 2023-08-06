from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, event: schemas.EventCreate):
        self.event = event.copy()
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
        db_services.Event.update_time_of_day(self.event.id, self.new_time_of_day_id)

    def undo(self):
        db_services.Event.update_time_of_day(self.event.id, self.old_time_of_day_id)

    def redo(self):
        db_services.Event.update_time_of_day(self.event.id, self.new_time_of_day_id)


class UpdateFixedCast(Command):
    def __init__(self, event: schemas.EventShow, fixed_cast: str):
        self.event = event
        self.fixed_cast = fixed_cast

    def execute(self):
        db_services.Event.update_fixed_cast(self.event.id, self.fixed_cast)

    def undo(self):
        db_services.Event.update_fixed_cast(self.event.id, self.event.fixed_cast)

    def redo(self):
        db_services.Event.update_fixed_cast(self.event.id, self.fixed_cast)


class Delete(Command):
    def __init__(self, event_id):
        self.event_id = event_id
        self.event = db_services.Event.get(event_id)

    def execute(self):
        db_services.Event.delete(self.event_id)

    def undo(self):
        """todo: Schwierigkeit: Beim Löschen wurden unter Umständen kaskadenweise EventGroups gelöscht.
           diese können auf diese Weise nicht wiederhergestellt werden."""
        self.event_id = db_services.Event.create(self.event)

    def redo(self):
        db_services.Event.delete(self.event_id)