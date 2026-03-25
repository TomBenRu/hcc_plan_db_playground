import datetime
from abc import ABC, abstractmethod
from functools import partial
from typing import Callable, Sequence, TypeAlias, NewType
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QDropEvent, QColor, QResizeEvent
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QDialogButtonBox, QTreeWidget, QTreeWidgetItem, QPushButton,
                               QHBoxLayout, QDialog, QMessageBox, QFormLayout, QCheckBox, QSlider, QLabel, QGroupBox,
                               QGridLayout, QScrollArea, QApplication, QMenu)

from database import schemas, db_services
from commands import command_base_classes
from commands.database_commands import event_group_commands, required_avail_day_groups_commands
from commands.database_commands import avail_day_group_commands
from gui import widget_styles
from gui.custom_widgets.slider_with_press_event import SliderWithPressEvent
from gui.observer import signal_handling
from gui.widget_styles.tree_widgets import ChildZebraDelegate
from tools.helper_functions import date_to_string, setup_form_help
from tools.screen import Screen


TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR = 0
TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR = 1
TREE_ITEM_DATA_COLUMN__GROUP = 4
TREE_ITEM_DATA_COLUMN__DATE_OBJECT = 5
TREE_HEAD_COLUMN__NR_GROUPS = 3
TREE_HEAD_COLUMN__PRIORITY = 4

VARIATION_WEIGHT_TEXT = {
    0: QCoreApplication.translate("GroupMode", "if necessary"),
    1: QCoreApplication.translate("GroupMode", "preferred"),
    2: QCoreApplication.translate("GroupMode", "highly preferred")
}


object_with_group_type: TypeAlias = schemas.ActorPlanPeriodForMask | schemas.LocationPlanPeriodShow
group_type: TypeAlias = schemas.AvailDayGroupShow | schemas.EventGroupShow
date_object_type: TypeAlias = schemas.AvailDayShow | schemas.EventShow
create_group_command_type: TypeAlias = type[avail_day_group_commands.Create] | type[event_group_commands.Create]
delete_group_command_type: TypeAlias = type[avail_day_group_commands.Delete] | type[event_group_commands.Delete]
set_new_parent_group_command_type: TypeAlias = (type[avail_day_group_commands.SetNewParent] |
                                                type[event_group_commands.SetNewParent])
group_id_type = NewType('group_id', UUID)


def text_num_avail_groups(group: group_type, builder: 'DlgGroupModeBuilderABC') -> str:
    nr_groups = builder.get_nr_groups_from_group(group)
    if isinstance(group, schemas.AvailDayGroup):
        required = builder.get_required_avail_day_groups(group.id)
        if required:
            num_locations = len(required.locations_of_work)
            if required.locations_of_work:
                locations_text = QCoreApplication.translate(
                    "GroupMode",
                    "{} facilities",
                ).format(num_locations)
            else:
                locations_text = QCoreApplication.translate("GroupMode", "all facilities")

            num_required_groups = QCoreApplication.translate(
                "GroupMode",
                " (min. {} for {})",
            ).format(required.num_avail_day_groups, locations_text)
        else:
            num_required_groups = ''
    else:
        num_required_groups = ''

    all_text = QCoreApplication.translate("GroupMode", "all")
    return f"{nr_groups or all_text}{num_required_groups}"


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
        self.get_date_object_from_group: Callable[[group_type], date_object_type] | None = None
        self.signal_handler_change__object_with_groups__group_mode: Callable[[signal_handling.DataGroupMode], None] = None
        self.text_date_object: str = ''
        self.num_required_group_field: bool = False

        self._generate_field_values()

    @abstractmethod
    def _generate_field_values(self):
        ...

    @abstractmethod
    def reload_object_with_groups(self):
        ...

    def get_required_avail_day_groups(self, avail_day_group_id: UUID) -> schemas.RequiredAvailDayGroups | None:
        ...

    def update_required_avail_day_groups_to_db(self, avail_day_group_id: UUID, required_num_groups: int,
                                               controller: command_base_classes.ContrExecUndoRedo):
        ...

    def all_child_groups_have_avail_day(self, avail_day_group: schemas.AvailDayGroup) -> bool:
        ...

    def get_max_value_num_required_avail_day_groups(self, avail_day_group: schemas.AvailDayGroup) -> int:
        ...

    def adjust_num_required_avail_day_groups(self, avail_day_group: schemas.AvailDayGroupShow,
                                             controller: command_base_classes.ContrExecUndoRedo):
        ...

    def build(self) -> 'DlgGroupMode':
        return DlgGroupMode(self.parent_widget, self)


