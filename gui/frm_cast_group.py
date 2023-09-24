import dataclasses
import datetime
import json
from typing import Callable, Sequence, Literal
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtGui import QDropEvent, QColor, QIcon
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDialogButtonBox, QTreeWidget,
                               QTreeWidgetItem, QGridLayout, QLabel, QComboBox, QSlider, QSpinBox, QMessageBox, QMenu)

from database import schemas, db_services
from gui import frm_cast_rule
from gui.actions import Action
from commands import command_base_classes
from commands.database_commands import cast_group_commands
from gui.frm_cast_rule import simplify_cast_rule
from gui.frm_fixed_cast import DlgFixedCastBuilderCastGroup, generate_fixed_cast_clear_text
from gui.observer import signal_handling
from gui.tools import custom_validators
from gui.tools.custom_widgets.custom_line_edits import LineEditWithCustomFont
from gui.tools.custom_widgets.slider_with_press_event import SliderWithPressEvent

TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR = 0
TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR = 1
TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__EVENT = 5
TREE_HEAD_COLUMN__TITEL = 0
TREE_HEAD_COLUMN__LOCATION = 1
TREE_HEAD_COLUMN__DATE = 2
TREE_HEAD_COLUMN__TIME_OF_DAY = 3
TREE_HEAD_COLUMN__NR_ACTORS = 4
TREE_HEAD_COLUMN__FIXED_CAST = 5
TREE_HEAD_COLUMN__RULE = 6
TREE_HEAD_COLUMN__STRICT_CAST_PREF = 7


def get_all_child_items(item: QTreeWidgetItem) -> list[QTreeWidgetItem]:
    all_items = []

    def recurse(parent_item):
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            all_items.append(child)
            recurse(child)

    recurse(item)
    return all_items


def location_plan_period_ids__from_cast_group(cast_group: schemas.CastGroup) -> set[UUID]:

    def find_recursive(child_group: schemas.CastGroup) -> set[UUID]:
        lpp_ids = set()
        child_group = db_services.CastGroup.get(child_group.id)
        if child_group.event:
            lpp_ids.add(db_services.Event.get(child_group.event.id).location_plan_period.id)
        else:
            for child in child_group.child_groups:
                lpp_ids |= find_recursive(child)
        return lpp_ids

    return find_recursive(cast_group)


@dataclasses.dataclass
class ProofResultSoloUnusedGroups:
    all_correct: bool
    solo_item: QTreeWidgetItem | None
    unused_groups: list[schemas.CastGroup] | None


@dataclasses.dataclass
class ProofResultCastRule:
    all_correct: bool = True
    child_rule_conflict: bool = False
    fixed_cast_conflict: bool = False

    def set(self, *, all_correct: bool = None, child_rule_conflict: bool = None, fixed_cast_conflict: bool = None):
        self.all_correct = self.all_correct if all_correct is None else all_correct
        self.child_rule_conflict = self.child_rule_conflict if child_rule_conflict is None else child_rule_conflict
        self.fixed_cast_conflict = self.fixed_cast_conflict if fixed_cast_conflict is None else fixed_cast_conflict


