import dataclasses
import datetime
import pprint
import time
from collections import defaultdict
from functools import partial
from typing import Literal, Callable
from uuid import UUID

from PySide6.QtCore import Qt, Slot, QTimer, QCoreApplication, QThreadPool, Signal
from PySide6.QtGui import QContextMenuEvent, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout, \
    QHBoxLayout, QMessageBox, QMenu, QAbstractItemView, QGraphicsDropShadowEffect, QDialog, QFormLayout, QGroupBox, \
    QDialogButtonBox, QComboBox, QProgressDialog, QProgressBar, QPushButton, QCheckBox, QLineEdit
from line_profiler import profile

from commands import command_base_classes
from commands.database_commands import plan_commands, appointment_commands, max_fair_shifts_per_app
from database import schemas, db_services
from database.special_schema_requests import get_persons_of_team_at_date
from gui.concurrency import general_worker
from gui.concurrency.general_worker import WorkerGetMaxFairShifts
from gui.custom_widgets import side_menu
from gui.custom_widgets.progress_bars import DlgProgressInfinite, GlobalUpdatePlanTabsProgressManager, DlgProgressSteps
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from gui.observer import signal_handling
from gui.widget_styles.plan_table import horizontal_header_colors, vertical_header_colors, locations_bg_color
from sat_solver import solver_main
from tools.helper_functions import get_appointments_of_actors_from_plan, get_appointments_of_all_actors_from_plan


def fill_in_data(appointment_field: 'AppointmentField'):
    appointment_field.lb_time_of_day.setText(f'{appointment_field.appointment.event.time_of_day.name}: '
                                             f'{appointment_field.appointment.event.time_of_day.start:%H:%M}'
                                             f'-{appointment_field.appointment.event.time_of_day.end:%H:%M}')
    employees = '\n'.join([f'{avd.actor_plan_period.person.f_name} {avd.actor_plan_period.person.l_name}'
                           for avd in sorted(appointment_field.appointment.avail_days,
                                             key=lambda x: (x.actor_plan_period.person.f_name,
                                                            x.actor_plan_period.person.l_name))]
                          + appointment_field.appointment.guests)
    nr_required_persons = db_services.CastGroup.get_cast_group_of_event(
        appointment_field.appointment.event.id).nr_actors

    if missing := (nr_required_persons - len(appointment_field.appointment.avail_days)
                   - len(appointment_field.appointment.guests)):
        missing_txt = f'unbesetzt: {missing}'
        appointment_field.lb_missing.setText(missing_txt)
        appointment_field.layout.addWidget(appointment_field.lb_missing)
    else:
        appointment_field.lb_missing.setParent(None)

    appointment_field.lb_employees.setText(employees)


class DlgGuest(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)
        self.setWindowTitle('Gastbesetzung')

        self._setup_layout()

    def _setup_layout(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)
        self.lb_explanation = QLabel('Fügen Sie den Namen des Gastes ein.')
        self.le_guest = QLineEdit()
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_head.addWidget(self.lb_explanation)
        self.layout_body.addRow('Gastbesetzung:', self.le_guest)
        self.layout_foot.addWidget(self.button_box)


class DlgEditAppointment(QDialog):
    def __init__(self, parent: QWidget, appointment: schemas.Appointment):
        super().__init__(parent=parent)
        self.appointment = appointment

        self._setup_layout()
        self._setup_data()
        self._setup_employee_combos()

    def _setup_layout(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)
        self.lb_explanation = QLabel(f'Einsätze am:\n'
                                     f'{self.appointment.event.date:%d.%m.%y}, '
                                     f'{self.appointment.event.location_plan_period.location_of_work.name} - '
                                     f'{self.appointment.event.location_plan_period.location_of_work.address.city}, '
                                     f'{self.appointment.event.time_of_day.name}\n'
                                     f'Hier können Sie die Besetzung ändern.')
        self.layout_head.addWidget(self.lb_explanation)
        self.group_employees = QGroupBox('Mitarbeiter')
        self.layout_body.addWidget(self.group_employees)
        self.form_employees = QFormLayout(self.group_employees)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.cast_group = db_services.CastGroup.get_cast_group_of_event(self.appointment.event.id)
        self.possible_avail_days = db_services.AvailDay.get_all_from__plan_period__date__time_of_day__location_prefs(
            self.appointment.event.location_plan_period.plan_period.id,
            self.appointment.event.date,
            self.appointment.event.time_of_day.time_of_day_enum.time_index,
            {self.appointment.event.location_plan_period.location_of_work.id}
        )
        self.possible_avail_days.sort(key=lambda x: x.actor_plan_period.person.f_name)

        self.new_avail_day_ids: dict[UUID, str] = {}

    def _setup_employee_combos(self):
        self.combos_employees = []
        for i in range(1, self.cast_group.nr_actors + 1):
            self.combos_employees.append(QComboBoxToFindData())
            self.form_employees.addRow(f'Mitarbeiter {i:02}', self.combos_employees[-1])
            self.combos_employees[-1].addItem('Unbesetzt', None)
            for avd in self.possible_avail_days:
                self.combos_employees[-1].addItem(
                    f'{avd.actor_plan_period.person.f_name} {avd.actor_plan_period.person.l_name}',
                    avd.id
                )
            self.combos_employees[-1].addItem('Gast', UUID('00000000000000000000000000000000'))
            self.combos_employees[-1].currentIndexChanged.connect(partial(self.combo_employees_index_changed, i - 1))
        for j, avd in enumerate(self.appointment.avail_days):
            self.combos_employees[j].setCurrentIndex(self.combos_employees[-1].findData(avd.id))
        for k, name in enumerate(self.appointment.guests, start=len(self.appointment.avail_days)):
            self.combos_employees[k].addItem(name, UUID('00000000000000000000000000000001'))
            self.combos_employees[k].setCurrentIndex(self.combos_employees[-1].findText(name))

    def combo_employees_index_changed(self, index_in_combos_employees: int, curr_index: int):
        if ((combo := self.combos_employees[index_in_combos_employees])
                .currentData() == UUID('00000000000000000000000000000000')):
            dlg = DlgGuest(self)
            if dlg.exec():
                if (idx := combo.findData(UUID('00000000000000000000000000000001'))) == -1:
                    combo.addItem(dlg.le_guest.text(), UUID('00000000000000000000000000000001'))
                    combo.setCurrentIndex(combo.findData(UUID('00000000000000000000000000000001')))
                else:
                    combo.setItemText(idx, dlg.le_guest.text())
                    combo.setCurrentIndex(idx)

    def accept(self):
        self.new_avail_day_ids = {combo.currentData(): combo.currentText()
                                  for combo in self.combos_employees if combo.currentData()}
        super().accept()


