import functools
import json
import pprint
from collections import defaultdict
from copy import deepcopy
from typing import Callable, Sequence

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QCloseEvent, QDropEvent, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, \
    QPushButton, QHBoxLayout, QDialog, QMessageBox, QApplication

from database import schemas, db_services
from gui.commands import command_base_classes, avail_day_group_commands


TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__AVAIL_DAY = 5


# @functools.total_ordering
class TreeWidgetItemUser(QTreeWidgetItem):

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        if column != 1:
            # Verwende die Standard-Sortierreihenfolge für andere Spalten
            print('Standard-Sortierreihenfolge')
            return self.text(column) < other.text(column)
        # Sortiere nach benutzerdefinierten Daten in Spalte TREE_ITEM_DATA_COLUMN__AVAIL_DAY
        my_avail_day: schemas.AvailDay = self.data(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.UserRole)
        other_avail_day: schemas.AvailDay = other.data(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.UserRole)
        if my_avail_day:
            my_value = f'{my_avail_day.day} {my_avail_day.time_of_day.time_of_day_enum.time_index:02}'
        elif not other_avail_day:
            return (
                self.treeWidget().header().sortIndicatorOrder()
                == Qt.SortOrder.DescendingOrder
                if db_services.AvailDayGroup.get_child_groups_from__parent_group(
                    self.data(
                        TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole
                    ).id
                )
                else self.treeWidget().header().sortIndicatorOrder()
                == Qt.SortOrder.AscendingOrder
            )
        else:
            return self.treeWidget().header().sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
        if other_avail_day:
            other_value = f'{other_avail_day.day} {other_avail_day.time_of_day.time_of_day_enum.time_index:02}'
        elif not my_avail_day:
            return (
                self.treeWidget().header().sortIndicatorOrder()
                == Qt.SortOrder.AscendingOrder
                if db_services.AvailDayGroup.get_child_groups_from__parent_group(
                    other.data(
                        TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole
                    ).id
                )
                else self.treeWidget().header().sortIndicatorOrder()
                == Qt.SortOrder.DescendingOrder
            )
        else:
            return self.treeWidget().header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder
        print(f'{my_value=} {other_value=}')
        return my_value < other_value



class TreeGroup(QTreeWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow,
                 slot_item_moved: Callable[[QTreeWidgetItem, QTreeWidgetItem], None]):
        super().__init__()

        # self.setIndentation(30)
        self.setColumnCount(3)
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit"])
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSortingEnabled(True)
        self.invisibleRootItem().setData(
            TREE_ITEM_DATA_COLUMN__GROUP,
            Qt.ItemDataRole.UserRole,
            db_services.AvailDayGroup.get_master_from__actor_plan_period(actor_plan_period.id)
        )

        self.actor_plan_period = actor_plan_period
        self.slot_item_moved = slot_item_moved

        self.curr_item: QTreeWidgetItem | None = None

        self.setup_tree()
        self.expand_all()

    def mimeData(self, items: Sequence[QTreeWidgetItem]) -> QtCore.QMimeData:
        self.curr_item = items[0]
        return super().mimeData(items)
    def dropEvent(self, event: QDropEvent) -> None:
        item = self.itemAt(event.position().toPoint())
        if item and item.data(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.ItemDataRole.UserRole):
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
                if avail_day := db_services.AvailDay.get_from__avail_day_group(child.id):
                    item = TreeWidgetItemUser(parent, ['Verfügbar',
                                                    avail_day.day.strftime('%d.%m.%y'), avail_day.time_of_day.name])
                    item.setData(0, Qt.ItemDataRole.ForegroundRole, QColor('#5a009f'))
                    item.setData(1, Qt.ItemDataRole.ForegroundRole, QColor('blue'))
                    item.setData(2, Qt.ItemDataRole.ForegroundRole, QColor('#9f0057'))
                    item.setData(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.ItemDataRole.UserRole, avail_day)
                else:
                    childs = db_services.AvailDayGroup.get_child_groups_from__parent_group(child.id)
                    item = TreeWidgetItemUser(parent, ['Gruppe'])
                    add_children(item, childs)
                item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, child)

        for child in db_services.AvailDayGroup.get_child_groups_from__parent_group(master_group.id):
            if avail_day := db_services.AvailDay.get_from__avail_day_group(child.id):
                item = TreeWidgetItemUser(self,
                                       ['Verfügbar', avail_day.day.strftime('%d.%m.%y'), avail_day.time_of_day.name])
                item.setData(0, Qt.ItemDataRole.ForegroundRole, QColor('#5a009f'))
                item.setData(1, Qt.ItemDataRole.ForegroundRole, QColor('blue'))
                item.setData(2, Qt.ItemDataRole.ForegroundRole, QColor('#9f0057'))
                item.setData(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.ItemDataRole.UserRole, avail_day)
            else:
                item = TreeWidgetItemUser(self, ['Gruppe'])
                children = db_services.AvailDayGroup.get_child_groups_from__parent_group(child.id)
                add_children(item, children)
            item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, child)

        self.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    def refresh_tree(self):
        self.reload_actor_plan_period()
        self.clear()
        self.setup_tree()
        self.expand_all()

    def expand_all(self):
        self.expandAll()
        for i in range(self.columnCount()): self.resizeColumnToContents(i)
    def reload_actor_plan_period(self):
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)


