import json
from typing import Callable, Sequence, Literal

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QDropEvent, QColor, QIcon, QPalette
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QTreeWidget,
                               QTreeWidgetItem, QFormLayout, QGroupBox, QGridLayout, QLabel, QCheckBox, QTextEdit,
                               QLineEdit, QComboBox, QSlider, QSpinBox, QMessageBox, QMenu)

from database import schemas, db_services
from gui.actions import Action
from gui.commands import command_base_classes, cast_group_commands
from gui.frm_fixed_cast import DlgFixedCastBuilderCastGroup, generate_fixed_cast_clear_text
from gui.observer import signal_handling
from gui.tools import custom_validators
from gui.tools.slider_with_press_event import SliderWithPressEvent

TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR = 0
TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR = 1
TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__EVENT = 5
TREE_HEAD_COLUMN__TITEL = 0
TREE_HEAD_COLUMN__DATE = 1
TREE_HEAD_COLUMN__TIME_OF_DAY = 2
TREE_HEAD_COLUMN__NR_ACTORS = 3
TREE_HEAD_COLUMN__FIXED_CAST = 4
TREE_HEAD_COLUMN__STRICT_CAST_PREF = 5


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, tree_widget_item: QTreeWidgetItem | QTreeWidget = None):
        super().__init__(tree_widget_item)

    def configure(self, group: schemas.CastGroup, event: schemas.Event | None,
                  group_nr: int | None, parent_group_nr: int):
        fixed_cast_text = generate_fixed_cast_clear_text(group.fixed_cast)
        if event:
            self.setText(TREE_HEAD_COLUMN__TITEL, 'gesetzt')
            self.setText(TREE_HEAD_COLUMN__DATE, event.date.strftime('%d.%m.%y'))
            self.setText(TREE_HEAD_COLUMN__TIME_OF_DAY, event.time_of_day.name)
            self.setText(TREE_HEAD_COLUMN__FIXED_CAST, fixed_cast_text)
            self.setText(TREE_HEAD_COLUMN__NR_ACTORS, str(group.nr_actors))

            self.setForeground(TREE_HEAD_COLUMN__TITEL, QColor('#5a009f'))
            self.setForeground(TREE_HEAD_COLUMN__DATE, QColor('blue'))
            self.setForeground(TREE_HEAD_COLUMN__TIME_OF_DAY, QColor('#9f0057'))
            self.setData(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole, event)
        else:
            self.setText(TREE_HEAD_COLUMN__TITEL, f'Gruppe_{group_nr:02}')
            self.setText(TREE_HEAD_COLUMN__STRICT_CAST_PREF, str(group.strict_cast_pref))
            self.setText(TREE_HEAD_COLUMN__FIXED_CAST, fixed_cast_text)
            self.setData(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole, group_nr)
            self.setText(TREE_HEAD_COLUMN__NR_ACTORS, str(group.nr_actors))
            self.setBackground(TREE_HEAD_COLUMN__TITEL, QColor('#e1ffde'))
            self.setToolTip(TREE_HEAD_COLUMN__TITEL, f'Doppelklick, um "Gruppe {group_nr:02}" zu bearbeiten.')

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
        self.setHeaderLabels(["Bezeichnung", "Datum", "Tageszeit", 'Anz. Mitarb.', "fixed_cast", "strict_cast_pref"])
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
                child = db_services.CastGroup.get(child.id)
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
                    add_children(item, child)

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

        item_data: schemas.CastGroupShow = self.item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        self.group = item_data.model_copy()

        self.setWindowTitle('Eigenschaften des Termins' if self.group.event
                            else f'Eigenschaften von Gruppe {self.group_nr:02}')

        self.strict_cast_pref_texts = {0: 'Besetzungsregel nicht beachten',
                                       1: 'möglichst nah an Besetzungsregel',
                                       2: 'unbedingt Besetzungsregel beachten'}

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.changing_custom_rules = False

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QGridLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_info = QLabel()

        self.lb_fixed_cast = QLabel('Feste Besetzung')
        self.bt_fixed_cast = QPushButton('Bearbeiten...', clicked=self.edit_fixed_cast)
        self.lb_fixed_cast_value = QLabel()
        self.lb_fixed_cast_warning = QLabel()
        self.lb_fixed_cast_warning.setObjectName('fixed_cast_warning')
        self.bt_correct_childs_fixed_cast = QPushButton('Feste Besetzung untergeordneter Elemente korrigieren')
        self.menu_bt_correct_childs_fixed_cast = QMenu()
        self.bt_correct_childs_fixed_cast.setFixedWidth(370)
        self.lb_rule = QLabel('Eigene Regel')
        self.combo_cast_rules = QComboBox()
        self.le_custom_rule = QLineEdit()
        self.lb_new_rule = QLabel('Neue Regel erstellen')
        self.bt_new_rule = QPushButton('Neu...', clicked=self.new_rule)
        self.lb_nr_actors = QLabel('Anzahl Mitarbeiter')
        self.spin_nr_actors = QSpinBox()
        self.lb_nr_actors_warning = QLabel()
        self.lb_nr_actors_warning.setObjectName('nr_actors_warning')
        self.bt_correct_childs_nr_actors = QPushButton('Besetzungsgröße untergeordneter Elemente korrigieren',
                                                       clicked=self.correct_childs_nr_actors)
        self.bt_correct_childs_nr_actors.setFixedWidth(370)
        self.lb_strict_cast_pref = QLabel('Regeln strikt befolgen?')
        self.slider_strict_cast_pref = SliderWithPressEvent(Qt.Orientation.Horizontal)
        self.lb_strict_cast_pref_value_text = QLabel()

        self.layout_head.addWidget(self.lb_info)

        self.layout_body.addWidget(self.lb_fixed_cast, 0, 0)
        self.layout_body.addWidget(self.bt_fixed_cast, 0, 1)
        self.layout_body.addWidget(self.lb_fixed_cast_value, 0, 2)
        self.layout_body.addWidget(self.lb_fixed_cast_warning, 1, 2)
        self.layout_body.addWidget(self.bt_correct_childs_fixed_cast, 2, 2)
        self.layout_body.addWidget(self.lb_rule, 3, 0)
        self.layout_body.addWidget(self.combo_cast_rules, 3, 1)
        self.layout_body.addWidget(self.le_custom_rule, 3, 2)
        self.layout_body.addWidget(self.lb_new_rule, 4, 0)
        self.layout_body.addWidget(self.bt_new_rule, 4, 1)
        self.layout_body.addWidget(self.lb_nr_actors, 5, 0)
        self.layout_body.addWidget(self.spin_nr_actors, 5, 1)
        self.layout_body.addWidget(self.lb_nr_actors_warning, 5, 2)
        self.layout_body.addWidget(self.bt_correct_childs_nr_actors, 6, 2)
        self.layout_body.addWidget(self.lb_strict_cast_pref, 7, 0)
        self.layout_body.addWidget(self.slider_strict_cast_pref, 7, 1)
        self.layout_body.addWidget(self.lb_strict_cast_pref_value_text, 7, 2)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.sliders_variation_weights = {}

        self.setup_widgets()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_widgets(self):
        self.lb_info.setText('Hier können Sie die Eigenschaften des Termins bearbeiten.' if self.group.event
                             else 'Hier können Sie die Eigenschaften der Besetzungsgruppe bearbeiten.\n'
                                  'Eigenschaften untergeordneter Gruppen überstimmen die Eigenschaft der '
                                  'übergeordneten Gruppe.\nDas gilt für: fixed_cast, nr_actors.'
                             )
        self.bt_correct_childs_fixed_cast__menu_config()
        self.lb_fixed_cast_value.setText(generate_fixed_cast_clear_text(self.group.fixed_cast))
        self.set_fixed_cast_warning()
        curr_combo_index = 0
        self.combo_cast_rules.addItem('keine Regel')
        rules = sorted(db_services.CastRule.get_all_from__project(self.group.project.id), key=lambda x: x.name)
        for i, rule in enumerate(rules, start=1):
            self.combo_cast_rules.addItem(QIcon('resources/toolbar_icons/icons/foaf.png'), rule.name, rule)
            if self.group.cast_rule and self.group.cast_rule.id == rule.id:
                curr_combo_index = i
        self.combo_cast_rules.setCurrentIndex(curr_combo_index)
        self.combo_cast_rules.currentIndexChanged.connect(self.combo_rules_changed)
        self.le_custom_rule.setText(self.group.cast_rule.rule if self.group.cast_rule else self.group.custom_rule)
        self.le_custom_rule.setValidator(custom_validators.LettersAndSymbolsValidator('*#~-'))
        self.le_custom_rule.textChanged.connect(self.custom_rule_changed)
        self.spin_nr_actors.setValue(self.group.nr_actors)
        self.spin_nr_actors.valueChanged.connect(self.nr_actors_changed)
        self.set_nr_actors_warning()
        self.slider_strict_cast_pref.setMinimum(0)
        self.slider_strict_cast_pref.setMaximum(2)
        self.slider_strict_cast_pref.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_strict_cast_pref.setFixedWidth(150)
        self.slider_strict_cast_pref.setValue(self.group.strict_cast_pref)
        self.lb_strict_cast_pref_value_text.setText(self.strict_cast_pref_texts[self.group.strict_cast_pref])
        self.slider_strict_cast_pref.valueChanged.connect(self.strict_cast_pref_changed)
        self.slider_strict_cast_pref.valueChanged.connect(
            lambda: self.lb_strict_cast_pref_value_text.setText(
                self.strict_cast_pref_texts[self.slider_strict_cast_pref.value()]))

    def bt_correct_childs_fixed_cast__menu_config(self):
        self.bt_correct_childs_fixed_cast.setMenu(self.menu_bt_correct_childs_fixed_cast)
        self.menu_bt_correct_childs_fixed_cast.addAction(
            Action(self, None, 'Besetzungen löschen', None,
                   lambda: self.correct_childs_fixed_cast('set_None')))
        self.menu_bt_correct_childs_fixed_cast.addAction(
            Action(self, None, 'Besetzung übernehmen', None,
                   lambda: self.correct_childs_fixed_cast('set_fixed_cast')))

    def set_nr_actors_warning(self):
        if self.check_childs_nr_actors_are_different():
            self.lb_nr_actors_warning.setStyleSheet('QWidget#nr_actors_warning{color: orangered}')
            self.lb_nr_actors_warning.setText('Untergeordnete Elemente haben eine andere Besetzungsstärke.')
        else:
            self.lb_nr_actors_warning.setStyleSheet('QWidget#nr_actors_warning{color: green}')
            self.lb_nr_actors_warning.setText('Alles in Ordnung.')

    def set_fixed_cast_warning(self):
        if self.check_childs_fixed_cast_are_different():
            self.lb_fixed_cast_warning.setStyleSheet('QWidget#fixed_cast_warning{color: orangered}')
            self.lb_fixed_cast_warning.setText('Untergeordnete Elemente haben eine andere feste Besetzung.')
        else:
            self.lb_fixed_cast_warning.setStyleSheet('QWidget#fixed_cast_warning{color: green}')
            self.lb_fixed_cast_warning.setText('Alles in Ordnung.')

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderCastGroup(self, self.group).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.group = db_services.CastGroup.get(self.group.id)
            self.lb_fixed_cast_value.setText(generate_fixed_cast_clear_text(self.group.fixed_cast)
                                             if self.group.fixed_cast else None)
            self.group = db_services.CastGroup.get(self.group.id)
            self.set_fixed_cast_warning()
        else:
            print('aboard')

    def new_rule(self):
        ...

    def combo_rules_changed(self):
        ...

    def custom_rule_changed(self):
        if self.changing_custom_rules:
            return
        self.changing_custom_rules = True
        self.le_custom_rule.setText(self.le_custom_rule.text().upper())
        if not (rule_to_save := self.le_custom_rule.text()):
            rule_to_save = None
        self.controller.execute(cast_group_commands.UpdateCustomRule(self.group.id, rule_to_save))
        self.changing_custom_rules = False

    def strict_cast_pref_changed(self):
        self.controller.execute(
            cast_group_commands.UpdateStrictCastPref(self.group.id, self.slider_strict_cast_pref.value()))
        self.group = db_services.CastGroup.get(self.group.id)

    def nr_actors_changed(self):
        self.controller.execute(cast_group_commands.UpdateNrActors(self.group.id, self.spin_nr_actors.value()))
        self.group = db_services.CastGroup.get(self.group.id)
        self.set_nr_actors_warning()

    def check_childs_nr_actors_are_different(self) -> bool:
        for child in self.get_all_items():
            child_group_id = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
            if db_services.CastGroup.get(child_group_id).nr_actors != self.group.nr_actors:
                return True

    def check_childs_fixed_cast_are_different(self) -> bool:
        for child in self.get_all_items():
            child_group_id = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
            if (child_fixed_cast := db_services.CastGroup.get(child_group_id).fixed_cast) is None:
                continue
            if child_fixed_cast != self.group.fixed_cast:
                return True

    def correct_childs_fixed_cast(self, mode: Literal['set_None', 'set_fixed_cast']):
        for child in self.get_all_items():
            child_group = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
            new_fixed_cast = self.group.fixed_cast if mode == 'set_fixed_cast' else None
            self.controller.execute(cast_group_commands.UpdateFixedCast(child_group.id, new_fixed_cast))
        self.set_fixed_cast_warning()

    def correct_childs_nr_actors(self):
        for child in self.get_all_items():
            child_group = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
            self.controller.execute(cast_group_commands.UpdateNrActors(child_group.id, self.group.nr_actors))
        self.set_nr_actors_warning()

    def get_all_items(self) -> list[QTreeWidgetItem]:
        all_items = []

        def recurse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                all_items.append(child)
                recurse(child)

        recurse(self.item)
        return all_items


