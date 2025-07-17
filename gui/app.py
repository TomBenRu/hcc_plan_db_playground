import logging
import os.path
import platform
import sys
import time
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication, QMessageBox

def setup_crash_logging(log_file_path):
    """Set up comprehensive crash logging with system information."""
    
    def log_system_info():
        """Log system information for debugging context."""
        logging.info("=== SYSTEM INFORMATION ===")
        logging.info(f"Python version: {sys.version}")
        logging.info(f"Platform: {platform.platform()}")
        logging.info(f"Architecture: {platform.architecture()}")
        logging.info(f"Processor: {platform.processor()}")
        logging.info(f"PySide6 version: {getattr(sys.modules.get('PySide6', None), '__version__', 'Unknown')}")
        logging.info("=" * 50)
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        """Handle uncaught exceptions with detailed logging."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logging.critical("=== UNHANDLED EXCEPTION ===")
        logging.critical(f"Exception type: {exc_type.__name__}")
        logging.critical(f"Exception value: {exc_value}")
        logging.critical(f"Timestamp: {datetime.now().isoformat()}")
        logging.critical("Stack trace:")
        logging.critical(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        logging.critical("=" * 50)
        
        # Show user-friendly error dialog
        try:
            QMessageBox.critical(None, "Application Error", 
                               f"A critical error occurred:\n{exc_type.__name__}: {exc_value}\n\n"
                               f"Details have been logged to: {log_file_path}")
        except:
            pass  # Avoid recursive errors if Qt is not available
    
    # Set up exception handler
    sys.excepthook = handle_exception
    log_system_info()

def safe_execute(func, error_context="Operation", *args, **kwargs):
    """Safely execute a function with error logging."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Error in {error_context}: {type(e).__name__}: {e}")
        logging.error(f"Stack trace:\n{traceback.format_exc()}")
        raise

from configuration.general_settings import general_settings_handler
from configuration.project_paths import curr_user_path_handler
from gui.custom_widgets.splash_screen import SplashScreen
from tools import proof_only_one_instance
from tools.screen import Screen


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

# Initialize logging early
if not os.path.exists(log_path := curr_user_path_handler.get_config().log_file_path):
    os.makedirs(log_path)

log_file_path = os.path.join(log_path, 'hcc-dispo.log')

# Enhanced logging configuration
logging.basicConfig(
    filename=log_file_path, 
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n',
    filemode='a'  # Append mode to preserve crash logs
)
logging.Formatter.converter = time.gmtime

# Set up crash logging immediately after basic logging config
setup_crash_logging(log_file_path)

logging.info("Application starting...")

app = QApplication(sys.argv)
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

def qt_message_handler(mode, context, message):
    """Handle Qt internal messages and log them."""
    mode_map = {
        0: "DEBUG",    # QtDebugMsg
        1: "WARNING",  # QtWarningMsg  
        2: "CRITICAL", # QtCriticalMsg
        3: "FATAL",    # QtFatalMsg
        4: "INFO"      # QtInfoMsg
    }
    
    level_name = mode_map.get(mode, "UNKNOWN")
    log_message = f"Qt {level_name}: {message}"
    
    if context.file:
        log_message += f" (File: {context.file}:{context.line})"
    
    if mode <= 1:  # Debug/Warning
        logging.warning(log_message)
    elif mode == 2:  # Critical
        logging.error(log_message)
    elif mode == 3:  # Fatal
        logging.critical(log_message)
    else:  # Info
        logging.info(log_message)

# Install Qt message handler after creating QApplication
from PySide6.QtCore import qInstallMessageHandler
qInstallMessageHandler(qt_message_handler)

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
