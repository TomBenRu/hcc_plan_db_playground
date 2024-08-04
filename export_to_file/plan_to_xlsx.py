import datetime
import os
from uuid import UUID

import xlsxwriter

from configuration import project_paths
from database import db_services, schemas
from gui import frm_plan


class ExportToXlsx:
    def __init__(self, tab_plan: frm_plan.FrmTabPlan):
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

    def _generate_weekday_num__col_locations(self):
        self.weekday_num__col_locations: dict[int, dict[str, int | list[schemas.LocationOfWorkShow]]] = {}
        curr_col = 0
        for weekday_num, locations in self.tab_plan.weekdays_locations.items():
            if not len(locations):
                continue
            self.weekday_num__col_locations[weekday_num] = {'column': curr_col, 'locations': locations}
            curr_col += len(locations)

    def _create_workbook(self):
        self.workbook = xlsxwriter.Workbook(self.excel_output_path)

    def _define_formats(self):
        self.format_title = self.workbook.add_format({'bold': True, 'font_size': 14})

    def _create_worksheet_plan(self):
        self.worksheet_plan = self.workbook.add_worksheet(self.tab_plan.plan.name)

    def _write_headers_week_day_names(self):
        for weekday_num, col_locations in self.weekday_num__col_locations.items():
            if len(col_locations['locations']) > 1:
                self.worksheet_plan.merge_range(
                    2, col_locations['column'] + 1, 2, col_locations['column'] + len(col_locations['locations']),
                    self.tab_plan.weekday_names[weekday_num]
                )
            else:
                self.worksheet_plan.write(2, col_locations['column'] + 1, self.tab_plan.weekday_names[weekday_num])

    def _write_locations(self):
        for weekday_num, col_locations in self.weekday_num__col_locations.items():
            for i, location in enumerate(col_locations['locations']):
                self.worksheet_plan.write(3, col_locations['column'] + 1 + i, location.name)

    def _write_week_nums(self):
        for week_num, row in self.tab_plan.week_num_rows.items():
            self.worksheet_plan.write(row + 3, 0, f'KW {week_num}')

    def _write_appointments(self):
        pass

    def execute(self):
        self.worksheet_plan.write(0, 1, f'Plan: {self.tab_plan.plan.name}', self.format_title)
        self.worksheet_plan.write(0, 7, f'Datum: {datetime.date.today().strftime("%d.%m.%Y")}')
        self._write_headers_week_day_names()
        self._write_locations()
        self._write_week_nums()

        self.workbook.close()