class DlgGroupModeBuilderActorPlanPeriod(DlgGroupModeBuilderABC):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodForMask):
        super().__init__(parent=parent, object_with_groups=actor_plan_period)

        self.object_with_groups: schemas.ActorPlanPeriodForMask = actor_plan_period

    def _generate_field_values(self):
        self.master_group = db_services.AvailDayGroup.get_master_from__actor_plan_period(self.object_with_groups.id)
        self.create_group_command = avail_day_group_commands.Create
        self.delete_group_command = avail_day_group_commands.Delete
        self.update_nr_groups_command = avail_day_group_commands.UpdateNrAvailDayGroups
        self.update_variation_weight_command = avail_day_group_commands.UpdateVariationWeight
        self.get_group_from_id = db_services.AvailDayGroup.get
        self.set_new_parent_group_command = avail_day_group_commands.SetNewParent
        self.get_nr_groups_from_group = lambda group: group.nr_avail_day_groups
        self.get_date_object_from_group = lambda group: getattr(group, 'avail_day')
        self.get_child_groups_from__parent_group_id = db_services.AvailDayGroup.get_child_groups_from__parent_group
        self.signal_handler_change__object_with_groups__group_mode = signal_handling.handler_actor_plan_period.change_actor_plan_period_group_mode
        self.text_date_object = QCoreApplication.translate("DlgGroupModeBuilderActorPlanPeriod", "available")
        self.num_required_group_field = True

    def reload_object_with_groups(self):
        self.object_with_groups = db_services.ActorPlanPeriod.get_for_mask(self.object_with_groups.id)

    def get_required_avail_day_groups(self, avail_day_group_id: UUID) -> schemas.RequiredAvailDayGroups | None:
        return db_services.RequiredAvailDayGroups.get_from__avail_day_group(avail_day_group_id)

    def update_required_avail_day_groups_to_db(self, required_avail_day_groups_id: UUID, required_num_groups: int,
                                               controller: command_base_classes.ContrExecUndoRedo):
        if required_num_groups is None:
            controller.execute(required_avail_day_groups_commands.Delete(required_avail_day_groups_id))
        else:
            controller.execute(required_avail_day_groups_commands.Update(
                required_avail_day_groups_id, required_num_groups, None))

    def all_child_groups_have_avail_day(self, avail_day_group: schemas.AvailDayGroup,
                                        child_groups: list[schemas.AvailDayGroupShow] = None) -> bool:
        child_groups = child_groups or db_services.AvailDayGroup.get_child_groups_from__parent_group(avail_day_group.id)
        return all(db_services.AvailDay.get_from__avail_day_group(child_group.id) for child_group in child_groups)

    def get_max_value_num_required_avail_day_groups(self, avail_day_group: schemas.AvailDayGroup) -> int:
        """
        Gibt den geringeren Wert von Child-Groups und der max. Anzahl der gewünschten Tage zurück,
        wenn alle Child-Groups verfügbare Tage haben.
        """
        child_groups = db_services.AvailDayGroup.get_child_groups_from__parent_group(avail_day_group.id)
        if not self.all_child_groups_have_avail_day(avail_day_group, child_groups):
            return 1
        return min([len(child_groups), avail_day_group.nr_avail_day_groups or 1000])

    def adjust_num_required_avail_day_groups(self, avail_day_group: schemas.AvailDayGroupShow,
                                             controller: command_base_classes.ContrExecUndoRedo):
        required_avail_day_groups = db_services.RequiredAvailDayGroups.get_from__avail_day_group(avail_day_group.id)
        if required_avail_day_groups is None:
            return
        required_max = self.get_max_value_num_required_avail_day_groups(avail_day_group)
        required_num = min(required_max,
                           required_avail_day_groups.num_avail_day_groups if required_avail_day_groups else 1)
        required_num = None if required_num == 1 else required_num
        self.update_required_avail_day_groups_to_db(required_avail_day_groups.id, required_num,
                                                    controller)


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
        self.get_date_object_from_group = lambda group: getattr(group, 'event')
        self.get_child_groups_from__parent_group_id = db_services.EventGroup.get_child_groups_from__parent_group
        self.signal_handler_change__object_with_groups__group_mode = (
            signal_handling.handler_location_plan_period.change_location_plan_period_group_mode)
        self.text_date_object = QCoreApplication.translate("DlgGroupModeBuilderLocationPlanPeriod", "assigned")

    def reload_object_with_groups(self):
        self.object_with_groups = db_services.LocationPlanPeriod.get(self.object_with_groups.id)


class TreeWidgetItem(QTreeWidgetItem):
    def __init__(self, builder: DlgGroupModeBuilderABC, tree_widget_item: QTreeWidgetItem | QTreeWidget = None,
                 date_object=None):
        super().__init__(tree_widget_item)
        self.builder = builder
        self.date_object = date_object

    def configure(self, group: group_type, date_object: date_object_type | None,
                  group_nr: int | None, parent_group_nr: int):
        text_variation_weight = VARIATION_WEIGHT_TEXT[group.variation_weight]
        if date_object:
            self.setText(0, self.builder.text_date_object)
            self.setText(1, date_to_string(date_object.date))
            self.setText(2, date_object.time_of_day.name)
            self.setText(4, text_variation_weight)

            self.setForeground(0, QColor(*widget_styles.tree_widgets.description_fg_color_rgba))
            self.setForeground(1, QColor(*widget_styles.tree_widgets.date_fg_color_rgba))
            self.setForeground(2, QColor(*widget_styles.tree_widgets.time_of_day_fg_color_rgba))
            self.setData(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole, date_object)
        else:
            text_nr_avail_day_groups = text_num_avail_groups(group, self.builder)
            self.setText(0, QCoreApplication.translate("TreeWidgetItem", "Group_{:02}").format(group_nr))
            self.setText(3, text_nr_avail_day_groups)
            self.setText(4, text_variation_weight)
            self.setData(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole, group_nr)
            self.setBackground(0, QColor(*widget_styles.tree_widgets.group_bg_color_rgba))
            self.setToolTip(0, QCoreApplication.translate(
                "TreeWidgetItem",
                "Double-click to edit Group {:02}"
            ).format(group_nr))

        self.setData(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole, group)
        self.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, parent_group_nr)

    def calculate_earliest_date_object(self, group: group_type) -> tuple[datetime.date, int]:
        date_object = self.builder.get_date_object_from_group(group)
        child_groups = self.builder.get_child_groups_from__parent_group_id(group.id)
        if not (date_object or child_groups):
            return datetime.date(2000, 1, 1), 0
        if date_object:
            return date_object.date, date_object.time_of_day.time_of_day_enum.time_index
        return min(self.calculate_earliest_date_object(cg) for cg in child_groups)

    def __lt__(self, other: 'TreeWidgetItem'):
        if self.treeWidget().sortColumn() != 1:
            return False
        my_group: group_type = self.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        other_group: group_type = other.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        return self.calculate_earliest_date_object(my_group) < self.calculate_earliest_date_object(other_group)


