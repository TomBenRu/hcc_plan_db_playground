"""
Haupt-Crash-Handler für Main-Thread-Exceptions und allgemeine Crash-Behandlung

Behandelt unbehandelte Exceptions im Main-Thread und bietet User-Dialogs
"""

import atexit
import logging
import os
import signal
import sys
import traceback
from datetime import datetime
from typing import Optional

from PySide6.QtCore import qInstallMessageHandler
from PySide6.QtWidgets import QMessageBox

from .system_info import SystemInfoLogger


class CrashHandler:
    """Haupt-Crash-Handler für Main-Thread-Exceptions"""
    
    def __init__(self, log_file_path: str, app_reference: Optional[object] = None):
        self.log_file_path = log_file_path
        self.app_reference = app_reference
        self._original_excepthook = sys.excepthook
        self.system_logger = SystemInfoLogger()
        
    def setup_exception_handlers(self):
        """Richtet umfassende Exception-Handler für den Main-Thread ein"""
        
        def handle_exception(exc_type, exc_value, exc_traceback):
            """Handler für unbehandelte Main-Thread-Exceptions"""
            if issubclass(exc_type, KeyboardInterrupt):
                self._original_excepthook(exc_type, exc_value, exc_traceback)
                return
            
            # Crash-Kontext loggen
            self.system_logger.log_crash_context("Main thread exception")
            
            logging.critical("=== UNHANDLED MAIN THREAD EXCEPTION ===")
            logging.critical(f"Exception type: {exc_type.__name__}")
            logging.critical(f"Exception value: {exc_value}")
            logging.critical(f"Timestamp: {datetime.now().isoformat()}")
            logging.critical(f"Process ID: {os.getpid()}")
            
            # Detaillierte Exception-Informationen
            self._log_exception_details(exc_type, exc_value, exc_traceback)
            
            logging.critical("Main thread stack trace:")
            logging.critical(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            logging.critical("=" * 50)
            
            # User-friendly Error Dialog
            self._show_error_dialog(exc_type, exc_value)
            
            # Emergency backup log
            self._write_emergency_log(f"Main thread exception: {exc_type.__name__}: {exc_value}")
        
        # Exception handler registrieren
        sys.excepthook = handle_exception
        logging.info("Main-Thread Exception Handler registriert")
    
    def setup_qt_message_handler(self):
        """Richtet Qt-Message-Handler für interne Qt-Fehler ein"""
        
        def qt_message_handler(mode, context, message):
            """Handler für Qt-interne Nachrichten und Fehler"""
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
                # Bei Qt Fatal auch Crash-Kontext loggen
                self.system_logger.log_crash_context(f"Qt Fatal: {message}")
            else:  # Info
                logging.info(log_message)
        
        # Qt message handler installieren
        qInstallMessageHandler(qt_message_handler)
        logging.info("Qt-Message-Handler installiert")
    
    def setup_process_monitoring(self):
        """Richtet Process-Monitoring und Signal-Handler ein"""
        
        def log_exit_status():
            """Wird beim ordnungsgemäßen Beenden aufgerufen"""
            logging.info("=== ORDNUNGSGEMÄSSER ANWENDUNGSABSCHLUSS ===")
            logging.info(f"Timestamp: {datetime.now().isoformat()}")
            self.system_logger.log_current_thread_state()
            logging.info("=" * 50)
        
        def signal_handler(signum, frame):
            """Handler für System-Signale"""
            logging.warning(f"=== SIGNAL {signum} EMPFANGEN ===")
            logging.warning(f"Timestamp: {datetime.now().isoformat()}")
            self.system_logger.log_crash_context(f"Signal {signum} received")
            
            # Graceful shutdown versuchen
            if self.app_reference and hasattr(self.app_reference, 'quit'):
                try:
                    self.app_reference.quit()
                except Exception as e:
                    logging.error(f"Error during graceful shutdown: {e}")
            
            sys.exit(signum)
        
        # Exit handler registrieren
        atexit.register(log_exit_status)
        
        # Signal handlers registrieren
        signal.signal(signal.SIGTERM, signal_handler)
        if hasattr(signal, 'SIGBREAK'):  # Windows
            signal.signal(signal.SIGBREAK, signal_handler)
        
        logging.info("Process-Monitoring und Signal-Handler eingerichtet")
    
    def _log_exception_details(self, exc_type, exc_value, exc_traceback):
        """Loggt detaillierte Exception-Informationen"""
        try:
            # Exception-Kette verfolgen
            current_exc = exc_value
            chain_depth = 0
            while current_exc and chain_depth < 10:  # Endlosschleifen vermeiden
                if hasattr(current_exc, '__cause__') and current_exc.__cause__:
                    logging.critical(f"Caused by: {type(current_exc.__cause__).__name__}: {current_exc.__cause__}")
                    current_exc = current_exc.__cause__
                elif hasattr(current_exc, '__context__') and current_exc.__context__:
                    logging.critical(f"During handling of: {type(current_exc.__context__).__name__}: {current_exc.__context__}")
                    current_exc = current_exc.__context__
                else:
                    break
                chain_depth += 1
            
            # Exception-Attribute
            if hasattr(exc_value, 'args') and exc_value.args:
                logging.critical(f"Exception args: {exc_value.args}")
            
            # Traceback-Objekt-Details
            if exc_traceback:
                tb_frame = exc_traceback.tb_frame
                logging.critical(f"Exception frame: {tb_frame.f_code.co_filename}:{tb_frame.f_lineno}")
                logging.critical(f"Function: {tb_frame.f_code.co_name}")
                
                # Lokale Variablen (vorsichtig)
                try:
                    local_vars = {k: str(v)[:100] for k, v in tb_frame.f_locals.items() 
                                 if not k.startswith('_')}
                    if local_vars:
                        logging.critical(f"Local variables: {local_vars}")
                except:
                    pass
                    
        except Exception as e:
            logging.error(f"Error logging exception details: {e}")
    
    def _show_error_dialog(self, exc_type, exc_value):
        """Zeigt user-friendly Error-Dialog"""
        try:
            QMessageBox.critical(
                None, 
                "Anwendungsfehler", 
                f"Ein kritischer Fehler ist aufgetreten:\n\n"
                f"{exc_type.__name__}: {str(exc_value)[:200]}\n\n"
                f"Details wurden in die Log-Datei geschrieben:\n{self.log_file_path}\n\n"
                f"Bitte senden Sie diese Log-Datei an den Support."
            )
        except Exception as e:
            # Fallback wenn Qt nicht verfügbar
            print(f"Critical error: {exc_type.__name__}: {exc_value}")
            print(f"Log file: {self.log_file_path}")
    
    def _write_emergency_log(self, message: str):
        """Schreibt Emergency-Log falls normales Logging fehlschlägt"""
        try:
            emergency_file = os.path.join(
                os.path.dirname(self.log_file_path), 
                'emergency_crash.log'
            )
            with open(emergency_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()}: {message}\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write("="*50 + "\n")
        except Exception as e:
            # Letzter Ausweg: stderr
            print(f"EMERGENCY: {message}", file=sys.stderr)
            print(f"Emergency log failed: {e}", file=sys.stderr)


def safe_execute(func, error_context="Operation", *args, **kwargs):
    """
    Sicher eine Funktion ausführen mit Error-Logging
    
    Args:
        func: Auszuführende Funktion
        error_context: Kontext-Beschreibung für Fehler
        *args, **kwargs: Argumente für die Funktion
        
    Returns:
        Rückgabewert der Funktion oder None bei Fehler
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logging.error(f"Fehler in {error_context}: {type(e).__name__}: {e}")
        logging.error(f"Stack trace:\n{traceback.format_exc()}")
        
        # Bei kritischen Fehlern auch System-Info loggen
        if isinstance(e, (MemoryError, RecursionError, SystemError)):
            system_logger = SystemInfoLogger()
            system_logger.log_crash_context(f"Critical error in {error_context}")
        
        raise
