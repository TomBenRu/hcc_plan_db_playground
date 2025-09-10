# -*- coding: utf-8 -*-
"""
App-Initialisierung mit echten Progress-Updates

Extrahiert die Initialisierungslogik aus app.py in eine separate Funktion
mit Progress-Callback-Integration für den erweiterten SplashScreen.

Folgt dem KEEP IT SIMPLE Prinzip - minimale Änderungen an bestehender Architektur.
"""

import logging
import os
import platform
import sys
import time
import traceback

from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication, QMessageBox, QSplashScreen

from gui.custom_widgets.splash_screen import InitializationProgressCallback
from gui.main_window import MainWindow
from tools.logging.crash_handler import safe_execute
from tools import proof_only_one_instance
from configuration.general_settings import general_settings_handler


def is_windows_dark_mode():
    """Erkennt Windows Dark Mode über Registry"""
    import winreg
    try:
        registry = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                  r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
        apps_use_light_theme, _ = winreg.QueryValueEx(registry, 'AppsUseLightTheme')
        winreg.CloseKey(registry)
        return apps_use_light_theme == 0
    except FileNotFoundError:
        return False


def set_dark_mode(app: QApplication):
    """Erstellt und setzt Dark Mode Farbpalette"""
    dark_palette = QPalette()

    # Allgemeine Farben
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)

    # Highlight Farben
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)

    app.setPalette(dark_palette)


def set_translator(app: QApplication):
    """Setzt Qt-Translator für Internationalisierung"""
    from configuration.general_settings import general_settings_handler
    
    app.translator = QTranslator()
    if general_settings_handler.get_general_settings().language:
        locale = general_settings_handler.get_general_settings().language
    else:
        locale = QLocale.system().name()[:2]
    if app.translator.load(f'translations_{locale}', os.path.join(os.path.dirname(__file__), 'translations')):
        app.installTranslator(app.translator)


def initialize_application_with_progress(app: QApplication, progress_callback: InitializationProgressCallback = None, 
                                       log_file_path: str = "", splash_screen: QSplashScreen = None):
    """
    Führt App-Initialisierung mit optionalen Progress-Updates durch
    
    Args:
        app: QApplication-Instanz
        progress_callback: Optional - Callback für Progress-Updates an SplashScreen
        log_file_path: Pfad zur Log-Datei
        
    Returns:
        Initialisierte MainWindow-Instanz
        
    Raises:
        Exception: Bei kritischen Initialisierungsfehlern
    """
    
    def update_progress(step_name: str):
        """Helper-Funktion für optionale Progress-Updates"""
        if progress_callback:
            progress_callback.update_progress(step_name)
    
    # === Schritt 1: Logging-System setup ===
    update_progress("Logging-System setup")
    from tools.logging import setup_comprehensive_logging
    app_log_file = setup_comprehensive_logging(log_file_path, app)
    
    # === Schritt 2: Theme detection ===
    update_progress("Theme detection")
    system = platform.system()
    logging.info(f"Detected system: {system}")
    
    try:
        if system == "Windows":
            if not is_windows_dark_mode():
                safe_execute(set_dark_mode, "Setting dark mode", app)
        else:
            safe_execute(set_dark_mode, "Setting dark mode", app)
    except Exception as e:
        logging.error(f"Failed to set theme: {e}")
    
    # === Schritt 3: Translator setup ===
    update_progress("Translator setup")
    safe_execute(set_translator, "Setting translator", app)
    
    # === Schritt 4: Instance check ===
    update_progress("Instance check")
    if system == "Windows":
        try:
            if not proof_only_one_instance.check():
                logging.warning("Another instance already running")
                QMessageBox.critical(None, "HCC Dispo", "hcc-dispo wird bereits ausgeführt.\n"
                                                        "Sie können nur eine Instanz des Programms öffnen.")
                sys.exit(0)
        except Exception as e:
            logging.error(f"Instance check failed: {e}")
    
    # === Schritt 5: MainWindow creation ===
    update_progress("MainWindow creation")
    try:
        from gui.main_window import MainWindow
        from tools.screen import Screen
        
        # === Schritt 6: Screen size calculation ===
        update_progress("Screen size calculation")
        Screen.set_screen_size()

        # === Schritt 7: Window display ===
        update_progress("Window display")
        window = safe_execute(MainWindow, "Creating main window", app, Screen.screen_width, Screen.screen_height)
        safe_execute(window.show, "Showing main window")
        splash_screen.raise_()
        window.setEnabled(False)  # Window deaktivieren während Tab-Restoration
        window.tab_restoration_in_progress = True  # Schließen verhindern während Tab-Restoration

        # === Schritt 8: Tab restoration ===
        update_progress("Tab restoration")
        safe_execute(window.restore_tabs, "Restoring tabs")

        # === Schritt 9: Finalisierung ===
        update_progress("Finalisierung")
        time.sleep(1)  # Splash Screen wird noch 1 Sekunde angezeigt
        window.setEnabled(True)   # Window wieder aktivieren nach Tab-Restoration
        window.tab_restoration_in_progress = False  # Schließen wieder erlauben

        
        logging.info("Application initialized successfully")
        return window
        
    except Exception as e:
        logging.critical(f"Failed to initialize main window: {e}")
        logging.critical(f"Stack trace:\n{traceback.format_exc()}")
        raise
