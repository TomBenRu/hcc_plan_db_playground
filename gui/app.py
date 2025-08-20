import logging
import os.path
import platform
import sys
import traceback

from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication, QMessageBox

# Import the new modular logging system
from tools.logging import setup_comprehensive_logging
from tools.logging.crash_handler import safe_execute

from configuration.general_settings import general_settings_handler
from configuration.project_paths import curr_user_path_handler
from gui.custom_widgets.splash_screen import SplashScreen
from tools import proof_only_one_instance
from tools.logging.logging_config import setup_crash_investigation_logging
from tools.screen import Screen

import faulthandler

# faulthandler.enable()


def is_windows_dark_mode():
    import winreg
    try:
        # Öffne den Registry-Schlüssel
        registry = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                  r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
        # Lese den Wert von 'AppsUseLightTheme'
        apps_use_light_theme, _ = winreg.QueryValueEx(registry, 'AppsUseLightTheme')
        winreg.CloseKey(registry)

        # Wenn der Wert 1 ist, wird der Lightmode verwendet, bei 0 der Darkmode
        return apps_use_light_theme == 0
    except FileNotFoundError:
        # Falls der Registry-Schlüssel nicht gefunden wird, Lightmode als Standard
        return False

def set_dark_mode(app: QApplication):
    # Erstelle eine Darkmode-Farbpalette
    dark_palette = QPalette()

    # Allgemeine Farben
    dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))  # Hintergrundfarbe der Fenster
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)        # Textfarbe
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(35, 35, 35))    # Hintergrundfarbe von Eingabefeldern
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))  # Alternativer Hintergrund
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(53, 53, 53))  # Tooltip-Hintergrund dunkler
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)  # Tooltip-Text hell
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)              # Standard Text
    dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))  # Schaltflächen-Hintergrund
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)        # Schaltflächen-Text
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)          # Hervorhebungen

    # Highlight Farben
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))  # Ausgewählte Elemente
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)    # Text von ausgewählten Elementen

    # Setze die erstellte Darkmode-Palette
    app.setPalette(dark_palette)

def set_translator(app: QApplication):
    app.translator = QTranslator()
    if general_settings_handler.get_general_settings().language:
        locale = general_settings_handler.get_general_settings().language
    else:
        locale = QLocale.system().name()[:2]
    if app.translator.load(f'translations_{locale}', os.path.join(os.path.dirname(__file__), 'translations')):
        app.installTranslator(app.translator)

# Initialize comprehensive logging system early
if not os.path.exists(log_path := curr_user_path_handler.get_config().log_file_path):
    os.makedirs(log_path)

log_file_path = os.path.join(log_path, 'hcc-dispo.log')

logging.info("Application starting...")

app = QApplication(sys.argv)

# Set up comprehensive crash logging with app reference
app_log_file = setup_comprehensive_logging(log_file_path, app)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n')
root_logger = logging.getLogger(__name__)
root_logger.setLevel(logging.INFO)
# for handler in root_logger.handlers:
#     handler.setLevel(logging.ERROR)

# Emergency File-Handler hinzufügen
emergency_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
emergency_handler.setLevel(logging.ERROR)
emergency_handler.setFormatter(formatter)
root_logger.addHandler(emergency_handler)
logging.info("🔧 Emergency File-Handler hinzugefügt!")

logging.info("DEBUG-Logging aktiviert für Signal-Debugging")

# Crash Investigation Logging bei Bedarf aktivieren
if enable_crash_investigation := False:
    emergency_log = setup_crash_investigation_logging(log_path)
    logging.info(f"Emergency crash logging: {emergency_log}")
safe_execute(app.setWindowIcon, "Setting window icon", 
             QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png')))
safe_execute(set_translator, "Setting translator", app)

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

# Instance check with error handling
if system == "Windows":
    try:
        if not proof_only_one_instance.check():
            logging.warning("Another instance already running")
            QMessageBox.critical(None, "HCC Dispo", "hcc-dispo wird bereits ausgeführt.\n"
                                                    "Sie können nur eine Instanz des Programms öffnen.")
            sys.exit(0)
    except Exception as e:
        logging.error(f"Instance check failed: {e}")

# Splash screen with error handling
try:
    splash = SplashScreen()
    splash.show()
    safe_execute(splash.simulate_loading, "Splash screen loading")
except Exception as e:
    logging.error(f"Splash screen error: {e}")
    splash = None

safe_execute(app.setStyle, "Setting app style", 'Fusion')

# Note: Qt message handler is now handled by the comprehensive logging system

try:
    from gui.main_window import MainWindow
    Screen.set_screen_size()
    window = safe_execute(MainWindow, "Creating main window", app, Screen.screen_width, Screen.screen_height)
    safe_execute(window.restore_tabs, "Restoring tabs")
    safe_execute(window.show, "Showing main window")
    
    if splash:
        safe_execute(splash.finish, "Finishing splash", window)
        
    logging.info("Application initialized successfully")
    
except Exception as e:
    logging.critical(f"Failed to initialize main window: {e}")
    logging.critical(f"Stack trace:\n{traceback.format_exc()}")
    if splash:
        splash.close()
    QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n{e}")
    sys.exit(1)
