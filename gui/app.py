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
from gui.custom_widgets.splash_screen import SplashScreen, InitializationProgressCallback
from gui.app_initialization import initialize_application_with_progress
from tools import proof_only_one_instance
from tools.logging.logging_config import setup_crash_investigation_logging
from tools.screen import Screen

import faulthandler

# faulthandler.enable()


# Funktionen wurden nach gui/app_initialization.py verschoben

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
# Window icon setup - moved to app_initialization.py
safe_execute(app.setWindowIcon, "Setting window icon", 
             QIcon(os.path.join(os.path.dirname(__file__), 'resources', 'hcc-dispo_klein.png')))

# Andere Initialisierungsschritte werden jetzt durch initialize_application_with_progress() erledigt

# Splash screen with error handling and real progress tracking
try:
    splash = SplashScreen(minimum_display_time=2.0)  # Option A: 2s Minimum-Display-Time
    splash.show()
    
    # Progress-Callback erstellen für echte Fortschrittsanzeige
    progress_callback = InitializationProgressCallback(splash)
    progress_callback.update_progress("QApplication setup")  # Initial 5%
    
except Exception as e:
    logging.error(f"Splash screen error: {e}")
    splash = None
    progress_callback = None

# Note: Qt message handler is now handled by the comprehensive logging system

# Hauptinitialisierung - einheitlich mit optionalen Progress-Updates
try:
    # Einheitliche Initialisierung - mit oder ohne Progress-Callback
    if progress_callback:
        logging.info("Initializing with progress updates")
        window = initialize_application_with_progress(app, progress_callback, log_file_path)
    else:
        logging.warning("Initializing without progress updates (splash screen failed)")
        window = initialize_application_with_progress(app, None, log_file_path)
    
    # Splash-Screen mit Minimum-Display-Time beenden
    if splash:
        splash.finish_when_ready(window)  # NEU: Respektiert 2s Minimum-Display-Time
        
except Exception as e:
    logging.critical(f"Failed to initialize application: {e}")
    logging.critical(f"Stack trace:\n{traceback.format_exc()}")
    if splash:
        splash.close()
    QMessageBox.critical(None, "Startup Error", f"Failed to start application:\n{e}")
    sys.exit(1)
