from typing import Callable

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QTreeWidget,
                               QTreeWidgetItem)

from database import schemas
from gui.commands import command_base_classes


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, tree_widget_item: QTreeWidgetItem | QTreeWidget = None):
        super().__init__(tree_widget_item)


class TreeWidget(QTreeWidget):
    def __init__(self, location_plan_period: schemas.LocationPlanPeriodShow,
                 slot_item_moved: Callable[[TreeWidgetItem, TreeWidgetItem, TreeWidgetItem], None]):
        super().__init__()


class DlgCastGroups(QDialog):
    def __init__(self, parent: QWidget, location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent)

        self.setWindowTitle('Cast Groups')
        self.resize(400, 400)

        self.location_plan_period = location_plan_period

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.tree_groups = TreeWidget(self.builder, self.item_moved)
        self.tree_groups.itemDoubleClicked.connect(self.edit_item)
        self.tree_groups.setExpandsOnDoubleClick(False)
        self.layout_body.addWidget(self.tree_groups)

        self.layout_mod_buttons = QHBoxLayout()
        self.layout_foot.addLayout(self.layout_mod_buttons)
        self.bt_add_group = QPushButton('Neue Gruppe', clicked=self.add_group)
        self.layout_mod_buttons.addWidget(self.bt_add_group)
        self.bt_remove_group = QPushButton('Gruppe entfernen', clicked=self.remove_group)
        self.layout_mod_buttons.addWidget(self.bt_remove_group)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                           QDialogButtonBox.StandardButton.Cancel)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)
