"""
Minimale Alternative zum umfassenden Logging-System
Falls du die Architektur vereinfachen möchtest
"""

import atexit
import logging
import os
import signal
import sys
import threading
import time
import traceback
from datetime import datetime
from typing import Optional

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QMessageBox


def setup_minimal_crash_logging(log_file_path: str, app_reference=None) -> str:
    """
    Minimale aber vollständige Crash-Logging-Lösung
    Kombiniert alle wichtigen Funktionen aus CrashHandler in einer Funktion
    """
    
    # === TEIL 1: BASIS-LOGGING SETUP ===
    
    # Existierende Handler entfernen falls nötig
    root_logger = logging.getLogger()
    
    # File-Handler hinzufügen falls nicht vorhanden
    has_file_handler = any(hasattr(h, 'baseFilename') for h in root_logger.handlers)
    if not has_file_handler:
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)
    
    # === TEIL 2: SYSTEM-INFO LOGGEN ===
    
    logging.info("=== MINIMAL CRASH LOGGING INITIALIZED ===")
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Platform: {sys.platform}")
    logging.info(f"Active threads: {threading.active_count()}")
    
    # === TEIL 3: EXCEPTION-HANDLER ===
    
    original_excepthook = sys.excepthook
    
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            original_excepthook(exc_type, exc_value, exc_traceback)
            return
        
        logging.critical("=== UNHANDLED EXCEPTION ===")
        logging.critical(f"Exception: {exc_type.__name__}: {exc_value}")
        logging.critical(f"Timestamp: {datetime.now().isoformat()}")
        logging.critical(f"Thread: {threading.current_thread().name}")
        logging.critical("Stack trace:")
        logging.critical(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
        logging.critical("=" * 50)
        
        # User-Dialog
        try:
            QMessageBox.critical(None, "Anwendungsfehler", 
                               f"Kritischer Fehler: {exc_type.__name__}: {exc_value}\n\n"
                               f"Details in: {log_file_path}")
        except:
            pass
    
    sys.excepthook = handle_exception
    
    # === TEIL 4: THREAD-EXCEPTION-HANDLER ===
    
    def handle_thread_exception(args):
        logging.critical("=== THREAD EXCEPTION ===")
        logging.critical(f"Thread: {args.thread.name} (ID: {args.thread.ident})")
        logging.critical(f"Exception: {args.exc_type.__name__}: {args.exc_value}")
        logging.critical("Thread trace:")
        logging.critical(''.join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback
        )))
        logging.critical("=" * 50)
    
    threading.excepthook = handle_thread_exception
    
    # === TEIL 5: QT-MESSAGE-HANDLER ===
    
    def qt_message_handler(mode, context, message):
        mode_map = {0: "DEBUG", 1: "WARNING", 2: "CRITICAL", 3: "FATAL", 4: "INFO"}
        level_name = mode_map.get(mode, "UNKNOWN")
        
        log_message = f"Qt {level_name}: {message}"
        if context.file:
            log_message += f" (File: {context.file}:{context.line})"
        
        if mode <= 1:
            logging.warning(log_message)
        elif mode == 2:
            logging.error(log_message)
        elif mode == 3:
            logging.critical(log_message)
        else:
            logging.info(log_message)
    
    qInstallMessageHandler(qt_message_handler)
    
    # === TEIL 6: EXIT-HANDLER ===
    
    def log_exit():
        logging.info("=== APPLICATION EXIT ===")
        logging.info(f"Timestamp: {datetime.now().isoformat()}")
        logging.info(f"Active threads: {threading.active_count()}")
    
    atexit.register(log_exit)
    
    # === TEIL 7: SIGNAL-HANDLER ===
    
    def signal_handler(signum, frame):
        logging.warning(f"Signal {signum} received - shutting down")
        if app_reference and hasattr(app_reference, 'quit'):
            try:
                app_reference.quit()
            except:
                pass
        sys.exit(signum)
    
    signal.signal(signal.SIGTERM, signal_handler)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)
    
    # === TEIL 8: WINDOWS-CRASH-HANDLER (VEREINFACHT) ===
    
    if sys.platform == "win32":
        try:
            import ctypes
            
            def windows_exception_filter(exception_pointers):
                logging.critical("=== WINDOWS CRITICAL EXCEPTION ===")
                logging.critical(f"Timestamp: {datetime.now().isoformat()}")
                logging.critical("Windows-level crash detected")
                return 1
            
            kernel32 = ctypes.windll.kernel32
            EXCEPTION_HANDLER = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)
            kernel32.SetUnhandledExceptionFilter(EXCEPTION_HANDLER(windows_exception_filter))
            
        except Exception as e:
            logging.warning(f"Windows crash handler setup failed: {e}")
    
    logging.info("Minimal crash logging setup complete")
    return log_file_path


# === SAFE-EXECUTE FUNKTION ===

def safe_execute(func, error_context="Operation", *args, **kwargs):
    """Vereinfachte safe_execute ohne Import-Dependencies"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Error in {error_context}: {type(e).__name__}: {e}")
        logging.error(f"Stack trace:\n{traceback.format_exc()}")
        raise
