from typing import Callable, Sequence

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QDropEvent, QColor
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QTreeWidget,
                               QTreeWidgetItem)

from database import schemas, db_services
from gui.commands import command_base_classes, cast_group_commands
from gui.observer import signal_handling

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
            self.setText(4, str(group.same_cast_pref))
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
        # self.invisibleRootItem().setData(
        #     TREE_ITEM_DATA_COLUMN__GROUP,
        #     Qt.ItemDataRole.UserRole,
        #     self.builder.master_group
        # )

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


# class DlgGroupProperties(QDialog):
#     def __init__(self, parent: QWidget, item: QTreeWidgetItem, builder: DlgGroupModeBuilderABC):
#         super().__init__(parent=parent)
#
#         self.item = item
#         self.builder = builder
#
#         self.group_nr = self.item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
#
#         self.setWindowTitle(f'Eigenschaften von Gruppe {self.group_nr:02}'
#                             if self.group_nr else 'Eigenschaften der Hauptgruppe')
#
#         self.group = self.builder.get_group_from_id(
#             self.item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
#         self.child_items = [self.item.child(i) for i in range(self.item.childCount())]
#         self.child_groups = [
#             self.builder.get_group_from_id(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
#             for item in self.child_items]
#         self.variation_weight_text = VARIATION_WEIGHT_TEXT
#
#         self.controller = command_base_classes.ContrExecUndoRedo()
#
#         self.layout = QVBoxLayout(self)
#
#         self.layout_head = QVBoxLayout()
#         self.layout_body = QFormLayout()
#         self.layout_foot = QVBoxLayout()
#         self.layout.addLayout(self.layout_head)
#         self.layout.addLayout(self.layout_body)
#         self.layout.addLayout(self.layout_foot)
#
#         self.group_nr_childs = QGroupBox('Anzahl direkt untergeordneter Gruppen/Termine')
#         self.layout_body.addWidget(self.group_nr_childs)
#         self.layout_group_nr_childs = QHBoxLayout(self.group_nr_childs)
#         self.group_child_variation_weights = QGroupBox('Priorisierung der untergeordneten Gruppen/Termine')
#         self.layout_body.addWidget(self.group_child_variation_weights)
#         self.layout_group_child_variation_weights = QGridLayout(self.group_child_variation_weights)
#
#         self.lb_nr_childs = QLabel('Anzahl:')
#         self.slider_nr_childs = SliderWithPressEvent(Qt.Orientation.Horizontal)
#         self.lb_slider_nr_childs_value = QLabel()
#         self.chk_none = QCheckBox('Alle dir. untergeordneten Elemente')
#         self.layout_group_nr_childs.addWidget(self.lb_nr_childs)
#         self.layout_group_nr_childs.addWidget(self.slider_nr_childs)
#         self.layout_group_nr_childs.addWidget(self.lb_slider_nr_childs_value)
#         self.layout_group_nr_childs.addWidget(self.chk_none)
#
#         self.button_box = QDialogButtonBox(
#             QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
#         self.button_box.accepted.connect(self.accept)
#         self.button_box.rejected.connect(self.reject)
#         self.layout_foot.addWidget(self.button_box)
#
#         self.sliders_variation_weights = {}
#
#         self.setup_sliders()
#
#     def reject(self) -> None:
#         self.controller.undo_all()
#         super().reject()
#
#     def nr_childs_changed(self, value: int):
#         if self.chk_none.isChecked():
#             return
#         self.controller.execute(self.builder.update_nr_groups_command(group_id_type(self.group.id), value))
#         self.lb_slider_nr_childs_value.setText(f'{value}')
#
#     def chk_none_toggled(self, checked: bool, clicked=False):
#         if not clicked:
#             return
#         if checked:
#             self.controller.execute(self.builder.update_nr_groups_command(group_id_type(self.group.id), None))
#             self.slider_nr_childs.setValue(len(self.child_groups))
#             self.lb_slider_nr_childs_value.setText(f'{len(self.child_groups)}')
#             self.slider_nr_childs.setEnabled(False)
#         else:
#             self.controller.execute(
#                 self.builder.update_nr_groups_command(group_id_type(self.group.id), self.slider_nr_childs.value()))
#             self.slider_nr_childs.setEnabled(True)
#
#     def variation_weight_changed(self, child_id: UUID, value: int):
#         self.sliders_variation_weights[child_id]['lb_value'].setText(f'{self.variation_weight_text[value]}')
#         self.controller.execute(self.builder.update_variation_weight_command(group_id_type(child_id), value))
#
#     def setup_sliders(self):
#         self.slider_nr_childs.setTickPosition(QSlider.TickPosition.TicksBelow)
#         self.slider_nr_childs.setTickInterval(1)
#         self.slider_nr_childs.setMinimum(1)
#         self.slider_nr_childs.setMaximum(len(self.child_groups))
#         self.slider_nr_childs.setMinimumWidth(max(150, 30 * (len(self.child_groups) - 1)))
#         self.slider_nr_childs.valueChanged.connect(self.nr_childs_changed)
#         nr_groups = self.builder.get_nr_groups_from_group(self.group)
#         self.slider_nr_childs.setValue(nr_groups or len(self.child_groups))
#         self.lb_slider_nr_childs_value.setText(f'{nr_groups or len(self.child_groups)}')
#         self.chk_none.toggled.connect(lambda val: self.chk_none_toggled(checked=val, clicked=True))
#         self.chk_none.setChecked(not nr_groups)
#
#         for row, child_item in enumerate(self.child_items):
#             child_item: TreeWidgetItem
#             child_group: group_type = child_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
#             if child_group_nr := child_item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole):
#                 text_child_group = f'Gruppe {child_group_nr:02}'
#             else:
#                 date_object: date_object_type = child_item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT,
#                                                                 Qt.ItemDataRole.UserRole)
#                 text_child_group = f'{date_object.date.strftime("%d.%m.%y")} ({date_object.time_of_day.name})'
#             lb_slider = QLabel(text_child_group)
#             slider = SliderWithPressEvent(Qt.Orientation.Horizontal)
#             slider.setTickInterval(1)
#             slider.setTickPosition(QSlider.TickPosition.TicksBelow)
#             slider.setMinimum(0)
#             slider.setMaximum(2)
#             slider.setValue(child_group.variation_weight)
#             slider.valueChanged.connect(partial(self.variation_weight_changed, child_group.id))
#             lb_val = QLabel(f'{self.variation_weight_text[child_group.variation_weight]}')
#             self.layout_group_child_variation_weights.addWidget(lb_slider, row, 0)
#             self.layout_group_child_variation_weights.addWidget(slider, row, 1)
#             self.layout_group_child_variation_weights.addWidget(lb_val, row, 2)
#             self.sliders_variation_weights[child_group.id] = {'slider': slider, 'lb_value': lb_val}
#
#     def resizeEvent(self, event: QResizeEvent) -> None:
#         self.slider_nr_childs.setMinimumWidth(0)
#         super().resizeEvent(event)


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
        return
        data_group = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        data_event = item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole)
        data_parent_group_nr = item.data(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole)
        if data_event:
            print(item.text(0), data_event.date, data_event.time_of_day.name, f'Gr. {data_parent_group_nr}')
            print(f'{data_group=}')
        else:
            dlg = DlgGroupProperties(self, item, self.builder)
            if not dlg.exec():
                return
            self.controller.add_to_undo_stack(dlg.controller.undo_stack)
            self.builder.reload_object_with_groups()

            self.update_items_after_edit(item)
