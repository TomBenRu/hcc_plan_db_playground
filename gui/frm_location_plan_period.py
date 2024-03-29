import datetime
import functools
from typing import Callable
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout, QAbstractItemView, QHeaderView, QTableWidgetItem, QPushButton, QMessageBox, QApplication, \
    QMenu

from database import schemas, db_services
from database.special_schema_requests import get_curr_assignment_of_location
from gui import side_menu, frm_flag, frm_time_of_day, frm_group_mode
from gui.actions import Action
from gui.commands import command_base_classes, event_commands
from gui.frm_fixed_cast import DlgFixedCast, DlgFixedCastBuilderLocationOfWork, DlgFixedCastBuilderLocationPlanPeriod, \
    DlgFixedCastBuilderEvent
from gui.frm_time_of_day import DlgTimeOfDaysEditList
from gui.observer import signal_handling


def disconnect_event_button_signals():
    try:
        signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.disconnect()
        signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.disconnect()
    except Exception as e:
        print(f'Fehler: {e}')


class ButtonEvent(QPushButton):  # todo: Ändern
    def __init__(self, parent: QWidget, date: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow, slot__event_toggled: Callable):
        super().__init__(parent)
        self.setObjectName(f'{date}-{time_of_day.time_of_day_enum.name}')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCheckable(True)
        self.clicked.connect(lambda: slot__event_toggled(self))
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.parent = parent

        signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.connect(
            lambda group_mode: self.set_group_mode(group_mode))
        signal_handling.handler_location_plan_period.signal_reload_location_pp__events.connect(
            lambda data: self.reload_location_plan_period(data.location_plan_period)
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
        if self.time_of_day.time_of_day_enum.time_index == 1:
            self.setStyleSheet("QPushButton {background-color: #cae4f4}"
                               "QPushButton::checked { background-color: #002aaa; border: none;}"
                               "QPushButton::disabled { background-color: #6a7585;}")
        elif self.time_of_day.time_of_day_enum.time_index == 2:
            self.setStyleSheet("QPushButton {background-color: #fff4d6}"
                               "QPushButton::checked { background-color: #ff4600; border: none;}"
                               "QPushButton::disabled { background-color: #7f7f7f;}")
        elif self.time_of_day.time_of_day_enum.time_index == 3:
            self.setStyleSheet("QPushButton {background-color: #daa4c9}"
                               "QPushButton::checked { background-color: #84033c; border: none;}"
                               "QPushButton::disabled { background-color: #674b56;}")

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
            self.context_menu.addAction(Action(self, None, text, None, slot))

    def reset_menu_times_of_day(self, location_plan_period: schemas.LocationPlanPeriodShow):
        self.location_plan_period = location_plan_period
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        for action in self.menu_times_of_day.actions():
            self.menu_times_of_day.removeAction(action)
        self.create_actions_times_of_day()
        self.menu_times_of_day.addActions(self.actions)

    def create_actions_times_of_day(self):
        self.actions = [
            Action(self, QIcon('resources/toolbar_icons/icons/clock-select.png') if t.name == self.time_of_day.name else None,
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
        signal_handling.handler_location_plan_period.reload_location_pp__frm_location_plan_period()

    def edit_skills(self):
        print('edit_skills')

    def edit_fixed_cast(self):
        if not self.isChecked():
            QMessageBox.critical(self, 'Flags',
                                 'Sie müssen zuerst einen Termin setzen, bevor Sie die Besetzung bearbeiten können.')
            return
        event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, self.date,
                                                                 self.time_of_day.id)
        dlg = DlgFixedCastBuilderEvent(self.parent, event).build()
        if dlg.exec():
            self.reload_location_plan_period()
            # todo: signal an FrmActorPlanPeriod und Tagesconfig-Button fixed_cast?

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

    def reload_location_plan_period(self, location_plan_period: schemas.LocationPlanPeriodShow = None):
        if location_plan_period:
            self.location_plan_period = location_plan_period
        else:
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)


class ButtonFixedCast(QPushButton):  # todo: Fertigstellen... + Tooltip Fest Besetzung der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent)

        self.setObjectName(f'fixed_cast: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)
        signal_handling.handler_location_plan_period.signal_reload_location_pp__frm_location_plan_period.connect(
            lambda event: print(event)
        )


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

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.location_plan_periods = self.plan_period.location_plan_periods
        self.location_id__location_pp = {str(loc_pp.location_of_work.id): loc_pp
                                         for loc_pp in self.plan_period.location_plan_periods}
        self.location_id: UUID | None = None
        self.location: schemas.PersonShow | None = None
        self.frame_events: FrmLocationPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_pp.setFixedHeight(180)

        self.lb_notes_location = QLabel('Infos zur Einrichtung:')
        self.lb_notes_location.setFixedHeight(20)
        font_lb_notes = self.lb_notes_location.font()
        font_lb_notes.setBold(True)
        self.lb_notes_location.setFont(font_lb_notes)
        self.te_notes_location = QTextEdit()
        self.te_notes_location.textChanged.connect(self.save_info_location)
        self.te_notes_location.setFixedHeight(180)

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
        self.location = db_services.LocationOfWork.get(self.location_id)
        location_plan_period = self.location_id__location_pp[str(self.location_id)]
        location_plan_period_show = db_services.LocationPlanPeriod.get(location_plan_period.id)
        self.lb_title_name.setText(f'Termine: {location_plan_period_show.location_of_work.name} '
                                   f'{location_plan_period_show.location_of_work.address.city}')

        if self.frame_events:
            disconnect_event_button_signals()
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


class FrmLocationPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabLocationPlanPeriods, location_plan_period: schemas.LocationPlanPeriodShow,
                 side_menu: side_menu.WidgetSideMenu):
        super().__init__(parent)

        self.setContentsMargins(0, 0, 0, 10)

        self.parent = parent
        self.layout_controllers = parent.layout_controllers

        signal_handling.handler_location_plan_period.signal_reload_location_pp__frm_location_plan_period.connect(
            self.reload_location_plan_period)

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
        self.bt_toggle__avd_group_mode: QPushButton | None = None
        self.setup_controllers()
        self.get_events()

    def setup_side_menu(self):
        self.side_menu.delete_all_buttons()
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
            label.setStyleSheet('background: qlineargradient( x1:0 y1:0, x2:1 y2:0, stop:0 #a9ffaa, stop:1 #137100)')
            label_font = label.font()
            label_font.setPointSize(12)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setContentsMargins(5, 5, 5, 5)
            self.layout.addWidget(label, 0, col, 1, count)
            col += count

    def set_chk_field(self):  # todo: Config-Zeile Anzahl der Termine am Tag. Wird automatisch über Group-Mode gelöst
        location_of_work = db_services.LocationOfWork.get(self.location_plan_period.location_of_work.id)

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
            disable_buttons = get_curr_assignment_of_location(location_of_work, d).team.id != self.location_plan_period.team.id
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            if not self.t_o_d_standards:
                QMessageBox.critical(self, 'Verfügbarkeiten',
                                     f'Für diesen Planungszeitraum von {self.actor_plan_period.person.f_name} '
                                     f'{self.actor_plan_period.person.l_name} sind noch keine '
                                     f'Tageszeiten-Standartwerte definiert.')
                return
            for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
                button_event = self.create_event_button(d, time_of_day)
                button_event.setDisabled(disable_buttons)
                self.layout.addWidget(button_event, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet('background-color: #ffdc99')
            self.layout.addWidget(lb_weekday, row + 1, col)
            bt_fixed_cast = ButtonFixedCast(self, d, 24, self.location_plan_period)
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
        self.bt_toggle__avd_group_mode = QPushButton('zum Gruppenmodus', clicked=self.change_mode__event_group)
        self.layout_controllers.addWidget(self.bt_toggle__avd_group_mode)

    def save_event(self, bt: ButtonEvent):

        date = bt.date
        t_o_d = bt.time_of_day
        if bt.isChecked():
            existing_events_on_day = [event for event in self.location_plan_period.events
                                      if event.date == date and not event.prep_delete]
            event_new = schemas.EventCreate(date=date, location_plan_period=self.location_plan_period,
                                            time_of_day=t_o_d, flags=[])
            save_command = event_commands.Create(event_new)
            self.controller.execute(save_command)

            '''Falls es an diesem Tage schon einen oder mehrere Events gibt,
            werden die fixed_casts vom ersten gefundenen Event übernommen, weil, davon ausgegangen
            wird, dass schon evt. geänderte fixed_casts für alle Events an diesem Tag gelten.'''
            if existing_events_on_day:
                self.controller.execute(
                   event_commands.UpdateFixedCast(save_command.created_event.id, existing_events_on_day[0].fixed_cast))

            self.reload_location_plan_period()

        else:
            event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, date, t_o_d.id)
            del_command = event_commands.Delete(event.id)
            self.controller.execute(del_command)
            self.reload_location_plan_period()
            if not (master_group := del_command.event_to_delete.event_group.event_group).location_plan_period:
                if len(childs := db_services.EventGroup.get_child_groups_from__parent_group(master_group.id)) < 2:
                    solo_event = childs[0].event
                    QMessageBox.critical(self, 'Verfügbarkeitsgruppen',
                                         f'Durch das Löschen des Termins hat eine Gruppe nur noch einen einzigen '
                                         f'Termin: {solo_event.date.strftime("%d.%m.%y")}\n'
                                         f'Bitte korrigieren Sie dies im folgenden Dialog.')
                    self.change_mode__event_group()

        bt.reload_location_plan_period()

        signal_handling.handler_location_plan_period.reload_location_pp__events(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )
        signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )

    def change_mode__event_group(self):  # todo: noch implementieren
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

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            self.reload_location_plan_period()
            buttons_event: list[ButtonEvent] = self.findChildren(ButtonEvent)
            for bt in buttons_event:
                bt.reset_menu_times_of_day(self.location_plan_period)
            self.reset_chk_field()

    def reset_all_event_t_o_ds(self):  # todo: noch implementieren
        ...

    def edit_fixed_cast(self):  # todo: noch implementieren
        dlg = DlgFixedCastBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_location_plan_period()

    def reset_all_fixed_cast(self):  # todo: noch implementieren
        ...


if __name__ == '__main__':
    app = QApplication()
    plan_periods = [pp for pp in db_services.PlanPeriod.get_all_from__project(UUID('A2997911589B405D9F5C8CB36DB1D48C'))
                    if not pp.prep_delete]
    window = FrmTabLocationPlanPeriods(None, plan_periods[0])
    window.show()
    app.exec()
