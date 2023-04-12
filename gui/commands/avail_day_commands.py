import datetime
from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, avail_day: schemas.AvailDayCreate):
        self.avail_day = avail_day.copy()
        self.created_avail_day: schemas.AvailDayShow | None = None

    def execute(self):
        self.created_avail_day = db_services.AvailDay.create(self.avail_day)

    def undo(self):
        db_services.AvailDay.delete(self.created_avail_day.id)

    def redo(self):
        self.created_avail_day = db_services.AvailDay.create(self.avail_day)


class Delete(Command):
    def __init__(self, avail_day_id: UUID):
        self.avail_day_id = avail_day_id
        self.deleted_avail_day = db_services.AvailDay.get(avail_day_id)

    def execute(self):
        db_services.AvailDay.delete(self.avail_day_id)

    def undo(self):
        """Schwierigkeit: Beim Löschen wurden unter Umständen caskadenweise AvailDayGroups gelöscht.
        diese können auf diese Weise nicht wiederhergestellt werden."""
        db_services.AvailDay.create(self.deleted_avail_day)

    def redo(self):
        db_services.AvailDay.delete(self.avail_day_id)
