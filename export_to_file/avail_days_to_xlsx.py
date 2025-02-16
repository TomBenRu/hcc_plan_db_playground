import datetime
from collections import defaultdict
from uuid import UUID

from PySide6.QtWidgets import QWidget, QMessageBox
import xlsxwriter
from xlsxwriter.exceptions import FileCreateError

from database import schemas, db_services
from gui.observer import signal_handling


class ExportToXlsx:
    def __init__(self, parent: QWidget, plan_period_id: UUID, output_path: str):
        self.parent = parent
        self.plan_period_id = plan_period_id
        self.output_path = output_path

        self._create_data()
        self._create_workbook()
        self._create_worksheet()
        self._define_formats()

    def _create_data(self):
        self.plan_period = db_services.PlanPeriod.get(self.plan_period_id)
        self.time_of_day_enums = db_services.TimeOfDayEnum.get_all_from__project(self.plan_period.project.id)
        self.month_names = [
            "Januar",
            "Februar",
            "März",
            "April",
            "Mai",
            "Juni",
            "Juli",
            "August",
            "September",
            "Oktober",
            "November",
            "Dezember"
        ]

        self.weekday_short_names = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

        self.days_in_plan_period: defaultdict[tuple[int, int], list] = defaultdict(list)
        for delta in range((self.plan_period.end - self.plan_period.start).days + 1):
            date = (self.plan_period.start + datetime.timedelta(days=delta))
            year, month, day = date.year, date.month, date.day
            self.days_in_plan_period[(year, month)].append(day)

        self.dates_columns: dict[datetime.date, int] = {}

        self.rows_actor_plan_periods = {
            row: db_services.ActorPlanPeriod.get(app.id)
            for row, app in enumerate(
                sorted(
                    db_services.ActorPlanPeriod.get_all_from__plan_period(self.plan_period.id),
                    key=lambda x: x.person.full_name,
                )
            )
        }

    def _create_workbook(self):
        self.workbook = xlsxwriter.Workbook(self.output_path)

    def _create_worksheet(self):
        self.worksheet = self.workbook.add_worksheet(name="Verfügbarkeiten")
        self.worksheet.set_landscape()
        self.worksheet.set_paper(9)
        self.worksheet.set_margins(0.4, 0.4, 0.4, 0.4)
        self.worksheet.fit_to_pages(1, 1)

    def _define_formats(self):
        self.format_header_months = self.workbook.add_format(
            {'bold': True, 'font_size': 18, 'valign': 'vcenter', 'bg_color': '#5ecaff', 'border': 1})
        self.format_header_days_default = self.workbook.add_format(
            format_header_days_default := {
                'bold': True, 'font_size': 12, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#93ff8b',
                'bottom': 2, 'right': 1, 'top': 1, 'left': 1
            }
        )
        self.format_header_days_saturday = self.workbook.add_format(
            format_header_days_default.copy() | {'bg_color': '#ffb766'}
        )
        self.format_header_days_sunday = self.workbook.add_format(
            format_header_days_default.copy() | {'bg_color': '#ff6c64'}
        )
        self.format_header_employees_even = self.workbook.add_format(
            format_header_employees_even := {
                'bold': True, 'font_size': 12, 'align': 'right', 'valign': 'vcenter', 'bg_color': '#b5e2e4',
             'bottom': 1, 'right': 2, 'top': 1, 'left': 1
            }
        )
        self.format_header_employees_odd = self.workbook.add_format(
            format_header_employees_even.copy() | {'bg_color': '#cffdff'}
        )
        self.format_availabilities_even = self.workbook.add_format(
            format_availabilities_even := {
                'bold': True, 'font_size': 12, 'align': 'center', 'valign': 'vcenter', 'bg_color': '#f2f2f2',
                'border': 1
            }
        )
        self.format_availabilities_odd = self.workbook.add_format(
            format_availabilities_even.copy() | {'bg_color': '#ffffff'}
        )
        self.format_title = self.workbook.add_format(
            {'bold': True, 'font_size': 24, 'valign': 'vcenter'}
        )
        self.format_explanation = self.workbook.add_format(
            {'font_size': 12, 'valign': 'vcenter'}
        )

    def _write_header_months(self):
        """Write the header row with the month names."""
        offset_x = 1
        offset_y = 2
        for i, ((year, month), days) in enumerate(self.days_in_plan_period.items()):
            self.worksheet.merge_range(offset_y, i + offset_x, offset_y, i + offset_x + len(days) - 1,
                                       f'{self.month_names[month - 1]} {year}',
                                       self.format_header_months)

    def _write_header_days(self):
        """Write the header row with the day names."""
        offset_x = 1
        offset_y = 3
        for (year, month), days in self.days_in_plan_period.items():
            for i, day in enumerate(days):
                date = datetime.date(year, month, day)
                day_format = (self.format_header_days_saturday if date.weekday() == 5
                              else self.format_header_days_sunday if date.weekday() == 6
                              else self.format_header_days_default)
                weekday = self.weekday_short_names[date.weekday()]
                self.worksheet.write(offset_y, i + offset_x, f'{weekday}, {day:02d}.', day_format)
                self.dates_columns[datetime.date(year, month, day)] = i + offset_x
            offset_x += len(days)

    def _write_header_employees(self):
        """Write the header column with the employee names."""
        offset_x = 0
        offset_y = 4
        formats_employees = [self.format_header_employees_odd, self.format_header_employees_even]
        for row, actor_plan_period in self.rows_actor_plan_periods.items():
            self.worksheet.write(
                row + offset_y, offset_x, actor_plan_period.person.full_name, formats_employees[row % 2])
        self.worksheet.set_column(0, 0, 20)


    def _write_availabilities(self):
        """Write the availabilities for each day."""
        offset_x = 0
        offset_y = 4
        formats_availabilities = [self.format_availabilities_odd, self.format_availabilities_even]

        for row in self.rows_actor_plan_periods.keys():
            for col in self.dates_columns.values():
                self.worksheet.write(row + offset_y, col + offset_x, '', formats_availabilities[row % 2])

        for row, actor_plan_period in self.rows_actor_plan_periods.items():
            dates_avail_days: defaultdict[datetime.date, list[schemas.AvailDay]] = defaultdict(list)
            for avd in actor_plan_period.avail_days:
                dates_avail_days[avd.date].append(avd)
            for date, avail_days in dates_avail_days.items():
                text_day_times = ', '.join([avd.time_of_day.time_of_day_enum.abbreviation
                                            for avd in sorted(avail_days,
                                                              key=lambda x: x.time_of_day.time_of_day_enum.time_index)])
                self.worksheet.write(row + offset_y, self.dates_columns[date] + offset_x, text_day_times,
                                     formats_availabilities[row % 2])

    def _write_titel(self):
        """Write the title of the worksheet."""
        self.worksheet.write(0, 0, f'Verfügbarkeiten für Team {self.plan_period.team.name} '
                                   f'{self.plan_period.start:%d.%m.%y} - {self.plan_period.end:%d.%m.%y}',
                             self.format_title)

    def _write_explanation(self):
        """Write the explanation of the worksheet."""
        offset_x = 1
        offset_y = len(self.rows_actor_plan_periods) + 5
        enums_text = ', '.join([f'{t_o_d_enum.abbreviation}: {t_o_d_enum.name}'
                                for t_o_d_enum in sorted(self.time_of_day_enums, key=lambda x: x.time_index)])
        self.worksheet.write(offset_y, offset_x, 'Abkürzungen:', self.format_explanation)
        self.worksheet.write(offset_y + 1, offset_x, enums_text, self.format_explanation)


    def execute(self):
        self._write_header_months()
        self._write_header_days()
        self._write_header_employees()
        self._write_availabilities()
        self._write_titel()
        self._write_explanation()

        self.workbook.close()

