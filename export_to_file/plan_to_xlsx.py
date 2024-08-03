from uuid import UUID

import xlsxwriter

from database import db_services, schemas


class ExportToXlsx:
    def __init__(self, plan_id: UUID, file_path: str):
        self.plan_id = plan_id
        self.plan: schemas.PlanShow = db_services.Plan.get(plan_id)
        self.file_path = file_path
        self.workbook: xlsxwriter.Workbook | None = None

    def create_workbook(self):
        self.workbook = xlsxwriter.Workbook(self.file_path)

    def execute(self):
        ws_plan = self.workbook.add_worksheet(self.plan.name)