class DlgCastGroups(QDialog):
    def __init__(self, parent: QWidget, location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent)

        self.setWindowTitle('Cast Groups')
        self.resize(400, 400)

        self.location_plan_period = location_plan_period

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.simplified = False

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
        self.controller.execute(cast_group_commands.SetNewParent(object_to_move.id, new_parent_id))
        self.update_all_items()

    def edit_item(self, item: QTreeWidgetItem):  # todo: Möglichkeit zum Anpassen von Eigenschaften der Childs hinzufügen
        dlg = DlgGroupProperties(self, item)

        if item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
            for widget in (dlg.lb_rule, dlg.combo_cast_rules, dlg.le_custom_rule, dlg.lb_new_rule, dlg.bt_new_rule,
                           dlg.lb_strict_cast_pref, dlg.slider_strict_cast_pref, dlg.lb_strict_cast_pref_value_text):
                widget.setParent(None)

        if not dlg.exec():
            return
        self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)

        self.update_all_items()

    def update_all_items(self):
        for item in self.get_all_child_items():
            cast_group = db_services.CastGroup.get(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, cast_group)
            item.setText(TREE_HEAD_COLUMN__FIXED_CAST, generate_fixed_cast_clear_text(cast_group.fixed_cast))
            if not item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
                item.setText(TREE_HEAD_COLUMN__STRICT_CAST_PREF, str(cast_group.strict_cast_pref))
            item.setText(TREE_HEAD_COLUMN__NR_ACTORS, str(cast_group.nr_actors))

    def get_all_child_items(self, item: QTreeWidgetItem = None) -> list[QTreeWidgetItem]:
        all_items = []

        def recurse(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                all_items.append(child)
                recurse(child)

        root_item = item or self.tree_groups.invisibleRootItem()
        recurse(root_item)
        return all_items

    def alert_solo_childs(self):
        all_items = self.get_all_child_items()
        for item in all_items:
            if item.childCount() == 1:
                if event := item.child(0).data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
                    QMessageBox.critical(
                        self, 'Gruppenmodus',
                        f'Mindestens eine Gruppe hat nur einen Termin:\n'
                        f'Gruppe {item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)}, '
                        f'{event.date.strftime("%d.%m.%y")} ({event.time_of_day.name})\n'
                        f'Bitte korrigieren Sie das.'
                    )
                else:
                    QMessageBox.critical(self, 'Gruppenmodus',
                                         f'Mindestens eine Gruppe beinhaltet nur eine Gruppe\n'
                                         f'Bitte korrigieren Sie das.')
                return True
        return False

    def delete_unused_groups(self):
        all_items = self.get_all_child_items()
        to_delete: list[schemas.CastGroup] = []
        for item in all_items:
            event = item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole)
            if not event and not item.childCount():
                to_delete.append(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole))

        if not to_delete:
            return self.alert_solo_childs()
        else:
            self.simplified = True
        for group in to_delete:
            self.controller.execute(cast_group_commands.Delete(group.id))
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
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
        if self.alert_solo_childs():  # ...um nach Löschung eines Solo-Childs zu korrigieren.
            return
        super().reject()

    def refresh_tree(self):
        self.tree_groups.refresh_tree()

    def resize_dialog(self):
        height = self.tree_groups.header().height()
        for item in self.get_all_child_items():
            height += self.tree_groups.visualItemRect(item).height()

        if self.tree_groups.horizontalScrollBar().isVisible():
            height += self.tree_groups.horizontalScrollBar().height()

        with open('config.json') as f:
            json_data = json.load(f)
        screen_width, screen_height = json_data['screen_size']['width'], json_data['screen_size']['height']

        self.resize(self.size().width(), min(height + 200, screen_height - 40))