class LabelDayNr(QLabel):
    def __init__(self, day: datetime.date, plan_period: schemas.PlanPeriod):
        super().__init__()

        self.day = day
        self.plan_period = plan_period

        self.set_font_and_style()

        self.setText(day.strftime('%d.%m.%y'))

    def set_font_and_style(self):
        self.setContentsMargins(0, 0, 0, 0)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        if self.day.isoweekday() % 2:
            self.setStyleSheet('background-color: #71bdff; color: #2b2b2b')
        else:
            self.setStyleSheet('background-color: #91d2ff; color: #2b2b2b')
        font = self.font()
        font.setBold(True)
        self.setFont(font)

    def contextMenuEvent(self, event: QContextMenuEvent):
        print('An diesem Tag im Team:')
        print([p.f_name for p in get_persons_of_team_at_date(self.plan_period.team.id, self.day)])
        print('An diesem Tag verfügbar:')
        print([(avd.actor_plan_period.person.f_name, avd.time_of_day.name)
               for avd in db_services.AvailDay.get_all_from__plan_period_date(self.plan_period.id, self.day)])
        menu = QMenu()
        menu.addAction('Day Action 1')
        menu.addAction('Day Action 2')
        menu.exec(event.globalPos())


class DayField(QWidget):
    def __init__(self, day: datetime.date, location_ids_order: list[UUID],
                 location_ids_appointments: dict[UUID, list[schemas.Appointment]] | None,
                 plan_period: schemas.PlanPeriod, appointment_widget_width: int, plan_widget: 'FrmTabPlan'):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)

        self.day = day
        self.location_ids_appointments = location_ids_appointments
        self.location_ids_order = location_ids_order
        self.plan_period = plan_period
        self.appointment_widget_width = appointment_widget_width
        self.plan_widget = plan_widget

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lb_date = LabelDayNr(day, plan_period)
        self.layout.addWidget(self.lb_date)
        self.container_locations = QWidget()
        self.container_locations.setContentsMargins(0, 0, 0, 0)
        self.layout_container_locations = QGridLayout(self.container_locations)
        self.layout_container_locations.setSpacing(0)
        self.layout_container_locations.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.container_locations)
        self.containers_appointments: dict[int, 'ContainerAppointments'] = {
            i: ContainerAppointments(loc_id, appointment_widget_width) for i, loc_id in enumerate(location_ids_order)}
        self.display_appointment_containers()
        self.display_appointments()

    def display_appointment_containers(self):
        for pos, container in self.containers_appointments.items():
            self.layout_container_locations.addWidget(container, 0, pos)

    def display_appointments(self):
        if not self.location_ids_appointments:
            return
        for loc_id, appointments in self.location_ids_appointments.items():
            for pos, container in self.containers_appointments.items():
                if loc_id == container.location_id:
                    for appointment in sorted(appointments,
                                              key=lambda x: x.event.time_of_day.time_of_day_enum.time_index):
                        container.add_appointment_field(AppointmentField(appointment, self.plan_widget))

    def set_location_ids_order(self, location_ids_order: list[UUID]):
        self.location_ids_order = location_ids_order
        if self.containers_appointments:
            decision = QMessageBox.question(self, 'Neue Locations-Order',
                                            'Es gibt bereits Einrichtungen an diesem Tag.\n'
                                            'Trotzdem fortfahren?')
            if decision == QMessageBox.StandardButton.No:
                return
        self.containers_appointments: dict[int, 'ContainerAppointments'] = {
            i: ContainerAppointments(loc_id, self.appointment_widget_width)
            for i, loc_id in enumerate(location_ids_order)}
        for i, container_appointments in self.containers_appointments.items():
            self.layout_container_locations.addWidget(container_appointments, 0, i)

    def add_appointment_field(self, appointment_field: 'AppointmentField'):
        for key, container in self.containers_appointments.items():
            if appointment_field.location_id == container.location_id:
                container.add_appointment_field(appointment_field)
                break
        else:
            new_container = ContainerAppointments(appointment_field.location_id, self.appointment_widget_width)
            new_container.add_appointment_field(appointment_field)
            self.containers_appointments[len(self.containers_appointments)] = new_container

            self.layout_container_locations.addWidget(new_container, 0, len(self.containers_appointments))

    def remove_appointment_field(self, appointment_field: 'AppointmentField'):
        for key, container in self.containers_appointments.items():
            if appointment_field.location_id == container.location_id:
                container.remove_appointment_field(appointment_field)
                break

    def display_containers_appointments(self):
        for i in range(self.layout_container_locations.count()):
            self.layout_container_locations.itemAt(i).widget().setParent(None)

        for i, container_appointment in self.containers_appointments.items():
            self.layout_container_locations.addWidget(container_appointment, 0, i)


