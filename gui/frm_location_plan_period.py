import datetime
import functools
import os
from typing import Callable, Literal
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout, QAbstractItemView, QHeaderView, QTableWidgetItem, QPushButton, QMessageBox, QApplication, \
    QMenu

from database import schemas, db_services
from database.special_schema_requests import get_curr_assignment_of_location
from gui import frm_flag, frm_time_of_day, frm_group_mode, frm_cast_group, widget_styles, data_processing
from gui.custom_widgets import side_menu
from tools import helper_functions
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import event_commands, cast_group_commands
from gui.frm_fixed_cast import DlgFixedCastBuilderLocationPlanPeriod, DlgFixedCastBuilderCastGroup
from gui.observer import signal_handling


# Durch direkte Implementierung von signal.disconnect in die entsprechenden Widget-Klassen
# ist diese Funktion nicht mehr notwendig
def disconnect_event_button_signals():
    print('disconnect_event_button_signals')
    try:
        signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.disconnect()
    except Exception as e:
        print(f'Fehler in disconnect_event_button_signals: {e}')
    try:
        signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.disconnect()
    except Exception as e:
        print(f'Fehler in disconnect_event_button_signals: {e}')


class ButtonEvent(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow, slot__event_toggled: Callable):
        super().__init__(parent)
        self.slot__event_toggled = slot__event_toggled
        self.setObjectName(f'{date}-{time_of_day.time_of_day_enum.name}')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCheckable(True)
        self.clicked.connect(self.button_clicked)
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.parent = parent

        signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.connect(
            self.set_group_mode)
        signal_handling.handler_location_plan_period.signal_reload_location_pp__events.connect(
            self.reload_location_plan_period
        )

        self.group_mode = False

        self.location_plan_period = location_plan_period
        self.date = date
        self.time_of_day = time_of_day
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        self.context_menu = QMenu()
        self.menu_times_of_day = QMenu('Tageszeiten')
        self.context_menu.addMenu(self.menu_times_of_day)
        self.create_actions__skills_fixed_flags_notes()

        self.set_stylesheet()

        self.actions = []
        self.create_actions_times_of_day()
        self.menu_times_of_day.addActions(self.actions)
        self.set_tooltip()

    def set_stylesheet(self):
        self.setStyleSheet(widget_styles.buttons.avail_day__event[self.time_of_day.time_of_day_enum.time_index])

    @Slot(signal_handling.DataGroupMode)
    def set_group_mode(self, group_mode: signal_handling.DataGroupMode):
        self.group_mode = group_mode.group_mode
        if self.isChecked():
            if self.group_mode:
                if group_mode.date and (group_mode.date == self.date
                                        and group_mode.time_index == self.time_of_day.time_of_day_enum.time_index):
                    self.setText(f'{group_mode.group_nr:02}' if group_mode.group_nr else None)
            else:
                self.setText(None)
        elif self.group_mode:
            self.setDisabled(True)
        else:
            self.setEnabled(True)

    def get_t_o_d_for_selection(self) -> list[schemas.TimeOfDay]:
        location_plan_period_time_of_days = sorted(
            [t_o_d for t_o_d in self.location_plan_period.time_of_days if not t_o_d.prep_delete], key=lambda x: x.start)
        return [t_o_d for t_o_d in location_plan_period_time_of_days
                if t_o_d.time_of_day_enum.time_index == self.time_of_day.time_of_day_enum.time_index]

    def contextMenuEvent(self, pos):
        self.context_menu.exec(pos.globalPos())

    def create_actions__skills_fixed_flags_notes(self):
        for text, slot in (('Skills', self.edit_skills), ('Feste Beseztung', self.edit_fixed_cast),
                           ('Flags', self.edit_flags), ('Notizen', self.edit_notes)):
            self.context_menu.addAction(MenuToolbarAction(self, None, text, None, slot))

    def reset_menu_times_of_day(self, location_plan_period: schemas.LocationPlanPeriodShow):
        self.location_plan_period = location_plan_period
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        for action in self.menu_times_of_day.actions():
            self.menu_times_of_day.removeAction(action)
        self.create_actions_times_of_day()
        self.menu_times_of_day.addActions(self.actions)

    def create_actions_times_of_day(self):
        self.actions = [
            MenuToolbarAction(self, QIcon(os.path.join(os.path.dirname(__file__),
                                            'resources/toolbar_icons/icons/clock-select.png'))
            if t.name == self.time_of_day.name else None,
                   f'{t.name}: {t.start.strftime("%H:%M")}-{t.end.strftime("%H:%M")}', None,
                              functools.partial(self.set_new_time_of_day, t))
            for t in self.t_o_d_for_selection]

    def set_new_time_of_day(self, new_time_of_day: schemas.TimeOfDay):
        if self.isChecked():
            event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id,
                                                                     self.date, self.time_of_day.id)
            event_commands.UpdateTimeOfDay(event, new_time_of_day.id).execute()

        self.time_of_day = new_time_of_day
        self.reload_location_plan_period()
        self.create_actions_times_of_day()
        self.reset_menu_times_of_day(self.location_plan_period)
        self.set_tooltip()
        signal_handling.handler_location_plan_period.reload_location_pp_on__frm_location_plan_period()

    def edit_skills(self):
        print('edit_skills')

    def edit_fixed_cast(self):
        if not self.isChecked():
            QMessageBox.critical(self, 'Flags',
                                 'Sie müssen zuerst einen Termin setzen, bevor Sie die Besetzung bearbeiten können.')
            return
        event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, self.date,
                                                                 self.time_of_day.id)
        cast_group = db_services.CastGroup.get(event.cast_group.id)
        dlg = DlgFixedCastBuilderCastGroup(self.parent, cast_group).build()
        if dlg.exec():
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, self.date)
            )

    def edit_flags(self):
        if not self.isChecked():
            QMessageBox.critical(self, 'Flags',
                                 'Sie müssen zuerst einen Termin setzen, bevor Sie die Flags bearbeiten können.')
            return
        event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, self.date,
                                                                 self.time_of_day.id)
        dlg = frm_flag.DlgFlagsBuilderEvent(self.parent, event).dlg_flags
        if dlg.exec():
            ...

    def edit_notes(self):
        print('edit_notes')

    def set_tooltip(self):
        self.setToolTip(f'Rechtsklick:\n'
                        f'Zeitspanne für die Tageszeit "{self.time_of_day.time_of_day_enum.name}" '
                        f'am {self.date} wechseln.\nAktuell: {self.time_of_day.name} '
                        f'({self.time_of_day.start.strftime("%H:%M")}-{self.time_of_day.end.strftime("%H:%M")})')

    @Slot(signal_handling.DataLocationPPWithDate)
    def reload_location_plan_period(self, data: signal_handling.DataLocationPPWithDate = None):
        if data is not None:
            self.location_plan_period = data.location_plan_period
        else:
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)

    @Slot()
    def button_clicked(self):
        self.slot__event_toggled(self)
        signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
            signal_handling.DataDate(self.location_plan_period.plan_period.id, self.date)
        )