class ConsistenceProof:
    # todo: alle Konsistenzprüfungen von DlgGroupProperties und DlgCastGroups werden in dieser Klasse zusammengefasst.

    @classmethod
    def check_conflict_for_cast_rule(cls, item: 'TreeWidgetItem') -> ProofResultCastRule:
        """Es wird nur auf den speziellen Fall: parent.cast_rule == '-' oder None und child.cast_rule == '~' oder None geprüft.
        Nur die direkten Childs werden geprüft."""
        proof_result = ProofResultCastRule(True, False, False)
        cast_group = db_services.CastGroup.get(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
        cast_group_rule = (cast_group.cast_rule and cast_group.cast_rule.rule) or cast_group.custom_rule
        cast_group_rule = simplify_cast_rule(cast_group_rule)
        if cast_group_rule and cast_group_rule != '~' and cast_group.fixed_cast:
            proof_result.set(all_correct=False, fixed_cast_conflict=True)
        for child in (item.child(i) for i in range(item.childCount())):
            child_group_id: UUID = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
            child_group = db_services.CastGroup.get(child_group_id)
            child_group_rule = (child_group.cast_rule and child_group.cast_rule.rule) or child_group.custom_rule
            child_group_rule = simplify_cast_rule(child_group_rule)
            if cast_group_rule == '-' and (child_group_rule and child_group_rule != '~'):
                proof_result.set(all_correct=False, child_rule_conflict=True)
            elif (not child_group.event and cast_group_rule == '~'
                  and (not child_group.fixed_cast and child_group_rule != '~')):
                proof_result.set(all_correct=False, child_rule_conflict=True)
            elif cast_group_rule and len(cast_group_rule) > 1 and child_group_rule:
                proof_result.set(all_correct=False, child_rule_conflict=True)
        return proof_result

    @classmethod
    def check_childs_nr_actors_are_different(cls, item: QTreeWidgetItem) -> bool:
        parent_group_id = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
        parent_group = db_services.CastGroup.get(parent_group_id)
        for child in get_all_child_items(item):
            child_group_id = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
            if db_services.CastGroup.get(child_group_id).nr_actors != parent_group.nr_actors:
                return True
        return False

    @classmethod
    def check_childs_fixed_cast_are_different(cls, item: QTreeWidgetItem) -> bool:
        parent_group_id = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
        parent_group = db_services.CastGroup.get(parent_group_id)
        for child in get_all_child_items(item):
            child_group_id = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id
            if (child_fixed_cast := db_services.CastGroup.get(child_group_id).fixed_cast) is None:
                continue
            if child_fixed_cast != parent_group.fixed_cast:
                return True
        return False

    @classmethod
    def proof_solo_childs(cls, item: QTreeWidgetItem) -> QTreeWidgetItem:
        for item in get_all_child_items(item):
            if item.childCount() == 1:
                return item

    @classmethod
    def proof_for_unused_groups(cls, item) -> list[schemas.CastGroup]:
        to_delete: list[schemas.CastGroup] = []
        for item in get_all_child_items(item):
            event = item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole)
            if not event and not item.childCount():
                to_delete.append(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole))
        return to_delete

    @classmethod
    def proof_for_unused_groups_and_solo_childs(cls, item: QTreeWidgetItem) -> ProofResultSoloUnusedGroups:
        to_delete_unused_groups = cls.proof_for_unused_groups(item)
        if not to_delete_unused_groups:
            return (ProofResultSoloUnusedGroups(False, solo_item, None) if (solo_item := cls.proof_solo_childs(item))
                    else ProofResultSoloUnusedGroups(True, None, None))
            # accept wird, falls solo_item, abgebrochen, damit solo_items gelöscht werden können.
            # andernfalls wird accept ohne weitere Maßnahme durchgeführt.
        elif solo_item := cls.proof_solo_childs(item):
            return ProofResultSoloUnusedGroups(False, solo_item, None)
            # accept wird abgebrochen, damit solo_items gelöscht werden können.
        else:
            return ProofResultSoloUnusedGroups(False, None, to_delete_unused_groups)
            # unused_groups müssen gelöscht werden, der status self.simplified wird auf True gesetzt
            # und proof_for_unused_groups_and_solo_childs wird automatisch erneut aufgerufen
            # (wobei dieses Mal logischerweise sofort in die erste Bedingung gesprungen wird)


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, tree_widget_item: QTreeWidgetItem | QTreeWidget = None):
        super().__init__(tree_widget_item)

    def configure(self, group: schemas.CastGroup, event: schemas.Event | None,
                  group_nr: int | None, parent_group_nr: int):
        group = db_services.CastGroup.get(group.id)
        fixed_cast_text = generate_fixed_cast_clear_text(group.fixed_cast)
        if event:
            self.setText(TREE_HEAD_COLUMN__TITEL, 'gesetzt')
            self.setText(TREE_HEAD_COLUMN__LOCATION, event.location_plan_period.location_of_work.name)
            self.setText(TREE_HEAD_COLUMN__DATE, event.date.strftime('%d.%m.%y'))
            self.setText(TREE_HEAD_COLUMN__TIME_OF_DAY, event.time_of_day.name)
            self.setText(TREE_HEAD_COLUMN__FIXED_CAST, fixed_cast_text)
            self.setText(TREE_HEAD_COLUMN__NR_ACTORS, str(group.nr_actors))

            self.setForeground(TREE_HEAD_COLUMN__TITEL, QColor('#5a009f'))
            self.setForeground(TREE_HEAD_COLUMN__DATE, QColor('blue'))
            self.setForeground(TREE_HEAD_COLUMN__TIME_OF_DAY, QColor('#9f0057'))
            self.setData(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole, event)
        else:
            rule_text = group.cast_rule.name if group.cast_rule else group.custom_rule
            self.setText(TREE_HEAD_COLUMN__TITEL, f'Gruppe_{group_nr:02}')
            self.setText(TREE_HEAD_COLUMN__STRICT_CAST_PREF, str(group.strict_cast_pref))
            self.setText(TREE_HEAD_COLUMN__FIXED_CAST, fixed_cast_text)
            self.setData(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole, group_nr)
            self.setText(TREE_HEAD_COLUMN__NR_ACTORS, str(group.nr_actors))
            self.setText(TREE_HEAD_COLUMN__RULE, rule_text)
            self.setBackground(TREE_HEAD_COLUMN__TITEL, QColor('#e1ffde'))
            self.setToolTip(TREE_HEAD_COLUMN__TITEL, f'Doppelklick, um "Gruppe {group_nr:02}" zu bearbeiten.')

        self.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, group)
        self.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, parent_group_nr)

    def calculate_earliest_date_object(self, item: 'TreeWidgetItem') -> tuple[datetime.date, int]:
        cast_group = db_services.CastGroup.get(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
        if not ((event := cast_group.event) or item.childCount()):
            return datetime.date(2000, 1, 1), 0
        if event:
            return event.date, event.time_of_day.time_of_day_enum.time_index
        visible_childs = [item.child(idx) for idx in range(item.childCount()) if not item.child(idx).isHidden()]
        return (min(self.calculate_earliest_date_object(child) for child in visible_childs)
                if visible_childs else (datetime.date(2000, 1, 1), 0))

    def __lt__(self, other: 'TreeWidgetItem'):
        column = self.treeWidget().sortColumn()

        if column != 1:
            return False

        # Sortiere nach benutzerdefinierten Daten in Spalte TREE_ITEM_DATA_COLUMN__DATE_OBJECT
        my_earliest_event = self.calculate_earliest_date_object(self)
        other_earliest_event = self.calculate_earliest_date_object(other)
        if my_earliest_event[0] == other_earliest_event[0]:
            return my_earliest_event[1] < other_earliest_event[1]
        return my_earliest_event[0] < other_earliest_event[0]


class TreeWidget(QTreeWidget):
    def __init__(self, plan_period: schemas.PlanPeriodShow,
                 slot_item_moved: Callable[[TreeWidgetItem, TreeWidgetItem, TreeWidgetItem], None],
                 visible_location_plan_period_ids: set[UUID]):
        super().__init__()

        self.plan_period = plan_period
        self.visible_location_plan_period_ids = visible_location_plan_period_ids

        self.setColumnCount(8)
        self.setHeaderLabels(["Bezeichnung", "Location", "Datum", "Tageszeit", 'Anz. Mitarb.', "fixed_cast", "Regel",
                              "strict_cast_pref"])
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
            children = parent_group.child_groups
            parent_group_nr = parent.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
            for child in children:
                child = db_services.CastGroup.get(child.id)
                if date_object := child.event:
                    item = TreeWidgetItem(parent)
                    if not (self.visible_location_plan_period_ids & location_plan_period_ids__from_cast_group(child)):
                        item.setHidden(True)
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

        cast_groups = db_services.CastGroup.get_all_from__plan_period(self.plan_period.id)

        most_top_cast_groups = [cg for cg in cast_groups if not cg.parent_groups]

        for child in most_top_cast_groups:
            item = TreeWidgetItem(self)
            if not (self.visible_location_plan_period_ids & location_plan_period_ids__from_cast_group(child)):
                item.setHidden(True)
            if event := child.event:
                item.configure(child, event, None, 0)
                signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
                    signal_handling.DataGroupMode(True,
                                                  event.date,
                                                  event.time_of_day.time_of_day_enum.time_index,
                                                  0)
                )
            else:
                self.nr_main_groups += 1
                item.configure(child, None, self.nr_main_groups, 0)
                add_children(item, child)

        self.sortByColumn(1, Qt.SortOrder.AscendingOrder)

    def refresh_tree(self):
        self.clear()
        self.nr_main_groups = 0
        self.setup_tree()
        self.expand_all()

    def expand_all(self):
        self.expandAll()
        for i in range(self.columnCount()): self.resizeColumnToContents(i)