class TreeWidget(QTreeWidget):
    def __init__(self, builder: DlgGroupModeBuilderABC,
                 slot_item_moved: Callable[[TreeWidgetItem, TreeWidgetItem, TreeWidgetItem], None],
                 slot_add_group: Callable[[], TreeWidgetItem]):
        super().__init__()
        self.builder = builder

        # self.setIndentation(30)
        self.setColumnCount(5)
        self.setHeaderLabels([
            self.tr("Description"),
            self.tr("Date"),
            self.tr("Time of Day"),
            self.tr("Possible Count"),
            self.tr("Priority")
        ])
        self.setDragDropMode(QTreeWidget.InternalMove)
        self.setSortingEnabled(True)
        
        # Multi-Selection aktivieren
        self.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        
        # Kontextmenü aktivieren
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # Master-Group-Daten werden über builder.master_group verwaltet
        # (kein setData auf invisibleRootItem, um Qt-Warnung zu vermeiden)

        self.slot_item_moved = slot_item_moved
        self.slot_add_group = slot_add_group

        self.nr_main_groups = 0

        # Variable für Drag-and-Drop Items
        self.drag_items: list[QTreeWidgetItem] = []

        self.setup_tree()
        self.expand_all()

        self.setItemDelegate(ChildZebraDelegate(parent=self))

    def mimeData(self, items: Sequence[QTreeWidgetItem]) -> QtCore.QMimeData:
        # Speichere alle ausgewählten Items für Multi-Selection-Drag-and-Drop
        self.drag_items = list(items)
        return super().mimeData(items)

    def send_signal_to_date_object(self, parent_group_nr: int, item: QTreeWidgetItem):
        """Sendet Signal für Gruppen-Änderung an das Date-Object eines Items"""
        if item and (date_object := item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole)):
            self.builder.signal_handler_change__object_with_groups__group_mode(
                signal_handling.DataGroupMode(True,
                                              date_object.date,
                                              date_object.time_of_day.time_of_day_enum.time_index,
                                              parent_group_nr,
                                              (date_object.actor_plan_period.id
                                               if isinstance(date_object, schemas.AvailDay)
                                               else date_object.location_plan_period.id)
                                               )
            )

    def dropEvent(self, event: QDropEvent) -> None:
        item_to_move_to = self.itemAt(event.position().toPoint())
        
        # Verwende gespeicherte drag_items oder fallback auf aktuell ausgewählte Items
        items_to_move = self.drag_items if hasattr(self, 'drag_items') and self.drag_items else self.selectedItems()
        
        if not items_to_move:
            event.ignore()
            return
        
        # Validierung: Prüfen ob Ziel ein Date-Object ist
        if item_to_move_to and item_to_move_to.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole):
            event.ignore()
            return
        
        # Validierung: Items können nicht in sich selbst oder ihre eigenen Kinder verschoben werden
        if item_to_move_to and item_to_move_to in items_to_move:
            event.ignore()
            return
        
        # Validierung: Items können nicht in ihre eigenen Kinder verschoben werden
        if item_to_move_to:
            for item in items_to_move:
                if self._is_child_of(item_to_move_to, item):
                    event.ignore()
                    return
        
        # WICHTIG: Previous_parent Werte VOR super().dropEvent() sammeln
        previous_parents = [(item, item.parent()) for item in items_to_move]
        
        # Drop-Event akzeptieren
        super().dropEvent(event)
        
        # Neue Parent-Gruppennummer ermitteln
        new_parent_group_nr = (item_to_move_to.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
                               if item_to_move_to else 0)
        
        # Für jedes Item die Verschiebung durchführen
        for item, previous_parent in previous_parents:
            # Signal an Date-Object senden
            self.send_signal_to_date_object(new_parent_group_nr, item)
            
            # Parent-Gruppennummer aktualisieren
            item.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, new_parent_group_nr)
            
            # Item-moved Callback aufrufen
            self.slot_item_moved(item, item_to_move_to, previous_parent)
        
        # Tree nach dem Drop aktualisieren
        self.expandAll()
        for i in range(self.columnCount()): 
            self.resizeColumnToContents(i)
        
        # Drag-Items zurücksetzen
        self.drag_items = []

    def setup_tree(self):
        def add_children(parent: QTreeWidgetItem, parent_group: group_type):
            children = self.builder.get_child_groups_from__parent_group_id(parent_group.id)
            parent_group_nr = parent.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
            for child in children:
                if date_object := self.builder.get_date_object_from_group(child):
                    item = TreeWidgetItem(self.builder, parent, True)
                    item.configure(child, date_object, None, parent_group_nr)
                    self.builder.signal_handler_change__object_with_groups__group_mode(
                        signal_handling.DataGroupMode(True,
                                                      date_object.date,
                                                      date_object.time_of_day.time_of_day_enum.time_index,
                                                      parent_group_nr,
                                                      (date_object.actor_plan_period.id
                                                       if isinstance(date_object, schemas.AvailDay)
                                                       else date_object.location_plan_period.id)
                                                      )
                    )
                else:
                    self.nr_main_groups += 1
                    item = TreeWidgetItem(self.builder, parent)
                    item.configure(child, None, self.nr_main_groups, parent_group_nr)
                    add_children(item, child)

        for child in self.builder.get_child_groups_from__parent_group_id(self.builder.master_group.id):
            if date_object := self.builder.get_date_object_from_group(child):
                item = TreeWidgetItem(self.builder, self, True)
                item.configure(child, date_object, None, 0)
                self.builder.signal_handler_change__object_with_groups__group_mode(
                    signal_handling.DataGroupMode(True,
                                                  date_object.date,
                                                  date_object.time_of_day.time_of_day_enum.time_index,
                                                  0,
                                                   (date_object.actor_plan_period.id if
                                                    isinstance(date_object, schemas.AvailDay)
                                                    else date_object.location_plan_period.id)
                                                  )
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

    def show_context_menu(self, position):
        """Zeigt das Kontextmenü für Selection-Operationen (einzeln oder mehrfach)"""
        selected_items = self.selectedItems()
        if len(selected_items) < 1:
            return  # Kontextmenü nur bei ausgewählten Items
        
        # Kontextmenü nur für Items anzeigen, die verschoben werden können
        # (nicht für die Hauptgruppe/Root)
        valid_items = [item for item in selected_items if item.parent() is not None or 
                      item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole) is not None]
        
        if len(valid_items) < len(selected_items):
            # Wenn nicht alle Items verschiebbar sind, verwende nur die gültigen
            selected_items = valid_items
            if len(selected_items) < 1:
                return
        
        menu = QMenu(self)
        
        # Action: In neue Gruppe verschieben
        action_new_group = menu.addAction(self.tr("Move into a new group"))
        action_new_group.triggered.connect(lambda: self.move_selected_items_to_new_group(selected_items))
        
        # Submenu: In bestehende Gruppe verschieben
        submenu_existing = menu.addMenu(self.tr("Move into an existing group"))
        self.populate_existing_groups_menu(submenu_existing, selected_items)
        
        # Menü an der Klickposition anzeigen
        menu.exec(self.mapToGlobal(position))
    
    def populate_existing_groups_menu(self, menu: QMenu, selected_items: list[QTreeWidgetItem]):
        """Füllt das Submenu mit verfügbaren Zielgruppen"""
        # Hauptgruppe (Root) als Option
        action_root = menu.addAction(self.tr("Main group"))
        action_root.triggered.connect(lambda: self.move_selected_items_to_group(selected_items, None))
        
        menu.addSeparator()
        
        # Alle verfügbaren Gruppen durchgehen
        self._add_group_items_to_menu(menu, self.invisibleRootItem(), selected_items, "")
    
    def _add_group_items_to_menu(self, menu: QMenu, parent_item: QTreeWidgetItem, 
                                selected_items: list[QTreeWidgetItem], prefix: str):
        """Rekursiv alle Gruppen zum Menü hinzufügen (aber nicht die ausgewählten Items selbst)"""
        for i in range(parent_item.childCount()):
            child = parent_item.child(i)
            # Nur Gruppen hinzufügen (keine date_objects) und nicht die ausgewählten Items
            date_object = child.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole)
            if not date_object and child not in selected_items:
                group_nr = child.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
                if group_nr:
                    action_text = self.tr("{prefix}group {group_nr:02d}").format(prefix=prefix, group_nr=group_nr)
                    action = menu.addAction(action_text)
                    action.triggered.connect(lambda checked, item=child: self.move_selected_items_to_group(selected_items, item))
                    
                    # Rekursiv Untergruppen hinzufügen
                    self._add_group_items_to_menu(menu, child, selected_items, prefix + "  ")
    
    def move_selected_items_to_new_group(self, selected_items: list[QTreeWidgetItem]):
        """Verschiebt alle ausgewählten Items in eine neue Gruppe"""
        
        # Neue Gruppe erstellen und direkt das Item erhalten
        new_group_item = self.slot_add_group()
        
        if new_group_item:
            # Alle ausgewählten Items in die neue Gruppe verschieben
            self.move_selected_items_to_group(selected_items, new_group_item)
    
    def move_selected_items_to_group(self, selected_items: list[QTreeWidgetItem], target_group: QTreeWidgetItem | None):
        """Verschiebt alle ausgewählten Items in die angegebene Gruppe"""
        
        # Validierung: Items können nicht in sich selbst oder ihre eigenen Kinder verschoben werden
        if target_group and target_group in selected_items:
            return
        
        # Validierung: Items können nicht in ihre eigenen Kinder verschoben werden
        if target_group:
            for item in selected_items:
                if self._is_child_of(target_group, item):
                    return
        
        # Für jedes ausgewählte Item die bestehende item_moved Logik verwenden
        for item in selected_items:
            previous_parent = item.parent()
            
            # Item aus dem Tree entfernen
            if previous_parent:
                previous_parent.removeChild(item)
            else:
                index = self.indexOfTopLevelItem(item)
                self.takeTopLevelItem(index)
            
            # Item zur Zielgruppe hinzufügen
            if target_group:
                target_group.addChild(item)
                target_group_nr = target_group.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)
            else:
                self.addTopLevelItem(item)
                target_group_nr = 0
            
            # Parent-Gruppe-Nummer im Item aktualisieren
            item.setData(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole, target_group_nr)
            
            # Signal senden (nur für date_objects)
            if item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole):
                self.send_signal_to_date_object(target_group_nr, item)
            
            # Bestehende item_moved Logik aufrufen
            self.slot_item_moved(item, target_group, previous_parent)
        
        # Tree aktualisieren
        self.expandAll()
        for i in range(self.columnCount()): 
            self.resizeColumnToContents(i)
    
    def _is_child_of(self, potential_child: QTreeWidgetItem, potential_parent: QTreeWidgetItem) -> bool:
        """Prüft, ob potential_child ein Nachfahre von potential_parent ist"""
        current = potential_child.parent()
        while current:
            if current == potential_parent:
                return True
            current = current.parent()
        return False

    def expand_all(self):
        self.expandAll()
        for i in range(self.columnCount()): self.resizeColumnToContents(i)


