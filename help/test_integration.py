"""
Vereinfachter Test für die HCC Plan Hilfe-Integration - Browser-Only

Einfacher Test der GUI-Integration ohne komplexe Build-Logik.

Autor: HCC Plan Development Team
Version: 2.0.0 (Vereinfacht)
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt

# Pfad zum help-Modul hinzufügen
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from help import HelpManager, HelpIntegration, init_help_system


class TestMainWindow(QMainWindow):
    """Vereinfachtes Test-Hauptfenster für Hilfe-Integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HCC Plan Hilfe-System Test (Browser-Only)")
        self.setGeometry(100, 100, 600, 400)
        
        # Zentrales Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Hilfe-System initialisieren
        self.help_manager = init_help_system()
        self.help_integration = HelpIntegration(self.help_manager)
        
        # Status anzeigen
        self.setup_status_display(layout)
        
        # Test-Buttons
        self.setup_test_buttons(layout)
        
        # Hilfe-Menü hinzufügen
        self.setup_help_menu()
        
        # F1-Shortcut für Hauptfenster
        self.help_integration.setup_f1_shortcut(self, form_name="plan")
        
    def setup_status_display(self, layout):
        """Zeigt Status des Hilfe-Systems an."""
        status = self.help_manager.get_help_status()
        
        status_label = QLabel("<h3>Hilfe-System Status:</h3>")
        layout.addWidget(status_label)
        
        status_items = [
            f"Modus: {status['mode']}",
            f"Aktuelle Sprache: {status['current_language']}",
            f"Hilfe verfügbar: {'✅' if status['help_available'] else '❌'}",
            f"Content-Verzeichnis: {'✅' if status['content_exists'] else '❌'}"
        ]
        
        for item in status_items:
            label = QLabel(item)
            layout.addWidget(label)
    
    def setup_test_buttons(self, layout):
        """Erstellt Test-Buttons für verschiedene Hilfe-Funktionen."""
        layout.addWidget(QLabel("<h3>Test-Funktionen:</h3>"))
        
        # Haupt-Hilfe Button
        btn_main_help = QPushButton("Haupt-Hilfe im Browser anzeigen")
        btn_main_help.clicked.connect(self.help_manager.show_main_help)
        layout.addWidget(btn_main_help)
        
        # Plan-Hilfe Button
        btn_plan_help = QPushButton("Plan-Formular Hilfe anzeigen")
        btn_plan_help.clicked.connect(lambda: self.help_manager.show_help_for_form("plan"))
        layout.addWidget(btn_plan_help)
        
        # Hilfe-Button Demo
        help_button = self.help_integration.create_help_button(self, form_name="plan")
        layout.addWidget(help_button)
        
        # Info
        info_label = QLabel("💡 Drücken Sie F1 für Hilfe! (Öffnet im Browser)")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("color: blue; font-weight: bold; margin: 10px;")
        layout.addWidget(info_label)
    
    def setup_help_menu(self):
        """Erstellt das Hilfe-Menü."""
        help_menu = self.help_integration.add_help_menu(self)
        
        # Toolbar mit Hilfe-Button
        toolbar = self.addToolBar("Hilfe")
        self.help_integration.add_help_toolbar_action(toolbar)


def main():
    """Haupt-Funktion für den Test."""
    app = QApplication(sys.argv)
    
    window = TestMainWindow()
    window.show()
    
    print("🚀 HCC Plan Hilfe-System Test gestartet!")
    print("💡 Verwenden Sie die Buttons oder F1 um die Hilfe zu testen")
    print("🌐 Hilfe öffnet sich im Standard-Browser")
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