class DlgGroupProperties(QDialog):
    def __init__(self, parent: QWidget, item: QTreeWidgetItem, visible_location_plan_period_ids: set[UUID]):
        super().__init__(parent=parent)

        self.item = item
        self.location_plan_period = (db_services.LocationPlanPeriod.get(visible_location_plan_period_ids.copy().pop())
                                     if len(visible_location_plan_period_ids) == 1 else None)

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
        self.changing_cast_rules = False

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
        self.lb_rule = QLabel('Besetzungsregel')
        self.combo_cast_rules = QComboBox()
        self.le_custom_rule = LineEditWithCustomFont(parent=None, font=None, bold=True, letter_spacing=4)
        self.lb_new_rule = QLabel('Neue Regel erstellen')
        self.bt_new_rule = QPushButton('Neu...', clicked=self.new_rule)
        self.lb_cast_rule_warning = QLabel()
        self.lb_cast_rule_warning.setObjectName('cast_rule_warning')
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
        self.layout_body.addWidget(self.lb_cast_rule_warning, 4, 2)
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
                                  'übergeordneten Gruppe.\nDas gilt für: fixed_cast, nr_actors.\n\n'
                                  'cast_rule:\n'
                                  '- Falls Besetzungsregel und  Besetzungsregel != ~, darf kein fixed_cast festgelegt '
                                  'werden.\n'
                                  '- Falls Untergruppen gleiche Besetzungen haben oder Events beinhalten, kann eine '
                                  'cast_rule festgelegt werden.\n'
                                  '-- Falls Untergruppen fixed_cast beinhalten oder kompliziertere Besetzungsregeln, '
                                  'ist eine genauere Konsistenzprüfung erforderlich.'
                             )
        self.bt_correct_childs_fixed_cast__menu_config()
        self.lb_fixed_cast_value.setText(generate_fixed_cast_clear_text(self.group.fixed_cast))
        self.set_fixed_cast_warning()
        self.setup_combo_cast_rules()
        self.le_custom_rule.setText(self.group.cast_rule.rule if self.group.cast_rule else self.group.custom_rule)
        self.le_custom_rule.setValidator(custom_validators.LettersAndSymbolsValidator('*~-'))
        self.le_custom_rule.textChanged.connect(self.custom_rule_changed)
        self.set_cast_rule_warning()
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
            Action(self, None, 'Untergeordnete Besetzungen löschen', None,
                   lambda: self.correct_childs_fixed_cast('set_None')))
        self.menu_bt_correct_childs_fixed_cast.addAction(
            Action(self, None, 'Untergeordnete Besetzungen angleichen', None,
                   lambda: self.correct_childs_fixed_cast('set_fixed_cast')))

    def set_nr_actors_warning(self):
        if ConsistenceProof.check_childs_nr_actors_are_different(self.item):
            self.lb_nr_actors_warning.setStyleSheet('QWidget#nr_actors_warning{color: orangered}')
            self.lb_nr_actors_warning.setText('Untergeordnete Elemente haben eine andere Besetzungsstärke.')
        else:
            self.lb_nr_actors_warning.setStyleSheet('QWidget#nr_actors_warning{color: green}')
            self.lb_nr_actors_warning.setText('Alles in Ordnung.')

    def set_fixed_cast_warning(self):
        if ConsistenceProof.check_childs_fixed_cast_are_different(self.item):
            self.lb_fixed_cast_warning.setStyleSheet('QWidget#fixed_cast_warning{color: orangered}')
            self.lb_fixed_cast_warning.setText('Untergeordnete Elemente haben eine andere feste Besetzung.')
        else:
            self.lb_fixed_cast_warning.setStyleSheet('QWidget#fixed_cast_warning{color: green}')
            self.lb_fixed_cast_warning.setText('Alles in Ordnung.')

    def set_cast_rule_warning(self):
        consistence_proof_result = ConsistenceProof.check_conflict_for_cast_rule(self.item)

        if consistence_proof_result.all_correct:
            self.lb_cast_rule_warning.setStyleSheet('QWidget#cast_rule_warning{color: green}')
            self.lb_cast_rule_warning.setText('Alles in Ordnung.')
        else:
            self.lb_cast_rule_warning.setStyleSheet('QWidget#cast_rule_warning{color: orangered}')
            text_conflict_cast_rules = (
                'Es darf keine feste Besetzung festgelegt werden.'
                if consistence_proof_result.fixed_cast_conflict
                else None
            )
            text_conflict_child_rules = (
                'Konflikt mit direkt untergeordneten Elementen.'
                if consistence_proof_result.child_rule_conflict
                else None
            )
            self.lb_cast_rule_warning.setText(
                '\n'.join([text for text in (text_conflict_child_rules, text_conflict_cast_rules) if text]))

    def setup_combo_cast_rules(self):
        self.combo_cast_rules.blockSignals(True)
        self.combo_cast_rules.clear()
        curr_combo_index = 0
        self.combo_cast_rules.addItem('Eigene Regel')
        rules = sorted(db_services.CastRule.get_all_from__project(self.group.plan_period.team.project.id), key=lambda x: x.name)
        for i, rule in enumerate(rules, start=1):
            self.combo_cast_rules.addItem(QIcon('resources/toolbar_icons/icons/foaf.png'), rule.name, rule)
            if self.group.cast_rule and (self.group.cast_rule.id == rule.id):
                curr_combo_index = i
        self.combo_cast_rules.setCurrentIndex(curr_combo_index)
        self.combo_cast_rules.currentIndexChanged.connect(self.combo_rules_changed)
        self.combo_cast_rules.blockSignals(False)

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderCastGroup(self, self.group, self.location_plan_period).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.group = db_services.CastGroup.get(self.group.id)
            self.lb_fixed_cast_value.setText(generate_fixed_cast_clear_text(self.group.fixed_cast)
                                             if self.group.fixed_cast else None)
            self.group = db_services.CastGroup.get(self.group.id)
            self.set_fixed_cast_warning()
            self.set_cast_rule_warning()
        else:
            print('aboard')

    def new_rule(self):
        dlg = frm_cast_rule.DlgCastRule(self, self.group.plan_period.team.project.id)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.controller.execute(cast_group_commands.UpdateCastRule(self.group.id, dlg.created_cast_rule.id))
            self.group = db_services.CastGroup.get(self.group.id)
            self.setup_combo_cast_rules()
            self.le_custom_rule.blockSignals(True)
            self.le_custom_rule.setText(self.group.cast_rule.rule)
            self.le_custom_rule.blockSignals(False)
            self.set_cast_rule_warning()

    def combo_rules_changed(self):
        if self.changing_cast_rules:
            return
        self.changing_cast_rules = True
        cast_rule: schemas.CastRuleShow | None = self.combo_cast_rules.currentData()
        self.changing_custom_rules = True
        self.le_custom_rule.setText(cast_rule.rule if cast_rule else None)
        self.changing_custom_rules = False
        self.controller.execute(cast_group_commands.UpdateCastRule(self.group.id, cast_rule.id if cast_rule else None))
        self.controller.execute(cast_group_commands.UpdateCustomRule(self.group.id, None))
        self.changing_cast_rules = False
        self.set_cast_rule_warning()

    def custom_rule_changed(self):
        if self.changing_custom_rules:
            return
        self.changing_custom_rules = True
        self.changing_cast_rules = True
        if self.combo_cast_rules.currentIndex() != 0:
            self.combo_cast_rules.setCurrentIndex(0)
            self.controller.execute(cast_group_commands.UpdateCastRule(self.group.id, None))
        self.changing_cast_rules = False
        self.le_custom_rule.setText(self.le_custom_rule.text().upper())
        rule_to_save = simplify_cast_rule(self.le_custom_rule.text())
        self.controller.execute(cast_group_commands.UpdateCustomRule(self.group.id, rule_to_save))
        self.changing_custom_rules = False
        self.set_cast_rule_warning()

    def strict_cast_pref_changed(self):
        self.controller.execute(
            cast_group_commands.UpdateStrictCastPref(self.group.id, self.slider_strict_cast_pref.value()))
        self.group = db_services.CastGroup.get(self.group.id)

    def nr_actors_changed(self):
        self.controller.execute(cast_group_commands.UpdateNrActors(self.group.id, self.spin_nr_actors.value()))
        self.group = db_services.CastGroup.get(self.group.id)
        self.set_nr_actors_warning()

    def correct_childs_fixed_cast(self, mode: Literal['set_None', 'set_fixed_cast']):
        for child in get_all_child_items(self.item):
            child_group = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
            new_fixed_cast = self.group.fixed_cast if mode == 'set_fixed_cast' else None
            self.controller.execute(cast_group_commands.UpdateFixedCast(child_group.id, new_fixed_cast))
        self.set_fixed_cast_warning()

    def correct_childs_nr_actors(self):
        for child in get_all_child_items(self.item):
            child_group = child.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
            self.controller.execute(cast_group_commands.UpdateNrActors(child_group.id, self.group.nr_actors))
        self.set_nr_actors_warning()