class ButtonFixedCast(QPushButton):  # todo: Fertigstellen... + Tooltip Feste Besetzung der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow, cast_groups_of_pp: list[schemas.CastGroupShow]):
        super().__init__(parent=parent)

        signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.connect(
            self.reload_location_plan_period
        )
        signal_handling.handler_location_plan_period.signal_reset_styling_fixed_cast_configs.connect(
            self.reset_styling
        )

        signal_handling.handler_location_plan_period.signal_reload_cast_groups__cast_configs.connect(
            self.reload_cast_groups_at_day
        )
        self.clicked.connect(self.set_fixed_casts_of_day)

        self.parent = parent
        self.location_plan_period = location_plan_period
        self.date = date
        self.cast_groups_at_day = [c for c in cast_groups_of_pp if c.event
                                   and c.event.location_plan_period.id == self.location_plan_period.id
                                   and c.event.date == self.date]
        self.setObjectName(f'fixed_cast: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.set_stylesheet_and_tooltip()

    @Slot(signal_handling.DataDate)
    def reload_cast_groups_at_day(self, data: signal_handling.DataDate = None):
        if data:
            if data.plan_period_id != self.location_plan_period.plan_period.id:
                return
            if data.date is not None and data.date != self.date:
                return
        self.cast_groups_at_day = [
            cast_group for cast_group in
            db_services.CastGroup.get_all_from__plan_period(self.location_plan_period.plan_period.id)
            if cast_group.event and cast_group.event.date == self.date
               and cast_group.event.location_plan_period.id == self.location_plan_period.id
        ]

    def check_fixed_cast__eq_to__local_pp(self):
        if not self.cast_groups_at_day:
            return
        fixed_casts_at_day = [c.fixed_cast for c in self.cast_groups_at_day]
        return (
            len(set(fixed_casts_at_day)) == 1
            and fixed_casts_at_day[0] == self.location_plan_period.fixed_cast
        )

    def set_stylesheet_and_tooltip(self):
        self.set_stylesheet()
        self.set_tooltip()

    def set_stylesheet(self):
        check_all_equal = self.check_fixed_cast__eq_to__local_pp()
        if check_all_equal is None:
            self.setStyleSheet(
                f"ButtonFixedCast {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonFixedCast::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif check_all_equal:
            self.setStyleSheet(
                f"ButtonFixedCast {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonFixedCast::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonFixedCast {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonFixedCast::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def set_tooltip(self):
        if not self.cast_groups_at_day:
            additional_txt = ''
        elif len({cg.fixed_cast for cg in self.cast_groups_at_day}) > 1:
            additional_txt = '\nBesetzung der Events an diesem Tag:\nUnterschiedliche Besetzungen.'
        else:
            cast_clear_txt = helper_functions.generate_fixed_cast_clear_text(self.cast_groups_at_day[0].fixed_cast)
            additional_txt = (f'\nBesetzung der Events an diesem Tag:\n'
                              f'{cast_clear_txt or "Keine Festen Besetzungen."}')

        self.setToolTip(f'Hier können die Festen Besetzungen des Tages geändert werden.{additional_txt}')

    @Slot()
    def set_fixed_casts_of_day(self):
        if not self.cast_groups_at_day:
            QMessageBox.information(self, 'Feste Besetzung am Tag',
                                    f'Am {self.date:%d.%m.} sind keine Events vorhanden.')
            return

        dlg = DlgFixedCastBuilderCastGroup(self.parent, self.cast_groups_at_day[0]).build()
        if dlg.exec():
            if len(self.cast_groups_at_day) > 1:
                for cg in self.cast_groups_at_day[1:]:
                    cast_group_commands.UpdateFixedCast(cg.id, dlg.fixed_cast_simplified).execute()
            self.set_stylesheet_and_tooltip()

    @Slot(signal_handling.DataLocationPPWithDate)
    def reload_location_plan_period(self, data: signal_handling.DataLocationPPWithDate):
        if (data.date and data.date == self.date) or not data.date:
            self.location_plan_period = data.location_plan_period

    @Slot(signal_handling.DataDate)
    def reset_styling(self, data: signal_handling.DataDate):
        if data.plan_period_id != self.location_plan_period.plan_period.id:
            return
        if (data.date and data.date == self.date) or not data.date:
            self.reload_cast_groups_at_day()
            self.set_stylesheet_and_tooltip()


class ButtonNotes(QPushButton):  # todo: Fertigstellen... + Tooltip Notes der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent)

        self.setObjectName(f'notes: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)


class ButtonFlags(QPushButton):  # todo: Fertigstellen... + Tooltip Flags der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent)

        self.setObjectName(f'flags: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)


class FrmTabLocationPlanPeriods(QWidget):
    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        signal_handling.handler_show_dialog.signal_show_dlg_cast_group_pp.connect(self.edit_cast_groups_plan_period)

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.location_plan_periods = self.plan_period.location_plan_periods
        self.location_id__location_pp = {str(loc_pp.location_of_work.id): loc_pp
                                         for loc_pp in self.plan_period.location_plan_periods}
        self.location_id: UUID | None = None
        self.location: schemas.LocationOfWorkShow | None = None
        self.frame_events: FrmLocationPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum der Einrichtung:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_pp.setFixedHeight(180)
        self.te_notes_pp.setDisabled(True)

        self.lb_notes_location = QLabel('Infos zur Einrichtung:')
        self.lb_notes_location.setFixedHeight(20)
        font_lb_notes = self.lb_notes_location.font()
        font_lb_notes.setBold(True)
        self.lb_notes_location.setFont(font_lb_notes)
        self.te_notes_location = QTextEdit()
        self.te_notes_location.textChanged.connect(self.save_info_location)
        self.te_notes_location.setFixedHeight(180)
        self.te_notes_location.setDisabled(True)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lb_title_name = QLabel('Einrichtungstermine')
        self.lb_title_name.setContentsMargins(10, 10, 10, 10)

        self.lb_title_name_font = self.lb_title_name.font()
        self.lb_title_name_font.setPointSize(16)
        self.lb_title_name_font.setBold(True)
        self.lb_title_name.setFont(self.lb_title_name_font)
        self.layout.addWidget(self.lb_title_name)

        self.splitter_events = QSplitter()
        self.layout.addWidget(self.splitter_events)

        self.table_select_location = QTableWidget()
        self.splitter_events.addWidget(self.table_select_location)
        self.setup_selector_table()
        self.widget_events = QWidget()
        self.layout_events = QVBoxLayout()
        self.layout_events.setContentsMargins(0, 0, 0, 0)
        self.widget_events.setLayout(self.layout_events)
        self.splitter_events.addWidget(self.widget_events)
        self.set_splitter_sizes()

        self.scroll_area_events = QScrollArea()

        self.bt_cast_groups_plan_period = QPushButton('Besetzungen der Planungsperiode bearbeiten...',
                                                      clicked=self.edit_cast_groups_plan_period)

        self.layout_controllers = QHBoxLayout()
        self.layout_notes = QHBoxLayout()
        self.layout_notes_location = QVBoxLayout()
        self.layout_notes_location_pp = QVBoxLayout()

        self.layout_events.addWidget(self.scroll_area_events)
        self.layout_events.addLayout(self.layout_controllers)
        self.layout_events.addLayout(self.layout_notes)
        self.layout_notes.addLayout(self.layout_notes_location_pp)
        self.layout_notes.addLayout(self.layout_notes_location)
        self.layout_notes_location_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_location_pp.addWidget(self.te_notes_pp)
        self.layout_notes_location.addWidget(self.lb_notes_location)
        self.layout_notes_location.addWidget(self.te_notes_location)

        self.layout.addWidget(self.bt_cast_groups_plan_period)

        self.side_menu = side_menu.WidgetSideMenu(self, 250, 10, 'right')

    def setup_selector_table(self):
        self.table_select_location.setSortingEnabled(True)
        self.table_select_location.setAlternatingRowColors(True)
        self.table_select_location.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_select_location.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_select_location.verticalHeader().setVisible(False)
        self.table_select_location.horizontalHeader().setHighlightSections(False)
        self.table_select_location.cellClicked.connect(self.data_setup)
        self.table_select_location.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_location.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        headers = ['id', 'Name', 'Ort']
        self.table_select_location.setColumnCount(len(headers))
        self.table_select_location.setRowCount(len(self.location_id__location_pp))
        self.table_select_location.setHorizontalHeaderLabels(headers)
        for row, location_pp in enumerate(sorted(self.location_id__location_pp.values(),
                                                 key=lambda x: x.location_of_work.name)):
            self.table_select_location.setItem(row, 0, QTableWidgetItem(str(location_pp.location_of_work.id)))
            self.table_select_location.setItem(row, 1, QTableWidgetItem(location_pp.location_of_work.name))
            self.table_select_location.setItem(row, 2, QTableWidgetItem(location_pp.location_of_work.address.city))
        self.table_select_location.hideColumn(0)

    def set_splitter_sizes(self):
        self.splitter_events.setStretchFactor(0, 0)
        self.splitter_events.setStretchFactor(1, 1)
        header_width = sum(self.table_select_location.horizontalHeader().sectionSize(i)
                           for i in range(self.table_select_location.columnCount()))
        header_width += 3

        self.splitter_events.setSizes([header_width, 10_000])
        self.table_select_location.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def data_setup(self, row: int = None, col: int = None, location_id: UUID = None):
        if location_id is None:
            self.location_id = UUID(self.table_select_location.item(row, 0).text())
        else:
            self.location_id = location_id
        self.te_notes_location.setEnabled(True)
        self.te_notes_pp.setEnabled(True)
        self.location = db_services.LocationOfWork.get(self.location_id)
        location_plan_period = self.location_id__location_pp[str(self.location_id)]
        location_plan_period_show = db_services.LocationPlanPeriod.get(location_plan_period.id)
        self.lb_title_name.setText(f'Termine: {location_plan_period_show.location_of_work.name} '
                                   f'{location_plan_period_show.location_of_work.address.city}')

        if self.frame_events:
            self.delete_location_plan_period_widgets()
        self.frame_events = FrmLocationPlanPeriod(self, location_plan_period_show, self.side_menu)
        self.scroll_area_events.setWidget(self.frame_events)
        self.scroll_area_events.setMinimumHeight(
            10000)  # brauche ich seltsamerweise, damit die Scrollarea expandieren kann.
        self.scroll_area_events.setMinimumHeight(0)

        self.info_text_setup()

    def delete_location_plan_period_widgets(self):
        self.frame_events.deleteLater()
        for widget in (self.layout_controllers.itemAt(i).widget() for i in range(self.layout_controllers.count())):
            widget.deleteLater()

    def info_text_setup(self):
        self.te_notes_pp.textChanged.disconnect()
        self.te_notes_pp.clear()
        self.te_notes_pp.setText(self.location_id__location_pp[str(self.location_id)].notes)
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)

        self.te_notes_location.textChanged.disconnect()
        self.te_notes_location.clear()
        self.te_notes_location.setText(self.location.notes)
        self.te_notes_location.textChanged.connect(self.save_info_location)

    def save_info_location_pp(self):
        updated_location_plan_period = db_services.LocationPlanPeriod.update_notes(
            self.location_id__location_pp[str(self.location_id)].id, self.te_notes_pp.toPlainText())
        self.location_id__location_pp[str(self.location_id)] = updated_location_plan_period

    def save_info_location(self):
        self.location.notes = self.te_notes_location.toPlainText()
        updated_location = db_services.LocationOfWork.update_notes(
            self.location_id, self.te_notes_location.toPlainText())

    def edit_cast_groups_plan_period(self):
        visible_plan_period_ids = {location_pp.id for location_pp in self.plan_period.location_plan_periods}
        dlg = frm_cast_group.DlgCastGroups(self, self.plan_period, visible_plan_period_ids)
        if dlg.exec():
            print('ausgeführt')


class FrmLocationPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabLocationPlanPeriods, location_plan_period: schemas.LocationPlanPeriodShow,
                 side_menu: side_menu.WidgetSideMenu):
        super().__init__(parent)

        self.setContentsMargins(0, 0, 0, 10)

        self.parent = parent
        self.layout_controllers = parent.layout_controllers

        signal_handling.handler_location_plan_period.signal_reload_location_pp__frm_location_plan_period.connect(
            self.reload_location_plan_period)
        signal_handling.handler_show_dialog.signal_show_dlg_event_group.connect(self.change_mode__event_group)

        self.data_processor = data_processing.LocationPlanPeriodData(self, location_plan_period)

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu
        self.setup_side_menu()

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.location_plan_period = location_plan_period
        self.t_o_d_standards: list[schemas.TimeOfDay] = []
        self.t_o_d_enums: list[schemas.TimeOfDayEnum] = []
        self.days: list[datetime.date] = []
        self.set_instance_variables()

        self.weekdays = {0: 'Mo', 1: 'Di', 2: 'Mi', 3: 'Do', 4: 'Fr', 5: 'Sa', 6: 'So'}
        self.months = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
                       9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}

        self.set_headers_months()
        self.set_chk_field()
        self.bt_event_group_mode: QPushButton | None = None
        self.bt_cast_group_mode: QPushButton | None = None
        self.setup_controllers()
        self.get_events()

    def setup_side_menu(self):
        self.side_menu.delete_all_buttons()
        bt_nr_actors = QPushButton('Besetzungsstärke', clicked=self.set_nr_actors)
        self.side_menu.add_button(bt_nr_actors)
        bt_time_of_days = QPushButton('Tageszeiten...', clicked=self.edit_time_of_days)
        self.side_menu.add_button(bt_time_of_days)
        bt_reset_all_event_t_o_ds = QPushButton('Eingabefeld Tagesz. Reset', clicked=self.reset_all_event_t_o_ds)
        self.side_menu.add_button(bt_reset_all_event_t_o_ds)
        bt_fixed_cast = QPushButton('Feste Besetzung', clicked=self.edit_fixed_cast)
        self.side_menu.add_button(bt_fixed_cast)

    def reload_location_plan_period(self, event=None):
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        self.set_instance_variables()

    def set_instance_variables(self):
        self.t_o_d_standards = sorted([t_o_d for t_o_d in self.location_plan_period.time_of_day_standards
                                       if not t_o_d.prep_delete], key=lambda x: x.time_of_day_enum.time_index)
        self.t_o_d_enums = [t_o_d.time_of_day_enum for t_o_d in self.t_o_d_standards]
        self.days = [
            self.location_plan_period.plan_period.start + datetime.timedelta(delta) for delta in
            range((self.location_plan_period.plan_period.end - self.location_plan_period.plan_period.start).days + 1)]

    def set_headers_months(self):
        month_year = [(d.month, d.year) for d in self.days]
        header_items_months = {
            m_y: month_year.count(m_y)
            for m_y in sorted(set(month_year), key=lambda x: f'{x[1]}{x[0]:02}')
        }
        col = 1
        for (month, year), count in header_items_months.items():
            label = QLabel(f'{self.months[month]} {year}')
            label.setStyleSheet(widget_styles.labels.month_header_label_stylesheet)
            label_font = label.font()
            label_font.setPointSize(12)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setContentsMargins(5, 5, 5, 5)
            self.layout.addWidget(label, 0, col, 1, count)
            col += count

    def set_chk_field(self):  # todo: Config-Zeile Anzahl der Termine am Tag. Wird automatisch über Group-Mode gelöst
        location_of_work = db_services.LocationOfWork.get(self.location_plan_period.location_of_work.id)
        cast_groups_of_pp = db_services.CastGroup.get_all_from__plan_period(
            self.location_plan_period.plan_period.id)

        # Tageszeiten Reihen-Bezeichner:
        for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
            self.layout.addWidget(QLabel(time_of_day.time_of_day_enum.name), row, 0)

        # Tages-Configs Reihenbezeichner / Buttons:
        bt_fixed_cast_reset = QPushButton('Besetzung -> Reset', clicked=self.reset_all_fixed_cast)
        bt_fixed_cast_reset.setStatusTip('Festgelegte Besetzung für alle Verfügbarkeiten in diesem Zeitraum '
                                   'auf die Standartwerte des Planungszeitraums zurücksetzen.')
        self.layout.addWidget(bt_fixed_cast_reset, row + 2, 0)
        lb_notes = QLabel('Notizen')  # todo: zu Button verändern; Notizen aller Events im Zeitraum
        self.layout.addWidget(lb_notes, row + 3, 0)
        lb_flags = QLabel('Besondere Eigensch.')
        self.layout.addWidget(lb_flags, row + 4, 0)

        # Tages-Config_Buttons:
        for col, d in enumerate(self.days, start=1):
            curr_assignment_of_location = get_curr_assignment_of_location(location_of_work, d)
            if curr_assignment_of_location is None:
                disable_buttons = True
            else:
                disable_buttons = curr_assignment_of_location.team.id != self.location_plan_period.team.id
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            if not self.t_o_d_standards:
                QMessageBox.critical(self, 'Verfügbarkeiten',
                                     f'Für diesen Planungszeitraum von '
                                     f'{self.location_plan_period.location_of_work.name} '
                                     f'{self.location_plan_period.location_of_work.address.city} '
                                     f'sind noch keine Tageszeiten-Standartwerte definiert.')
                return
            for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
                button_event = self.create_event_button(d, time_of_day)
                button_event.setDisabled(disable_buttons)
                self.layout.addWidget(button_event, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet(
                    f'background-color: rgba{widget_styles.labels.check_field_weekend_color_rgba_string}')
            self.layout.addWidget(lb_weekday, row + 1, col)
            bt_fixed_cast = ButtonFixedCast(self, d, 24, self.location_plan_period, cast_groups_of_pp)
            bt_fixed_cast.setDisabled(disable_buttons)
            self.layout.addWidget(bt_fixed_cast, row + 2, col)
            bt_notes = ButtonNotes(self, d, 24, self.location_plan_period)
            bt_notes.setDisabled(disable_buttons)
            self.layout.addWidget(bt_notes, row + 3, col)
            bt_flags = ButtonFlags(self, d, 24, self.location_plan_period)
            bt_flags.setDisabled(disable_buttons)
            self.layout.addWidget(bt_flags, row + 4, col)

    def reset_chk_field(self):
        self.parent.data_setup(location_id=self.location_plan_period.location_of_work.id)

    def create_event_button(self, date: datetime.date, time_of_day: schemas.TimeOfDay) -> ButtonEvent:
        # sourcery skip: inline-immediately-returned-variable
        button = ButtonEvent(self, date, time_of_day, 24, self.location_plan_period, self.save_event)
        return button

    def setup_controllers(self):
        """Buttons im Bereich self.layout_controllers"""
        self.bt_event_group_mode = QPushButton('zum Gruppenmodus', clicked=self.change_mode__event_group)
        self.layout_controllers.addWidget(self.bt_event_group_mode)
        self.bt_cast_group_mode = QPushButton('zum Fixed Cast Gruppenmodus', clicked=self.change_mode__cast_group)
        self.layout_controllers.addWidget(self.bt_cast_group_mode)

    def save_event(self, bt: ButtonEvent):
        date = bt.date
        t_o_d = bt.time_of_day
        mode: Literal['added', 'deleted'] = 'added' if bt.isChecked() else 'deleted'
        self.data_processor.save_event(date, t_o_d, mode)

    def change_mode__event_group(self):
        dlg = frm_group_mode.DlgGroupModeBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            QMessageBox.information(self, 'Gruppenmodus', 'Alle Änderungen wurden vorgenommen.')
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__events(
                signal_handling.DataLocationPPWithDate(self.location_plan_period))
        else:
            QMessageBox.information(self, 'Gruppenmodus', 'Keine Änderungen wurden vorgenommen.')

        signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
            signal_handling.DataGroupMode(False))

    def change_mode__cast_group(self):
        plan_period = db_services.PlanPeriod.get(self.location_plan_period.plan_period.id)
        dlg = frm_cast_group.DlgCastGroups(self, plan_period, {self.location_plan_period.id})
        if dlg.exec():
            QMessageBox.information(self, 'Gruppenmodus', 'Alle Änderungen wurden vorgenommen.')
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__events(
                signal_handling.DataLocationPPWithDate(self.location_plan_period))
        else:
            QMessageBox.information(self, 'Gruppenmodus', 'Keine Änderungen wurden vorgenommen.')

    def get_events(self):
        events = (e for e in db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id)
                  if not e.prep_delete)
        for event in events:
            button: ButtonEvent = self.findChild(ButtonEvent, f'{event.date}-{event.time_of_day.time_of_day_enum.name}')
            if not button:
                QMessageBox.critical(self, 'Fehlende Standards',
                                     f'Fehler:\n'
                                     f'Kann die verfügbaren Zeiten nicht anzeigen.\nEventuell haben Sie nachträglich '
                                     f'"{event.time_of_day.time_of_day_enum.name}" aus den Standards gelöscht.')
                return
            button.setChecked(True)
            button.time_of_day = event.time_of_day
            button.create_actions_times_of_day()
            button.reset_menu_times_of_day(self.location_plan_period)
            button.set_tooltip()

    def set_nr_actors(self):  # todo: noch implementieren
        ...

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            self.reload_location_plan_period()
            buttons_event: list[ButtonEvent] = self.findChildren(ButtonEvent)
            for bt in buttons_event:
                bt.reset_menu_times_of_day(self.location_plan_period)
            self.reset_chk_field()

    def reset_all_event_t_o_ds(self):
        # not_sure: noch implementieren? Zur Zeit werden Tageszeiten, die für die LocalPlanPeriod festgelegt werden,
        #  automatisch von den EventButtons übernommen.
        ...

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
                signal_handling.DataLocationPPWithDate(self.location_plan_period)
            )
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(plan_period_id=self.location_plan_period.plan_period.id)
            )

    def reset_all_fixed_cast(self):
        # todo: noch implementieren
        reply = QMessageBox.question(self, 'Besetzungen zurücksetzen',
                                     f'Möchten Sie wirklich die Festen Besetzungen aller Events auf den '
                                     f'Besetzungsstandard der dieser Planungsperiode von '
                                     f'{self.location_plan_period.location_of_work.name} '
                                     f'{self.location_plan_period.location_of_work.address.city} zurücksetzen?')
        if reply != QMessageBox.StandardButton.Yes:
            return
        cast_groups_of_plan_period = db_services.CastGroup.get_all_from__plan_period(
            self.location_plan_period.plan_period.id)
        event_cast_groups = (c for c in cast_groups_of_plan_period
                             if c.event
                             and c.event.location_plan_period.id == self.location_plan_period.id
                             and c.fixed_cast != self.location_plan_period.fixed_cast)
        for c in event_cast_groups:
            command = cast_group_commands.UpdateFixedCast(c.id,  self.location_plan_period.fixed_cast)
            self.controller.execute(command)
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, c.event.date)
            )

        QMessageBox.information(self, 'Besetzungen zurücksetzen',
                                'Die Besetzungen aller Events wurden erfolgreich zurückgesetzt.')




if __name__ == '__main__':
    app = QApplication()
    plan_periods = [pp for pp in db_services.PlanPeriod.get_all_from__project(UUID('72F1D1E9BF554F11AE44916411A9819E'))
                    if not pp.prep_delete]
    window = FrmTabLocationPlanPeriods(None, plan_periods[0])
    window.show()
    app.exec()

# todo: Reset-Buttons in event-frame sollten Signale senden
