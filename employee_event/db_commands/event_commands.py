from uuid import UUID

from commands.command_base_classes import Command
from employee_event import EventCreate, EventDetail, EventUpdate, ErrorResponseSchema, SuccessResponseSchema
from employee_event import db_service
from gui.api_client import employee_event as api_ee


class Create(Command):
    def __init__(self, event_create: EventCreate):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads (get_event)
        self.event_create = event_create.model_copy()
        self.result: EventDetail | ErrorResponseSchema | None = None

    def execute(self):
        self.result = api_ee.create(self.event_create)

    def _undo(self):
        if isinstance(self.result, EventDetail):
            api_ee.delete(self.result.id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def _redo(self):
        if isinstance(self.result, EventDetail):
            api_ee.undelete(self.result.id)


class Update(Command):
    def __init__(self, event_update: EventUpdate):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads
        self.event_update = event_update.model_copy()
        self.result: EventDetail | ErrorResponseSchema | None = None
        self.old_event: EventDetail = self.db_services.get_event(self.event_update.id)

    def execute(self):
        self.result = api_ee.update(self.event_update)

    def _undo(self):
        if isinstance(self.result, EventDetail):
            event_update = EventUpdate.model_validate(self.old_event)
            api_ee.update(event_update)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def _redo(self):
        if isinstance(self.result, EventDetail):
            api_ee.update(self.event_update)


class UpdateGoogleCalendarEventId(Command):
    def __init__(self, event_id: UUID, google_calendar_event_id: str):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads
        self.event_id = event_id
        self.google_calendar_event_id = google_calendar_event_id
        self.old_google_calendar_event_id = None
        self.result: SuccessResponseSchema | ErrorResponseSchema | None = None

    def execute(self):
        self.old_google_calendar_event_id = self.db_services.get_event(self.event_id).google_calendar_event_id
        self.result = api_ee.update_google_calendar_id(self.event_id, self.google_calendar_event_id)

    def _undo(self):
        api_ee.update_google_calendar_id(self.event_id, self.old_google_calendar_event_id)

    def _redo(self):
        api_ee.update_google_calendar_id(self.event_id, self.google_calendar_event_id)


class Delete(Command):
    def __init__(self, event_id: UUID):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads
        self.event_id = event_id
        self.result: SuccessResponseSchema | ErrorResponseSchema | None = None

    def execute(self):
        self.result = api_ee.delete(self.event_id)

    def _undo(self):
        if isinstance(self.result, SuccessResponseSchema):
            api_ee.undelete(self.event_id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def _redo(self):
        if isinstance(self.result, SuccessResponseSchema):
            api_ee.delete(self.event_id)