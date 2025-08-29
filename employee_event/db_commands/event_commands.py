from uuid import UUID

from commands.command_base_classes import Command
from employee_event import EventCreate, EventDetail, EventUpdate, ErrorResponseSchema, SuccessResponseSchema
from employee_event import db_service


class Create(Command):
    def __init__(self, event_create: EventCreate):
        self.db_services = db_service.EmployeeEventService()
        self.event_create = event_create.model_copy()
        self.result: EventDetail | ErrorResponseSchema | None = None

    def execute(self):
        self.result = self.db_services.create_event(self.event_create)

    def undo(self):
        if isinstance(self.result, EventDetail):
            self.db_services.delete_event(self.created_event.id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def redo(self):
        if isinstance(self.result, EventDetail):
            self.result = self.db_services.undelete_event(self.result.id)



class Update(Command):
    def __init__(self, event_update: EventUpdate):
        self.db_services = db_service.EmployeeEventService()
        self.event_update = event_update.model_copy()
        self.result: EventDetail | ErrorResponseSchema | None = None
        self.old_event: EventDetail = self.db_services.get_event(self.event_update.id)

    def execute(self):
        self.result = self.db_services.update_event(self.event_update)

    def undo(self):
        if isinstance(self.result, EventDetail):
            event_update = EventUpdate.model_validate(self.old_event)
            self.db_services.update_event(event_update)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def redo(self):
        if isinstance(self.result, EventDetail):
            self.db_services.update_event(self.event_update)


class UpdateGoogleCalendarEventId(Command):
    def __init__(self, event_id: UUID, google_calendar_event_id: str):
        self.db_services = db_service.EmployeeEventService()
        self.event_id = event_id
        self.google_calendar_event_id = google_calendar_event_id
        self.old_google_calendar_event_id = None
        self.result: SuccessResponseSchema | ErrorResponseSchema | None = None

    def execute(self):
        self.old_google_calendar_event_id = self.db_services.get_event(self.event_id).google_calendar_event_id
        self.result = self.db_services.update_google_calendar_event_id(self.event_id, self.google_calendar_event_id)

    def undo(self):
        self.db_services.update_google_calendar_event_id(self.event_id, self.old_google_calendar_event_id)

    def redo(self):
        self.db_services.update_google_calendar_event_id(self.event_id, self.google_calendar_event_id)


class Delete(Command):
    def __init__(self, event_id: UUID):
        self.db_services = db_service.EmployeeEventService()
        self.event_id = event_id
        self.result: SuccessResponseSchema | ErrorResponseSchema | None = None

    def execute(self):
        self.result = self.db_services.delete_event(self.event_id)

    def undo(self):
        if isinstance(self.result, EventDetail):
            self.db_services.undelete_event(self.event_id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def redo(self):
        if isinstance(self.result, EventDetail):
            self.db_services.delete_event(self.event_id)
