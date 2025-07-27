"""
Umfassendes Logging-System für PyInstaller-Anwendungen

Dieses Paket bietet spezialisierte Module für:
- Crash-Logging und Exception-Handling 
- Thread-spezifisches Monitoring
- Windows-spezifische Crash-Handler
- System-Informationen sammeln
"""

from .crash_handler import CrashHandler
from .system_info import SystemInfoLogger
from .thread_monitor import ThreadMonitor
from .windows_handler import WindowsExceptionHandler

__all__ = [
    'CrashHandler',
    'SystemInfoLogger', 
    'ThreadMonitor',
    'WindowsExceptionHandler',
    'setup_comprehensive_logging'
]


def setup_comprehensive_logging(log_file_path: str, app_reference=None) -> str:
    """
    Hauptfunktion zum Einrichten des umfassenden Logging-Systems
    
    Args:
        log_file_path: Pfad zur Log-Datei
        app_reference: Referenz zur QApplication (optional)
        
    Returns:
        str: Pfad zur Log-Datei
    """
    # System-Info-Logger initialisieren
    system_logger = SystemInfoLogger()
    system_logger.setup_basic_logging(log_file_path)
    system_logger.log_system_info()
    
    # Crash-Handler initialisieren
    crash_handler = CrashHandler(log_file_path, app_reference)
    crash_handler.setup_exception_handlers()
    crash_handler.setup_qt_message_handler()
    crash_handler.setup_process_monitoring()
    
    # Thread-Monitor aktivieren
    thread_monitor = ThreadMonitor()
    thread_monitor.setup_thread_monitoring()
    
    # Windows-spezifische Handler (falls Windows)
    import platform
    if platform.system() == "Windows":
        windows_handler = WindowsExceptionHandler(log_file_path)
        windows_handler.setup_windows_crash_handler()
    
    import logging
    logging.info("Umfassendes Logging-System initialisiert")
    return log_file_path
