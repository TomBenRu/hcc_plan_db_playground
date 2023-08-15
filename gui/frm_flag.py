from abc import ABC, abstractmethod

from typing import Callable
from uuid import UUID

from PySide6.QtWidgets import QWidget, QDialog

from database import schemas, db_services, enums
from gui.commands import person_commands, event_commands


class DlgFlagsBuilderABC(ABC):
    def __init__(self, parent: QWidget, object_with_flags: schemas.ModelWithFlags):

        self.parent_widget = parent
        self.object_with_flags: schemas.PersonShow | schemas.EventShow = object_with_flags
        self.object_with_flags__refresh_func: Callable[[UUID], schemas.ModelWithFlags] | None = None
        self.put_in_command: (type[person_commands.PutInFlag] |
                              type[event_commands.PutInFlag] | None) = None
        self.remove_command: (type[person_commands.RemoveFlag] |
                              type[event_commands.RemoveFlag] | None) = None
        self.category: enums.FlagCategories | None = None

    @abstractmethod
    def _generate_field_values(self):
        ...

    @property
    def dlg_flags(self) -> 'DlgFlags':
        return DlgFlags(self.parent_widget, self)


class DlgFlagsBuilderPerson(DlgFlagsBuilderABC):
    def __init__(self, parent: QWidget, person: schemas.PersonShow):
        super().__init__(parent=parent, object_with_flags=person)

    def _generate_field_values(self):
        self.object_with_flags__refresh_func = db_services.Person.get(self.object_with_flags.id)
        self.put_in_command = person_commands.PutInFlag
        self.remove_command = person_commands.RemoveFlag
        self.category = enums.FlagCategories.PERSON


class DlgFlagsBuilderEvent(DlgFlagsBuilderABC):
    def __init__(self, parent: QWidget, event: schemas.EventShow):
        super().__init__(parent=parent, object_with_flags=event)

    def _generate_field_values(self):
        self.object_with_flags__refresh_func = db_services.Event.get(self.object_with_flags.id)
        self.put_in_command = event_commands.PutInFlag
        self.remove_command = event_commands.RemoveFlag
        self.category = enums.FlagCategories.EVENT


class DlgFlags(QDialog):
    def __init__(self, parent: QWidget, builder: DlgFlagsBuilderABC):
        super().__init__(parent=parent)


