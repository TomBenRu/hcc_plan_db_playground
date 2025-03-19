import os
from abc import ABC, abstractmethod
from typing import Callable
from uuid import UUID

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QDialog, QVBoxLayout, QLabel, QTableWidget, QDialogButtonBox, QHBoxLayout, \
    QPushButton

from database import schemas, db_services, enums
from commands import command_base_classes
from commands.database_commands import person_commands, event_commands
from tools.helper_functions import date_to_string


class DlgFlagsBuilderABC(ABC):
    def __init__(self, parent: QWidget, object_with_flags: schemas.ModelWithFlags):

        self.parent_widget = parent
        self.object_with_flags: schemas.PersonShow | schemas.EventShow = object_with_flags
        self.title_text: str | None = None
        self.info_text: str | None = None
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

        self._generate_field_values()

    def _generate_field_values(self):
        self.title_text = QCoreApplication.translate('DlgFlagsBuilderPerson', 'Person Flags')
        self.info_text = QCoreApplication.translate(
            'DlgFlagsBuilderPerson','Here you can add or remove flags for\n{} {}.').format(
            self.object_with_flags.f_name, self.object_with_flags.l_name)
        self.object_with_flags__refresh_func = db_services.Person.get(self.object_with_flags.id)
        self.put_in_command = person_commands.PutInFlag
        self.remove_command = person_commands.RemoveFlag
        self.category = enums.FlagCategories.PERSON


class DlgFlagsBuilderEvent(DlgFlagsBuilderABC):
    def __init__(self, parent: QWidget, event: schemas.EventShow):
        super().__init__(parent=parent, object_with_flags=event)

        self._generate_field_values()

    def _generate_field_values(self):
        self.title_text = QCoreApplication.translate('DlgFlagsBuilderEvent','Event Flags')
        self.info_text = QCoreApplication.translate(
            'DlgFlagsBuilderEvent','Here you can add or remove flags for the event on\n{} {}.').format(
            date_to_string(self.object_with_flags.date),
            self.object_with_flags.time_of_day.name)
        self.object_with_flags__refresh_func = db_services.Event.get(self.object_with_flags.id)
        self.put_in_command = event_commands.PutInFlag
        self.remove_command = event_commands.RemoveFlag
        self.category = enums.FlagCategories.EVENT


class DlgFlags(QDialog):
    def __init__(self, parent: QWidget, builder: DlgFlagsBuilderABC):
        super().__init__(parent=parent)

        self.builder = builder

        self.setWindowTitle(self.builder.title_text)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.lb_info = QLabel(self.builder.info_text)
        self.table_flags = QTableWidget()
        self.layout_buttons = QHBoxLayout()
        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')
        self.bt_add = QPushButton(QIcon(os.path.join(self.path_to_icons, 'plus.png')), self.tr('Add'))
        self.bt_delete = QPushButton(QIcon(os.path.join(self.path_to_icons, 'minus.png')), self.tr('Delete'))
        self.bt_clear = QPushButton(QIcon(os.path.join(self.path_to_icons, 'cross.png')), self.tr('Clear'))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)

        self.layout.addWidget(self.lb_info)
        self.layout.addWidget(self.table_flags)
        self.layout.addLayout(self.layout_buttons)
        self.layout_buttons.addWidget(self.bt_add)
        self.layout_buttons.addWidget(self.bt_delete)
        self.layout_buttons.addWidget(self.bt_clear)
        self.layout.addWidget(self.button_box)

        self.bt_add.clicked.connect(self.add_flag)
        self.bt_delete.clicked.connect(self.delete_flag)
        self.bt_clear.clicked.connect(self.clear_flags)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def add_flag(self):
        ...

    def delete_flag(self):
        ...

    def clear_flags(self):
        ...





