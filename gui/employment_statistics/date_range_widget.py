"""
Date Range Widget für Employment Statistics

Widget zur Auswahl von Zeiträumen und Kontext (Team/Projekt) für die Statistiken.
"""

import datetime
from typing import Optional, Tuple, List
from uuid import UUID

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QDateEdit, QComboBox, QRadioButton, QButtonGroup, QPushButton,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QFont

from database.db_services import Project, Team
from employment_statistics.service import EmploymentStatisticsService


class DateRangeWidget(QWidget):
    """Widget für Zeitraum- und Kontext-Auswahl"""
    
    # Signal wird emittiert wenn sich die Auswahl ändert
    selection_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_id: Optional[UUID] = None
        self.available_teams: List[Tuple[UUID, str]] = []
        
        self.setup_ui()
        self.connect_signals()
        self.load_projects()

    def setup_ui(self):
        """Erstellt die Benutzeroberfläche"""
        layout = QVBoxLayout(self)
        
        # Projekt-Auswahl
        self.create_project_selection(layout)
        
        # Kontext-Auswahl (Team vs. Projekt)
        self.create_context_selection(layout)
        
        # Zeitraum-Auswahl
        self.create_date_selection(layout)
        
        # Action-Buttons
        self.create_action_buttons(layout)

        layout.addStretch()

    def create_project_selection(self, layout: QVBoxLayout):
        """Erstellt die Projekt-Auswahl"""
        project_group = QGroupBox("Projekt")
        project_layout = QVBoxLayout(project_group)
        
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(300)
        project_layout.addWidget(self.project_combo)
        
        layout.addWidget(project_group)

    def create_context_selection(self, layout: QVBoxLayout):
        """Erstellt die Kontext-Auswahl (Team vs. Projekt)"""
        context_group = QGroupBox("Statistik-Bereich")
        context_layout = QVBoxLayout(context_group)
        
        # Radio-Buttons für Team vs. Projekt
        self.context_button_group = QButtonGroup()
        
        self.project_radio = QRadioButton("Gesamtes Projekt")
        self.team_radio = QRadioButton("Einzelnes Team")
        
        self.context_button_group.addButton(self.project_radio, 0)
        self.context_button_group.addButton(self.team_radio, 1)
        
        # Standard: Projekt-weit
        self.project_radio.setChecked(True)
        
        context_layout.addWidget(self.project_radio)
        context_layout.addWidget(self.team_radio)
        
        # Team-Auswahl (initial deaktiviert)
        team_layout = QHBoxLayout()
        team_label = QLabel("Team:")
        self.team_combo = QComboBox()
        self.team_combo.setEnabled(False)
        self.team_combo.setMinimumWidth(250)
        
        team_layout.addWidget(team_label)
        team_layout.addWidget(self.team_combo)
        team_layout.addStretch()
        
        context_layout.addLayout(team_layout)
        layout.addWidget(context_group)

    def create_date_selection(self, layout: QVBoxLayout):
        """Erstellt die Datumsauswahl"""
        date_group = QGroupBox("Zeitraum")
        date_layout = QVBoxLayout(date_group)
        
        # Datum-Zeile
        date_row = QHBoxLayout()
        
        # Start-Datum
        start_label = QLabel("Von:")
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-6))
        
        # End-Datum
        end_label = QLabel("Bis:")
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        
        date_row.addWidget(start_label)
        date_row.addWidget(self.start_date)
        date_row.addSpacing(20)
        date_row.addWidget(end_label)
        date_row.addWidget(self.end_date)
        date_row.addStretch()
        
        date_layout.addLayout(date_row)
        
        # Quick-Selection Buttons
        quick_layout = QHBoxLayout()
        
        self.btn_last_month = QPushButton("Letzter Monat")
        self.btn_last_quarter = QPushButton("Letztes Quartal")
        self.btn_last_year = QPushButton("Letztes Jahr")
        self.btn_current_year = QPushButton("Aktuelles Jahr")
        
        quick_layout.addWidget(self.btn_last_month)
        quick_layout.addWidget(self.btn_last_quarter)
        quick_layout.addWidget(self.btn_last_year)
        quick_layout.addWidget(self.btn_current_year)
        quick_layout.addStretch()
        
        date_layout.addLayout(quick_layout)
        
        # Info-Label für verfügbaren Datumsbereich
        self.date_info_label = QLabel()
        self.date_info_label.setStyleSheet("color: rgba(0, 150, 50, 0.5); font-style: italic;")
        date_layout.addWidget(self.date_info_label)
        
        layout.addWidget(date_group)

    def create_action_buttons(self, layout: QVBoxLayout):
        """Erstellt die Action-Buttons"""
        button_layout = QHBoxLayout()
        
        self.btn_update_range = QPushButton("Verfügbaren Zeitraum aktualisieren")
        
        button_layout.addWidget(self.btn_update_range)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)

    def connect_signals(self):
        """Verbindet die Signale"""
        self.project_combo.currentIndexChanged.connect(self.on_project_changed)
        self.context_button_group.buttonToggled.connect(self.on_context_changed)
        self.team_combo.currentIndexChanged.connect(self.on_team_changed)
        
        self.start_date.dateChanged.connect(lambda: self.selection_changed.emit())
        self.end_date.dateChanged.connect(lambda: self.selection_changed.emit())
        
        # Quick-Selection Buttons
        self.btn_last_month.clicked.connect(self.set_last_month)
        self.btn_last_quarter.clicked.connect(self.set_last_quarter)
        self.btn_last_year.clicked.connect(self.set_last_year)
        self.btn_current_year.clicked.connect(self.set_current_year)
        
        self.btn_update_range.clicked.connect(self.update_available_date_range)

    def load_projects(self):
        """Lädt verfügbare Projekte"""
        try:
            projects = Project.get_all()
            
            self.project_combo.clear()
            self.project_combo.addItem("-- Projekt wählen --", None)
            
            for project in projects:
                self.project_combo.addItem(project.name, project.id)
                
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Laden der Projekte: {str(e)}")

    def on_project_changed(self):
        """Wird aufgerufen wenn sich das Projekt ändert"""
        project_id = self.project_combo.currentData()
        
        if project_id:
            self.current_project_id = project_id
            self.load_teams()
            self.update_available_date_range()
        else:
            self.current_project_id = None
            self.team_combo.clear()
            self.date_info_label.setText("")
            
        self.selection_changed.emit()

    def load_teams(self):
        """Lädt Teams für das aktuelle Projekt"""
        if not self.current_project_id:
            return
            
        try:
            self.available_teams = EmploymentStatisticsService.get_available_teams_for_project(
                self.current_project_id
            )
            
            self.team_combo.clear()
            self.team_combo.addItem("-- Team wählen --", None)
            
            for team_id, team_name in self.available_teams:
                self.team_combo.addItem(team_name, team_id)
                
        except Exception as e:
            QMessageBox.warning(self, "Fehler", f"Fehler beim Laden der Teams: {str(e)}")

    def on_context_changed(self, button, checked):
        """Wird aufgerufen wenn sich der Kontext ändert"""
        if checked:
            if button == self.team_radio:
                self.team_combo.setEnabled(True)
            else:
                self.team_combo.setEnabled(False)
                
            self.update_available_date_range()
            self.selection_changed.emit()

    def on_team_changed(self):
        """Wird aufgerufen wenn sich das Team ändert"""
        if self.team_radio.isChecked():
            self.update_available_date_range()
            self.selection_changed.emit()

    def update_available_date_range(self):
        """Aktualisiert den verfügbaren Datumsbereich"""
        if not self.current_project_id:
            self.date_info_label.setText("")
            return
            
        try:
            if self.team_radio.isChecked():
                team_id = self.team_combo.currentData()
                if not team_id:
                    self.date_info_label.setText("")
                    return
                min_date, max_date = EmploymentStatisticsService.get_date_range_for_context(
                    team_id=team_id
                )
            else:
                min_date, max_date = EmploymentStatisticsService.get_date_range_for_context(
                    project_id=self.current_project_id
                )
            
            if min_date and max_date:
                self.date_info_label.setText(
                    f"Verfügbarer Zeitraum: {min_date.strftime('%d.%m.%Y')} - {max_date.strftime('%d.%m.%Y')}"
                )
                
                # Setze Date-Edit Bereiche
                self.start_date.setDateRange(QDate(min_date), QDate(max_date))
                self.end_date.setDateRange(QDate(min_date), QDate(max_date))
            else:
                self.date_info_label.setText("Keine Planungsdaten verfügbar")
                
        except Exception as e:
            self.date_info_label.setText(f"Fehler: {str(e)}")

    def set_last_month(self):
        """Setzt Zeitraum auf letzten Monat"""
        today = datetime.date.today()
        first_this_month = today.replace(day=1)
        last_month_end = first_this_month - datetime.timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        self.start_date.setDate(QDate(last_month_start))
        self.end_date.setDate(QDate(last_month_end))

    def set_last_quarter(self):
        """Setzt Zeitraum auf letztes Quartal"""
        today = datetime.date.today()
        current_quarter = (today.month - 1) // 3 + 1
        
        if current_quarter == 1:
            # Q4 des Vorjahres
            start = datetime.date(today.year - 1, 10, 1)
            end = datetime.date(today.year - 1, 12, 31)
        else:
            # Vorheriges Quartal im aktuellen Jahr
            prev_quarter = current_quarter - 1
            start_month = (prev_quarter - 1) * 3 + 1
            end_month = prev_quarter * 3
            
            start = datetime.date(today.year, start_month, 1)
            
            # Letzter Tag des Quartals
            if end_month == 12:
                end = datetime.date(today.year, 12, 31)
            else:
                next_month_first = datetime.date(today.year, end_month + 1, 1)
                end = next_month_first - datetime.timedelta(days=1)
        
        self.start_date.setDate(QDate(start))
        self.end_date.setDate(QDate(end))

    def set_last_year(self):
        """Setzt Zeitraum auf letztes Jahr"""
        today = datetime.date.today()
        last_year = today.year - 1
        
        start = datetime.date(last_year, 1, 1)
        end = datetime.date(last_year, 12, 31)
        
        self.start_date.setDate(QDate(start))
        self.end_date.setDate(QDate(end))

    def set_current_year(self):
        """Setzt Zeitraum auf aktuelles Jahr"""
        today = datetime.date.today()
        
        start = datetime.date(today.year, 1, 1)
        end = today
        
        self.start_date.setDate(QDate(start))
        self.end_date.setDate(QDate(end))

    def get_selection(self) -> Tuple[Optional[datetime.date], Optional[datetime.date], 
                                   Optional[UUID], Optional[UUID]]:
        """
        Gibt die aktuelle Auswahl zurück
        
        Returns:
            Tuple[start_date, end_date, team_id, project_id]
        """
        if not self.current_project_id:
            return None, None, None, None
            
        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()
        
        if self.team_radio.isChecked():
            team_id = self.team_combo.currentData()
            return start_date, end_date, team_id, None
        else:
            return start_date, end_date, None, self.current_project_id

    def is_valid_selection(self) -> bool:
        """Prüft ob die aktuelle Auswahl gültig ist"""
        start_date, end_date, team_id, project_id = self.get_selection()
        
        if not (team_id or project_id):
            return False
            
        if not start_date or not end_date:
            return False
            
        if start_date > end_date:
            return False
            
        if self.team_radio.isChecked() and not team_id:
            return False
            
        return True

    def get_selection_description(self) -> str:
        """Gibt eine Beschreibung der aktuellen Auswahl zurück"""
        if not self.is_valid_selection():
            return "Ungültige Auswahl"
            
        start_date, end_date, team_id, project_id = self.get_selection()
        
        context = ""
        if team_id:
            team_name = next((name for tid, name in self.available_teams if tid == team_id), "Unbekannt")
            context = f"Team: {team_name}"
        elif project_id:
            project_name = self.project_combo.currentText()
            context = f"Projekt: {project_name}"
            
        date_range = f"{start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
        
        return f"{context}, Zeitraum: {date_range}"
