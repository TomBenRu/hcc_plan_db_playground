import datetime
from collections import defaultdict
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView

from commands import command_base_classes
from commands.database_commands import plan_commands
from database import schemas, db_services


class FrmTabPlan(QWidget):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)

        self.plan = plan

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.week_num_weekday = self.generate_week_num_weekday()
        self.weekdays_locations = self.get_weekdays_locations()
        self.column_assignments = self.generate_column_assignments()

        self.layout = QVBoxLayout(self)

        self.table_plan = QTableWidget()
        self.layout.addWidget(self.table_plan)

        self.table_plan_config()
        self.display_appointments()

    def get_weekdays_locations(self):
        if self.plan.location_columns:
            return {k: [db_services.LocationOfWork.get(u) for u in v] for k, v in self.plan.location_columns.items()}

        weekdays_locations = self.generate_weekdays_locations()

        location_columns = {k: [loc.id for loc in v] for k, v in weekdays_locations.items()}
        self.controller.execute(plan_commands.UpdateLocationColumns(self.plan.id, location_columns))
        return weekdays_locations

    def generate_weekdays_locations(self):
        weekdays_locations: defaultdict[int, list[schemas.LocationOfWork]] = defaultdict(list)
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
        num_rows = len(self.week_num_weekday) + 3
        num_cols = len([loc for locations in self.weekdays_locations.values() for loc in locations]) + 2
        self.table_plan.setRowCount(num_rows)
        self.table_plan.setColumnCount(num_cols)
        self.table_plan.horizontalHeader().setVisible(False)
        self.display_headers_weekdays()
        self.display_headers_locations()
        self.table_plan.setVerticalHeaderLabels(['', ''] + [f'KW {kw}' for kw in sorted(self.week_num_weekday.keys())])
        self.table_plan.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_plan.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def display_headers_weekdays(self):
        weekdays_names = {
            1: 'Montag',
            2: 'Dienstag',
            3: 'Mittwoch',
            4: 'Donnerstag',
            5: 'Freitag',
            6: 'Samstag',
            7: 'Sonntag',
        }

        curr_col = 0
        for weekday in sorted(self.weekdays_locations.keys()):
            header_item = QTableWidgetItem(weekdays_names[weekday])
            header_item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.table_plan.setItem(0, curr_col, header_item)
            if (len_wd := len(self.weekdays_locations[weekday])) > 1:
                self.table_plan.setSpan(0, curr_col, 1, len_wd)
            curr_col += max(len(self.weekdays_locations[weekday]), 1)
    
    def display_headers_locations(self):
        curr_col = 0
        for weekday in sorted(self.weekdays_locations.keys()):
            for i, location in enumerate(self.weekdays_locations[weekday]):
                self.table_plan.setItem(1, curr_col + i,
                                        QTableWidgetItem(f'{location.name}\n{location.address.city}'))
            curr_col += max(len(self.weekdays_locations[weekday]), 1)

    def display_appointments(self):
        min_week_num = min(self.week_num_weekday.keys())
        date_appointments: defaultdict[datetime.date, defaultdict[UUID, list[schemas.Appointment]]] = defaultdict(lambda: defaultdict(list))
        for appointment in self.plan.appointments:
            date_appointments[appointment.event.date][appointment.event.location_plan_period.location_of_work.id].append(appointment)

        for date, dict_uuid_appointments in date_appointments.items():
            kw, wd = date.isocalendar()[1:3]
            for loc_id, appointments in dict_uuid_appointments.items():
                row = kw - min_week_num + 2
                col = self.column_assignments[wd][loc_id]
                container = QWidget()
                layout = QVBoxLayout(container)
                layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
                layout.addWidget(QLabel(date.strftime('%d.%m.%y')))
                for appointment in sorted(appointments, key=lambda x: x.event.time_of_day.time_of_day_enum.time_index):
                    appointment_text = (f'{appointment.event.time_of_day.name}\n'
                                        + ', '.join(a.actor_plan_period.person.f_name
                                                    for a in sorted(appointment.avail_days,
                                                                    key=lambda x: x.actor_plan_period.person.f_name)))
                    label = QLabel(appointment_text)
                    layout.addWidget(label)
                self.table_plan.setCellWidget(row, col, container)
