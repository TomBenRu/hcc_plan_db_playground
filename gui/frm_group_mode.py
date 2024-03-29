import json
from abc import ABC, abstractmethod
from functools import partial
from typing import Callable, Sequence, Literal, TypeAlias, NewType
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QDropEvent, QColor, QResizeEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QPushButton,
                               QHBoxLayout, QDialog, QMessageBox, QFormLayout, QCheckBox, QSlider, QLabel, QGroupBox,
                               QApplication, QGridLayout)

from database import schemas, db_services
from gui.commands import command_base_classes, avail_day_group_commands, event_group_commands
from gui.observer import signal_handling
from gui.tools.slider_with_press_event import SliderWithPressEvent

TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR = 0
TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR = 1
TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__DATE_OBJECT = 5
TREE_HEAD_COLUMN__NR_GROUPS = 3
TREE_HEAD_COLUMN__PRIORITY = 4

VARIATION_WEIGHT_TEXT = {0: 'notfalls', 1: 'gerne', 2: 'bevorzugt'}


object_with_group_type: TypeAlias = schemas.ActorPlanPeriodShow | schemas.LocationPlanPeriodShow
group_type: TypeAlias = schemas.AvailDayGroupShow | schemas.EventGroupShow
date_object_type: TypeAlias = schemas.AvailDayShow | schemas.EventShow
create_group_command_type: TypeAlias = type[avail_day_group_commands.Create] | type[event_group_commands.Create]
delete_group_command_type: TypeAlias = type[avail_day_group_commands.Delete] | type[event_group_commands.Delete]
set_new_parent_group_command_type: TypeAlias = (type[avail_day_group_commands.SetNewParent] |
                                                type[event_group_commands.SetNewParent])
group_id_type = NewType('group_id', UUID)


class DlgGroupModeBuilderABC(ABC):
    def __init__(self, parent: QWidget, object_with_groups: object_with_group_type):

        self.parent_widget = parent
        self.object_with_groups = object_with_groups.model_copy()
        self.master_group: group_type | None = None
        self.create_group_command: create_group_command_type | None = None
        self.delete_group_command: delete_group_command_type | None = None
        self.update_nr_groups_command: Callable[[group_id_type, int | None], command_base_classes.Command] | None = None
        self.update_variation_weight_command: Callable[[group_id_type, int], command_base_classes.Command] | None = None
        self.get_group_from_id: Callable[[group_id_type], group_type] | None = None
        self.set_new_parent_group_command: set_new_parent_group_command_type | None = None
        self.get_nr_groups_from_group: Callable[[group_type], int] | None = None
        self.get_child_groups_from__parent_group_id: Callable[[UUID], list[group_type]] | None = None
        self.get_date_object_from_group_id: Callable[[UUID], date_object_type] | None = None
        self.signal_handler_change__object_with_groups__group_mode: Callable[[signal_handling.DataGroupMode], None] = None
        self.text_date_object: str = ''

        self._generate_field_values()

    @abstractmethod
    def _generate_field_values(self):
        ...

    @abstractmethod
    def reload_object_with_groups(self):
        ...

    def build(self) -> 'DlgGroupMode':
        return DlgGroupMode(self.parent_widget, self)


class DlgGroupModeBuilderActorPlanPeriod(DlgGroupModeBuilderABC):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent=parent, object_with_groups=actor_plan_period)

        self.object_with_groups: schemas.ActorPlanPeriodShow = actor_plan_period

    def _generate_field_values(self):
        self.master_group = db_services.AvailDayGroup.get_master_from__actor_plan_period(self.object_with_groups.id)
        self.create_group_command = avail_day_group_commands.Create
        self.delete_group_command = avail_day_group_commands.Delete
        self.update_nr_groups_command = avail_day_group_commands.UpdateNrAvailDayGroups
        self.update_variation_weight_command = avail_day_group_commands.UpdateVariationWeight
        self.get_group_from_id = db_services.AvailDayGroup.get
        self.set_new_parent_group_command = avail_day_group_commands.SetNewParent
        self.get_nr_groups_from_group = lambda group: group.nr_avail_day_groups
        self.get_date_object_from_group_id = db_services.AvailDay.get_from__avail_day_group
        self.get_child_groups_from__parent_group_id = db_services.AvailDayGroup.get_child_groups_from__parent_group
        self.signal_handler_change__object_with_groups__group_mode = signal_handling.handler_actor_plan_period.change_actor_plan_period_group_mode
        self.text_date_object = 'verfügbar'

    def reload_object_with_groups(self):
        self.object_with_groups = db_services.ActorPlanPeriod.get(self.object_with_groups.id)


