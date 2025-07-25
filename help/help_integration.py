"""
Vereinfachte Help Integration für HCC Plan - Browser-only

Stellt einfache Funktionen zur Integration der Hilfe in die GUI bereit.

Autor: HCC Plan Development Team
Version: 2.0.0 (Vereinfacht)
"""

from PySide6.QtWidgets import QMainWindow, QWidget, QPushButton, QMenu, QToolBar
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QIcon
from typing import Optional

from .help_manager import HelpManager


class HelpIntegration:
    """Vereinfachte Hilfe-Integration für GUI-Komponenten."""
    
    def __init__(self, help_manager: HelpManager):
        """
        Initialisiert die Help Integration.
        
        Args:
            help_manager: Der Help Manager
        """
        self.help_manager = help_manager
    
    def setup_f1_shortcut(self, widget: QWidget, form_name: str = "main"):
        """
        Richtet F1-Shortcut für ein Widget ein.
        
        Args:
            widget: Das Widget
            form_name: Name des Formulars für spezifische Hilfe
        """
        def show_help():
            if form_name != "main":
                self.help_manager.show_help_for_form(form_name)
            else:
                self.help_manager.show_main_help()
        
        # F1 Shortcut
        from PySide6.QtGui import QShortcut
        shortcut = QShortcut(QKeySequence("F1"), widget)
        shortcut.activated.connect(show_help)
    
    def create_help_button(self, parent: QWidget, form_name: str = "main", 
                          text: str = "?") -> QPushButton:
        """
        Erstellt einen Hilfe-Button.
        
        Args:
            parent: Parent Widget
            form_name: Name des Formulars
            text: Button-Text
            
        Returns:
            QPushButton: Der Hilfe-Button
        """
        button = QPushButton(text, parent)
        button.setMaximumSize(30, 30)
        button.setToolTip("Hilfe anzeigen (F1)")
        
        def show_help():
            if form_name != "main":
                self.help_manager.show_help_for_form(form_name)
            else:
                self.help_manager.show_main_help()
        
        button.clicked.connect(show_help)
        return button
    
    def add_help_menu(self, main_window: QMainWindow) -> QMenu:
        """
        Fügt ein Hilfe-Menü zur Menüleiste hinzu.
        
        Args:
            main_window: Das Hauptfenster
            
        Returns:
            QMenu: Das Hilfe-Menü
        """
        menu_bar = main_window.menuBar()
        help_menu = menu_bar.addMenu("&Hilfe")
        
        # Haupt-Hilfe
        help_action = QAction("&Hilfe anzeigen", main_window)
        help_action.setShortcut(QKeySequence("F1"))
        help_action.triggered.connect(self.help_manager.show_main_help)
        help_menu.addAction(help_action)
        
        help_menu.addSeparator()
        
        # Über-Dialog (optional, kann später erweitert werden)
        about_action = QAction("&Über HCC Plan", main_window)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        return help_menu
    
    def add_help_toolbar_action(self, toolbar: QToolBar):
        """
        Fügt Hilfe-Aktion zur Toolbar hinzu.
        
        Args:
            toolbar: Die Toolbar
        """
        help_action = QAction("Hilfe", toolbar)
        help_action.setToolTip("Hilfe anzeigen (F1)")
        help_action.setShortcut(QKeySequence("F1"))
        help_action.triggered.connect(self.help_manager.show_main_help)
        
        # Icon setzen (falls verfügbar)
        try:
            help_action.setIcon(toolbar.style().standardIcon(
                toolbar.style().StandardPixmap.SP_DialogHelpButton
            ))
        except:
            pass
        
        toolbar.addAction(help_action)
    
    def _show_about(self):
        """Zeigt einen einfachen Über-Dialog."""
        from PySide6.QtWidgets import QMessageBox
        
        QMessageBox.about(
            None,
            "Über HCC Plan",
            "HCC Plan - Humor Hilft Heilen Einsatzplaner\n\n"
            "Version: 1.0.0\n"
            "Entwickelt für Humor Hilft Heilen e.V."
        )
