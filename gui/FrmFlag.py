from abc import ABC, abstractmethod
from typing import Callable
from uuid import UUID

from PySide6.QtWidgets import QWidget

from database import schemas
from gui.commands import person_commands, event_commands


class DlgFlagBuilder(ABC):
    def __init__(self, parent: QWidget, object_with_flags: schemas.ModelWithFlags):

        self.parent_widget = parent
        self.object_with_flags: schemas.PersonShow | schemas.EventShow = object_with_flags
        self.object_with_flags__refresh_func: Callable[[UUID], schemas.ModelWithFlags] | None = None
        self.put_in_command: (type[person_commands.PutInFlag] |
                              type[event_commands.PutInFlag] | None) = None
        self.remove_command: (type[person_commands.RemoveFlag] |
                              type[event_commands.RemoveFlag] | None) = None
