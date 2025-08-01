from uuid import UUID

from commands.command_base_classes import Command
from employee_event import CategoryCreate, db_service, CategoryDetail, ErrorResponseSchema, SuccessResponseSchema, \
    CategoryUpdate


class Create(Command):
    def __init__(self, category_create: CategoryCreate):
        self.db_services = db_service.EmployeeEventService()
        self.category_create = category_create
        self.result: CategoryDetail | ErrorResponseSchema | None = None

    def execute(self):
        self.result = self.db_services.create_category(self.category_create)

    def undo(self):
        if isinstance(self.result, CategoryDetail):
            self.db_services.delete_category(self.result.id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def redo(self):
        if isinstance(self.result, CategoryDetail):
            self.result = self.db_services.undelete_category(self.result.id)


class Update(Command):
    def __init__(self, category_update: CategoryUpdate):
        self.db_services = db_service.EmployeeEventService()
        self.category_update = category_update
        self.result: CategoryDetail | ErrorResponseSchema | None = None
        self.old_category: CategoryDetail = self.db_services.get_category(self.category_update.id)

    def execute(self):
        self.result = self.db_services.update_category(self.category_update)

    def undo(self):
        if isinstance(self.result, CategoryDetail):
            category_update = CategoryUpdate.model_validate(self.old_category)
            self.db_services.update_category(category_update)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def redo(self):
        if isinstance(self.result, CategoryDetail):
            self.db_services.update_category(self.category_update)


class Delete(Command):
    def __init__(self, category_id: UUID):
        self.db_services = db_service.EmployeeEventService()
        self.category_id = category_id
        self.result: SuccessResponseSchema | ErrorResponseSchema | None = None

    def execute(self):
        self.result = self.db_services.delete_category(self.category_id)

    def undo(self):
        if isinstance(self.result, SuccessResponseSchema):
            self.db_services.undelete_category(self.category_id)
        else:
            raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')

    def redo(self):
        if isinstance(self.result, SuccessResponseSchema):
            self.db_services.delete_category(self.category_id)