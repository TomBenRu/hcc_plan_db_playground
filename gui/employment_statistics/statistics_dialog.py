"""
Employment Statistics Dialog

Hauptdialog für die Darstellung der Einsatzstatistiken mit verschiedenen Ansichten.
"""

import datetime
import tempfile
import webbrowser
import os
import logging
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton, QTextEdit, QFileDialog,
    QSplitter, QGroupBox, QProgressBar, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

from employment_statistics.service import EmploymentStatisticsService, EmploymentStatistics
from employment_statistics.dashboard.service import DashboardService
from employment_statistics.utils import (
    format_statistics_summary, get_top_employees, get_top_locations,
    calculate_distribution_percentages, group_employees_by_assignment_range,
    calculate_workload_balance, export_statistics_to_dict
)
from .date_range_widget import DateRangeWidget

# Logging für Dashboard-Debug aktivieren
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class StatisticsWorker(QThread):
    """Worker-Thread für die Berechnung der Statistiken"""
    
    statistics_ready = Signal(object)  # EmploymentStatistics
    error_occurred = Signal(str)
    
    def __init__(self, start_date, end_date, team_id, project_id):
        super().__init__()
        self.start_date = start_date
        self.end_date = end_date
        self.team_id = team_id
        self.project_id = project_id

    def run(self):
        """Führt die Statistik-Berechnung im Hintergrund aus"""
        try:
            statistics = EmploymentStatisticsService.get_employment_statistics(
                start_date=self.start_date,
                end_date=self.end_date,
                team_id=self.team_id,
                project_id=self.project_id
            )
            self.statistics_ready.emit(statistics)
        except Exception as e:
            self.error_occurred.emit(str(e))