class DlgGroupProperties(QDialog):
    def __init__(self, parent: QWidget, item: TreeWidgetItem, builder: DlgGroupModeBuilderABC):
        super().__init__(parent=parent)

        self.setFixedWidth(800)

        self.item = item
        self.builder = builder

        self.group_nr = self.item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole)

        self.setWindowTitle(
            self.tr("Properties of Group {:02}").format(self.group_nr)
            if self.group_nr
            else self.tr("Properties of Main Group")
        )

        # Für invisibleRootItem: builder.master_group verwenden (da keine Daten auf item gespeichert)
        item_group_data = self.item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        if item_group_data:
            self.group = self.builder.get_group_from_id(item_group_data.id)
        else:
            self.group = self.builder.get_group_from_id(self.builder.master_group.id)
        self.child_items: [TreeWidgetItem] = [self.item.child(i) for i in range(self.item.childCount())]
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

        self.group_nr_childs = QGroupBox(
            self.tr("Number of directly subordinate groups/appointments")
        )
        self.layout_body.addWidget(self.group_nr_childs)
        self.layout_group_nr_childs = QGridLayout(self.group_nr_childs)
        self.group_child_variation_weights = QGroupBox(
            self.tr("Prioritization of subordinate groups/appointments")
        )

        # Eine Scroll-Area zu self.group_child_variation_weights hinzufügen.
        self.scroll_area_group_child_variation_weights = QScrollArea()
        self.scroll_area_group_child_variation_weights.setWidget(self.group_child_variation_weights)
        self.scroll_area_group_child_variation_weights.setWidgetResizable(True)
        self.layout_body.addWidget(self.scroll_area_group_child_variation_weights)
        self.layout_group_child_variation_weights = QGridLayout(self.group_child_variation_weights)

        self.lb_nr_childs = QLabel(self.tr("Count:"))
        self.slider_nr_childs = SliderWithPressEvent(Qt.Orientation.Horizontal)
        self.lb_slider_nr_childs_value = QLabel()
        self.chk_none = QCheckBox(
            self.tr("All directly subordinate elements")
        )
        self.layout_group_nr_childs.addWidget(self.lb_nr_childs, 0, 0)
        self.layout_group_nr_childs.addWidget(self.slider_nr_childs, 0, 1)
        self.layout_group_nr_childs.addWidget(self.lb_slider_nr_childs_value, 0, 2)
        self.layout_group_nr_childs.addWidget(self.chk_none, 0, 3)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.sliders_variation_weights = {}

        self.setup_sliders()
        
        # Help-System Integration (nur wenn nicht überschrieben)
        self._setup_help_system()

    def _setup_help_system(self):
        """Setup Help-System (kann von Child-Klassen überschrieben werden)"""
        setup_form_help(self, "group_properties", add_help_button=True)

    def _setup_help_system(self):
        """Setup Help-System (kann von Child-Klassen überschrieben werden)"""
        setup_form_help(self, "group_properties", add_help_button=True)

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def nr_childs_changed(self, value: int):
        if self.chk_none.isChecked():
            return
        self.controller.execute(self.builder.update_nr_groups_command(group_id_type(self.group.id), value))
        self.lb_slider_nr_childs_value.setText(f'{value}')
        self.group = self.builder.get_group_from_id(group_id_type(self.group.id))

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
        self.group = self.builder.get_group_from_id(group_id_type(self.group.id))

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
                text_child_group = self.tr('Group {:02}').format(child_group_nr)
            else:
                date_object: date_object_type = child_item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT,
                                                                Qt.ItemDataRole.UserRole)
                text_child_group = f'{date_to_string(date_object.date)} ({date_object.time_of_day.name})'
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


