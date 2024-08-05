import datetime
import itertools
import os
from collections import defaultdict
from pprint import pprint
from uuid import UUID

import xlsxwriter
from PySide6.QtWidgets import QWidget, QMessageBox
from xlsxwriter.exceptions import FileCreateError

from configuration import project_paths
from database import db_services, schemas
from gui import frm_plan
from gui.observer import signal_handling


class ExportToXlsx:
    def __init__(self, parent: QWidget, tab_plan: frm_plan.FrmTabPlan):
        self.parent = parent
        self.tab_plan = tab_plan
        self.excel_output_path = os.path.join(project_paths.Paths.root_path,
                                              'excel_output',
                                              f'{self.tab_plan.plan.name}.xlsx')
        self.offset_x = 0
        self.offset_y = 0
        self._create_workbook()
        self._define_formats()
        self._create_worksheet_plan()
        self._generate_weekday_num__col_locations()
        self._generate_week_num__row_merge()

    def _generate_weekday_num__col_locations(self):
        self.weekday_num__col_locations: dict[int, dict[str, int | list[schemas.LocationOfWorkShow]]] = {}
        curr_col = 0
        for weekday_num, locations in self.tab_plan.weekdays_locations.items():
            if not len(locations):
                continue
            self.weekday_num__col_locations[weekday_num] = {'column': curr_col, 'locations': locations}
            curr_col += len(locations)

    def _generate_week_num__row_merge(self):
        self.week_num__weekday_location_appointments: defaultdict[
            int, defaultdict[int, defaultdict[UUID, list[schemas.Appointment]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        self.week_num__row_merge: dict[int, dict[str, int]] = {}

        for appointment in self.tab_plan.plan.appointments:
            week_num = appointment.event.date.isocalendar()[1]
            weekday = appointment.event.date.isocalendar()[2]
            location_id = appointment.event.location_plan_period.location_of_work.id
            self.week_num__weekday_location_appointments[week_num][weekday][location_id].append(appointment)

        curr_row = 4
        for week_num in sorted(self.week_num__weekday_location_appointments.keys()):
            weekday_location_appointment = self.week_num__weekday_location_appointments[week_num]
            max_appointments_in_week = max(
                max(len(appointments) for appointments in location_appointments.values())
                for weekday, location_appointments in weekday_location_appointment.items()
            )
            self.week_num__row_merge[week_num] = {'row': curr_row, 'merge': max_appointments_in_week + 1}
            curr_row += max_appointments_in_week + 1

    def _create_workbook(self):
        self.workbook = xlsxwriter.Workbook(self.excel_output_path)

    def _define_formats(self):
        self.format_title = self.workbook.add_format({'bold': True, 'font_size': 14})
        self.format_weekday_1 = self.workbook.add_format({'bold': True, 'font_size': 12, 'font_color': 'white'})
        self.format_weekday_2 = self.workbook.add_format({'bold': True, 'font_size': 12, 'font_color': 'white'})
        self.format_locations_1 = self.workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'white',
                                                            'text_wrap': True})
        self.format_locations_2 = self.workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'white',
                                                            'text_wrap': True})
        self.format_day_nrs_1 = self.workbook.add_format({'bold': False, 'font_size': 10})
        self.format_day_nrs_2 = self.workbook.add_format({'bold': False, 'font_size': 10})
        self.format_column_kw_1 = self.workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'white'})
        self.format_column_kw_2 = self.workbook.add_format({'bold': True, 'font_size': 10, 'font_color': 'white'})
        self.format_appointments = self.workbook.add_format({'bold': False, 'font_size': 10, 'border': 1})
        self.format_appointments_unbesetzt = self.workbook.add_format({'bold': False, 'font_size': 10,
                                                                       'font_color': 'red', 'border': 1})
        self.format_weekday_1.bg_color = self.tab_plan.plan.excel_export_settings.color_head_weekdays_1
        self.format_weekday_2.bg_color = self.tab_plan.plan.excel_export_settings.color_head_weekdays_2
        self.format_locations_1.bg_color = self.tab_plan.plan.excel_export_settings.color_head_locations_1
        self.format_locations_2.bg_color = self.tab_plan.plan.excel_export_settings.color_head_locations_2
        self.format_day_nrs_1.bg_color = self.tab_plan.plan.excel_export_settings.color_day_nrs_1
        self.format_day_nrs_2.bg_color = self.tab_plan.plan.excel_export_settings.color_day_nrs_2

        self.row_height_weekdays = 20
        self.row_height_locations = 25
        self.row_height_appointments = 35
        self.row_height_dates = 20
        self.col_width_kw = 7
        self.col_width_locations = 18

    def _create_worksheet_plan(self):
        self.worksheet_plan = self.workbook.add_worksheet(self.tab_plan.plan.name)

    def _write_headers_week_day_names(self):
        self.worksheet_plan.set_row(2, self.row_height_weekdays)
        for i, (weekday_num, col_locations) in enumerate(self.weekday_num__col_locations.items()):
            if len(col_locations['locations']) > 1:
                self.worksheet_plan.merge_range(
                    2, col_locations['column'] + 1, 2, col_locations['column'] + len(col_locations['locations']),
                    self.tab_plan.weekday_names[weekday_num],
                    self.format_weekday_1 if i % 2 else self.format_weekday_2
                )
            else:
                self.worksheet_plan.write(2, col_locations['column'] + 1, self.tab_plan.weekday_names[weekday_num],
                                          self.format_weekday_1 if i % 2 else self.format_weekday_2)

    def _write_locations(self):
        self.worksheet_plan.set_row(3, self.row_height_locations)
        format_idx = 0
        for weekday_num, col_locations in self.weekday_num__col_locations.items():
            for i, location in enumerate(col_locations['locations']):
                column = col_locations['column'] + 1 + i
                self.worksheet_plan.write(3, column, location.name,
                                          self.format_locations_1 if format_idx % 2 else self.format_locations_2)
                self.worksheet_plan.set_column(column, column, self.col_width_locations)
                format_idx += 1

    def _write_week_nums(self):
        self.worksheet_plan.set_column(0, 0, self.col_width_kw)
        for i, (week_num, row_merge) in enumerate(self.week_num__row_merge.items()):
            if row_merge['merge'] > 1:
                self.worksheet_plan.merge_range(
                    row_merge['row'], 0, row_merge['row'] + row_merge['merge'] - 1, 0,
                    f'KW {week_num}', self.format_weekday_1 if i % 2 else self.format_weekday_2
                )
            else:
                self.worksheet_plan.write(row_merge['row'], 0, f'KW {week_num}',
                                          self.format_weekday_1 if i % 2 else self.format_weekday_2)

    def _write_dates(self):
        date_rows = set()
        self.cells_for_default_appointments = []
        min_date = min(appointment.event.date for appointment in self.tab_plan.plan.appointments)
        max_date = max(appointment.event.date for appointment in self.tab_plan.plan.appointments)
        curr_date = min_date
        while curr_date <= max_date:
            if not (column_locations := self.weekday_num__col_locations.get(curr_date.isocalendar()[2])):
                curr_date += datetime.timedelta(days=1)
                continue
            column = column_locations['column'] + 1
            row = self.week_num__row_merge[curr_date.isocalendar()[1]]['row']
            date_rows.add(row)
            merge_cols = len(column_locations['locations'])

            # Dies wird gebraucht, um Appointment-Zellen mit einem Default-Format zu füllen:
            cols_of_date_cells = [column + i for i in range(merge_cols)]
            rows_of_loc_cells = [row + i for i in range(1, self.week_num__row_merge[curr_date.isocalendar()[1]]['merge'])]
            print(f'{rows_of_loc_cells=}')
            print(f'{cols_of_date_cells=}')
            for r, c in itertools.product(rows_of_loc_cells, cols_of_date_cells):
                self.cells_for_default_appointments.append((r, c))

            color_idx = list(self.weekday_num__col_locations.keys()).index(curr_date.isocalendar()[2])
            if merge_cols > 1:
                self.worksheet_plan.merge_range(
                    row, column, row, column + merge_cols - 1, curr_date.strftime('%d.%m.%y'),
                    self.format_day_nrs_1 if color_idx % 2 else self.format_day_nrs_2)
            else:
                self.worksheet_plan.write(row, column, curr_date.strftime('%d.%m.%y'),
                                          self.format_day_nrs_1 if color_idx % 2 else self.format_day_nrs_2)
            curr_date += datetime.timedelta(days=1)

        for row in date_rows:
            self.worksheet_plan.set_row(row, self.row_height_dates)

    def _write_appointments(self):

        for row, col in self.cells_for_default_appointments:
            self.worksheet_plan.write(row, col, '', self.format_appointments)

        def make_text_names():
            text = ''
            if len(appointment.avail_days):
                text = '\n' + '\n'.join(f'{avd.actor_plan_period.person.f_name} '
                                        f'{avd.actor_plan_period.person.l_name}'
                                        for avd in appointment.avail_days)
            cast_group = db_services.CastGroup.get_cast_group_of_event(appointment.event.id)
            for _ in range(cast_group.nr_actors - len(appointment.avail_days)):
                text += '\nunbesetzt'
            return text

        rows_cols: defaultdict[int, list[int]] = defaultdict(list)
        rows = set()
        cols = set()
        for week_num, weekday_location_appointments in self.week_num__weekday_location_appointments.items():
            for weekday, location_appointments in weekday_location_appointments.items():
                for location_id, appointments in location_appointments.items():
                    for i, appointment in enumerate(
                            sorted(appointments, key=lambda x: x.event.time_of_day.time_of_day_enum.time_index)):
                        loc_header = self.weekday_num__col_locations[appointment.event.date.isocalendar()[2]]['locations']
                        loc_indexes = {loc.id: i for i, loc in enumerate(loc_header)}
                        row = self.week_num__row_merge[appointment.event.date.isocalendar()[1]]['row'] + 1 + i
                        col = (self.weekday_num__col_locations[appointment.event.date.isocalendar()[2]]['column']
                               + 1 + loc_indexes[location_id])
                        rows_cols[row].append(col)
                        rows.add(row)
                        cols.add(col)
                        text_names = make_text_names()
                        self.worksheet_plan.write(
                            row, col, f'{appointment.event.time_of_day.start.strftime("%H:%M")}{text_names}',
                        )

        for row, cols_ in rows_cols.items():
            self.worksheet_plan.set_row(row, self.row_height_appointments)
            self.worksheet_plan.conditional_format(row, min(cols), row, max(cols),
                                                   {'type': 'text', 'criteria': 'containing', 'value': 'unbesetzt',
                                                    'format': self.format_appointments_unbesetzt})

    def execute(self):
        self.worksheet_plan.write(0, 1, f'Plan: {self.tab_plan.plan.name}', self.format_title)
        self.worksheet_plan.write(0, 7, f'Datum: {datetime.date.today().strftime("%d.%m.%Y")}')
        self._write_headers_week_day_names()
        self._write_locations()
        self._write_week_nums()
        self._write_dates()
        self._write_appointments()

        while True:
            try:
                self.workbook.close()
            except FileCreateError as e:
                reply = QMessageBox.critical(self.parent,
                                             'Excel-Export',
                                             'Datei kann nicht gespeichert werden. Bitte schließen Sie die Datei, '
                                             'falls sie in Excel geöffnet ist.\nMöchten Sie erneut versuchen, '
                                             'die Datei zu speichern?',
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    continue
            break

        signal_handling.handler_excel_export.finished(self.excel_output_path)

# todo: extra rows for day numbers
#  plan = xlsxwriter.Workbook(os.path.relpath(f'clients/{self.active_client}/ergebnisse/{self.year}-{self.month:02}/{filename}.xlsx'))
#         spielplan = plan.add_worksheet('Spielplan')
#         clowntermine = plan.add_worksheet('Clowntermine')
#         spielplan.set_landscape()
#         clowntermine.set_landscape()
#         spielplan.set_paper(9)
#         clowntermine.set_paper(9)
#         spielplan.set_margins(0.4, 0.4, 0.4, 0.4)
#         clowntermine.set_margins(0.4, 0.4, 0.4, 0.4)
#         spielplan.fit_to_pages(1, 1)
#         clowntermine.fit_to_pages(1, 1)
