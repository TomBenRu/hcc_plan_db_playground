import datetime
import logging
from uuid import UUID

from PySide6.QtWidgets import QWidget, QMessageBox
import xlsxwriter
from xlsxwriter.worksheet import Worksheet
from xlsxwriter.exceptions import FileCreateError

from database import schemas
from gui import frm_plan
from gui.observer import signal_handling
from tools.helper_functions import date_to_string, time_to_string

logger = logging.getLogger(__name__)


class EventsInPlanForFibu:
    def __init__(self, parent: QWidget, plan: schemas.PlanShow, output_path: str):
        self.parent = parent
        self.plan = plan
        self.output_path = output_path

        self.weekday_names = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

        self.offset_x = 1
        self.offset_y = 2
        self.col_width_kw = 10
        self.min_col_width_employees = 30

        self.nbsp = '\u00A0'
        self.nb_minus = "\u2212"

        self._create_workbook()
        self._define_formats()
        self._create_worksheets()

    def _create_workbook(self):
        self.workbook = xlsxwriter.Workbook(self.output_path)
        self.workbook.set_properties({'title': f'Spitting for Fibu - {self.plan.name}',
                                      'subject': 'Einsatzplan', 'author': 'hcc-plan'})
    def _define_formats(self):
        self.format_horizontal_header = self.workbook.add_format(
            {'bold': True, 'font_size': 16, 'font_color': '#ff1802', 'bg_color': '#a6fcff', 'border': 1,
             'align': 'center', 'valign': 'vcenter'})
        self.format_vertical_header = self.workbook.add_format(
            {'font_size': 14, 'font_color': 'black', 'bg_color': 'white', 'border': 1,
             'align': 'center', 'valign': 'vcenter'})
        self.format_data = self.workbook.add_format(
            {'font_size': 14, 'border': 1, 'align': 'left', 'valign': 'vcenter', 'text_wrap': True, 'indent': 1})
        self.format_empty_cell = self.workbook.add_format(
            {'font_size': 14, 'border': 1, 'align': 'center', 'valign': 'vcenter',
             'diag_type': 1})  # 1 = diagonal von links oben nach rechts unten

    def _calculate_text_width(self, len_text: int, font_size: int = 18) -> float:
        """Approximiert die Textbreite basierend auf Font-Größe"""
        # Durchschnittliche Zeichenbreite in Excel bei verschiedenen Font-Größen
        char_width_factor = {
            10: 1.2, 12: 1.4, 14: 1.6, 16: 1.8, 18: 2.0, 20: 2.2
        }
        factor = char_width_factor.get(font_size, font_size * 0.11) * 0.8
        return max(len_text * factor, self.min_col_width_employees)

    def _define_col_widths(self, worksheet: Worksheet, max_num_chars_date_and_time: int, max_num_chars_employees: int):
        col_width_date_and_time = self._calculate_text_width(max_num_chars_date_and_time, self.format_data.font_size)
        col_width_employees = self._calculate_text_width(max_num_chars_employees, self.format_data.font_size)
        worksheet.set_column(self.offset_x, self.offset_x, self.col_width_kw)
        worksheet.set_column(self.offset_x + 1, self.offset_x + 1, col_width_date_and_time)
        worksheet.set_column(self.offset_x + 2, self.offset_x + 2, col_width_employees)

    def _create_worksheets(self):
        self.location_ids_location: dict[UUID, schemas.LocationOfWork] = {}
        for appointment in self.plan.appointments:
            if not appointment.event.location_plan_period.location_of_work.id in self.location_ids_location:
                location = appointment.event.location_plan_period.location_of_work
                self.location_ids_location[location.id] = location
        for location in self.location_ids_location.values():
            # limit name to 30 characters
            location_name = location.name_an_city
            if len(location_name) > 30:
                location_name = location_name[:27] + '...'
            worksheet = self.workbook.add_worksheet(f'{location_name}')
            self._create_worksheet_content(location, worksheet)

    def _create_worksheet_content(self, location: schemas.LocationOfWork, worksheet: Worksheet):
        worksheet.write(self.offset_y, self.offset_x, 'KW', self.format_horizontal_header)
        worksheet.write(self.offset_y, self.offset_x + 1, 'Termin', self.format_horizontal_header)
        worksheet.write(self.offset_y, self.offset_x + 2, 'Klinikclowns', self.format_horizontal_header)

        # all calendar weeks between start and end date of plan with appointments
        calender_week_numbers: dict[int, list[schemas.Appointment]] = {
            (self.plan.plan_period.start + datetime.timedelta(days=delta)).isocalendar()[1]: []
            for delta in range((self.plan.plan_period.end - self.plan.plan_period.start).days + 1)}

        for appointment in self.plan.appointments:
            if appointment.event.location_plan_period.location_of_work.id != location.id:
                continue
            calender_week_numbers[appointment.event.date.isocalendar()[1]].append(appointment)

        max_num_chars_date_and_time = 0
        max_num_chars_employees = 0

        # write data and calculate column widths
        for row, (calender_week_number, appointments) in enumerate(calender_week_numbers.items()):
            worksheet.write(row + self.offset_y + 1, self.offset_x,
                            f'KW {calender_week_number}', self.format_vertical_header)
            date_and_time_strings = []
            employees_strings = []
            for appointment in sorted(appointments,
                                      key=lambda x: (x.event.date, x.event.time_of_day.start)):
                weekday = self.weekday_names[appointment.event.date.weekday()]
                date = date_to_string(appointment.event.date)
                time = f'{time_to_string(appointment.event.time_of_day.start)} Uhr'
                date_and_time_string = f'{weekday}, {date}, {time}'
                max_num_chars_date_and_time = max(max_num_chars_date_and_time, len(date_and_time_string))
                date_and_time_strings.append(date_and_time_string)
                employees_string = ' + '.join(sorted([a.actor_plan_period.person.full_name
                                                      for a in appointment.avail_days]
                                                     + appointment.guests))
                max_num_chars_employees = max(max_num_chars_employees, len(employees_string))
                employees_strings.append(employees_string)

            if not any(es for es in employees_strings):
                worksheet.write(row + self.offset_y + 1, self.offset_x + 1,
                                '', self.format_empty_cell)
                worksheet.write(row + self.offset_y + 1, self.offset_x + 2,
                                '', self.format_empty_cell)
                continue

            worksheet.write(row + self.offset_y + 1, self.offset_x + 1,
                            '\n'.join(date_and_time_strings), self.format_data)
            worksheet.write(row + self.offset_y + 1, self.offset_x + 2,
                            '\n'.join(employees_strings), self.format_data)
        self._define_col_widths(worksheet, max_num_chars_date_and_time, max_num_chars_employees)

    def execute(self):
        while True:
            success = True
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
                else:
                    logger.error(f'❌ Error closing workbook: {e}')
                    success = False
            break

        return success



def export_events_in_plan_for_fibu(parent: QWidget, plan: schemas.PlanShow, output_path: str):
    exporter = EventsInPlanForFibu(parent, plan, output_path)
    success = exporter.execute()
    signal_handling.handler_excel_export.finished(success)




