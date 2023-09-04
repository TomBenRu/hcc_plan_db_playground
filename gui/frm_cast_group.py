from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QTreeWidget,
                               QTreeWidgetItem)

from database import schemas, db_services
from gui.commands import command_base_classes, cast_group_commands


TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR = 0
TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR = 1
TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__EVENT = 5
TREE_HEAD_COLUMN__NR_GROUPS = 3
TREE_HEAD_COLUMN__PRIORITY = 4


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

        self.tree_groups = TreeWidget(self.location_plan_period, self.item_moved)
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

    def add_group(self):
        create_command = cast_group_commands.Create(self.location_plan_period.id)
        self.controller.execute(create_command)
        self.tree_groups.nr_main_groups += 1

        new_item = TreeWidgetItem(self.tree_groups.invisibleRootItem())
        new_item.configure(create_command.created_cast_group, None, self.tree_groups.nr_main_groups, 0)

    def remove_group(self):
        selected_items = self.tree_groups.selectedItems()
        selected_item = selected_items[0]
        if not selected_items or selected_item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
            return
        data: schemas.CastGroupShow = selected_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        if selected_item.childCount() == 0:
            if parent_item := selected_item.parent():
                parent_item.removeChild(selected_item)
                parent_group = db_services.CastGroup.get(
                    parent_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            else:
                index = self.tree_groups.indexOfTopLevelItem(selected_item)
                self.tree_groups.takeTopLevelItem(index)
                parent_group = db_services.CastGroup.get(
                    self.tree_groups.invisibleRootItem().data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
                )
            self.controller.execute(cast_group_commands.Delete(data.id))

            # Weil sich nr_groups durch Inkonsistenzen geändert haben könnte:
            nr_groups = self.builder.get_nr_groups_from_group(parent_group)
            text_nr_groups = str(nr_groups) if nr_groups else 'alle'
            if parent_item:
                parent_item.setText(TREE_HEAD_COLUMN__NR_GROUPS, text_nr_groups)
            else:
                self.tree_groups.invisibleRootItem().setText(TREE_HEAD_COLUMN__NR_GROUPS, text_nr_groups)

    def item_moved(self, moved_item: TreeWidgetItem, moved_to: TreeWidgetItem, previous_parent: TreeWidgetItem):
        object_to_move = moved_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        if moved_to:
            obj_to_move_to: group_type = moved_to.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        else:
            obj_to_move_to = self.tree_groups.invisibleRootItem().data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                       Qt.ItemDataRole.UserRole)

        self.controller.execute(self.builder.set_new_parent_group_command(object_to_move.id, obj_to_move_to.id))

        # Weil sich nr_groups durch Inkonsistenzen geändert haben könnte:
        if not previous_parent:
            return
        parent_group = self.builder.get_group_from_id(
            previous_parent.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
        nr_groups = self.builder.get_nr_groups_from_group(parent_group)
        text_nr_groups = str(nr_groups) if nr_groups else 'alle'
        previous_parent.setText(TREE_HEAD_COLUMN__NR_GROUPS, text_nr_groups)

    def edit_item(self, item: QTreeWidgetItem):
        data_group = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        data_date_object = item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole)
        data_parent_group_nr = item.data(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole)
        if data_date_object:
            print(item.text(0), data_date_object.date, data_date_object.time_of_day.name, f'Gr. {data_parent_group_nr}')
            print(f'{data_group=}')
        else:
            dlg = DlgGroupProperties(self, item, self.builder)
            if not dlg.exec():
                return
            self.controller.add_to_undo_stack(dlg.controller.undo_stack)
            self.builder.reload_object_with_groups()

            self.update_items_after_edit(item)