class DlgGroupModeBuilderLocationPlanPeriod(DlgGroupModeBuilderABC):
    def __init__(self, parent: QWidget, location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent, object_with_groups=location_plan_period)

        self.object_with_groups: schemas.LocationPlanPeriodShow = location_plan_period

    def _generate_field_values(self):
        self.master_group = db_services.EventGroup.get_master_from__location_plan_period(self.object_with_groups.id)
        self.create_group_command = event_group_commands.Create
        self.delete_group_command = event_group_commands.Delete
        self.update_nr_groups_command = event_group_commands.UpdateNrEventGroups
        self.update_variation_weight_command = event_group_commands.UpdateVariationWeight
        self.get_group_from_id = db_services.EventGroup.get
        self.set_new_parent_group_command = event_group_commands.SetNewParent
        self.get_nr_groups_from_group = lambda group: group.nr_event_groups
        self.get_date_object_from_group_id = db_services.Event.get_from__event_group
        self.get_child_groups_from__parent_group_id = db_services.EventGroup.get_child_groups_from__parent_group
        self.signal_handler_change__object_with_groups__group_mode = signal_handling.handler_location_plan_period.change_location_plan_period_group_mode
        self.text_date_object = 'gesetzt'

    def reload_object_with_groups(self):
        self.object_with_groups = db_services.LocationPlanPeriod.get(self.object_with_groups.id)


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, builder: DlgGroupModeBuilderABC, tree_widget_item: QTreeWidgetItem | QTreeWidget = None):
        super().__init__(tree_widget_item)
        self.builder = builder

    def configure(self, group: group_type, date_object: date_object_type | None,
                  group_nr: int | None, parent_group_nr: int):
        text_variation_weight = VARIATION_WEIGHT_TEXT[group.variation_weight]
        if date_object:
            self.setText(0, self.builder.text_date_object)
            self.setText(1, date_object.date.strftime('%d.%m.%y'))
            self.setText(2, date_object.time_of_day.name)
            self.setText(4, text_variation_weight)

            self.setForeground(0, QColor('#5a009f'))
            self.setForeground(1, QColor('blue'))
            self.setForeground(2, QColor('#9f0057'))
            self.setData(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole, date_object)
        else:
            nr_groups = self.builder.get_nr_groups_from_group(group)
            text_nr_avail_day_groups = (str(nr_groups) if nr_groups else 'alle')
            self.setText(0, f'Gruppe_{group_nr:02}')
            self.setText(3, text_nr_avail_day_groups)
            self.setText(4, text_variation_weight)
            self.setData(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole, group_nr)
            self.setBackground(0, QColor('#e1ffde'))
            self.setToolTip(0, f'Doppelklick, um "Gruppe {group_nr:02}" zu bearbeiten.')

        self.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, group)
        self.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, parent_group_nr)

    def __lt__(self, other):
        column = self.treeWidget().sortColumn()
        my_date_object: date_object_type = self.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.UserRole)
        other_date_object: date_object_type = other.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.UserRole)
        my_group = self.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        other_group = other.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        my_group_id = my_group.id if my_group else None
        other_group_id = other_group.id if other_group else None
        sort_order = self.treeWidget().header().sortIndicatorOrder()

        if column != 1:
            # Verwende die Standard-Sortierreihenfolge für andere Spalten
            if my_date_object and not other_date_object:
                return sort_order == Qt.SortOrder.DescendingOrder
            elif not my_date_object and other_date_object:
                return sort_order == Qt.SortOrder.AscendingOrder
            elif not my_date_object and not other_date_object:
                has_child_groups = self.builder.get_child_groups_from__parent_group_id(my_group_id)
                return sort_order == (Qt.SortOrder.DescendingOrder if has_child_groups else Qt.SortOrder.AscendingOrder)
            else:
                return self.text(column) < other.text(column)

        # Sortiere nach benutzerdefinierten Daten in Spalte TREE_ITEM_DATA_COLUMN__DATE_OBJECT
        if my_date_object:
            my_value = f'{my_date_object.date} {my_date_object.time_of_day.time_of_day_enum.time_index:02}'
        elif not other_date_object:
            has_child_groups = self.builder.get_child_groups_from__parent_group_id(my_group_id)
            return sort_order == (Qt.SortOrder.DescendingOrder if has_child_groups else Qt.SortOrder.AscendingOrder)
        else:
            return sort_order == Qt.SortOrder.AscendingOrder

        if other_date_object:
            other_value = f'{other_date_object.date} {other_date_object.time_of_day.time_of_day_enum.time_index:02}'
        elif not my_date_object:
            has_child_groups = self.builder.get_child_groups_from__parent_group_id(other_group_id)
            return sort_order == (Qt.SortOrder.AscendingOrder if has_child_groups else Qt.SortOrder.DescendingOrder)
        else:
            return sort_order == Qt.SortOrder.DescendingOrder

        return my_value < other_value