class EmploymentStatisticsDialog(QDialog):
    """Hauptdialog für Employment Statistics"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_statistics: Optional[EmploymentStatistics] = None
        self.statistics_worker: Optional[StatisticsWorker] = None
        
        self.setup_ui()
        self.connect_signals()
        
        # Auto-Update wenn sich Auswahl ändert (mit Verzögerung)
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.load_statistics)

    def setup_ui(self):
        """Erstellt die Benutzeroberfläche"""
        self.setWindowTitle("Einsatzstatistik")
        self.setModal(True)
        self.resize(1200, 800)
        
        # Hauptlayout
        layout = QVBoxLayout(self)
        
        # Titel
        title_label = QLabel("Einsatzstatistik")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFixedHeight(40)  # Feste Höhe für den Titel
        layout.addWidget(title_label)
        
        # Splitter für Auswahl und Statistiken
        splitter = QSplitter(Qt.Horizontal)
        
        # Linke Seite: Auswahl-Widget
        self.date_range_widget = DateRangeWidget()
        self.date_range_widget.setMinimumWidth(350)  # Minimale Breite statt maximale
        splitter.addWidget(self.date_range_widget)
        
        # Rechte Seite: Statistik-Anzeige
        self.create_statistics_view(splitter)
        
        splitter.setStretchFactor(0, 0)  # Linke Seite: nicht dehnbar
        splitter.setStretchFactor(1, 1)  # Rechte Seite: dehnbar
        
        # Setze initiale Größenverhältnisse (etwa 30% links, 70% rechts)
        splitter.setSizes([350, 850])
        
        layout.addWidget(splitter, 1)  # Stretch-Faktor 1 für den Splitter
        
        # Button-Leiste
        self.create_button_bar(layout)
        
        # Progress Bar (initial versteckt)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def create_statistics_view(self, parent):
        """Erstellt die Statistik-Anzeige"""
        # Container für Statistiken
        stats_container = QWidget()
        stats_layout = QVBoxLayout(stats_container)
        
        # Info-Label für aktuelle Auswahl
        self.selection_info_label = QLabel("Bitte wählen Sie einen Zeitraum und Kontext aus.")
        self.selection_info_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 150, 50, 0.3);
                border: 1px solid rgba(0, 150, 50, 0.5);
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
        """)
        stats_layout.addWidget(self.selection_info_label)
        
        # Tab-Widget für verschiedene Statistik-Ansichten
        self.stats_tabs = QTabWidget()
        
        # Übersicht-Tab
        self.create_overview_tab()
        
        # Mitarbeiter-Tab
        self.create_employees_tab()
        
        # Standorte-Tab
        self.create_locations_tab()
        
        # Planperioden-Tab
        self.create_periods_tab()
        
        stats_layout.addWidget(self.stats_tabs)
        
        # Initial alle Tabs deaktivieren
        self.stats_tabs.setEnabled(False)
        
        parent.addWidget(stats_container)

    def create_overview_tab(self):
        """Erstellt den Übersicht-Tab"""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        
        # Scroll-Area für den gesamten Inhalt
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Zusammenfassung
        summary_group = QGroupBox("Zusammenfassung")
        summary_layout = QVBoxLayout(summary_group)
        
        self.summary_text = QTextEdit()
        self.summary_text.setMaximumHeight(150)
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)
        
        scroll_layout.addWidget(summary_group)
        
        # Workload Balance
        balance_group = QGroupBox("Arbeitsverteilung")
        balance_layout = QVBoxLayout(balance_group)
        
        self.balance_info_label = QLabel()
        balance_layout.addWidget(self.balance_info_label)
        
        scroll_layout.addWidget(balance_group)
        
        # Top Listen nebeneinander
        top_lists_layout = QHBoxLayout()
        
        # Top Mitarbeiter
        top_employees_group = QGroupBox("Top 10 Mitarbeiter")
        top_employees_layout = QVBoxLayout(top_employees_group)
        
        self.top_employees_table = QTableWidget()
        self.top_employees_table.setColumnCount(2)
        self.top_employees_table.setHorizontalHeaderLabels(["Mitarbeiter", "Einsätze"])
        self.top_employees_table.horizontalHeader().setStretchLastSection(True)
        self.top_employees_table.setMaximumHeight(300)
        top_employees_layout.addWidget(self.top_employees_table)
        
        top_lists_layout.addWidget(top_employees_group)
        
        # Top Standorte
        top_locations_group = QGroupBox("Top 10 Standorte")
        top_locations_layout = QVBoxLayout(top_locations_group)
        
        self.top_locations_table = QTableWidget()
        self.top_locations_table.setColumnCount(3)
        self.top_locations_table.setHorizontalHeaderLabels(["Standort", "Einsätze", "Mitarbeiter"])
        self.top_locations_table.horizontalHeader().setStretchLastSection(True)
        self.top_locations_table.setMaximumHeight(300)
        top_locations_layout.addWidget(self.top_locations_table)
        
        top_lists_layout.addWidget(top_locations_group)
        
        scroll_layout.addLayout(top_lists_layout)
        
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        
        self.stats_tabs.addTab(overview_widget, "Übersicht")

    def create_employees_tab(self):
        """Erstellt den Mitarbeiter-Tab"""
        employees_widget = QWidget()
        layout = QVBoxLayout(employees_widget)
        
        # Info-Label
        info_label = QLabel("Detaillierte Einsatzstatistiken pro Mitarbeiter")
        info_label.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(info_label)
        
        # Mitarbeiter-Tabelle
        self.employees_table = QTableWidget()
        self.employees_table.setColumnCount(4)
        self.employees_table.setHorizontalHeaderLabels([
            "Mitarbeiter", "Einsätze", "Häufigste Standorte", "Aktive Perioden"
        ])
        
        # Spaltenbreiten
        header = self.employees_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 200)  # Name
        header.resizeSection(1, 100)  # Einsätze
        header.resizeSection(2, 300)  # Standorte
        
        layout.addWidget(self.employees_table)
        
        self.stats_tabs.addTab(employees_widget, "Mitarbeiter")

    def create_locations_tab(self):
        """Erstellt den Standorte-Tab"""
        locations_widget = QWidget()
        layout = QVBoxLayout(locations_widget)
        
        # Info-Label
        info_label = QLabel("Einsatzstatistiken pro Standort")
        info_label.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(info_label)
        
        # Standorte-Tabelle
        self.locations_table = QTableWidget()
        self.locations_table.setColumnCount(4)
        self.locations_table.setHorizontalHeaderLabels([
            "Standort", "Einsätze", "Mitarbeiter", "Ø Einsätze/Mitarbeiter"
        ])
        
        # Spaltenbreiten
        header = self.locations_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 250)  # Name
        header.resizeSection(1, 100)  # Einsätze
        header.resizeSection(2, 100)  # Mitarbeiter
        
        layout.addWidget(self.locations_table)
        
        self.stats_tabs.addTab(locations_widget, "Standorte")

    def create_periods_tab(self):
        """Erstellt den Planperioden-Tab"""
        periods_widget = QWidget()
        layout = QVBoxLayout(periods_widget)
        
        # Info-Label
        info_label = QLabel("Einsatzstatistiken pro Planperiode")
        info_label.setStyleSheet("font-weight: bold; color: #666;")
        layout.addWidget(info_label)
        
        # Perioden-Tabelle
        self.periods_table = QTableWidget()
        self.periods_table.setColumnCount(5)
        self.periods_table.setHorizontalHeaderLabels([
            "Planperiode", "Zeitraum", "Einsätze", "Mitarbeiter", "Standorte"
        ])
        
        # Spaltenbreiten
        header = self.periods_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.resizeSection(0, 200)  # Name
        header.resizeSection(1, 200)  # Zeitraum
        header.resizeSection(2, 100)  # Einsätze
        header.resizeSection(3, 100)  # Mitarbeiter
        
        layout.addWidget(self.periods_table)
        
        self.stats_tabs.addTab(periods_widget, "Planperioden")

    def create_button_bar(self, layout):
        """Erstellt die Button-Leiste"""
        button_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("Aktualisieren")
        self.btn_refresh.setEnabled(False)
        
        self.btn_dashboard = QPushButton("🎭 Dashboard")
        self.btn_dashboard.setEnabled(False)
        self.btn_dashboard.setToolTip("Öffnet interaktives Dashboard im Browser")
        self.btn_save_dashboard = QPushButton("💾 Dashboard speichern")
        self.btn_save_dashboard.setEnabled(False)
        self.btn_save_dashboard.setToolTip("Speichert das Dashboard als HTML-Datei")
        
        self.btn_export = QPushButton("Exportieren...")
        self.btn_export.setEnabled(False)
        
        self.btn_close = QPushButton("Schließen")
        
        button_layout.addWidget(self.btn_refresh)
        button_layout.addWidget(self.btn_dashboard)
        button_layout.addWidget(self.btn_save_dashboard)
        button_layout.addWidget(self.btn_export)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_close)
        
        layout.addLayout(button_layout)

    def connect_signals(self):
        """Verbindet die Signale"""
        self.date_range_widget.selection_changed.connect(self.on_selection_changed)
        
        self.btn_refresh.clicked.connect(self.load_statistics)
        self.btn_dashboard.clicked.connect(self.open_dashboard)
        self.btn_save_dashboard.clicked.connect(self.save_dashboard)
        self.btn_export.clicked.connect(self.export_statistics)
        self.btn_close.clicked.connect(self.close)

    def on_selection_changed(self):
        """Wird aufgerufen wenn sich die Auswahl ändert"""
        # Update Info-Label
        if self.date_range_widget.is_valid_selection():
            description = self.date_range_widget.get_selection_description()
            self.selection_info_label.setText(f"Gewählter Bereich: {description}")
            self.btn_refresh.setEnabled(True)
            self.btn_dashboard.setEnabled(True)
            self.btn_save_dashboard.setEnabled(True)
            self.btn_export.setEnabled(True)
            
            # Auto-Update mit Verzögerung starten
            self.update_timer.start(1000)  # 1 Sekunde Verzögerung
        else:
            self.selection_info_label.setText("Bitte wählen Sie einen gültigen Zeitraum und Kontext aus.")
            self.btn_refresh.setEnabled(False)
            self.stats_tabs.setEnabled(False)
            self.btn_dashboard.setEnabled(False)
            self.btn_save_dashboard.setEnabled(False)
            self.btn_export.setEnabled(False)

    def load_statistics(self):
        """Lädt die Statistiken"""
        if not self.date_range_widget.is_valid_selection():
            return
            
        # Parameter holen
        start_date, end_date, team_id, project_id = self.date_range_widget.get_selection()
        
        # Progress anzeigen
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.btn_refresh.setEnabled(False)
        
        # Worker-Thread starten
        self.statistics_worker = StatisticsWorker(start_date, end_date, team_id, project_id)
        self.statistics_worker.statistics_ready.connect(self.on_statistics_ready)
        self.statistics_worker.error_occurred.connect(self.on_statistics_error)
        self.statistics_worker.start()

    def on_statistics_ready(self, statistics: EmploymentStatistics):
        """Wird aufgerufen wenn die Statistiken berechnet wurden"""
        self.current_statistics = statistics
        
        # Progress verstecken
        self.progress_bar.setVisible(False)
        self.btn_refresh.setEnabled(True)
        self.btn_dashboard.setEnabled(True)
        self.btn_save_dashboard.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.stats_tabs.setEnabled(True)
        
        # Statistiken anzeigen
        self.display_statistics()

    def on_statistics_error(self, error_message: str):
        """Wird aufgerufen wenn ein Fehler bei der Berechnung auftritt"""
        self.progress_bar.setVisible(False)
        self.btn_refresh.setEnabled(True)
        
        QMessageBox.critical(
            self, 
            "Fehler bei der Statistik-Berechnung",
            f"Die Statistiken konnten nicht berechnet werden:\n\n{error_message}"
        )

    def display_statistics(self):
        """Zeigt die berechneten Statistiken an"""
        if not self.current_statistics:
            return
            
        stats = self.current_statistics
        
        # Übersicht-Tab aktualisieren
        self.update_overview_tab(stats)
        
        # Mitarbeiter-Tab aktualisieren
        self.update_employees_tab(stats)
        
        # Standorte-Tab aktualisieren
        self.update_locations_tab(stats)
        
        # Planperioden-Tab aktualisieren
        self.update_periods_tab(stats)

    def update_overview_tab(self, stats: EmploymentStatistics):
        """Aktualisiert den Übersicht-Tab"""
        # Zusammenfassung
        summary = format_statistics_summary(stats)
        self.summary_text.setPlainText(summary)
        
        # Workload Balance
        balance = calculate_workload_balance(stats.employee_statistics)
        balance_text = f"""
Arbeitsverteilung:
• Minimum: {balance['min_assignments']} Einsätze
• Maximum: {balance['max_assignments']} Einsätze  
• Median: {balance['median_assignments']} Einsätze
• Standardabweichung: {balance['std_deviation']}
• Balance-Score: {balance['balance_score']}% (100% = perfekt ausgewogen)
"""
        self.balance_info_label.setText(balance_text.strip())
        
        # Top Mitarbeiter
        top_employees = get_top_employees(stats, 10)
        self.top_employees_table.setRowCount(len(top_employees))
        
        for row, employee in enumerate(top_employees):
            self.top_employees_table.setItem(row, 0, QTableWidgetItem(employee.person_name))
            self.top_employees_table.setItem(row, 1, QTableWidgetItem(str(employee.total_assignments)))
        
        # Top Standorte
        top_locations = get_top_locations(stats, 10)
        self.top_locations_table.setRowCount(len(top_locations))
        
        for row, location in enumerate(top_locations):
            self.top_locations_table.setItem(row, 0, QTableWidgetItem(location.location_name))
            self.top_locations_table.setItem(row, 1, QTableWidgetItem(str(location.total_assignments)))
            self.top_locations_table.setItem(row, 2, QTableWidgetItem(str(location.employees_count)))

    def update_employees_tab(self, stats: EmploymentStatistics):
        """Aktualisiert den Mitarbeiter-Tab"""
        self.employees_table.setRowCount(len(stats.employee_statistics))
        
        for row, employee in enumerate(stats.employee_statistics):
            # Name
            self.employees_table.setItem(row, 0, QTableWidgetItem(employee.person_name))
            
            # Einsätze
            self.employees_table.setItem(row, 1, QTableWidgetItem(str(employee.total_assignments)))
            
            # Häufigste Standorte (Top 3)
            top_locations = sorted(
                employee.assignments_by_location.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:]
            locations_text = ", ".join([f"{loc} ({count})" for loc, count in top_locations])
            self.employees_table.setItem(row, 2, QTableWidgetItem(locations_text))
            
            # Aktive Perioden
            periods_count = len(employee.assignments_by_period)
            self.employees_table.setItem(row, 3, QTableWidgetItem(str(periods_count)))

    def update_locations_tab(self, stats: EmploymentStatistics):
        """Aktualisiert den Standorte-Tab"""
        self.locations_table.setRowCount(len(stats.location_statistics))
        
        for row, location in enumerate(stats.location_statistics):
            # Name
            self.locations_table.setItem(row, 0, QTableWidgetItem(location.location_name))
            
            # Einsätze
            self.locations_table.setItem(row, 1, QTableWidgetItem(str(location.total_assignments)))
            
            # Mitarbeiter
            self.locations_table.setItem(row, 2, QTableWidgetItem(str(location.employees_count)))
            
            # Durchschnitt
            avg_text = f"{location.average_assignments_per_employee:.1f}"
            self.locations_table.setItem(row, 3, QTableWidgetItem(avg_text))

    def update_periods_tab(self, stats: EmploymentStatistics):
        """Aktualisiert den Planperioden-Tab"""
        self.periods_table.setRowCount(len(stats.period_statistics))
        
        for row, period in enumerate(stats.period_statistics):
            # Name
            self.periods_table.setItem(row, 0, QTableWidgetItem(period.period_name))
            
            # Zeitraum
            timespan = f"{period.period_start.strftime('%d.%m.%Y')} - {period.period_end.strftime('%d.%m.%Y')}"
            self.periods_table.setItem(row, 1, QTableWidgetItem(timespan))
            
            # Einsätze
            self.periods_table.setItem(row, 2, QTableWidgetItem(str(period.total_assignments)))
            
            # Mitarbeiter
            self.periods_table.setItem(row, 3, QTableWidgetItem(str(period.employees_count)))
            
            # Standorte
            self.periods_table.setItem(row, 4, QTableWidgetItem(str(period.locations_count)))

    def export_statistics(self):
        """Exportiert die Statistiken"""
        if not self.current_statistics:
            return
            
        # Hier könntest du einen Datei-Dialog implementieren
        # Für jetzt zeigen wir die Daten als JSON in einem Dialog
        
        export_data = export_statistics_to_dict(self.current_statistics)
        
        # Simple Text-Ausgabe für Demo
        export_dialog = QDialog(self)
        export_dialog.setWindowTitle("Export-Daten")
        export_dialog.setModal(True)
        export_dialog.resize(600, 400)
        
        layout = QVBoxLayout(export_dialog)
        
        text_edit = QTextEdit()
        text_edit.setPlainText(str(export_data))
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        button_layout = QHBoxLayout()
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(export_dialog.close)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        export_dialog.exec_()

    def render_dashboard(self) -> str:
        """Rendert das Dashboard"""
        # Parameter holen
        start_date, end_date, team_id, project_id = self.date_range_widget.get_selection()

        # Dashboard-Daten laden - BEIDE Modi für Client-seitiges Umschalten
        dashboard_data_standard = DashboardService.get_dashboard_data(
            start_date=start_date,
            end_date=end_date,
            team_id=team_id,
            project_id=project_id,
            include_zero_cast_events=False
        )

        dashboard_data_with_zero_cast = DashboardService.get_dashboard_data(
            start_date=start_date,
            end_date=end_date,
            team_id=team_id,
            project_id=project_id,
            include_zero_cast_events=True
        )

        # HTML-Template laden und rendern
        template_path = os.path.join(
            os.path.dirname(__file__),
            '..', '..',
            'employment_statistics', 'dashboard', 'template.html'
        )

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except FileNotFoundError:
            QMessageBox.critical(
                self,
                "Template nicht gefunden",
                f"Dashboard-Template nicht gefunden:\n{template_path}"
            )
            return

        # Jinja2-Template rendern
        from jinja2 import Template
        template = Template(template_content)

        # Template-Variablen - Standard-Daten (besetzte Termine) + Alternative (alle Termine)
        template_vars = {
            # Standard Dashboard-Daten (nur besetzte Termine)
            'aktive_clowns': dashboard_data_standard.aktive_clowns,
            'einrichtungen_count': dashboard_data_standard.einrichtungen_count,
            'total_geplante_mitarbeiter': dashboard_data_standard.total_geplante_mitarbeiter,
            'total_durchgefuehrte_mitarbeiter': dashboard_data_standard.total_durchgefuehrte_mitarbeiter,
            'mitarbeiter_erfuellung': dashboard_data_standard.mitarbeiter_erfuellung,
            'total_geplante_termine': dashboard_data_standard.total_geplante_termine,
            'total_durchgefuehrte_termine': dashboard_data_standard.total_durchgefuehrte_termine,
            'termine_erfuellung': dashboard_data_standard.termine_erfuellung,
            'einrichtungen': [e.dict() for e in dashboard_data_standard.einrichtungen],
            'clowns': [c.dict() for c in dashboard_data_standard.clowns],
            'monatliche_erfuellung': [m.dict() for m in dashboard_data_standard.monatliche_erfuellung],
            'netzwerk_nodes': dashboard_data_standard.netzwerk_nodes,
            'netzwerk_links': dashboard_data_standard.netzwerk_links,

            # Alternative Dashboard-Daten (alle Termine inkl. Zero-Cast)
            'zero_cast_data': {
                'aktive_clowns': dashboard_data_with_zero_cast.aktive_clowns,
                'einrichtungen_count': dashboard_data_with_zero_cast.einrichtungen_count,
                'total_geplante_mitarbeiter': dashboard_data_with_zero_cast.total_geplante_mitarbeiter,
                'total_durchgefuehrte_mitarbeiter': dashboard_data_with_zero_cast.total_durchgefuehrte_mitarbeiter,
                'mitarbeiter_erfuellung': dashboard_data_with_zero_cast.mitarbeiter_erfuellung,
                'total_geplante_termine': dashboard_data_with_zero_cast.total_geplante_termine,
                'total_durchgefuehrte_termine': dashboard_data_with_zero_cast.total_durchgefuehrte_termine,
                'termine_erfuellung': dashboard_data_with_zero_cast.termine_erfuellung,
                'einrichtungen': [e.dict() for e in dashboard_data_with_zero_cast.einrichtungen],
                'clowns': [c.dict() for c in dashboard_data_with_zero_cast.clowns],
                'monatliche_erfuellung': [m.dict() for m in dashboard_data_with_zero_cast.monatliche_erfuellung],
                'netzwerk_nodes': dashboard_data_with_zero_cast.netzwerk_nodes,
                'netzwerk_links': dashboard_data_with_zero_cast.netzwerk_links
            },

            # Meta-Informationen (verwende Standard-Daten)
            'zeitraum_start': dashboard_data_standard.zeitraum_start,
            'zeitraum_ende': dashboard_data_standard.zeitraum_ende,
            'team_name': dashboard_data_standard.team_name,
            'project_name': dashboard_data_standard.project_name,
            'now': datetime.datetime.now()
        }

        return template.render(**template_vars)

    def open_dashboard(self):
        """Öffnet das interaktive Dashboard im Browser"""
        try:
            rendered_html = self.render_dashboard()
            # Temporäre HTML-Datei erstellen
            with tempfile.NamedTemporaryFile(
                mode='w', 
                suffix='.html', 
                delete=False, 
                encoding='utf-8'
            ) as temp_file:
                temp_file.write(rendered_html)
                temp_file_path = temp_file.name
            
            # Im Browser öffnen
            webbrowser.open(f'file://{temp_file_path}')
            
            # Nach 60 Sekunden aufräumen
            QTimer.singleShot(60000, lambda: self._cleanup_temp_file(temp_file_path))
            
        except Exception as e:
            logger.exception("Dashboard-Fehler:")
            QMessageBox.critical(
                self,
                "Dashboard-Fehler",
                f"Das Dashboard konnte nicht geöffnet werden:\n\n{str(e)}"
            )

    def save_dashboard(self):
        """Speichert das Dashboard als HTML-Datei"""
        try:
            rendered_html = self.render_dashboard()
            # Verwende den konfigurierten Excel-Output-Pfad
            from configuration.project_paths import curr_user_path_handler
            save_path = os.path.join(curr_user_path_handler.get_config().excel_output_path, 'dashboard.html')
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Dashboard speichern",
                save_path,
                "HTML-Dateien (*.html)"
            )
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(rendered_html)
                QMessageBox.information(
                    self,
                    "Dashboard gespeichert",
                    f"Das Dashboard wurde erfolgreich unter\n{file_path}\ngespeichert."
                )
        except Exception as e:
            logger.exception("Dashboard-Fehler:")
            QMessageBox.critical(
                self,
                "Dashboard-Fehler",
                f"Das Dashboard konnte nicht gespeichert werden:\n\n{str(e)}"
            )

    def _cleanup_temp_file(self, file_path: str):
        """Räumt temporäre Dateien auf"""
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception:
            pass  # Ignoriere Cleanup-Fehler

    def closeEvent(self, event):
        """Wird beim Schließen aufgerufen"""
        # Worker-Thread beenden falls aktiv
        if self.statistics_worker and self.statistics_worker.isRunning():
            self.statistics_worker.terminate()
            self.statistics_worker.wait()
            
        event.accept()