class DlgCastGroups(QDialog):
    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriodShow,
                 visible_location_plan_period_ids: set[UUID]):
        """Wenn location_plan_period angegeben ist, werden nur die events und cast_groups
        der location_plan_period angezeigt"""
        super().__init__(parent=parent)

        self.setWindowTitle('Cast Groups')
        self.resize(800, 400)

        self.plan_period = plan_period
        self.visible_location_plan_period_ids = visible_location_plan_period_ids

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.simplified = False

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.tree_groups = TreeWidget(self.plan_period, self.item_moved,
                                      self.visible_location_plan_period_ids)
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
        create_command = cast_group_commands.Create(self.plan_period.id)
        self.controller.execute(create_command)
        self.tree_groups.nr_main_groups += 1
        if len(self.visible_location_plan_period_ids) == 1:
            location_plan_period = db_services.LocationPlanPeriod.get(self.visible_location_plan_period_ids.pop())
            self.controller.execute(cast_group_commands.UpdateFixedCast(
                create_command.created_cast_group.id, location_plan_period.fixed_cast))
            self.controller.execute(cast_group_commands.UpdateNrActors(
                create_command.created_cast_group.id, location_plan_period.nr_actors))

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

    def item_moved(self, moved_item: TreeWidgetItem, moved_to: TreeWidgetItem, previous_parent: TreeWidgetItem | None):
        object_to_move = moved_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        if moved_to:
            obj_to_move_to: schemas.CastGroupShow = moved_to.data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                  Qt.ItemDataRole.UserRole)
        else:
            obj_to_move_to = self.tree_groups.invisibleRootItem().data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                       Qt.ItemDataRole.UserRole)

        if previous_parent:
            previous_object: schemas.CastGroupShow = previous_parent.data(TREE_ITEM_DATA_COLUMN__GROUP,
                                                                          Qt.ItemDataRole.UserRole)
            self.controller.execute(cast_group_commands.RemoveFromParent(object_to_move.id, previous_object.id))

        new_parent_id = obj_to_move_to.id if obj_to_move_to else None
        if new_parent_id:
            self.controller.execute(cast_group_commands.SetNewParent(object_to_move.id, new_parent_id))

        self.update_all_items()

    def edit_item(self, item: QTreeWidgetItem):
        if event := item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
            event: schemas.Event
            visible_location_plan_period_ids = {event.location_plan_period.id}
        else:
            visible_location_plan_period_ids = location_plan_period_ids__from_cast_group(
                item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole))
        dlg = DlgGroupProperties(self, item, visible_location_plan_period_ids)

        if item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole):
            for widget in (dlg.lb_rule, dlg.combo_cast_rules, dlg.le_custom_rule, dlg.lb_new_rule, dlg.bt_new_rule,
                           dlg.lb_strict_cast_pref, dlg.slider_strict_cast_pref, dlg.lb_strict_cast_pref_value_text):
                widget.setParent(None)

        if not dlg.exec():
            return
        self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())

        self.update_all_items()

    def update_all_items(self):
        all_items = get_all_child_items(self.tree_groups.invisibleRootItem())

        for item in all_items:
            cast_group = db_services.CastGroup.get(item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            item.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, cast_group)
            item.setText(TREE_HEAD_COLUMN__FIXED_CAST, generate_fixed_cast_clear_text(cast_group.fixed_cast))
            if not (event_object := item.data(TREE_ITEM_DATA_COLUMN__EVENT, Qt.ItemDataRole.UserRole)):
                item.setText(TREE_HEAD_COLUMN__STRICT_CAST_PREF, str(cast_group.strict_cast_pref))
                rule_text = cast_group.cast_rule.name if cast_group.cast_rule else cast_group.custom_rule
                item.setText(TREE_HEAD_COLUMN__RULE, rule_text)
            else:
                item.setText(TREE_HEAD_COLUMN__LOCATION, event_object.location_plan_period.location_of_work.name)
            item.setText(TREE_HEAD_COLUMN__NR_ACTORS, str(cast_group.nr_actors))

    def show_message_solo_childs(self, item: TreeWidgetItem):
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

    def tree_is_consistent(self) -> bool:
        proof_result = ConsistenceProof.proof_for_unused_groups_and_solo_childs(
            self.tree_groups.invisibleRootItem())
        if proof_result.all_correct:
            return True
        if proof_result.solo_item:
            # falls solo_childs vorhanden sind
            group = proof_result.solo_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
            # falls das solo_child nicht in der aktuellen Ansicht sichtbar ist, wird die Ansicht erweitert.
            if not ((new_location_pp_ids := location_plan_period_ids__from_cast_group(group))
                    & self.visible_location_plan_period_ids):
                self.visible_location_plan_period_ids |= new_location_pp_ids
                self.refresh_tree()
                self.tree_is_consistent()
            else:
                self.show_message_solo_childs(proof_result.solo_item)
            return False
        if proof_result.unused_groups:
            # falls unused_groups vorhanden sind
            for cg in proof_result.unused_groups:
                self.controller.execute(cast_group_commands.Delete(cg.id))
                self.simplified = True
            self.tree_groups.setSortingEnabled(False)  # fixme: Wenn Sorting enabled, gibt es beim Sortieren Fehler
            self.refresh_tree()

        return self.tree_is_consistent()

    def accept(self):
        if self.tree_is_consistent():
            self.replace_group_nrs_from_events()
            super().accept()
            if self.simplified:
                QMessageBox.information(self, 'Gruppenmodus',
                                        'Die Gruppenstruktur wurde durch Entfernen unnötiger Gruppen vereinfacht.')

    def reject(self) -> None:
        self.controller.undo_all()
        # self.refresh_tree()  # notwendig, falls der Dialog automatisch aufgerufen wurde,...
        self.replace_group_nrs_from_events()
        super().reject()

    @staticmethod
    def replace_group_nrs_from_events():
        signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
            signal_handling.DataGroupMode(False))

    def refresh_tree(self):
        self.tree_groups.refresh_tree()

    def resize_dialog(self):
        height = self.tree_groups.header().height()
        for item in get_all_child_items(self.tree_groups.invisibleRootItem()):
            height += self.tree_groups.visualItemRect(item).height()

        if self.tree_groups.horizontalScrollBar().isVisible():
            height += self.tree_groups.horizontalScrollBar().height()

        with open('config.json') as f:
            json_data = json.load(f)
        screen_width, screen_height = json_data['screen_size']['width'], json_data['screen_size']['height']

        self.resize(self.size().width(), min(height + 200, screen_height - 40))


# todo: Gruppenmodus für Besetzung:
#       Konsistenzprüfung:...?
#       Wenn eine cast_rule in einer cast_group existiert, dann dürfen untergeordnete cast_groups keine cast_rule haben.
#       Makros für bestimmte Aufgaben wie: gleiche, ungleiche Besetzung am Tag etc.