class TreeWidget(QTreeWidget):
    def __init__(self, builder: DlgGroupModeBuilderABC,
                 slot_item_moved: Callable[[TreeWidgetItem, TreeWidgetItem, TreeWidgetItem], None]):
        super().__init__()

        self.builder = builder

        # self.setIndentation(30)
        self.setColumnCount(5)
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit", "mögl. Anzahl", "Priorität"])
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSortingEnabled(True)
        self.invisibleRootItem().setData(
            TREE_ITEM_DATA_COLUMN__GROUP,
            Qt.ItemDataRole.UserRole,
            self.builder.master_group
        )

        self.slot_item_moved = slot_item_moved

        self.nr_main_groups = 0

        self.curr_item: QTreeWidgetItem | None = None

        self.setup_tree()
        self.expand_all()

    def mimeData(self, items: Sequence[QTreeWidgetItem]) -> QtCore.QMimeData:
        self.curr_item = items[0]
        return super().mimeData(items)

    def send_signal_to_date_object(self, parent_group_nr: int):
        if date_object := self.curr_item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole):
            self.builder.signal_handler_change__object_with_groups__group_mode(
                signal_handling.DataGroupMode(True,
                                              date_object.date,
                                              date_object.time_of_day.time_of_day_enum.time_index,
                                              parent_group_nr)
            )

    def dropEvent(self, event: QDropEvent) -> None:
        item_to_move_to = self.itemAt(event.position().toPoint())
        previous_parent = self.curr_item.parent()
        if item_to_move_to and item_to_move_to.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole):
            event.ignore()
        else:
            super().dropEvent(event)
            new_parent_group_nr = (item_to_move_to.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
                                   if item_to_move_to else 0)

            self.send_signal_to_date_object(new_parent_group_nr)

            self.curr_item.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, new_parent_group_nr)
            self.expandAll()
            for i in range(self.columnCount()): self.resizeColumnToContents(i)
            self.slot_item_moved(self.curr_item, item_to_move_to, previous_parent)

    def setup_tree(self):
        def add_children(parent: QTreeWidgetItem, parent_group: group_type):
            children = self.builder.get_child_groups_from__parent_group_id(parent_group.id)
            parent_group_nr = parent.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
            for child in children:
                if date_object := self.builder.get_date_object_from_group_id(child.id):
                    item = TreeWidgetItem(self.builder, parent)
                    item.configure(child, date_object, None, parent_group_nr)
                    self.builder.signal_handler_change__object_with_groups__group_mode(
                        signal_handling.DataGroupMode(True,
                                                      date_object.date,
                                                      date_object.time_of_day.time_of_day_enum.time_index,
                                                      parent_group_nr)
                    )
                else:
                    self.nr_main_groups += 1
                    item = TreeWidgetItem(self.builder, parent)
                    item.configure(child, None, self.nr_main_groups, parent_group_nr)
                    add_children(item, child)

        for child in self.builder.get_child_groups_from__parent_group_id(self.builder.master_group.id):
            if date_object := self.builder.get_date_object_from_group_id(child.id):
                item = TreeWidgetItem(self.builder, self)
                item.configure(child, date_object, None, 0)
                self.builder.signal_handler_change__object_with_groups__group_mode(
                    signal_handling.DataGroupMode(True,
                                                  date_object.date,
                                                  date_object.time_of_day.time_of_day_enum.time_index,
                                                  0)
                )
            else:
                self.nr_main_groups += 1
                item = TreeWidgetItem(self.builder, self)
                item.configure(child, None, self.nr_main_groups, 0)
                add_children(item, child)

        self.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    def refresh_tree(self):
        self.builder.reload_object_with_groups()
        self.clear()
        self.nr_main_groups = 0
        self.setup_tree()
        self.expand_all()

    def expand_all(self):
        self.expandAll()
        for i in range(self.columnCount()): self.resizeColumnToContents(i)


