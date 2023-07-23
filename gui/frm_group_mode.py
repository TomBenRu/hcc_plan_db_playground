import pprint
from collections import defaultdict
from copy import deepcopy
from typing import Callable, Sequence

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QDropEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, \
    QPushButton, QHBoxLayout, QDialog, QMessageBox

from database import schemas, db_services
from gui.commands import command_base_classes, avail_day_group_commands


class TreeGroup(QTreeWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow,
                 slot_item_moved: Callable[[QTreeWidgetItem, QTreeWidgetItem], None]):
        super().__init__()

        self.setColumnCount(2)
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit"])
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSortingEnabled(True)
        self.invisibleRootItem().setData(
            0, Qt.UserRole, db_services.AvailDayGroup.get_master_from__actor_plan_period(actor_plan_period.id)
        )

        self.actor_plan_period = actor_plan_period
        self.slot_item_moved = slot_item_moved

        self.curr_item: QTreeWidgetItem | None = None

        self.setup_tree()

    def mimeData(self, items: Sequence[QTreeWidgetItem]) -> QtCore.QMimeData:
        self.curr_item = items[0]
        return super().mimeData(items)
    def dropEvent(self, event: QDropEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item and isinstance(item.data(0, Qt.UserRole), schemas.AvailDay):
            event.ignore()
        else:
            super().dropEvent(event)
            self.expandAll()
            for i in range(self.columnCount()): self.resizeColumnToContents(i)
            self.slot_item_moved(self.curr_item, item)

    def setup_tree(self):
        master_group = db_services.AvailDayGroup.get_master_from__actor_plan_period(self.actor_plan_period.id)

        def add_children(parent: QTreeWidgetItem, children: list[schemas.AvailDayGroupShow]):
            for child in children:
                childs = db_services.AvailDayGroup.get_child_groups_from__parent_group(child.id)
                if childs:
                    item = QTreeWidgetItem(parent, ['Gruppe'])
                    item.setData(0, Qt.UserRole, child)
                    add_children(item, childs)
                else:
                    avail_day = db_services.AvailDay.get_from__avail_day_group(child.id)
                    if not avail_day:  # AvailDayGroup kann gelöscht werden, weil sie weder eine AvailDayGroup noch einen AvailDay enthält.
                        avail_day_group_commands.Delete(child.id).execute()
                        continue
                    item = QTreeWidgetItem(parent, ['Verfügbar', avail_day.day.strftime('%d.%m.%y'), avail_day.time_of_day.name])
                    item.setData(0, Qt.UserRole, avail_day)

        for child in db_services.AvailDayGroup.get_child_groups_from__parent_group(master_group.id):
            children = db_services.AvailDayGroup.get_child_groups_from__parent_group(child.id)
            if children:
                item = QTreeWidgetItem(self, ['Gruppe'])
                item.setData(0, Qt.UserRole, child)
                add_children(item, children)
            else:
                avail_day = db_services.AvailDay.get_from__avail_day_group(child.id)
                if not avail_day:  # AvailDayGroup kann gelöscht werden, weil sie weder eine AvailDayGroup noch einen AvailDay enthält.
                    avail_day_group_commands.Delete(child.id).execute()
                    continue
                item = QTreeWidgetItem(self, ['Verfügbar', avail_day.day.strftime('%d.%m.%y'), avail_day.time_of_day.name])
                item.setData(0, Qt.UserRole, avail_day)


class DlgGroupMode(QDialog):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.setWindowTitle('Group-Mode')
        self.actor_plan_period = actor_plan_period

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.tree_groups = TreeGroup(self.actor_plan_period, self.item_moved)
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
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def add_group(self):
        master_group = db_services.AvailDayGroup.get_master_from__actor_plan_period(self.actor_plan_period.id)
        create_command = avail_day_group_commands.Create(avail_day_group_id=master_group.id)
        self.controller.execute(create_command)
        new_item = QTreeWidgetItem(self.tree_groups.invisibleRootItem(), ['Gruppe'])
        new_item.setData(0, Qt.UserRole, create_command.created_group)

    def remove_group(self):
        selected_items = self.tree_groups.selectedItems()
        if not selected_items or isinstance(selected_items[0].data(0, Qt.UserRole), schemas.AvailDay):
            return
        selected_item = selected_items[0]
        data: schemas.AvailDayGroup = selected_item.data(0, Qt.UserRole)
        if selected_item.childCount() == 0:
            if parent := selected_item.parent():
                parent.removeChild(selected_item)
            else:
                index = self.tree_groups.indexOfTopLevelItem(selected_item)
                self.tree_groups.takeTopLevelItem(index)
        self.controller.execute(avail_day_group_commands.Delete(data.id))

    def item_moved(self, moved_item: QTreeWidgetItem, moved_to: QTreeWidgetItem):
        if isinstance(obj := moved_item.data(0, Qt.UserRole), schemas.AvailDayGroup):
            object_to_move = obj
        elif isinstance(obj, schemas.AvailDay):
            object_to_move = obj.avail_day_group
        else:
            raise AssertionError('Das zu verschiebende Object hat kein Schema.')

        if moved_to:
            obj_to_move_to: schemas.AvailDayGroup = moved_to.data(0, Qt.UserRole)
        else:
            obj_to_move_to = self.tree_groups.invisibleRootItem().data(0, Qt.UserRole)
        print(f'{object_to_move.id=}\n{obj_to_move_to.id=}')

        self.controller.execute(avail_day_group_commands.SetNewParent(object_to_move.id, obj_to_move_to.id))

    def edit_item(self, item: QTreeWidgetItem):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, schemas.AvailDay):
            print(item.text(0), data.day, data.time_of_day.name)
        elif isinstance(data, schemas.AvailDayGroup):
            print(item.text(0), f'{data.id=}, {data.nr_avail_day_groups=}')
        else:
            print(item.text(0), data)

    def get_all_items(self) -> list[QTreeWidgetItem]:
        all_items = []

        def recurse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                all_items.append(child)
                recurse(child)

        recurse(self.tree_groups.invisibleRootItem())
        return all_items

    def accept(self):
        all_items = self.get_all_items()
        to_delete: list[schemas.AvailDayGroup] = []
        for item in all_items:
            if isinstance((data:=item.data(0, Qt.UserRole)), schemas.AvailDayGroup):
                if not item.childCount():
                    to_delete.append(data)
                if item.childCount() == 1:
                    if isinstance(data:=item.child(0).data(0, Qt.UserRole), schemas.AvailDay):
                        QMessageBox.critical(self, 'Gruppenmodus',
                                             f'Mindestens eine Gruppe hat nur einen Termin: {data.day}\n'
                                             f'Bitte korrigieren Sie das.')
                    else:
                        QMessageBox.critical(self, 'Gruppenmodus',
                                             f'Mindestens eine Gruppe beinhaltet nur eine Gruppe\n'
                                             f'Bitte korrigieren Sie das.')
                    return
        for group in to_delete:
            avail_day_group_commands.Delete(group.id).execute()
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

