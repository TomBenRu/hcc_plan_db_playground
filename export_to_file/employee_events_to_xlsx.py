"""
Employee Events Excel Export Extension.

This module extends the existing plan Excel export to include Employee Events
that are relevant to the specific team and planning period.

Features:
- Integrates Employee Events into existing Excel export
- Filters events by team and planning period
- Shows events in a separate worksheet
- Includes event details: title, description, start/end datetime, address, participants
"""

import datetime
from typing import List
from uuid import UUID

import xlsxwriter
from xlsxwriter.exceptions import FileCreateError
from PySide6.QtCore import QCoreApplication

from database import db_services, schemas
from employee_event import EmployeeEventService
from tools.helper_functions import date_to_string, time_to_string


class EmployeeEventsExcelExporter:
    """
    Extension class to add Employee Events to existing Excel exports.
    
    This class can be integrated into the existing ExportToXlsx workflow
    to add Employee Events relevant to the team and planning period.
    """
    
    def __init__(self, workbook: xlsxwriter.Workbook, team: schemas.Team, 
                 plan_period: schemas.PlanPeriod, excel_settings: schemas.ExcelExportSettings):
        self.workbook = workbook
        self.team = team
        self.plan_period = plan_period
        self.excel_settings = excel_settings
        self.employee_event_service = EmployeeEventService()
        
        # Data
        self.employee_events: List = []  # Will hold filtered employee events
        
        # Layout settings
        self.offset_x = 0
        self.offset_y = 2
        
        # Create worksheet and formats
        self._create_worksheet()
        self._define_formats()
        
    def _create_worksheet(self):
        """Create the Employee Events worksheet."""
        self.worksheet = self.workbook.add_worksheet(
            QCoreApplication.translate("EmployeeEventsExcelExporter", 'Employee Events')
        )
        
        # Set worksheet properties
        self.worksheet.set_landscape()
        self.worksheet.set_paper(9)
        self.worksheet.set_margins(0.4, 0.4, 0.4, 0.4)
        self.worksheet.fit_to_pages(1, 1)
        
    def _define_formats(self):
        """Define cell formats for Employee Events."""
        # Title formats
        self.format_title = self.workbook.add_format({
            'bold': True, 
            'font_size': 16, 
            'font_color': 'white',
            'bg_color': '#0078d4',
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Header formats
        self.format_header = self.workbook.add_format({
            'bold': True, 
            'font_size': 12, 
            'font_color': 'white',
            'bg_color': '#106ebe',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Data formats
        self.format_data = self.workbook.add_format({
            'font_size': 10,
            'border': 1,
            'valign': 'top',
            'text_wrap': True
        })
        
        self.format_data_center = self.workbook.add_format({
            'font_size': 10,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # DateTime format for Start/End columns
        self.format_datetime = self.workbook.add_format({
            'font_size': 10,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        # Alternating row formats
        self.format_data_alt = self.workbook.add_format({
            'font_size': 10,
            'border': 1,
            'valign': 'top',
            'text_wrap': True,
            'bg_color': '#f0f0f0'
        })
        
        self.format_data_center_alt = self.workbook.add_format({
            'font_size': 10,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f0f0f0'
        })
        
        # DateTime format alternating for Start/End columns
        self.format_datetime_alt = self.workbook.add_format({
            'font_size': 10,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#f0f0f0'
        })
        
        # Column widths
        self.col_widths = {
            'start': 18,           # DateTime braucht mehr Platz als nur Datum
            'end': 18,             # DateTime braucht mehr Platz als nur Zeit
            'title': 25,
            'description': 40,
            'address': 25,
            'categories': 20,
            'participants': 30
        }
        
    def _load_employee_events(self):
        """Load Employee Events filtered by team and planning period."""
        try:
            # Get all events for the project
            all_events = self.employee_event_service.get_all_events(self.team.project.id)
            
            # Filter events by team and planning period
            filtered_events = []
            
            for event in all_events:
                # Check if event is assigned to current team
                team_assigned = False
                if event.teams:
                    team_assigned = any(t.id == self.team.id for t in event.teams)
                else:
                    # If no specific teams assigned, include for all teams
                    team_assigned = True
                
                # Check if event is within planning period
                within_period = (
                    event.start.date() >= self.plan_period.start and 
                    event.start.date() <= self.plan_period.end
                )
                
                if team_assigned and within_period:
                    filtered_events.append(event)
            
            # Sort events by start date and time
            self.employee_events = sorted(filtered_events, key=lambda e: (e.start.date(), e.start.time()))
            
        except Exception as e:
            print(f"Error loading employee events: {e}")
            self.employee_events = []
    
    def _write_title(self):
        """Write the title section."""
        # Main title
        title_text = (QCoreApplication.translate("EmployeeEventsExcelExporter", "Employee Events - {team_name}")
                      .format(team_name=self.team.name))
        self.worksheet.merge_range(self.offset_y, self.offset_x, self.offset_y, self.offset_x + 6, 
                                   title_text, self.format_title)
        
        # Subtitle with period
        subtitle_text = (QCoreApplication.translate("EmployeeEventsExcelExporter", "Period: {start_date} - {end_date}")
                         .format(start_date=date_to_string(self.plan_period.start),
                                 end_date=date_to_string(self.plan_period.end)))
        self.worksheet.merge_range(self.offset_y + 1, self.offset_x, self.offset_y + 1, self.offset_x + 6, 
                                   subtitle_text, self.format_data_center)
        
        # Set row heights
        self.worksheet.set_row(self.offset_y, 25)
        self.worksheet.set_row(self.offset_y + 1, 20)
        
    def _write_headers(self):
        """Write table headers."""
        headers = [
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "Start"), 'start'),
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "End"), 'end'),
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "Title"), 'title'),
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "Description"), 'description'),
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "Address"), 'address'),
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "Categories"), 'categories'),
            (QCoreApplication.translate("EmployeeEventsExcelExporter", "Participants"), 'participants')
        ]
        
        header_row = self.offset_y + 3
        
        for col, (header_text, col_key) in enumerate(headers):
            self.worksheet.write(header_row, self.offset_x + col, header_text, self.format_header)
            self.worksheet.set_column(self.offset_x + col, self.offset_x + col, self.col_widths[col_key])
        
        # Set header row height
        self.worksheet.set_row(header_row, 25)
        
    def _write_events(self):
        """Write Employee Events data."""
        if not self.employee_events:
            # No events message
            no_events_row = self.offset_y + 4
            self.worksheet.merge_range(no_events_row, self.offset_x, no_events_row, self.offset_x + 6,
                                       QCoreApplication.translate("EmployeeEventsExcelExporter",
                                                                  "No Employee Events found for this team and period."),
                                       self.format_data_center)
            self.worksheet.set_row(no_events_row, 25)
            return
        
        start_row = self.offset_y + 4
        
        for row_idx, event in enumerate(self.employee_events):
            current_row = start_row + row_idx
            
            # Alternating row colors
            is_even = row_idx % 2 == 0
            format_data = self.format_data if is_even else self.format_data_alt
            format_center = self.format_data_center if is_even else self.format_data_center_alt
            format_datetime = self.format_datetime if is_even else self.format_datetime_alt
            
            # Start (DateTime)
            start_text = f"{date_to_string(event.start.date())} {time_to_string(event.start.time())}"
            self.worksheet.write(current_row, self.offset_x, start_text, format_datetime)
            
            # End (DateTime)  
            end_text = f"{date_to_string(event.end.date())} {time_to_string(event.end.time())}"
            self.worksheet.write(current_row, self.offset_x + 1, end_text, format_datetime)
            
            # Title
            self.worksheet.write(current_row, self.offset_x + 2, event.title, format_data)
            
            # Description
            # Limit description length for better display
            description = event.description
            if len(description) > 100:
                description = description[:97] + "..."
            self.worksheet.write(current_row, self.offset_x + 3, description, format_data)
            
            # Address
            address_text = ""
            if event.address:
                address_text = f"{event.address.street}, {event.address.city}"
            self.worksheet.write(current_row, self.offset_x + 4, address_text, format_data)
            
            # Categories
            categories_text = ""
            if event.employee_event_categories:
                categories_text = ", ".join(cat.name for cat in event.employee_event_categories)
            self.worksheet.write(current_row, self.offset_x + 5, categories_text, format_data)
            
            # Participants
            participants_text = ""
            if event.participants:
                participants_text = ", ".join(p.full_name for p in event.participants)
                # Limit length for display
                if len(participants_text) > 80:
                    participant_count = len(event.participants)
                    participants_text = (QCoreApplication.translate("EmployeeEventsExcelExporter",
                                                                  "{participant_count} participants (see details)")
                                         .format(participant_count=participant_count))
            self.worksheet.write(current_row, self.offset_x + 6, participants_text, format_data)
            
            # Set row height based on content
            row_height = max(20, min(60, len(description) // 40 * 15 + 20))
            self.worksheet.set_row(current_row, row_height)
    
    def _write_summary(self):
        """Write summary information."""
        if not self.employee_events:
            return
            
        summary_start_row = self.offset_y + 4 + len(self.employee_events) + 2
        
        # Summary title
        self.worksheet.merge_range(summary_start_row, self.offset_x,
                                   summary_start_row, self.offset_x + 1,
                             QCoreApplication.translate("EmployeeEventsExcelExporter", "Summary:"),
                             self.format_header)
        
        # Event count
        self.worksheet.merge_range(summary_start_row + 1, self.offset_x,
                                   summary_start_row + 1, self.offset_x + 1,
                           QCoreApplication.translate(
                               "EmployeeEventsExcelExporter", "Total Events: {number_of_events}"
                           ).format(number_of_events=len(self.employee_events)),
                             self.format_data)
        
        # Events by category
        if any(event.employee_event_categories for event in self.employee_events):
            category_counts = {}
            for event in self.employee_events:
                if event.employee_event_categories:
                    for cat in event.employee_event_categories:
                        category_counts[cat.name] = category_counts.get(cat.name, 0) + 1
                else:
                    category_counts["No Category"] = category_counts.get("No Category", 0) + 1
            
            self.worksheet.merge_range(summary_start_row + 2, self.offset_x,
                                       summary_start_row + 2, self.offset_x + 1,
                                 QCoreApplication.translate("EmployeeEventsExcelExporter", "Events by Category:"),
                                 self.format_data)
            for idx, (cat_name, count) in enumerate(sorted(category_counts.items())):
                self.worksheet.merge_range(summary_start_row + 3 + idx, self.offset_x,
                                           summary_start_row + 3 + idx, self.offset_x + 1,
                                   f"  • {cat_name}: {count}", self.format_data)
    
    def execute(self):
        """Execute the Employee Events export."""
        self._load_employee_events()
        self._write_title()
        self._write_headers()
        self._write_events()
        self._write_summary()
        
        return len(self.employee_events)  # Return number of events exported


def integrate_employee_events_into_export(workbook: xlsxwriter.Workbook, team: schemas.Team, 
                                         plan_period: schemas.PlanPeriod, 
                                         excel_settings: schemas.ExcelExportSettings) -> int:
    """
    Convenience function to integrate Employee Events into an existing Excel export.
    
    Args:
        workbook: The xlsxwriter workbook to add the Employee Events worksheet to
        team: The team to filter events for
        plan_period: The planning period to filter events for
        excel_settings: Excel export settings for formatting
        
    Returns:
        int: Number of Employee Events that were exported
    """
    exporter = EmployeeEventsExcelExporter(workbook, team, plan_period, excel_settings)
    return exporter.execute()
