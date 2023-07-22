from collections import defaultdict
from copy import deepcopy
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QDialogButtonBox, QTreeWidget, QTreeWidgetItem

from database import schemas
from gui.commands import command_base_classes


class TreeGroup(QTreeWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()

        self.itemClicked.connect(self.on_item_clicked)

        self.setColumnCount(2)
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit"])
        self.setDragDropMode(QTreeWidget.InternalMove)

        self.actor_plan_period = actor_plan_period

        self.setup_tree()

    def dropEvent(self, event: QDropEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        # print(item.data(0, Qt.UserRole))
        if item and isinstance(item.data(0, Qt.UserRole), schemas.AvailDay):
            event.ignore()
        else:
            super().dropEvent(event)
            self.expandAll()
            for i in range(self.columnCount()): self.resizeColumnToContents(i)

    def on_item_clicked(self):
        ...

    def setup_tree(self):
        avail_days = sorted((avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete),
                            key=lambda x: f'{x.day} {x.time_of_day.time_of_day_enum.time_index}')
        def add_parents(children: list[QTreeWidgetItem]):
            curr_parents = {}
            for item in children:
                if (obj := item.data(0, Qt.UserRole)).avail_day_group:
                    if not (group_item := curr_parents.get(obj.avail_day_group.id)):
                        group_item = QTreeWidgetItem(self, ['Gruppe'])
                        curr_parents[obj.avail_day_group.id] = group_item
                        group_item.setData(0, Qt.UserRole, obj.avail_day_group)
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
        self.tree_groups.expandAll()
        for i in range(self.tree_groups.columnCount()): self.tree_groups.resizeColumnToContents(i)
        self.layout_body.addWidget(self.tree_groups)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save_groups)
        self.button_box.rejected.connect(self.close)
        self.layout_foot.addWidget(self.button_box)


    def save_groups(self):
        ...

    def closeEvent(self, event: QCloseEvent) -> None:
        self.change_group_mode(False)
        super().closeEvent(event)

