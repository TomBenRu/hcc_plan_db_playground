from collections import defaultdict
from copy import deepcopy
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, \
    QPushButton, QHBoxLayout

from database import schemas
from gui.commands import command_base_classes


class TreeGroup(QTreeWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()

        self.setColumnCount(2)
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit"])
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSortingEnabled(True)

        self.actor_plan_period = actor_plan_period

        self.setup_tree()

    def dropEvent(self, event: QDropEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item and isinstance(item.data(0, Qt.UserRole), schemas.AvailDay):
            event.ignore()
        else:
            super().dropEvent(event)
            self.expandAll()
            for i in range(self.columnCount()): self.resizeColumnToContents(i)

    def setup_tree(self):
        avail_days = sorted((avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete),
                            key=lambda x: f'{x.day} {x.time_of_day.time_of_day_enum.time_index}')
        def add_parents(children: list[QTreeWidgetItem]):
            curr_parents = {}
            for item in children:
                if isinstance(obj := item.data(0, Qt.UserRole), schemas.AvailDay):
                    group_object = obj.avail_day_group.avail_day_group
                else:
                    group_object = obj.avail_day_group
                if group_object and not group_object.actor_plan_period:
                    if not (group_item := curr_parents.get(group_object.id)):
                        group_item = QTreeWidgetItem(self, ['Gruppe'])
                        group_item.setData(0, Qt.UserRole, group_object)
                        curr_parents[group_object.id] = group_item
                    self.invisibleRootItem().removeChild(item)
                    group_item.addChild(item)
            if curr_parents:
                add_parents(list(curr_parents.values()))

        avd_items = []
        for avd in avail_days:
            item = QTreeWidgetItem(self, ['Verfügbark.', avd.day.strftime('%d.%m'), avd.time_of_day.name])
            item.setData(0, Qt.UserRole, avd)
            avd_items.append(item)
        add_parents(avd_items)


class FrmGroupMode(QWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow, change_group_mode: Callable[[bool], None]):
        super().__init__()

        self.setWindowTitle('Group-Mode')
        self.actor_plan_period = actor_plan_period
        self.change_group_mode = change_group_mode

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.tree_groups = TreeGroup(self.actor_plan_period)
        self.tree_groups.itemClicked.connect(self.edit_item)
        self.tree_groups.expandAll()
        for i in range(self.tree_groups.columnCount()): self.tree_groups.resizeColumnToContents(i)
        self.layout_body.addWidget(self.tree_groups)

        self.layout_mod_buttons = QHBoxLayout()
        self.layout_foot.addLayout(self.layout_mod_buttons)
        self.bt_add_group = QPushButton('Neue Gruppe', clicked=self.add_group)
        self.layout_mod_buttons.addWidget(self.bt_add_group)
        self.bt_remove_group = QPushButton('Gruppe entfernen', clicked=self.remove_group)
        self.layout_mod_buttons.addWidget(self.bt_remove_group)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_groups)
        self.button_box.rejected.connect(self.close)
        self.layout_foot.addWidget(self.button_box)

    def add_group(self):
        new_item = QTreeWidgetItem(self.tree_groups.invisibleRootItem(), ['Gruppe'])
        new_item.setData(0, Qt.UserRole, None)

    def remove_group(self):
        selected_items = self.tree_groups.selectedItems()
        if not selected_items or isinstance(selected_items[0].data(0, Qt.UserRole), schemas.AvailDay):
            return
        selected_item = selected_items[0]
        if selected_item.childCount() == 0:
            if parent := selected_item.parent():
                parent.removeChild(selected_item)
            else:
                index = self.tree_groups.indexOfTopLevelItem(selected_item)
                self.tree_groups.takeTopLevelItem(index)

    def edit_item(self, item: QTreeWidgetItem):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, schemas.AvailDay):
            print(item.text(0), data.day, data.time_of_day.name)
        elif isinstance(data, schemas.AvailDayGroup):
            print(item.text(0), f'{data.nr_avail_day_groups=}')
        else:
            print(item.text(0), data)

    def save_groups(self):
        ...

    def closeEvent(self, event: QCloseEvent) -> None:
        self.change_group_mode(False)
        super().closeEvent(event)

