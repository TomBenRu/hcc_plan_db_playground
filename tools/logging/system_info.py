"""
System-Informationen für Crash-Debugging

Sammelt und loggt detaillierte System-Informationen für bessere Fehleranalyse
"""

import logging
import os
import platform
import sys
import threading
import time
from datetime import datetime


class SystemInfoLogger:
    """Sammelt und loggt System-Informationen für Debugging-Zwecke"""
    
    def __init__(self):
        self.logged_initial_info = False
    
    def setup_basic_logging(self, log_file_path: str):
        """Konfiguriert die Basis-Logging-Einstellungen"""
        
        # PROBLEM: logging.basicConfig() wird ignoriert wenn bereits Handler existieren
        # LÖSUNG: Explizit File-Handler hinzufügen
        
        root_logger = logging.getLogger()
        
        # Prüfe ob bereits File-Handler existiert
        has_file_handler = any(
            hasattr(handler, 'baseFilename') 
            for handler in root_logger.handlers
        )
        
        if not has_file_handler:
            # File-Handler explizit hinzufügen
            file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n'
            )
            file_handler.setFormatter(formatter)
            
            root_logger.addHandler(file_handler)
            
            # Sicherstellen dass Root-Logger DEBUG-Level hat
            if root_logger.level > logging.DEBUG:
                root_logger.setLevel(logging.DEBUG)
            
            logging.info(f"File-Handler hinzugefügt: {log_file_path}")
        
        # Zeit-Converter setzen
        logging.Formatter.converter = time.gmtime
    
    def log_system_info(self):
        """Loggt detaillierte System-Informationen für Debugging-Kontext"""
        if self.logged_initial_info:
            return
            
        logging.info("=== SYSTEM INFORMATION ===")
        
        # Python und Platform Info
        logging.info(f"Python version: {sys.version}")
        logging.info(f"Python executable: {sys.executable}")
        logging.info(f"Platform: {platform.platform()}")
        logging.info(f"Architecture: {platform.architecture()}")
        logging.info(f"Processor: {platform.processor()}")
        logging.info(f"Machine: {platform.machine()}")
        
        # PySide6/Qt Info
        try:
            pyside_version = getattr(sys.modules.get('PySide6', None), '__version__', 'Unknown')
            logging.info(f"PySide6 version: {pyside_version}")
        except:
            logging.info("PySide6 version: Not available")
        
        # Threading-Informationen
        logging.info(f"Threading support: {threading.active_count()} active threads")
        main_thread = threading.main_thread()
        logging.info(f"Main thread: {main_thread.name} (alive: {main_thread.is_alive()})")
        
        # Memory-Informationen (wenn verfügbar)
        self._log_memory_info()
        
        # Environment-Informationen
        self._log_environment_info()
        
        # PyInstaller-spezifische Informationen
        self._log_pyinstaller_info()
        
        logging.info("=" * 50)
        self.logged_initial_info = True
    
    def log_current_thread_state(self):
        """Loggt den aktuellen Zustand aller Threads"""
        logging.info("=== CURRENT THREAD STATE ===")
        logging.info(f"Timestamp: {datetime.now().isoformat()}")
        logging.info(f"Total active threads: {threading.active_count()}")
        
        try:
            for thread in threading.enumerate():
                status = "alive" if thread.is_alive() else "dead"
                logging.info(f"  - {thread.name}: {status} (daemon: {thread.daemon}, ident: {thread.ident})")
        except Exception as e:
            logging.error(f"Error enumerating threads: {e}")
        
        logging.info("=" * 30)
    
    def _log_memory_info(self):
        """Loggt Memory-Informationen wenn psutil verfügbar ist"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            
            logging.info(f"Memory RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
            logging.info(f"Memory VMS: {memory_info.vms / 1024 / 1024:.1f} MB")
            
            # CPU-Info
            logging.info(f"CPU percent: {process.cpu_percent()}%")
            logging.info(f"CPU count: {psutil.cpu_count()}")
            
        except ImportError:
            logging.info("Memory info: psutil not available")
        except Exception as e:
            logging.info(f"Memory info error: {e}")
    
    def _log_environment_info(self):
        """Loggt relevante Environment-Variablen"""
        relevant_env_vars = [
            'PATH', 'PYTHONPATH', 'TEMP', 'TMP', 
            'USERPROFILE', 'USERNAME', 'COMPUTERNAME'
        ]
        
        logging.info("Environment variables:")
        for var in relevant_env_vars:
            value = os.environ.get(var, 'Not set')
            # PATH kann sehr lang sein, kürzen
            if var == 'PATH' and len(value) > 200:
                value = value[:200] + "... (truncated)"
            logging.info(f"  {var}: {value}")
    
    def _log_pyinstaller_info(self):
        """Loggt PyInstaller-spezifische Informationen"""
        # Check if running in PyInstaller bundle
        if hasattr(sys, '_MEIPASS'):
            logging.info("Running in PyInstaller bundle")
            logging.info(f"Bundle dir: {sys._MEIPASS}")
            logging.info(f"Executable: {sys.executable}")
        else:
            logging.info("Running in development mode")
        
        # Check if frozen
        if getattr(sys, 'frozen', False):
            logging.info("Application is frozen (compiled)")
        else:
            logging.info("Application is not frozen (development)")
    
    def log_crash_context(self, context_info: str = ""):
        """Loggt Kontext-Informationen bei einem Crash"""
        logging.critical("=== CRASH CONTEXT ===")
        logging.critical(f"Timestamp: {datetime.now().isoformat()}")
        logging.critical(f"Process ID: {os.getpid()}")
        
        if context_info:
            logging.critical(f"Context: {context_info}")
        
        # Aktuelle Thread-Informationen
        self.log_current_thread_state()
        
        # Last chance memory info
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            logging.critical(f"Memory at crash: {memory_info.rss / 1024 / 1024:.1f} MB")
        except:
            pass
        
        logging.critical("=" * 30)