class DlgGroupPropertiesAvailDay(DlgGroupProperties):
    def __init__(self, parent: QWidget, item: TreeWidgetItem, builder: DlgGroupModeBuilderABC):
        self.required_avail_day_widgets_are_available = False
        self.chk_required_avail_day_groups_is_locked = False

        super().__init__(parent, item, builder)

        self.required_avail_day_groups = db_services.RequiredAvailDayGroups.get_from__avail_day_group(self.group.id)

        self.scroll_required_avail_day_groups_locations = QScrollArea()
        self.scroll_required_avail_day_groups_locations.setWidgetResizable(True)
        self.group_required_avail_day_groups_locations = QGroupBox(
            self.tr("Locations requiring minimum number of assignments")
        )
        self.scroll_required_avail_day_groups_locations.setWidget(self.group_required_avail_day_groups_locations)

        self.layout_required_avail_day_groups_locations = QVBoxLayout(self.group_required_avail_day_groups_locations)

        if all(child.date_object for child in self.child_items):
            self._setup_required_avail_day_groups_widgets()
            self.setup_required_avail_day_groups_widget_values()
            self.required_avail_day_widgets_are_available = True

    def _setup_help_system(self):
        """Setup Help-System für erweiterte Verfügbarkeits-Features"""
        setup_form_help(self, "group_properties_avail_day", add_help_button=True)

    def chk_none_toggled(self, checked: bool, clicked=False):
        super().chk_none_toggled(checked, clicked)
        if self.required_avail_day_widgets_are_available:
            self.update_required_avail_day_groups_widget_values()

    def _setup_required_avail_day_groups_widgets(self):
        self.locations_of_work = self._locations_of_work()
        self.checkboxes_locations_of_work: dict[UUID, QCheckBox] = {}
        text_tooltip = self.tr(
            "When activated:\n"
            "Staff will only be assigned in this group\n"
            "if they reach the specified minimum number of assignments."
        )
        self.lb_num_required_avail_day_groups = QLabel(self.tr("Minimum number of assignments:"))
        self.slider_num_required_avail_day_groups = SliderWithPressEvent(Qt.Orientation.Horizontal)
        self.slider_num_required_avail_day_groups.setTickInterval(1)
        self.slider_num_required_avail_day_groups.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_num_required_avail_day_groups.setRange(
            1, self.builder.get_max_value_num_required_avail_day_groups(self.group))
        self.slider_num_required_avail_day_groups.setToolTip(text_tooltip)

        self.lb_without_required_avail_day_groups = QLabel(self.tr("...Without condition"))
        self.lb_without_required_avail_day_groups.setStyleSheet('color: green')
        self.lb_num_avail_day_groups_value = QLabel()
        self.chk_num_required_avail_day_groups = QCheckBox(self.tr("Activate condition?"))
        self.chk_num_required_avail_day_groups.setToolTip(text_tooltip)
        self.chk_required_avail_day_groups_locations = QCheckBox(self.tr("Activate only for specific facilities"))
        self.chk_required_avail_day_groups_locations.setToolTip(
            self.tr("Condition should only apply to selected facilities")
        )
        self.layout_group_nr_childs.addWidget(self.lb_num_required_avail_day_groups, 1, 0)
        self.layout_group_nr_childs.addWidget(self.lb_num_avail_day_groups_value, 1, 2)
        self.layout_group_nr_childs.addWidget(self.chk_num_required_avail_day_groups, 1, 3)
        self.layout_group_nr_childs.addWidget(self.chk_required_avail_day_groups_locations, 1, 4)
        self._setup_locations_of_work_checkboxes()

    def _setup_locations_of_work_checkboxes(self):
        for location in self.locations_of_work:
            chk = QCheckBox(location.name_an_city)
            self.checkboxes_locations_of_work[location.id] = chk
            chk.setToolTip(self.tr("Right-click: Select only {name}").format(name=location.name_an_city))
            self.layout_required_avail_day_groups_locations.addWidget(chk)

    def setup_required_avail_day_groups_widget_values(self):
        # if not self.builder.all_child_groups_have_avail_day(self.group):
        #     self.chk_required_avail_day_groups_is_locked = True
        #     return
        # self.update_required_widget_values()
        required_avail_day_groups = self.required_avail_day_groups
        self.slider_nr_childs.valueChanged.connect(
            lambda: self.slider_num_required_avail_day_groups.setMaximum(
                self.builder.get_max_value_num_required_avail_day_groups(self.group)))
        if required_avail_day_groups:
            self.slider_num_required_avail_day_groups.setValue(required_avail_day_groups.num_avail_day_groups)
            self.layout_group_nr_childs.addWidget(self.slider_num_required_avail_day_groups, 1, 1)
            self.chk_num_required_avail_day_groups.setChecked(True)
            self.lb_num_avail_day_groups_value.setText(f'{required_avail_day_groups.num_avail_day_groups}')
            if required_avail_day_groups.locations_of_work:
                self.layout_group_nr_childs.addWidget(self.scroll_required_avail_day_groups_locations, 2, 0, 1, 5)
                self.chk_required_avail_day_groups_locations.setChecked(True)
                for location in required_avail_day_groups.locations_of_work:
                    self.checkboxes_locations_of_work[location.id].setChecked(True)
            else:
                self.chk_required_avail_day_groups_locations.setChecked(False)
                for chk in self.checkboxes_locations_of_work.values():
                    chk.setChecked(True)
        else:
            self.chk_required_avail_day_groups_locations.setEnabled(False)
            self.lb_num_avail_day_groups_value.setText('1')
            self.layout_group_nr_childs.addWidget(self.lb_without_required_avail_day_groups, 1, 1)

        self.chk_num_required_avail_day_groups.toggled.connect(self.chk_num_required_avail_day_groups_toggled)
        self.chk_required_avail_day_groups_locations.toggled.connect(self.chk_required_avail_day_groups_locations_toggled)
        self.slider_num_required_avail_day_groups.valueChanged.connect(
            self._update_required_avail_day_groups)
        for l_id, chk in self.checkboxes_locations_of_work.items():
            chk.toggled.connect(self._update_required_avail_day_groups)
            # Rechtsklick-Kontextmenü für die Checkboxes
            chk.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            chk.customContextMenuRequested.connect(lambda pos, loc_id=l_id: self._right_click_chk_location_of_work(loc_id, pos))

    def _right_click_chk_location_of_work(self, l_id, pos):
        """
        Slot, der bei einem Rechtsklick (Kontextmenü) ausgeführt wird.
        Setzt die angeklickte Checkbox auf True und alle anderen auf False.
        """
        # Setze die angeklickte Checkbox
        self.checkboxes_locations_of_work[l_id].setChecked(True)

        # Iteriere über alle Checkboxes und deaktiviere die, die nicht angeklickt wurden
        for other_id, other_chk in self.checkboxes_locations_of_work.items():
            if other_id != l_id:
                other_chk.setChecked(False)

    def update_required_avail_day_groups_widget_values(self):
        if not self.required_avail_day_widgets_are_available:
            return
        max_required = self.builder.get_max_value_num_required_avail_day_groups(self.group)
        if max_required < 2:
            self.chk_num_required_avail_day_groups.setChecked(False)
            self.chk_num_required_avail_day_groups.setDisabled(True)
        else:
            if not self.chk_required_avail_day_groups_is_locked:
                self.chk_num_required_avail_day_groups.setEnabled(True)
            if self.chk_num_required_avail_day_groups.isChecked():
                new_value = min([max_required, self.slider_num_required_avail_day_groups.value()])
                self.slider_num_required_avail_day_groups.setValue(new_value)
                self.lb_num_avail_day_groups_value.setText(str(new_value))
        self.slider_num_required_avail_day_groups.setRange(1, max_required)

    def chk_num_required_avail_day_groups_toggled(self):
        self.scroll_required_avail_day_groups_locations.setParent(None)
        if self.chk_num_required_avail_day_groups.isChecked():
            max_value = self.builder.get_max_value_num_required_avail_day_groups(self.group)
            self.lb_without_required_avail_day_groups.setParent(None)
            self.layout_group_nr_childs.addWidget(self.slider_num_required_avail_day_groups, 1, 1)
            self.slider_num_required_avail_day_groups.setValue(max_value)
            self.lb_num_avail_day_groups_value.setText(str(max_value))
            self.chk_required_avail_day_groups_locations.setEnabled(True)
        else:
            self.slider_num_required_avail_day_groups.setParent(None)
            self.slider_num_required_avail_day_groups.setValue(1)
            self.layout_group_nr_childs.addWidget(self.lb_without_required_avail_day_groups, 1, 1)
            self.lb_num_avail_day_groups_value.setText('1')
            self.chk_required_avail_day_groups_locations.toggled.disconnect()
            self.chk_required_avail_day_groups_locations.setChecked(False)
            self.chk_required_avail_day_groups_locations.toggled.connect(
                self.chk_required_avail_day_groups_locations_toggled)
            self.chk_required_avail_day_groups_locations.setEnabled(False)

    def chk_required_avail_day_groups_locations_toggled(self):
        if self.chk_required_avail_day_groups_locations.isChecked():
            self.layout_group_nr_childs.addWidget(self.scroll_required_avail_day_groups_locations, 2, 0, 1, 5)
        else:
            self.scroll_required_avail_day_groups_locations.setParent(None)
        for chk in self.checkboxes_locations_of_work.values():
            chk.setChecked(True)
        self._adjust_widget_height()


    def _locations_of_work(self) -> list[schemas.LocationOfWork]:
        dates = [child_item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole).date
                 for child_item in self.child_items]
        return sorted(db_services.LocationOfWork.get_all_locations_at_dates(
            self.builder.object_with_groups.team.id, dates), key=lambda l: l.name_an_city)


    def _update_required_avail_day_groups(self):
        new_value_nums = self.slider_num_required_avail_day_groups.value()
        location_ids = [location_id for location_id, chk in self.checkboxes_locations_of_work.items() if chk.isChecked()]
        if new_value_nums < 2:
            new_value_nums = None
            command = required_avail_day_groups_commands.Delete(
                self.required_avail_day_groups.id)
            self.controller.execute(command)
            self.chk_num_required_avail_day_groups.setChecked(False)
            self.required_avail_day_groups = None
        else:
            if not self.required_avail_day_groups:
                command = required_avail_day_groups_commands.Create(self.group.id, new_value_nums, [])
                self.controller.execute(command)
                self.required_avail_day_groups = command.created_required_avail_day_groups
            else:
                if not location_ids and self.chk_required_avail_day_groups_locations.isChecked():
                    self.chk_required_avail_day_groups_locations.setChecked(False)
                    self.chk_num_required_avail_day_groups.setChecked(False)
                    return
                elif len(location_ids) == len(self.checkboxes_locations_of_work):
                    location_ids = []
                command = required_avail_day_groups_commands.Update(self.required_avail_day_groups.id,
                                                                    new_value_nums, location_ids)
                self.controller.execute(command)
                self.required_avail_day_groups = command.updated_required_avail_day_groups
        self.lb_num_avail_day_groups_value.setText(str(new_value_nums or 1))

    def _adjust_widget_height(self):
        QApplication.processEvents()
        height_group_child_variation_weights = self.group_child_variation_weights.sizeHint().height() + 37
        height_group_required_avail_day_groups_locations = (
            self.group_required_avail_day_groups_locations.sizeHint().height() + 37
            if self.chk_required_avail_day_groups_locations.isChecked() else 0)
        self.resize(
            self.width(),
            min(height_group_required_avail_day_groups_locations
                + height_group_child_variation_weights + 90,
                Screen.screen_height - 40)
        )