class DlgGroupProperties(QDialog):
    def __init__(self, parent: QWidget, item: QTreeWidgetItem, builder: DlgGroupModeBuilderABC):
        super().__init__(parent=parent)

        self.item = item
        self.builder = builder

        self.group_nr = self.item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)

        self.setWindowTitle(f'Eigenschaften von Gruppe {self.group_nr:02}'
                            if self.group_nr else 'Eigenschaften der Hauptgruppe')

        self.group = self.builder.get_group_from_id(
            self.item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
        self.child_items = [self.item.child(i) for i in range(self.item.childCount())]
        self.child_groups = [
            self.builder.get_group_from_id(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            for item in self.child_items]
        self.variation_weight_text = VARIATION_WEIGHT_TEXT

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.group_nr_childs = QGroupBox('Anzahl direkt untergeordneter Gruppen/Termine')
        self.layout_body.addWidget(self.group_nr_childs)
        self.layout_group_nr_childs = QHBoxLayout(self.group_nr_childs)
        self.group_child_variation_weights = QGroupBox('Priorisierung der untergeordneten Gruppen/Termine')
        self.layout_body.addWidget(self.group_child_variation_weights)
        self.layout_group_child_variation_weights = QGridLayout(self.group_child_variation_weights)

        self.lb_nr_childs = QLabel('Anzahl:')
        self.slider_nr_childs = SliderWithPressEvent(Qt.Orientation.Horizontal)
        self.lb_slider_nr_childs_value = QLabel()
        self.chk_none = QCheckBox('Alle dir. untergeordneten Elemente')
        self.layout_group_nr_childs.addWidget(self.lb_nr_childs)
        self.layout_group_nr_childs.addWidget(self.slider_nr_childs)
        self.layout_group_nr_childs.addWidget(self.lb_slider_nr_childs_value)
        self.layout_group_nr_childs.addWidget(self.chk_none)

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

    def nr_childs_changed(self, value: int):
        if self.chk_none.isChecked():
            return
        self.controller.execute(self.builder.update_nr_groups_command(group_id_type(self.group.id), value))
        self.lb_slider_nr_childs_value.setText(f'{value}')

    def chk_none_toggled(self, checked: bool, clicked=False):
        if not clicked:
            return
        if checked:
            self.controller.execute(self.builder.update_nr_groups_command(group_id_type(self.group.id), None))
            self.slider_nr_childs.setValue(len(self.child_groups))
            self.lb_slider_nr_childs_value.setText(f'{len(self.child_groups)}')
            self.slider_nr_childs.setEnabled(False)
        else:
            self.controller.execute(
                self.builder.update_nr_groups_command(group_id_type(self.group.id), self.slider_nr_childs.value()))
            self.slider_nr_childs.setEnabled(True)

    def variation_weight_changed(self, child_id: UUID, value: int):
        self.sliders_variation_weights[child_id]['lb_value'].setText(f'{self.variation_weight_text[value]}')
        self.controller.execute(self.builder.update_variation_weight_command(group_id_type(child_id), value))

    def setup_sliders(self):
        self.slider_nr_childs.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_nr_childs.setTickInterval(1)
        self.slider_nr_childs.setMinimum(1)
        self.slider_nr_childs.setMaximum(len(self.child_groups))
        self.slider_nr_childs.setMinimumWidth(max(150, 30 * (len(self.child_groups) - 1)))
        self.slider_nr_childs.valueChanged.connect(self.nr_childs_changed)
        nr_groups = self.builder.get_nr_groups_from_group(self.group)
        self.slider_nr_childs.setValue(nr_groups or len(self.child_groups))
        self.lb_slider_nr_childs_value.setText(f'{nr_groups or len(self.child_groups)}')
        self.chk_none.toggled.connect(lambda val: self.chk_none_toggled(checked=val, clicked=True))
        self.chk_none.setChecked(not nr_groups)

        for row, child_item in enumerate(self.child_items):
            child_item: TreeWidgetItem
            child_group: group_type = child_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
            if child_group_nr := child_item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole):
                text_child_group = f'Gruppe {child_group_nr:02}'
            else:
                date_object: date_object_type = child_item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT,
                                                                Qt.ItemDataRole.UserRole)
                text_child_group = f'{date_object.date.strftime("%d.%m.%y")} ({date_object.time_of_day.name})'
            lb_slider = QLabel(text_child_group)
            slider = SliderWithPressEvent(Qt.Orientation.Horizontal)
            slider.setTickInterval(1)
            slider.setTickPosition(QSlider.TickPosition.TicksBelow)
            slider.setMinimum(0)
            slider.setMaximum(2)
            slider.setValue(child_group.variation_weight)
            slider.valueChanged.connect(partial(self.variation_weight_changed, child_group.id))
            lb_val = QLabel(f'{self.variation_weight_text[child_group.variation_weight]}')
            self.layout_group_child_variation_weights.addWidget(lb_slider, row, 0)
            self.layout_group_child_variation_weights.addWidget(slider, row, 1)
            self.layout_group_child_variation_weights.addWidget(lb_val, row, 2)
            self.sliders_variation_weights[child_group.id] = {'slider': slider, 'lb_value': lb_val}

    def resizeEvent(self, event: QResizeEvent) -> None:
        self.slider_nr_childs.setMinimumWidth(0)
        super().resizeEvent(event)


