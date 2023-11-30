import datetime
from collections import defaultdict
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout, \
    QHBoxLayout

from commands import command_base_classes
from commands.database_commands import plan_commands
from database import schemas, db_services


class AppointmentField(QWidget):
    def __init__(self, appointment: schemas.AppointmentShow):
        super().__init__()
        self.appointment = appointment
        self.layout = QVBoxLayout(self)
        self.lb_time_of_day = QLabel()
        self.lb_employees = QLabel()

        self.set_styling()
        self.fill_in_data()

        self.layout.addWidget(self.lb_time_of_day)
        self.layout.addWidget(self.lb_employees)

    def fill_in_data(self):
        self.lb_time_of_day.setText(f'{self.appointment.event.time_of_day.name}: '
                                    f'{self.appointment.event.time_of_day.start:%H:%M}'
                                    f'-{self.appointment.event.time_of_day.end:%H:%M}')
        employees = '\n'.join([avd.actor_plan_period.person.f_name for avd in self.appointment.avail_days])
        self.lb_employees.setText(employees)

    def set_styling(self):
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setContentsMargins(0, 0, 0, 0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.lb_time_of_day.setContentsMargins(0, 0, 0, 0)
        self.lb_employees.setContentsMargins(0, 0, 0, 0)
        self.lb_time_of_day.font().setPixelSize(8)
        self.lb_employees.font().setBold(True)


class FrmTabPlan(QWidget):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)

        self.plan = plan

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.weekdays_names = {
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
        self.week_num_row = self.generate_week_num_row()
        self.weekday_col = self.generate_weekday_col()

        self.week_num_weekday = self.generate_week_num_weekday()
        self.weekdays_locations = self.get_weekdays_locations()
        self.column_assignments = self.generate_column_assignments()
        self.day_location_id_appointments = self.generate_day_appointments()

        self.layout = QVBoxLayout(self)

        self.table_plan = QTableWidget()
        self.layout.addWidget(self.table_plan)

        self.table_plan_config()

    def get_weekdays_locations(self):
        if self.plan.location_columns:
            return {k: [db_services.LocationOfWork.get(u) for u in v] for k, v in self.plan.location_columns.items()}

        weekdays_locations = self.generate_weekdays_locations()

        location_columns = {k: [loc.id for loc in v] for k, v in weekdays_locations.items()}
        self.controller.execute(plan_commands.UpdateLocationColumns(self.plan.id, location_columns))
        return weekdays_locations

    def generate_weekdays_locations(self):
        weekdays_locations = {weekday_num: [] for weekday_num in self.weekdays_names}
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

    def table_plan_config(self):
        num_rows = max(self.week_num_row.values()) + 1
        num_cols = max(self.weekday_col.values()) + 1
        self.table_plan.setRowCount(num_rows)
        self.table_plan.setColumnCount(num_cols)
        self.table_plan.setHorizontalHeaderLabels(list(self.weekdays_names.values()))
        self.table_plan.setVerticalHeaderLabels([''] + [f'KW {wd}' for wd in self.week_num_row])
        self.display_headers_locations()
        self.display_days()
        self.display_appointments()
        # self.table_plan.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # self.table_plan.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_plan.resizeColumnsToContents()
        self.table_plan.resizeRowsToContents()

    def generate_all_days(self):
        start, end = self.plan.plan_period.start, self.plan.plan_period.end
        days_between = (end - start).days + 1
        return [start + datetime.timedelta(days=i) for i in range(days_between)]

    def generate_all_week_nums_of_month(self):
        return sorted({d.isocalendar()[1] for d in self.all_days_of_month})

    def generate_week_num_row(self):
        return {week_num: week_num - min(self.all_week_nums_of_month) + 1 for week_num in self.all_week_nums_of_month}

    def generate_weekday_col(self):
        return {weekday: weekday - min(self.weekdays_names) for weekday in self.weekdays_names}

    def generate_day_appointments(self):
        day_location_id_appointments: defaultdict[datetime.date, defaultdict[UUID, list]] = defaultdict(lambda: defaultdict(list))
        for appointment in self.plan.appointments:
            date = appointment.event.date
            location_id = appointment.event.location_plan_period.location_of_work.id
            day_location_id_appointments[date][location_id].append(appointment)
        return day_location_id_appointments

    def display_days(self):
        for day in self.all_days_of_month:
            row = self.week_num_row[day.isocalendar()[1]]
            col = self.weekday_col[day.isoweekday()]
            widget_day = QWidget()
            layout_day = QVBoxLayout(widget_day)
            layout_day.setAlignment(Qt.AlignmentFlag.AlignTop)
            layout_day.addWidget(QLabel(day.strftime('%d.%m.%y')))
            container_locations = QWidget()
            container_locations.setObjectName('container_locations')
            layout_locations = QGridLayout(container_locations)
            layout_day.addWidget(container_locations)
            for i, _ in enumerate(self.weekdays_locations[day.isoweekday()]):
                container_appointments = QWidget()
                container_appointments.setFixedWidth(150)
                layout_appointments = QVBoxLayout(container_appointments)
                layout_locations.addWidget(container_appointments, 0, i)
            self.table_plan.setCellWidget(row, col, widget_day)

    def display_headers_locations(self):
        for weekday, locations in self.weekdays_locations.items():
            container = QWidget()
            container_layout = QHBoxLayout(container)
            for location in locations:
                widget = QLabel(f'{location.name} {location.address.city}')
                widget.setFixedWidth(150)
                widget.setWordWrap(True)
                container_layout.addWidget(widget)
            self.table_plan.setCellWidget(0, self.weekday_col[weekday], container)

    def display_appointments(self):
        for day, location_ids_appointments in self.day_location_id_appointments.items():
            row = self.week_num_row[day.isocalendar()[1]]
            col = self.weekday_col[day.isoweekday()]
            container_day = self.table_plan.cellWidget(row, col)
            container_locations = container_day.findChild(QWidget, 'container_locations')
            for loc_id, appointments in location_ids_appointments.items():
                pos = [loc.id for loc in self.weekdays_locations[day.isoweekday()]].index(loc_id)
                container_appointments = container_locations.layout().itemAtPosition(0, pos).widget()
                for appointment in sorted(appointments, key=lambda x: x.event.time_of_day.time_of_day_enum.time_index):
                    container_appointment = QWidget()
                    layout_appointment = QVBoxLayout(container_appointment)
                    container_appointments.layout().addWidget(container_appointment)
                    lb_time_of_day = QLabel(f'{appointment.event.time_of_day.name}: '
                                            f'{appointment.event.time_of_day.start:%H:%M}'
                                            f'-{appointment.event.time_of_day.end:%H:%M}')
                    employees = '\n'.join([avd.actor_plan_period.person.f_name for avd in appointment.avail_days])
                    lb_employees = QLabel(f'{employees}')
                    layout_appointment.addWidget(lb_time_of_day)
                    layout_appointment.addWidget(lb_employees)



