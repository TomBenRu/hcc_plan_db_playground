import datetime
from collections import defaultdict
from uuid import UUID

from PySide6.QtCore import Qt, QRect, QThread, Signal, QObject, Slot
from PySide6.QtGui import QContextMenuEvent, QColor, QPainter, QBrush, QPen
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout, \
    QHBoxLayout, QMessageBox, QMenu, QAbstractItemView, QGraphicsDropShadowEffect, QDialog, QFormLayout, QGroupBox, \
    QDialogButtonBox, QComboBox, QProgressDialog, QProgressBar

from commands import command_base_classes
from commands.database_commands import plan_commands, appointment_commands
from database import schemas, db_services
from database.special_schema_requests import get_persons_of_team_at_date
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from gui.observer import signal_handling
from gui.widget_styles.plan_table import horizontal_header_colors, vertical_header_colors, locations_bg_color
from sat_solver import solver_main


class SolverThread(QThread):
    finished = Signal(bool)  # Signal emitted when the solver finishes

    def __init__(self, parent: QObject, plan_id: UUID):
        super().__init__(parent)
        self.plan_id = plan_id

    def run(self):
        # Call the solver function here
        success = solver_main.test_plan(self.plan_id)
        self.finished.emit(success)  # Emit the finished signal when the solver completes