class ContainerAppointments(QWidget):
    def __init__(self, location_id: UUID, width: int):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.setFixedWidth(width)
        self.location_id = location_id
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.appointment_fields: list['AppointmentField'] = []

    def add_appointment_field(self, appointment_field: 'AppointmentField'):
        self.appointment_fields.append(appointment_field)
        self.appointment_fields.sort(key=lambda x: x.appointment.event.time_of_day.time_of_day_enum.time_index)
        self.display_appointments_fields()

    def remove_appointment_field(self, appointment_field: 'AppointmentField'):
        self.appointment_fields = [a for a in self.appointment_fields
                                   if a.appointment.id != appointment_field.appointment.id]
        self.display_appointments_fields()

    def display_appointments_fields(self):
        for i in range(self.layout.count()):
            self.layout.itemAt(i).widget().setParent(None)
        for appointment_field in self.appointment_fields:
            self.layout.addWidget(appointment_field)


class AppointmentField(QWidget):
    def __init__(self, appointment: schemas.Appointment, plan_widget: 'FrmTabPlan'):
        super().__init__()
        self.setObjectName(str(appointment.id))
        self.plan_widget = plan_widget
        self.appointment = appointment
        self.location_id = appointment.event.location_plan_period.location_of_work.id
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.lb_time_of_day = QLabel()
        self.lb_employees = QLabel()
        self.lb_missing = QLabel()

        self.set_styling()

        self.layout.addWidget(self.lb_time_of_day)
        self.layout.addWidget(self.lb_employees)

        fill_in_data(self)

        self.command_avail_days: appointment_commands.UpdateAvailDays | None = None
        self.command_guests: appointment_commands.UpdateGuests | None = None
        self.thread_pool = QThreadPool()

        self.setToolTip(f'Hallo {" und ".join([a.actor_plan_period.person.f_name for a in appointment.avail_days])}.\n'
                        f'Benutze Rechtsklick, um zum Context-Menü zu gelangen.')

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        dlg = DlgEditAppointment(self, self.appointment)
        if dlg.exec():
            new_avail_day_ids = [avd_id for avd_id in dlg.new_avail_day_ids.keys()
                                 if avd_id != UUID('00000000000000000000000000000001')]
            new_guests = [guest for avd_id, guest in dlg.new_avail_day_ids.items()
                          if avd_id == UUID('00000000000000000000000000000001')]
            self.command_avail_days = appointment_commands.UpdateAvailDays(self.appointment.id, new_avail_day_ids)
            self.plan_widget.controller.execute(self.command_avail_days)
            self.appointment = self.command_avail_days.updated_appointment
            if sorted(new_guests) != sorted(self.appointment.guests):
                self.command_guests = appointment_commands.UpdateGuests(self.appointment.id, new_guests)
                self.plan_widget.controller.execute(self.command_guests)
                self.appointment = self.command_guests.updated_appointment
            fill_in_data(self)
            if self.plan_widget.permanent_plan_check:
                self._start_plan_check()
            else:
                signal_handling.handler_plan_tabs.reload_plan_from_db(self.plan_widget.plan.id)
                signal_handling.handler_plan_tabs.reload_specific_plan_statistics_plan(self.plan_widget.plan.id)
                signal_handling.handler_plan_tabs.refresh_specific_plan_statistics_plan(self.plan_widget.plan.id)

    def _start_plan_check(self):
        self.progress_bar = DlgProgressInfinite(self, 'Überprüfung',
                                                'Besetzungsänderungen werden auf Fehler getestet.', 'Abbruch',
                                                signal_handling.handler_solver.cancel_solving)
        self.progress_bar.show()
        worker = general_worker.WorkerCheckPlan(solver_main.test_plan, self.plan_widget.plan.id)
        worker.signals.finished.connect(self.check_finished)
        self.thread_pool.start(worker)

    @Slot(bool, list)
    def check_finished(self, success: bool, problems: list[str]):
        self.progress_bar.close()
        if success:
            QMessageBox.information(self, 'Besetzungsänderung',
                                    'Die Änderung der Besetzung wurde erfolgreich vorgenommen.')
            signal_handling.handler_plan_tabs.reload_plan_from_db(self.plan_widget.plan.id)
            signal_handling.handler_plan_tabs.reload_specific_plan_statistics_plan(self.plan_widget.plan.id)
            signal_handling.handler_plan_tabs.refresh_specific_plan_statistics_plan(self.plan_widget.plan.id)
        else:
            problems_txt = "\n        +\n    ".join(problems)
            reply = QMessageBox.critical(self, 'Besetzungsänderung',
                                         f'Die Änderung der Besetzung ist nicht ohne Konflikt machbar.\n\n'
                                         f'Unvereinbarkeiten:\n    {problems_txt}\n\n'
                                         f'Sollen die Änderungen zurückgenommen werden',
                                         QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                self.plan_widget.controller.undo()
                if self.command_guests:
                    self.plan_widget.controller.undo()
                self.appointment = self.command_avail_days.appointment
                fill_in_data(self)
            else:
                signal_handling.handler_plan_tabs.reload_plan_from_db(self.plan_widget.plan.id)
                signal_handling.handler_plan_tabs.reload_specific_plan_statistics_plan(self.plan_widget.plan.id)
                signal_handling.handler_plan_tabs.refresh_specific_plan_statistics_plan(self.plan_widget.plan.id)

    def contextMenuEvent(self, event: QContextMenuEvent):
        context_menu = QMenu(self)
        context_menu.addAction(f'Action 1 {self.appointment.event.date} ({self.appointment.event.time_of_day.name}) '
                               f'{self.appointment.event.location_plan_period.location_of_work.name}')
        context_menu.addAction(f'Action 2 {self.appointment.event.date} ({self.appointment.event.time_of_day.name}) '
                               f'{self.appointment.event.location_plan_period.location_of_work.name}')
        context_menu.exec(event.globalPos())

    def set_styling(self):
        self.setStyleSheet("background-color: #393939;")
        '444444'
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setContentsMargins(2, 2, 2, 2)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.lb_time_of_day.setContentsMargins(5, 2, 0, 0)
        self.lb_employees.setContentsMargins(10, 5, 0, 5)
        font_lb_time_of_day = self.lb_time_of_day.font()
        font_lb_employees = self.lb_employees.font()
        font_lb_time_of_day.setPointSizeF(font_lb_time_of_day.pointSize() * 0.8)
        font_lb_employees.setBold(True)
        self.lb_time_of_day.setFont(font_lb_time_of_day)
        self.lb_employees.setFont(font_lb_employees)
        font_lb_missing = self.lb_missing.font()
        font_lb_missing.setPointSizeF(font_lb_missing.pointSize() * 0.8)
        self.lb_missing.setFont(font_lb_missing)
        self.lb_missing.setContentsMargins(5, 0, 0, 2)
        self.lb_missing.setStyleSheet('color: #ff7c00')


class FrmTabPlan(QWidget):
    resize_signal = Signal()
    
    def __init__(self, parent: QWidget, plan: schemas.PlanShow,
                 update_progress_manager: GlobalUpdatePlanTabsProgressManager):
        super().__init__(parent=parent)

        signal_handling.handler_plan_tabs.signal_reload_plan_from_db.connect(self.reload_specific_plan)
        signal_handling.handler_plan_tabs.signal_reload_and_refresh_plan_tab.connect(self.reload_and_refresh_specific_plan)
        signal_handling.handler_plan_tabs.signal_reload_all_plan_period_plans_from_db.connect(self.reload_plan_period_plan)
        signal_handling.handler_plan_tabs.signal_refresh_all_plan_period_plans_from_db.connect(self.refresh_plan_period_plan)
        signal_handling.handler_plan_tabs.signal_refresh_plan.connect(self.refresh_specific_plan)

        self.plan = plan
        self.update_progress_manager = update_progress_manager
        self.thread_pool = QThreadPool()

        self.appointment_widget_width = 120

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.permanent_plan_check = True

        self.weekday_names = {
            1: 'Montag',
            2: 'Dienstag',
            3: 'Mittwoch',
            4: 'Donnerstag',
            5: 'Freitag',
            6: 'Samstag',
            7: 'Sonntag',
        }

        self.layout = QVBoxLayout(self)

        self._generate_plan_data()

        self._show_table_plan()

        self._setup_side_menu()
        self._setup_bottom_menu()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_signal.emit()
    
    def _setup_side_menu(self):
        self.side_menu = side_menu.SlideInMenu(self, 250, 10, 'right')
        self.chk_permanent_plan_check = QCheckBox('Überprüfung im Hintergrund')
        self.chk_permanent_plan_check.setToolTip('Fehlerüberprüfung bei jeder Besetzungsänderung.')
        self.chk_permanent_plan_check.setChecked(True)
        self.chk_permanent_plan_check.toggled.connect(self._chk_permanent_plan_check_toggled)
        self.side_menu.add_check_box(self.chk_permanent_plan_check)
        self.bt_check_plan = QPushButton('Plan überprüfen')
        self.bt_check_plan.clicked.connect(self._check_plan)
        self.side_menu.add_button(self.bt_check_plan)
        self.bt_get_max_fair_shifts = QPushButton('Statistiken aktualisieren')
        self.bt_get_max_fair_shifts.clicked.connect(self._update_statistics)
        self.side_menu.add_button(self.bt_get_max_fair_shifts)
        self.bt_undo = QPushButton('Undo')
        self.bt_undo.clicked.connect(self._undo_shift_command)
        self.side_menu.add_button(self.bt_undo)
        self.bt_redo = QPushButton('Redo')
        self.bt_redo.clicked.connect(self._redo_shift_command)
        self.side_menu.add_button(self.bt_redo)
        self.bt_refresh = QPushButton('Ansicht aktualisieren')
        self.bt_refresh.clicked.connect(self.refresh_plan)
        self.side_menu.add_button(self.bt_refresh)

    def _setup_bottom_menu(self):
        self.bottom_menu = side_menu.SlideInMenu(self, 210, 10, 'bottom', (20, 10, 20, 10), (128, 128, 128,255))
        self.plan_statistics = TblPlanStatistics(self, self.plan.id)
        self.bottom_menu.add_widget(self.plan_statistics)

    def _generate_plan_data(self):
        self.all_days_of_month = self.generate_all_days()
        self.all_week_nums_of_month = self.generate_all_week_nums_of_month()
        self.week_num_rows = self.generate_week_num_row()
        self.weekday_cols = self.generate_weekday_col()

        self.week_num_weekday = self.generate_week_num_weekday()
        self.weekdays_locations = self.get_weekdays_locations()
        self.column_assignments = self.generate_column_assignments()
        self.day_location_id_appointments = self.generate_day_appointments()
        self.execution_allowed: bool = True
        self.post_undo_redo_timer = QTimer()
        self.post_undo_redo_timer.setInterval(1000)
        self.post_undo_redo_timer.setSingleShot(True)
        self.post_undo_redo_timer.timeout.connect(self._post_undo_redo_actions)

    def _chk_permanent_plan_check_toggled(self, checked: bool):
        self.permanent_plan_check = checked

    def _check_plan(self):
        self.progress_bar = DlgProgressInfinite(self, 'Überprüfung',
                                                'Plan wird auf Fehler getestet.', 'Abbruch',
                                                signal_handling.handler_solver.cancel_solving)
        self.progress_bar.show()

        worker = general_worker.WorkerCheckPlan(solver_main.test_plan, self.plan.id)
        worker.signals.finished.connect(self._check_finished)
        self.thread_pool.start(worker)

    @Slot(bool, list)
    def _check_finished(self, success: bool, problems: list[str]):
        self.progress_bar.close()
        if success:
            QMessageBox.information(self, 'Plan Überprüfung',
                                    'Es wurden keine Fehler in diesem Plan festgestellt.')
        else:
            problems_txt = "\n        +\n    ".join(problems)
            QMessageBox.critical(self, 'Besetzungsänderung',
                                 f'Es wurden Konflikte in diesem Plan festgestellt.\n\n'
                                 f'Unvereinbarkeiten:\n    {problems_txt}\n\n')

    def _update_statistics(self):
        num_actor_plan_periods = len(db_services.PlanPeriod.get(self.plan.plan_period.id).actor_plan_periods)
        self.progress_bar = DlgProgressSteps(self, 'Statistiken aktualisieren',
                                             'Die Besetzungsstatistiken werden aktualisiert.',
                                             0, num_actor_plan_periods + 1,
                                             'Abbruch', signal_handling.handler_solver.cancel_solving)
        worker = WorkerGetMaxFairShifts(solver_main.get_max_fair_shifts_per_app, self.plan.plan_period.id, 20, 80)
        self.progress_bar.show()
        worker.signals.finished.connect(self._update_statistics_finished)
        self.thread_pool.start(worker)

    @Slot(object, object)
    def _update_statistics_finished(self, max_shifts: dict[UUID, int], fair_shifts: dict[UUID, float]):
        for app_id in max_shifts:
            max_fair_shifts_create = schemas.MaxFairShiftsOfAppCreate(max_shifts=max_shifts[app_id],
                                                                      fair_shifts=fair_shifts[app_id],
                                                                      actor_plan_period_id=app_id)
            command = max_fair_shifts_per_app.Create(max_fair_shifts_create)
            self.controller.execute(command)
        signal_handling.handler_plan_tabs.refresh_plan_statistics(self.plan.plan_period.id)

    def _undo_shift_command(self):
        command: appointment_commands.UpdateAvailDays | None = self.controller.get_recent_undo_command()
        if command is None:
            self._undo_redo_no_more_action(self.bt_undo, 'undo')
            return
        appointment = command.appointment
        appointment_field: AppointmentField = self.findChild(AppointmentField, str(appointment.id))
        self._highlight_undo_redo_appointment_field(appointment_field)
        appointment_field.appointment = appointment
        fill_in_data(appointment_field)
        self.controller.undo()
        self._handle_post_undo_redo_actions()

    def _redo_shift_command(self):
        command: appointment_commands.UpdateAvailDays | None = self.controller.get_recent_redo_command()
        if command is None:
            self._undo_redo_no_more_action(self.bt_redo, 'redo')
            return
        appointment = command.updated_appointment
        appointment_field: AppointmentField = self.findChild(AppointmentField, str(appointment.id))
        self._highlight_undo_redo_appointment_field(appointment_field)
        appointment_field.appointment = appointment
        fill_in_data(appointment_field)
        self.controller.redo()
        self._handle_post_undo_redo_actions()

    def _highlight_undo_redo_appointment_field(self, appointment_field: AppointmentField):
        def reset_field():
            appointment_field.setStyleSheet(self._original_undo_redo_highlight_style_sheet)

        # Verhindert, dass auch bei mehrfach schnellem Auslösen der Action immer auf das originale Stylesheet
        # zurückgesetzt wird:
        if not hasattr(self, '_original_undo_redo_highlight_style_sheet'):
            self._original_undo_redo_highlight_style_sheet = appointment_field.styleSheet()
        appointment_field.setStyleSheet('background-color: rgba(0, 0, 255, 128);')
        QTimer.singleShot(1500, reset_field)

    def _handle_post_undo_redo_actions(self):
        self.post_undo_redo_timer.start()

    def _post_undo_redo_actions(self):
        self.reload_plan()
        signal_handling.handler_plan_tabs.reload_specific_plan_statistics_plan(self.plan.id)
        signal_handling.handler_plan_tabs.refresh_specific_plan_statistics_plan(self.plan.id)

    def _undo_redo_no_more_action(self, button: QPushButton, action: Literal['undo', 'redo']):
        def reset_button():
            # Setze den Button-Text und die Farbe zurück
            if action == 'undo':
                button.setText(self._original_undo_bt_text)
                button.setStyleSheet(self._original_undo_bt_style_sheet)
            else:
                button.setText(self._original_redo_bt_text)
                button.setStyleSheet(self._original_redo_bt_style_sheet)

        # Verhindert, dass auch bei mehrfach schnellem Auslösen der Action immer auf das originale Stylesheet
        # und den originalen Button-Text zurückgesetzt wird:
        if action == 'undo':
            if not hasattr(self, '_original_undo_bt_text'):
                self._original_undo_bt_text = button.text()
            if not hasattr(self, '_original_undo_bt_style_sheet'):
                self._original_undo_bt_style_sheet = button.styleSheet()
        if action == 'redo':
            if not hasattr(self, '_original_redo_bt_text'):
                self._original_redo_bt_text = button.text()
            if not hasattr(self, '_original_redo_bt_style_sheet'):
                self._original_redo_bt_style_sheet = button.styleSheet()
        # Ändere den Button-Text und die Farbe
        button.setText("Keine verbleibende Aktion")
        button.setStyleSheet("color: red")
        # Timer für 1 Sekunde starten
        QTimer.singleShot(1000, reset_button)

    def reload_plan(self):
        self.plan = db_services.Plan.get(self.plan.id)

    def refresh_plan(self):
        self.table_plan.deleteLater()
        self._generate_plan_data()
        self._show_table_plan()
        self.side_menu.raise_()

    @Slot(UUID)
    def refresh_specific_plan(self, plan_id: UUID):
        if plan_id == self.plan.id:
            self.refresh_plan()

    def _reload_from_db_and_generate_plan_data(self):
        self.reload_plan()
        self._generate_plan_data()

    @Slot(UUID)
    def reload_and_refresh_specific_plan(self, plan_period_id: UUID):
        if self.plan.plan_period.id == plan_period_id:
            worker = general_worker.WorkerGeneral(self._reload_from_db_and_generate_plan_data)
            worker.signals.finished.connect(lambda: self.update_progress_manager.tab_finished(self.plan.id))
            self.update_progress_manager.tab_started()
            self.thread_pool.start(worker)

    @Slot(object)
    def reload_specific_plan(self, plan_id: UUID | None):
        if plan_id:
            if self.plan.id == plan_id:
                self.reload_plan()
        else:
            self.reload_plan()

    @Slot(UUID)
    def refresh_plan_period_plan(self, plan_period_id: UUID):
        if self.plan.plan_period.id == plan_period_id:
            self.refresh_plan()

    @Slot(UUID)
    def reload_plan_period_plan(self, plan_period_id: UUID):
        if self.plan.plan_period.id == plan_period_id:
            self.reload_plan()

    def get_weekdays_locations(self):
        if self.plan.location_columns:
            return {k: [db_services.LocationOfWork.get(u) for u in v]
                    for k, v in self.plan.location_columns.items()}

        weekdays_locations = self.generate_weekdays_locations()

        location_columns = {k: [loc.id for loc in v] for k, v in weekdays_locations.items()}
        self.controller.execute(
            plan_commands.UpdateLocationColumns(self.plan.id, location_columns)
        )
        return weekdays_locations

    def generate_weekdays_locations(self):
        weekdays_locations = {weekday_num: [] for weekday_num in self.weekday_names}
        for appointment in self.plan.appointments:
            weekday = appointment.event.date.isoweekday()
            if (appointment.event.location_plan_period.location_of_work.id
                    not in {loc.id for loc in weekdays_locations[weekday]}):
                weekdays_locations[weekday].append(appointment.event.location_plan_period.location_of_work)
        for weekday, locations in weekdays_locations.items():
            weekdays_locations[weekday] = sorted(locations, key=lambda x: (x.name, x.address.city))

        return weekdays_locations

    def generate_week_num_weekday(self):
        kws_wds: defaultdict[int, defaultdict[int, list[schemas.Appointment]]] = defaultdict(lambda: defaultdict(list))
        for appointment in self.plan.appointments:
            week_number, weekday = appointment.event.date.isocalendar()[1:3]
            kws_wds[week_number][weekday].append(appointment)
        for week in kws_wds.values():
            for appointments in week.values():
                appointments.sort(key=lambda x: (x.event.location_plan_period.location_of_work.name,
                                                 x.event.location_plan_period.location_of_work.address.city))
        return kws_wds

    def generate_column_assignments(self):
        column_assignments: defaultdict[int, defaultdict[UUID, int]] = defaultdict(lambda: defaultdict(int))
        curr_column = 0
        for weekday in sorted(self.weekdays_locations.keys()):
            for location in self.weekdays_locations[weekday]:
                column_assignments[weekday][location.id] = curr_column
                curr_column += 1
        return column_assignments

    def _show_table_plan(self):
        self.table_plan = QTableWidget()
        self.layout.addWidget(self.table_plan)
        num_rows = max(self.week_num_rows.values()) + 1
        num_cols = max(self.weekday_cols.values()) + 1
        self.table_plan.setRowCount(num_rows)
        self.table_plan.setColumnCount(num_cols)
        self.table_plan.setStyleSheet('background-color: #2d2d2d; color: white')
        self.display_headers_week_day_names()
        # self.table_plan.setHorizontalHeaderLabels(list(self.weekdays_names.values()))

        self.display_headers_calender_weeks()
        # self.table_plan.setVerticalHeaderLabels([''] + [f'KW {wd}' for wd in self.week_num_row])

        self.table_plan.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.display_headers_locations()
        self.display_days()

        self.resize_table_plan_headers()

    def display_headers_week_day_names(self):
        # funktioniert nur mit app.setStyle(QStyleFactory.create('Fusion'))
        for i, weekday_name in enumerate(self.weekday_names.values()):
            item = QTableWidgetItem(weekday_name)
            item.setBackground(horizontal_header_colors[i % 2])
            self.table_plan.setHorizontalHeaderItem(i, item)

    def display_headers_calender_weeks(self):
        # funktioniert nur mit app.setStyle(QStyleFactory.create('Fusion'))
        self.table_plan.setVerticalHeaderItem(0, QTableWidgetItem(''))
        for week_num, i in self.week_num_rows.items():
            item = QTableWidgetItem(f'KW {week_num}')
            item.setBackground(vertical_header_colors[i % 2])
            self.table_plan.setVerticalHeaderItem(i, item)

    def resize_table_plan_headers(self):
        self.table_plan.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_plan.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def generate_all_days(self):
        start, end = self.plan.plan_period.start, self.plan.plan_period.end
        days_between = (end - start).days + 1
        return [start + datetime.timedelta(days=i) for i in range(days_between)]

    def generate_all_week_nums_of_month(self):
        return sorted({d.isocalendar()[1] for d in self.all_days_of_month})

    def generate_week_num_row(self):
        return {week_num: week_num - min(self.all_week_nums_of_month) + 1 for week_num in self.all_week_nums_of_month}

    def generate_weekday_col(self):
        return {weekday: weekday - min(self.weekday_names) for weekday in self.weekday_names}

    def generate_day_appointments(self):
        day_location_id_appointments: defaultdict[datetime.date, defaultdict[UUID, list]] = defaultdict(lambda: defaultdict(list))
        for appointment in self.plan.appointments:
            date = appointment.event.date
            location_id = appointment.event.location_plan_period.location_of_work.id
            day_location_id_appointments[date][location_id].append(appointment)
        return day_location_id_appointments

    def display_days(self):
        for day in self.all_days_of_month:
            row = self.week_num_rows[day.isocalendar()[1]]
            col = self.weekday_cols[day.isoweekday()]
            location_ids_order = [loc.id for loc in self.weekdays_locations[day.isoweekday()]]
            day_field = DayField(day,
                                 location_ids_order,
                                 self.day_location_id_appointments.get(day),
                                 self.plan.plan_period,
                                 self.appointment_widget_width,
                                 self)
            self.table_plan.setCellWidget(row, col, day_field)

    def display_headers_locations(self):
        for weekday, locations in self.weekdays_locations.items():
            container = QWidget()
            container.setContentsMargins(0, 0, 0, 0)
            container.setStyleSheet(f'background-color: {locations_bg_color};')
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            for location in locations:
                widget = QLabel(f'{location.name} {location.address.city}')
                widget.setStyleSheet('border-left: 1px solid #4d4d4d; border-right: 1px solid black;')
                '3d3d3d'
                widget.setContentsMargins(7, 7, 7, 7)
                widget.setFixedWidth(self.appointment_widget_width)
                widget.setWordWrap(True)
                container_layout.addWidget(widget)
            self.table_plan.setCellWidget(0, self.weekday_cols[weekday], container)

    def display_appointments(self):
        for day, location_ids_appointments in self.day_location_id_appointments.items():
            row = self.week_num_rows[day.isocalendar()[1]]
            col = self.weekday_cols[day.isoweekday()]
            day_field = self.table_plan.cellWidget(row, col)
            day_field: DayField
            day_field.set_location_ids_order([loc.id for loc in self.weekdays_locations[day.isoweekday()]])
            for loc_id, appointments in location_ids_appointments.items():
                for appointment in appointments:
                    day_field.add_appointment_field(
                        AppointmentField(appointment, self))


class TblPlanStatistics(QTableWidget):
    def __init__(self, parent: QWidget, plan_id: UUID):
        super().__init__(parent)

        signal_handling.handler_plan_tabs.signal_refresh_plan_statistics.connect(self.refresh_statistics)
        signal_handling.handler_plan_tabs.signal_reload_specific_plan_statistics_plan.connect(self._reload_plan)
        signal_handling.handler_plan_tabs.signal_refresh_specific_plan_statistics_plan.connect(self._refresh_statistics)

        self.plan_id = plan_id
        self._setup_data()
        self._setup_table()
        self._fill_in_table_cells()

    def _setup_table(self):
        self.setColumnCount(len(self.appointments_of_employees))
        self.setRowCount(4)
        self.setHorizontalHeaderLabels(self.appointments_of_employees.keys())
        for i in range(self.columnCount()):
            self.setColumnWidth(i, 100)
        self.setVerticalHeaderLabels(('Wunsch', 'kann', 'gerecht', 'zugeteilt'))
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        self.setStyleSheet("QTableView {gridline-color: black;}")
        # self.setStyleSheet("QTableView::item { border: 1px solid blue; }")
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)

    def _fill_in_table_cells(self):
        max_fair_shifts = db_services.MaxFairShiftsOfApp.get_all_from__plan_period(self.plan.plan_period.id)
        max_fair_shifts_of_app_ids = {mfs.actor_plan_period.id: (mfs.max_shifts, mfs.fair_shifts)
                                      for mfs in max_fair_shifts}
        for c, (name, (actor_plan_period, appointments)) in enumerate(self.appointments_of_employees.items()):
            requested = actor_plan_period.requested_assignments if actor_plan_period else 0
            if actor_plan_period and (max_fair_shifts := max_fair_shifts_of_app_ids.get(actor_plan_period.id)):
                max_shifts, fair_shifts = max_fair_shifts
            else:
                max_shifts, fair_shifts = 0, 0
            actor_plan_period_id = actor_plan_period.id if actor_plan_period else None
            self._create_item_dates_of_actor(c, requested, 'requested', actor_plan_period_id)
            self._create_item_dates_of_actor(c, max_shifts, 'able', actor_plan_period_id)
            self._create_item_dates_of_actor(c, fair_shifts, 'fair', actor_plan_period_id)
            self._create_item_dates_of_actor(c, len(appointments), 'current', actor_plan_period_id)

    def _create_item_dates_of_actor(self, column: int, num_dates: int | float,
                                    kind: Literal['requested', 'able', 'fair', 'current'],
                                    actor_plan_period_id: UUID) -> None:
        item = QTableWidgetItem(str(num_dates))
        item.setData(Qt.ItemDataRole.UserRole, actor_plan_period_id)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor('black'))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        color = QColor(self.cell_backgrounds[kind][column % 2])
        item.setBackground(color)
        self.setItem(self.row_kind_of_dates[kind], column, item)

    def _setup_data(self):
        self.plan: schemas.PlanShow = db_services.Plan.get(self.plan_id)
        self.appointments_of_employees = get_appointments_of_all_actors_from_plan(self.plan)
        self.cell_backgrounds = {
            'requested': [QColor(0, 0, 0, 32), QColor(0, 0, 0, 16)],
            'able': [QColor(0, 0, 0, 32), QColor(0, 0, 0, 16)],
            'fair': [QColor(0, 0, 0, 32), QColor(0, 0, 0, 16)],
            'current': [QColor(0, 0, 0, 32), QColor(0, 0, 0, 16)]
        }
        self.row_kind_of_dates = {'requested': 0, 'able': 1, 'fair': 2, 'current': 3}

    @Slot(UUID)
    def refresh_statistics(self, plan_period_id: UUID | None):
        if self.plan.plan_period.id == plan_period_id or plan_period_id is None:
            self.clear()
            self._setup_data()
            self._setup_table()
            self._fill_in_table_cells()

    @Slot(UUID)
    def _reload_plan(self, plan_id: UUID):
        if plan_id == self.plan_id:
            self.plan = db_services.Plan.get(self.plan_id)

    @Slot(UUID)
    def _refresh_statistics(self, plan_id: UUID):
        if plan_id == self.plan_id:
            self.refresh_statistics(None)
