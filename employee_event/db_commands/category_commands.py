from uuid import UUID

from commands.command_base_classes import Command
from employee_event import CategoryCreate, db_service, CategoryDetail, ErrorResponseSchema, SuccessResponseSchema, \
    CategoryUpdate
from gui.api_client import employee_event_category as api_cat


class Create(Command):
    def __init__(self, category_create: CategoryCreate):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads
        self.category_create = category_create
        self.result: CategoryDetail | ErrorResponseSchema | None = None

    def execute(self):
        self.result = api_cat.create(self.category_create)

    def _undo(self):
        if isinstance(self.result, CategoryDetail):
            api_cat.delete(self.result.id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def _redo(self):
        if isinstance(self.result, CategoryDetail):
            api_cat.undelete(self.result.id)


class Update(Command):
    def __init__(self, category_update: CategoryUpdate):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads
        self.category_update = category_update
        self.result: CategoryDetail | ErrorResponseSchema | None = None
        self.old_category: CategoryDetail = self.db_services.get_category(self.category_update.id)

    def execute(self):
        self.result = api_cat.update(self.category_update)

    def _undo(self):
        if isinstance(self.result, CategoryDetail):
            category_update = CategoryUpdate.model_validate(self.old_category)
            api_cat.update(category_update)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def _redo(self):
        if isinstance(self.result, CategoryDetail):
            api_cat.update(self.category_update)


class Delete(Command):
    def __init__(self, category_id: UUID):
        super().__init__()
        self.db_services = db_service.EmployeeEventService()  # fuer reads
        self.category_id = category_id
        self.result: SuccessResponseSchema | ErrorResponseSchema | None = None

    def execute(self):
        self.result = api_cat.delete(self.category_id)

    def _undo(self):
        if isinstance(self.result, SuccessResponseSchema):
            api_cat.undelete(self.category_id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def _redo(self):
        if isinstance(self.result, SuccessResponseSchema):
            api_cat.delete(self.category_id)