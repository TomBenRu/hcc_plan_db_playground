from typing import Callable, Sequence

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QDropEvent, QColor
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QTreeWidget,
                               QTreeWidgetItem, QFormLayout, QGroupBox, QGridLayout, QLabel, QCheckBox, QTextEdit,
                               QLineEdit)

from database import schemas, db_services
from gui.commands import command_base_classes, cast_group_commands
from gui.observer import signal_handling
from gui.tools.slider_with_press_event import SliderWithPressEvent

TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR = 0
TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR = 1
TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__EVENT = 5
TREE_HEAD_COLUMN__NR_GROUPS = 3
TREE_HEAD_COLUMN__PRIORITY = 4


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, tree_widget_item: QTreeWidgetItem | QTreeWidget = None):
        super().__init__(tree_widget_item)

    def configure(self, group: schemas.CastGroup, event: schemas.Event | None,
                  group_nr: int | None, parent_group_nr: int):
        if event:
            self.setText(0, 'gesetzt')
            self.setText(1, event.date.strftime('%d.%m.%y'))
            self.setText(2, event.time_of_day.name)
            self.setText(5, group.fixed_cast or '')

            self.setForeground(0, QColor('#5a009f'))
            self.setForeground(1, QColor('blue'))
            self.setForeground(2, QColor('#9f0057'))
            self.setData(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole, event)
        else:
            text_mode = (None if not(group.same_cast or group.alternating_cast)
                         else 'gleiche Besetzung' if group.same_cast else 'alternierende Besetzung')
            self.setText(0, f'Gruppe_{group_nr:02}')
            self.setText(3, text_mode)
            self.setText(4, str(group.strict_cast_pref))
            self.setData(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole, group_nr)
            self.setBackground(0, QColor('#e1ffde'))
            self.setToolTip(0, f'Doppelklick, um "Gruppe {group_nr:02}" zu bearbeiten.')

        self.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, group)
        self.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, parent_group_nr)

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        my_event: schemas.Event = self.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.UserRole)
        other_event: schemas.Event = other.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.UserRole)
        my_group: schemas.CastGroupShow = self.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        other_group: schemas.CastGroupShow = other.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        sort_order = self.treeWidget().header().sortIndicatorOrder()

        if column != 1:
            # Verwende die Standard-Sortierreihenfolge für andere Spalten
            if my_event and not other_event:
                return sort_order == Qt.SortOrder.DescendingOrder
            elif not my_event and other_event:
                return sort_order == Qt.SortOrder.AscendingOrder
            elif not my_event and not other_event:
                has_child_groups = my_group.cast_groups
                return sort_order == (Qt.SortOrder.DescendingOrder if has_child_groups else Qt.SortOrder.AscendingOrder)
            else:
                return self.text(column) < other.text(column)

        # Sortiere nach benutzerdefinierten Daten in Spalte TREE_ITEM_DATA_COLUMN__DATE_OBJECT
        if my_event:
            my_value = f'{my_event.date} {my_event.time_of_day.time_of_day_enum.time_index:02}'
        elif not other_event:
            has_child_groups = my_group.cast_groups
            return sort_order == (Qt.SortOrder.DescendingOrder if has_child_groups else Qt.SortOrder.AscendingOrder)
        else:
            return sort_order == Qt.SortOrder.AscendingOrder

        if other_event:
            other_value = f'{other_event.date} {other_event.time_of_day.time_of_day_enum.time_index:02}'
        elif not my_event:
            has_child_groups = other_group.cast_groups
            return sort_order == (Qt.SortOrder.AscendingOrder if has_child_groups else Qt.SortOrder.DescendingOrder)
        else:
            return sort_order == Qt.SortOrder.DescendingOrder

        return my_value < other_value


