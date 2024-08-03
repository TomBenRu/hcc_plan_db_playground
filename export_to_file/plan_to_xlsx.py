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
        self._create_workbook()
        self._define_formats()
        self._create_worksheet_plan()

    def _create_workbook(self):
        self.workbook = xlsxwriter.Workbook(self.excel_output_path)

    def _define_formats(self):
        self.format_title = self.workbook.add_format({'bold': True, 'font_size': 14})

    def _create_worksheet_plan(self):
        self.worksheet_plan = self.workbook.add_worksheet(self.tab_plan.plan.name)

    def execute(self):
        self.worksheet_plan.write(0, 1, f'Plan: {self.tab_plan.plan.name}', self.format_title)
        self.worksheet_plan.write(0, 7, f'Datum: {datetime.date.today().strftime("%d.%m.%Y")}')

        self.workbook.close()