class DlgProgress(QProgressDialog):
    def __init__(self, parent: QWidget, window_title: str, label_text: str, cancel_button_text: str):
        super().__init__(label_text, cancel_button_text, 0, 0, parent)
        self.setWindowTitle(window_title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.canceled.connect(self.cancel_solving)
        # self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)

    @Slot()
    def cancel_solving(self):
        signal_handling.handler_solver.cancel_solving()


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
        self.lb_explanation = QLabel('Hier können Sie die Besetzung ändern.')
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

        self.new_avail_day_ids: list[UUID] = []

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
        for j, avd in enumerate(self.appointment.avail_days):
            self.combos_employees[j].setCurrentIndex(self.combos_employees[-1].findData(avd.id))

    def accept(self):
        self.new_avail_day_ids = [combo.currentData() for combo in self.combos_employees if combo.currentData()]
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
                 plan_period: schemas.PlanPeriod, appointment_widget_width: int,
                 controller: command_base_classes.ContrExecUndoRedo, plan_id: UUID):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)

        self.plan_id = plan_id
        self.day = day
        self.location_ids_appointments = location_ids_appointments
        self.location_ids_order = location_ids_order
        self.plan_period = plan_period
        self.appointment_widget_width = appointment_widget_width
        self.controller = controller

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
                        container.add_appointment_field(AppointmentField(appointment, self.controller, self.plan_id))

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
    def __init__(self, appointment: schemas.Appointment, controller: command_base_classes.ContrExecUndoRedo, 
                 plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id
        self.appointment = appointment
        self.location_id = appointment.event.location_plan_period.location_of_work.id
        self.controller = controller
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.lb_time_of_day = QLabel()
        self.lb_employees = QLabel()
        self.lb_missing = QLabel()

        self.set_styling()

        self.layout.addWidget(self.lb_time_of_day)
        self.layout.addWidget(self.lb_employees)

        self.fill_in_data()

        self.setToolTip(f'Hallo {" und ".join([a.actor_plan_period.person.f_name for a in appointment.avail_days])}.\n'
                        f'Benutze Rechtsklick, um zum Context-Menü zu gelangen.')

    def mouseReleaseEvent(self, event):
        dlg = DlgEditAppointment(self, self.appointment)
        if dlg.exec():
            self.command = appointment_commands.UpdateAvailDays(self.appointment.id, dlg.new_avail_day_ids)
            self.controller.execute(self.command)
            self.appointment = self.command.updated_appointment
            self.fill_in_data()

            self.progress_bar = DlgProgress(self, 'Überprüfung',
                                            'Besetzungsänderungen werden auf Validität getestet.', 'Abbruch')
            self.progress_bar.show()

            solver_thread = SolverThread(self, self.plan_id)
            solver_thread.finished.connect(self.test_finished)
            solver_thread.start()
            return

            success = solver_main.test_plan(self.plan_id)
            if success:
                QMessageBox.information(self, 'Besetzungsänderung',
                                        'Die Änderung der Besetzung wurde erfolgreich vorgenommen.')
            else:
                reply = QMessageBox.critical(self, 'Besetzungsänderung',
                                             'Die Änderung der Besetzung ist nicht ohne Konflikt machbar.\n'
                                             'Sollen die Änderungen zurückgenommen werden',
                                             QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self.controller.undo()
                    self.appointment = self.command.appointment
                    self.fill_in_data()

    @Slot(bool)
    def test_finished(self, success: bool):
        self.progress_bar.close()
        if success:
            QMessageBox.information(self, 'Besetzungsänderung',
                                    'Die Änderung der Besetzung wurde erfolgreich vorgenommen.')
        else:
            reply = QMessageBox.critical(self, 'Besetzungsänderung',
                                         'Die Änderung der Besetzung ist nicht ohne Konflikt machbar.\n'
                                         'Sollen die Änderungen zurückgenommen werden',
                                         QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.controller.undo()
                self.appointment = self.command.appointment
                self.fill_in_data()

    def contextMenuEvent(self, event: QContextMenuEvent):
        context_menu = QMenu(self)
        context_menu.addAction(f'Action 1 {self.appointment.event.date} ({self.appointment.event.time_of_day.name}) '
                               f'{self.appointment.event.location_plan_period.location_of_work.name}')
        context_menu.addAction(f'Action 2 {self.appointment.event.date} ({self.appointment.event.time_of_day.name}) '
                               f'{self.appointment.event.location_plan_period.location_of_work.name}')
        context_menu.exec(event.globalPos())

    def fill_in_data(self):
        self.lb_time_of_day.setText(f'{self.appointment.event.time_of_day.name}: '
                                    f'{self.appointment.event.time_of_day.start:%H:%M}'
                                    f'-{self.appointment.event.time_of_day.end:%H:%M}')
        employees = '\n'.join([f'{avd.actor_plan_period.person.f_name} {avd.actor_plan_period.person.l_name}'
                               for avd in sorted(self.appointment.avail_days,
                                                 key=lambda x: (x.actor_plan_period.person.f_name,
                                                                x.actor_plan_period.person.l_name))])
        nr_required_persons = db_services.CastGroup.get_cast_group_of_event(self.appointment.event.id).nr_actors

        if missing := (nr_required_persons - len(self.appointment.avail_days)):
            missing_txt = f'unbesetzt: {missing}'
            self.lb_missing.setText(missing_txt)
            self.layout.addWidget(self.lb_missing)
        else:
            self.lb_missing.setParent(None)

        self.lb_employees.setText(employees)

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
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)

        signal_handling.handler_plan_tabs.signal_reload_plan_from_db.connect(self.reload_plan)

        self.plan = plan

        self.appointment_widget_with = 120

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.weekday_names = {
            1: 'Montag',
            2: 'Dienstag',
            3: 'Mittwoch',
            4: 'Donnerstag',
            5: 'Freitag',
            6: 'Samstag',
            7: 'Sonntag',
        }
        self.all_days_of_month = self.generate_all_days()
        self.all_week_nums_of_month = self.generate_all_week_nums_of_month()
        self.week_num_rows = self.generate_week_num_row()
        self.weekday_cols = self.generate_weekday_col()

        self.week_num_weekday = self.generate_week_num_weekday()
        self.weekdays_locations = self.get_weekdays_locations()
        self.column_assignments = self.generate_column_assignments()
        self.day_location_id_appointments = self.generate_day_appointments()

        self.layout = QVBoxLayout(self)

        self.table_plan = QTableWidget()
        self.layout.addWidget(self.table_plan)

        self.configure_table_plan()

    def reload_plan(self):
        self.plan = db_services.Plan.get(self.plan.id)

    def get_weekdays_locations(self):
        if self.plan.location_columns:
            return {k: [db_services.LocationOfWork.get(u) for u in v] for k, v in self.plan.location_columns.items()}

        weekdays_locations = self.generate_weekdays_locations()

        location_columns = {k: [loc.id for loc in v] for k, v in weekdays_locations.items()}
        self.controller.execute(plan_commands.UpdateLocationColumns(self.plan.id, location_columns))
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

    def configure_table_plan(self):
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
                                 self.appointment_widget_with,
                                 self.controller, 
                                 self.plan.id)
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
                widget.setFixedWidth(self.appointment_widget_with)
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
                    day_field.add_appointment_field(AppointmentField(appointment, self.controller, self.plan.id))