class TreeWidget(QTreeWidget):
    def __init__(self, location_plan_period: schemas.LocationPlanPeriodShow,
                 slot_item_moved: Callable[[TreeWidgetItem, TreeWidgetItem, TreeWidgetItem], None]):
        super().__init__()

        self.location_plan_period = location_plan_period

        self.setColumnCount(6)
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit", "modus", "same_cast_pref", "fixed_cast"])
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSortingEnabled(True)

        self.slot_item_moved = slot_item_moved

        self.nr_main_groups = 0

        self.curr_item: QTreeWidgetItem | None = None

        self.setup_tree()
        self.expand_all()

    def mimeData(self, items: Sequence[QTreeWidgetItem]) -> QtCore.QMimeData:
        self.curr_item = items[0]
        return super().mimeData(items)

    def send_signal_to_date_object(self, parent_group_nr: int):
        if date_object := self.curr_item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
            signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
                signal_handling.DataGroupMode(True,
                                              date_object.date,
                                              date_object.time_of_day.time_of_day_enum.time_index,
                                              parent_group_nr)
            )

    def dropEvent(self, event: QDropEvent) -> None:
        item_to_move_to = self.itemAt(event.position().toPoint())
        previous_parent = self.curr_item.parent()
        if item_to_move_to and item_to_move_to.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
            event.ignore()
        else:
            super().dropEvent(event)
            new_parent_group_nr = (item_to_move_to.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
                                   if item_to_move_to else 0)

            self.send_signal_to_date_object(new_parent_group_nr)

            self.curr_item.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole,
                                   new_parent_group_nr)
            self.expandAll()
            for i in range(self.columnCount()): self.resizeColumnToContents(i)
            self.slot_item_moved(self.curr_item, item_to_move_to, previous_parent)

    def setup_tree(self):
        def add_children(parent: QTreeWidgetItem, parent_group: schemas.CastGroupShow):
            children = parent_group.cast_groups
            parent_group_nr = parent.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
            for child in children:
                if date_object := child.event:
                    item = TreeWidgetItem(parent)
                    item.configure(child, date_object, None, parent_group_nr)
                    signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
                        signal_handling.DataGroupMode(True,
                                                      date_object.date,
                                                      date_object.time_of_day.time_of_day_enum.time_index,
                                                      parent_group_nr)
                    )
                else:
                    self.nr_main_groups += 1
                    item = TreeWidgetItem(parent)
                    item.configure(child, None, self.nr_main_groups, parent_group_nr)
                    add_children(item, db_services.CastGroup.get(child.id))

        cast_groups = db_services.CastGroup.get_all_from__location_plan_period(self.location_plan_period.id)
        most_top_cast_groups = [cg for cg in cast_groups if not cg.cast_group]

        for child in most_top_cast_groups:
            if event := child.event:
                item = TreeWidgetItem(self)
                item.configure(child, event, None, 0)
                signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
                    signal_handling.DataGroupMode(True,
                                                  event.date,
                                                  event.time_of_day.time_of_day_enum.time_index,
                                                  0)
                )
            else:
                self.nr_main_groups += 1
                item = TreeWidgetItem(self)
                item.configure(child, None, self.nr_main_groups, 0)
                add_children(item, child)

        self.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    def refresh_tree(self):
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        self.clear()
        self.nr_main_groups = 0
        self.setup_tree()
        self.expand_all()

    def expand_all(self):
        self.expandAll()
        for i in range(self.columnCount()): self.resizeColumnToContents(i)


class DlgGroupProperties(QDialog):
    def __init__(self, parent: QWidget, item: QTreeWidgetItem):
        super().__init__(parent=parent)

        self.item = item

        self.group_nr = self.item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)

        self.setWindowTitle(f'Eigenschaften von Gruppe {self.group_nr:02}')

        self.group: schemas.CastGroupShow = self.item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QGridLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_same_cast = QLabel('gleiche Besetzung aller Termine')
        self.chk_same_cast = QCheckBox('aktivieren?')
        self.lb_alternating_cast = QLabel('unterschiedl. Besetzung 2er aufeinanderfolgender Termine')
        self.chk_alternating_cast = QCheckBox('aktivieren?')
        self.lb_strict_alternating = QLabel('Terminreihen strikt alternieren (A | B | A usw.)')
        self.chk_strict_alternating = QCheckBox('aktivieren?')
        self.lb_custom_rule = QLabel('Eigene Regel')
        self.le_custom_rule = QLineEdit()
        self.lb_strict_cast_pref = QLabel('Regeln strikt befolgen?')
        self.slider_strict_cast_pref = SliderWithPressEvent(Qt.Orientation.Horizontal)
        self.lb_strict_cast_pref_value_text = QLabel()

        self.layout_body.addWidget(self.lb_same_cast, 0, 0)
        self.layout_body.addWidget(self.chk_same_cast, 0, 1)
        self.layout_body.addWidget(self.lb_alternating_cast, 1, 0)
        self.layout_body.addWidget(self.chk_alternating_cast, 1, 1)
        self.layout_body.addWidget(self.lb_strict_alternating, 2, 0)
        self.layout_body.addWidget(self.chk_strict_alternating, 2, 1)
        self.layout_body.addWidget(self.lb_custom_rule, 3, 0)
        self.layout_body.addWidget(self.le_custom_rule, 3, 1)
        self.layout_body.addWidget(self.lb_strict_cast_pref, 4, 0)
        self.layout_body.addWidget(self.slider_strict_cast_pref, 4, 1)
        self.layout_body.addWidget(self.lb_strict_cast_pref_value_text, 4, 2)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.sliders_variation_weights = {}

        self.setup_sliders()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_sliders(self):
        ...


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
            else:
                index = self.tree_groups.indexOfTopLevelItem(selected_item)
                self.tree_groups.takeTopLevelItem(index)
            self.controller.execute(cast_group_commands.Delete(data.id))

    def item_moved(self, moved_item: TreeWidgetItem, moved_to: TreeWidgetItem, previous_parent: TreeWidgetItem):
        object_to_move = moved_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        if moved_to:
            obj_to_move_to: schemas.CastGroupShow = moved_to.data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                  Qt.ItemDataRole.UserRole)
        else:
            obj_to_move_to = self.tree_groups.invisibleRootItem().data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                       Qt.ItemDataRole.UserRole)

        new_parent_id = obj_to_move_to.id if obj_to_move_to else None
        self.controller.execute(cast_group_commands.SetNewParent(object_to_move.id,
                                                                 new_parent_id))

    def edit_item(self, item: QTreeWidgetItem):
        print('edit item')
        data_group = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        data_event = item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole)
        data_parent_group_nr = item.data(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole)
        if data_event:
            print(item.text(0), data_event.date, data_event.time_of_day.name, f'Gr. {data_parent_group_nr}')
            print(f'{data_group=}')
        else:
            dlg = DlgGroupProperties(self, item)
            if not dlg.exec():
                return
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)

            # self.update_items_after_edit(item)