class DlgGroupMode(QDialog):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.setWindowTitle('Group-Mode')
        self.resize(280, 400)
        self.actor_plan_period = actor_plan_period

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.simplified = False

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.tree_groups = TreeGroup(self.actor_plan_period, self.item_moved)
        self.tree_groups.itemClicked.connect(self.edit_item)
        self.layout_body.addWidget(self.tree_groups)
        self.resize_dialog()

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

    def add_group(self):
        master_group = db_services.AvailDayGroup.get_master_from__actor_plan_period(self.actor_plan_period.id)
        create_command = avail_day_group_commands.Create(avail_day_group_id=master_group.id)
        self.controller.execute(create_command)
        new_item = TreeWidgetItemUser(self.tree_groups.invisibleRootItem(), ['Gruppe'])
        new_item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, create_command.created_group)
        self.resize_dialog()

    def remove_group(self):
        selected_items = self.tree_groups.selectedItems()
        if not selected_items or isinstance(selected_items[0].data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                   Qt.ItemDataRole.UserRole), schemas.AvailDay):
            return
        selected_item = selected_items[0]
        data: schemas.AvailDayGroup = selected_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        if selected_item.childCount() == 0:
            if parent := selected_item.parent():
                parent.removeChild(selected_item)
            else:
                index = self.tree_groups.indexOfTopLevelItem(selected_item)
                self.tree_groups.takeTopLevelItem(index)
        self.controller.execute(avail_day_group_commands.Delete(data.id))

    def item_moved(self, moved_item: QTreeWidgetItem, moved_to: QTreeWidgetItem):
        object_to_move = moved_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        if moved_to:
            obj_to_move_to: schemas.AvailDayGroup = moved_to.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        else:
            obj_to_move_to = self.tree_groups.invisibleRootItem().data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        self.controller.execute(avail_day_group_commands.SetNewParent(object_to_move.id, obj_to_move_to.id))

    def edit_item(self, item: QTreeWidgetItem):
        # sourcery skip: use-named-expression
        data_avail_day_group = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        data_avail_day = item.data(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.ItemDataRole.UserRole)
        if data_avail_day:
            print(item.text(0), data_avail_day.day, data_avail_day.time_of_day.name)
        else:
            print(item.text(0), f'{data_avail_day_group.id=}, {data_avail_day_group.nr_avail_day_groups=}')

    def get_all_items(self) -> list[QTreeWidgetItem]:
        all_items = []

        def recurse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                all_items.append(child)
                recurse(child)

        recurse(self.tree_groups.invisibleRootItem())
        return all_items

    def alert_solo_childs(self):
        all_items = self.get_all_items()
        for item in all_items:
            if item.childCount() == 1:
                if avail_day := item.child(0).data(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.ItemDataRole.UserRole):
                    QMessageBox.critical(self, 'Gruppenmodus',
                                         f'Mindestens eine Gruppe hat nur einen Termin: '
                                         f'{avail_day.day.strftime("%d.%m.%y")} ({avail_day.time_of_day.name})\n'
                                         f'Bitte korrigieren Sie das.')
                else:
                    QMessageBox.critical(self, 'Gruppenmodus',
                                         f'Mindestens eine Gruppe beinhaltet nur eine Gruppe\n'
                                         f'Bitte korrigieren Sie das.')
                return True
        return False

    def delete_unused_groups(self):
        all_items = self.get_all_items()
        to_delete: list[schemas.AvailDayGroup] = []
        for item in all_items:
            avail_day = item.data(TREE_ITEM_DATA_COLUMN__AVAIL_DAY, Qt.ItemDataRole.UserRole)
            if not avail_day and not item.childCount():
                to_delete.append(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole))

        if not to_delete:
            return self.alert_solo_childs()
        else:
            self.simplified = True
        for group in to_delete:
            self.controller.execute(avail_day_group_commands.Delete(group.id))
        self.reload_actor_plan_period()
        self.refresh_tree()

        return self.delete_unused_groups()

    def accept(self):
        if self.delete_unused_groups():
            return
        if self.simplified:
            QMessageBox.information(self, 'Gruppenmodus',
                                    'Die Gruppenstruktur wurde durch Entfernen unnötiger Gruppen vereinfacht.')
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def reload_actor_plan_period(self):
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)

    def refresh_tree(self):
        self.tree_groups.refresh_tree()
        self.resize_dialog()

    def resize_dialog(self):
        height = self.tree_groups.header().height()
        for item in self.get_all_items():
            height += self.tree_groups.visualItemRect(item).height()

        if self.tree_groups.horizontalScrollBar().isVisible():
            height += self.tree_groups.horizontalScrollBar().height()

        with open('config.json') as f:
            json_data = json.load(f)
        screen_width, screen_height = json_data['screen_size']['width'], json_data['screen_size']['height']

        self.resize(self.size().width(), min(height + 100, screen_height - 40))