class DlgGroupMode(QDialog):
    def __init__(self, parent: QWidget, builder: DlgGroupModeBuilderABC):
        super().__init__(parent)

        self.setWindowTitle('Gruppenmodus')
        self.resize(400, 400)

        self.builder = builder

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.simplified = False

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.bt_edit_main_group = QPushButton('Hauptgruppe bearbeiten',
                                              clicked=lambda: self.edit_item(self.tree_groups.invisibleRootItem()))
        self.layout_body.addWidget(self.bt_edit_main_group)
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

        self.resize_dialog()

    def add_group(self):
        create_command = self.builder.create_group_command(event_avail_day_group_id=self.builder.master_group.id)
        self.controller.execute(create_command)
        self.tree_groups.nr_main_groups += 1

        new_item = TreeWidgetItem(self.builder, self.tree_groups.invisibleRootItem())
        new_item.configure(create_command.created_group, None, self.tree_groups.nr_main_groups, 0)

    def remove_group(self):
        selected_items = self.tree_groups.selectedItems()
        selected_item = selected_items[0]
        if not selected_items or selected_item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole):
            return
        data: group_type = selected_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        if selected_item.childCount() == 0:
            if parent_item := selected_item.parent():
                parent_item.removeChild(selected_item)
                parent_group = self.builder.get_group_from_id(
                    parent_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            else:
                index = self.tree_groups.indexOfTopLevelItem(selected_item)
                self.tree_groups.takeTopLevelItem(index)
                parent_group = self.builder.get_group_from_id(
                    self.tree_groups.invisibleRootItem().data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
                )
            self.controller.execute(self.builder.delete_group_command(data.id))

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

    def update_items_after_edit(self, item: TreeWidgetItem):
        new_group_data = self.builder.get_group_from_id(
            item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
        nr_groups = self.builder.get_nr_groups_from_group(new_group_data)
        text_nr_groups = str(nr_groups) if nr_groups else 'alle'
        item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, new_group_data)
        item.setText(TREE_HEAD_COLUMN__NR_GROUPS, text_nr_groups)
        child_items = (item.child(i) for i in range(item.childCount()))
        for child_item in child_items:
            new_group_data = self.builder.get_group_from_id(
                child_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            child_item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, new_group_data)
            child_item.setText(TREE_HEAD_COLUMN__PRIORITY, VARIATION_WEIGHT_TEXT[new_group_data.variation_weight])

    def get_all_items(self) -> list[QTreeWidgetItem]:
        all_items = []

        def recurse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                all_items.append(child)
                recurse(child)

        recurse(self.tree_groups.invisibleRootItem())
        return all_items

    def get_child_group_items(self, item: QTreeWidgetItem) -> list[QTreeWidgetItem]:
        """returns all child_groups of item"""
        return [item.child(i) for i in range(item.childCount())]

    def alert_solo_childs(self):
        all_items = self.get_all_items()
        for item in all_items:
            if item.childCount() == 1:
                if date_object := item.child(0).data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole):
                    QMessageBox.critical(
                        self, 'Gruppenmodus',
                        f'Mindestens eine Gruppe hat nur einen Termin:\n'
                        f'Gruppe {item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)}, '
                        f'{date_object.date.strftime("%d.%m.%y")} ({date_object.time_of_day.name})\n'
                        f'Bitte korrigieren Sie das.'
                    )
                else:
                    QMessageBox.critical(self, 'Gruppenmodus',
                                         f'Mindestens eine Gruppe beinhaltet nur eine Gruppe\n'
                                         f'Bitte korrigieren Sie das.')
                return True
        return False

    def delete_unused_groups(self):
        all_items = self.get_all_items()
        to_delete: list[group_type] = []
        for item in all_items:
            date_object = item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole)
            if not date_object and not item.childCount():
                to_delete.append(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole))

        if not to_delete:
            return self.alert_solo_childs()
        else:
            self.simplified = True
        for group in to_delete:
            self.controller.execute(self.builder.delete_group_command(group.id))
        self.builder.reload_object_with_groups()
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
        self.refresh_tree()  # notwendig, falls der Dialog automatisch aufgerufen wurde,...
        if self.alert_solo_childs():  # ...um nach Löschung eines avail_day Solo-Childs zu korrigieren.
            return
        super().reject()

    def refresh_tree(self):
        self.tree_groups.refresh_tree()

    def resize_dialog(self):
        height = self.tree_groups.header().height()
        for item in self.get_all_items():
            height += self.tree_groups.visualItemRect(item).height()

        if self.tree_groups.horizontalScrollBar().isVisible():
            height += self.tree_groups.horizontalScrollBar().height()

        with open('config.json') as f:
            json_data = json.load(f)
        screen_width, screen_height = json_data['screen_size']['width'], json_data['screen_size']['height']

        self.resize(self.size().width(), min(height + 200, screen_height - 40))


# todo: Toolset, um bestimmte Gruppierungs-Abläufe automatisiert festzulegen (Periodenweit, Tagesweit)...
#       Z.B.: nur 1 Schicht am Tag, die gleiche Schicht, pro Woche...
#       Voreinstellungen in: Project, Person, PlanPeriod, ActorPlanPeriod
# todo: Gruppenmodus für Besetzung
#       Besetzung in CastGroups verlagern.
#       Modus für: gleiche Besetzung aller Childs, alternierende ungleiche Besetzung aller Childs
#                  Dafür jeweils Konsistenzüberprüfung.
#       Regeln: Wenn same_cast = True dann alternating_cast = False und umgekehrt
#               Wenn same_cast dann fixed_cast möglich, child-groups haben kein fixed_cast, cast_group möglich
#               Wenn fixed_cast und cast_groups, dass same_cast = True
#               Wenn alternating_cast = True dann fixed_cast = None, child-groups fixed_cast möglich, cast_group = None (sinnlos)
#               Wenn event dann same_cast = False, alternating_cast = False, fixed_cast möglich
#       Makros für bestimmte Aufgaben wie: gleiche, ungleiche Besetzung am Tag etc.