class DlgGroupMode(QDialog):
    def __init__(self, parent: QWidget, builder: DlgGroupModeBuilderABC):
        super().__init__(parent)

        self.setWindowTitle(self.tr('Group Mode'))
        self.resize(400, 400)

        # Help-System Integration
        setup_form_help(self, "group_mode", add_help_button=True)

        self.builder = builder
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.simplified = False

        # Setup layouts
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        # Setup main group button
        self.text_template_master_group = self.tr('Edit Main Group (possible count: {count})')
        text_master_group = self.text_template_master_group.format(
            count=text_num_avail_groups(builder.master_group, builder)
        )
        self.bt_edit_main_group = QPushButton(text_master_group,
                                              clicked=lambda: self.edit_item(self.tree_groups.invisibleRootItem()))
        self.layout_body.addWidget(self.bt_edit_main_group)

        # Setup tree widget
        self.tree_groups = TreeWidget(self.builder, self.item_moved, self.add_group)
        self.tree_groups.itemDoubleClicked.connect(self.edit_item)
        self.tree_groups.setExpandsOnDoubleClick(False)
        self.layout_body.addWidget(self.tree_groups)

        # Setup modification buttons
        self.layout_mod_buttons = QHBoxLayout()
        self.layout_foot.addLayout(self.layout_mod_buttons)
        self.bt_add_group = QPushButton(self.tr('New Group'), clicked=self.add_group)
        self.layout_mod_buttons.addWidget(self.bt_add_group)
        self.bt_remove_group = QPushButton(self.tr('Remove Group'), clicked=self.remove_group)
        self.layout_mod_buttons.addWidget(self.bt_remove_group)

        # Setup dialog buttons
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
        return new_item

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
                parent_group = self.builder.get_group_from_id(self.builder.master_group.id)
            self.controller.execute(self.builder.delete_group_command(data.id))

            # Weil sich nr_groups durch Inkonsistenzen geändert haben könnte:
            nr_groups = self.builder.get_nr_groups_from_group(parent_group)
            text_nr_groups = str(nr_groups) if nr_groups else 'alle'
            if parent_item:
                parent_item.setText(TREE_HEAD_COLUMN__NR_GROUPS, text_nr_groups)
            else:
                # Button-Text aktualisieren statt invisibleRootItem (vermeidet Qt-Warnung)
                self.bt_edit_main_group.setText(
                    self.text_template_master_group.format(count=text_nr_groups))

    def item_moved(self, moved_item: TreeWidgetItem, moved_to: TreeWidgetItem, previous_parent: TreeWidgetItem):
        object_to_move = moved_item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        if moved_to:
            obj_to_move_to: group_type = moved_to.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        else:
            obj_to_move_to = self.builder.master_group

        self.controller.execute(self.builder.set_new_parent_group_command(object_to_move.id, obj_to_move_to.id))

        if not previous_parent:
            parent_group = self.builder.master_group
        else:
            parent_group = previous_parent.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)

        if self.builder.num_required_group_field:
            self.builder.adjust_num_required_avail_day_groups(obj_to_move_to, self.controller)
            self.builder.adjust_num_required_avail_day_groups(parent_group, self.controller)

        # Weil sich nr_groups durch Inkonsistenzen geändert haben könnte:
        if not previous_parent:
            return
        nr_groups = self.builder.get_nr_groups_from_group(parent_group)
        text_nr_groups = str(nr_groups) if nr_groups else 'alle'
        previous_parent.setText(TREE_HEAD_COLUMN__NR_GROUPS, text_nr_groups)

    def edit_item(self, item: QTreeWidgetItem):
        data_group = item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole)
        data_date_object = item.data(TREE_ITEM_DATA_COLUMN__DATE_OBJECT, Qt.ItemDataRole.UserRole)
        data_parent_group_nr = item.data(TREE_ITEM_DATA_COLUMN__PARENT_GROUP_NR, Qt.ItemDataRole.UserRole)
        if data_date_object:
            # todo: implement moving items with date_object to other groups or to root
            print(item.text(0), data_date_object.date, data_date_object.time_of_day.name, f'Gr. {data_parent_group_nr}')
            print(f'{data_group=}')
        else:
            if self.builder.num_required_group_field:
                dlg = DlgGroupPropertiesAvailDay(self, item, self.builder) #
            else:
                dlg = DlgGroupProperties(self, item, self.builder)
            if not dlg.exec():
                return
            self.controller.add_to_undo_stack(dlg.controller.undo_stack)
            self.builder.reload_object_with_groups()

            self.update_items_after_edit(item)

    def update_items_after_edit(self, item: TreeWidgetItem):
        if item == self.tree_groups.invisibleRootItem():
            # Für invisibleRootItem: builder.master_group aktualisieren (vermeidet Qt-Warnung)
            new_group_data = self.builder.get_group_from_id(self.builder.master_group.id)
            self.builder.master_group = new_group_data
            text_nr_groups = text_num_avail_groups(new_group_data, self.builder)
            self.bt_edit_main_group.setText(self.text_template_master_group.format(count=text_nr_groups))
        else:
            new_group_data = self.builder.get_group_from_id(
                item.data(TREE_ITEM_DATA_COLUMN__GROUP, Qt.ItemDataRole.UserRole).id)
            text_nr_groups = text_num_avail_groups(new_group_data, self.builder)
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
                        self,
                        self.tr('Group Mode'),
                        self.tr('At least one group has only one appointment:\n'
                               'Group {group_nr}, {date} ({time_of_day})\n'
                               'Please correct this.').format(
                                   group_nr=item.data(TREE_ITEM_DATA_COLUMN__MAIN_GROUP_NR, Qt.ItemDataRole.UserRole),
                                   date=date_object.date.strftime("%d.%m.%y"),
                                   time_of_day=date_object.time_of_day.name
                               )
                    )
                else:
                    QMessageBox.critical(
                        self,
                        self.tr('Group Mode'),
                        self.tr('At least one group contains only one group\n'
                               'Please correct this.')
                    )
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
            QMessageBox.information(
                self,
                self.tr('Group Mode'),
                self.tr('The group structure was simplified by removing unnecessary groups.')
            )
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

        self.resize(self.size().width(), min(height + 200, Screen.screen_height - 40))


# todo: Toolset, um bestimmte Gruppierungs-Abläufe automatisiert festzulegen (Periodenweit, Tagesweit)...
#       Z.B.: nur 1 Schicht am Tag, die gleiche Schicht, pro Woche...
#       Voreinstellungen in: Project, Person, PlanPeriod, ActorPlanPeriod
