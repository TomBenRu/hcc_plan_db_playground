"""
Debug-Helfer für kritische Code-Bereiche
Spezielle Logging-Funktionen für Thread-Safety und Performance-kritische Stellen
"""

import functools
import logging
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from .system_info import SystemInfoLogger
from .thread_monitor import ThreadMonitor

# Globale Instanzen
system_logger = SystemInfoLogger()
thread_monitor = ThreadMonitor()


def log_thread_context(func_name: str, extra_info: str = ""):
    """Loggt Thread-Kontext für debugging"""
    current_thread = threading.current_thread()
    logging.debug(f"[THREAD-CONTEXT] {func_name}: Thread={current_thread.name} (ID: {current_thread.ident}) {extra_info}")


def debug_thread_safe(operation_name: str):
    """Decorator für Thread-Safety-kritische Operationen"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_thread = threading.current_thread()
            start_time = time.time()
            
            # Vollständigen Funktionsname mit Modul erstellen
            module_name = func.__module__ or "unknown"
            qualified_name = f"{module_name}.{func.__qualname__}"
            
            # Pre-operation logging
            logging.debug(f"[THREAD-SAFE] START {operation_name}")
            logging.debug(f"[THREAD-SAFE] Thread: {current_thread.name} (ID: {current_thread.ident})")
            logging.debug(f"[THREAD-SAFE] Function: {qualified_name}")
            logging.debug(f"[THREAD-SAFE] Active threads: {threading.active_count()}")
            
            try:
                result = func(*args, **kwargs)
                
                # Success logging
                duration = time.time() - start_time
                logging.debug(f"[THREAD-SAFE] SUCCESS {operation_name} in {duration:.3f}s")
                
                return result
                
            except Exception as e:
                # Error logging with thread context
                duration = time.time() - start_time
                logging.error(f"[THREAD-SAFE] ERROR {operation_name} after {duration:.3f}s")
                logging.error(f"[THREAD-SAFE] Exception: {type(e).__name__}: {e}")
                logging.error(f"[THREAD-SAFE] Thread: {current_thread.name}")
                logging.error(f"[THREAD-SAFE] Function: {qualified_name}")
                
                # Log current thread state
                system_logger.log_current_thread_state()
                
                raise
                
        return wrapper
    return decorator


def debug_qt_operation(qt_object_name: str = "Unknown"):
    """Decorator für Qt-Operations die Thread-Safety-Probleme haben können"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_thread = threading.current_thread()
            
            # Vollständigen Funktionsname mit Modul erstellen
            module_name = func.__module__ or "unknown"
            qualified_name = f"{module_name}.{func.__qualname__}"
            
            # Qt Main Thread Check
            try:
                from PySide6.QtWidgets import QApplication
                app = QApplication.instance()
                is_main_thread = current_thread == threading.main_thread()
                
                if app and not is_main_thread:
                    logging.warning(f"[QT-THREAD] {qt_object_name}: Qt operation in non-main thread!")
                    logging.warning(f"[QT-THREAD] Current thread: {current_thread.name}")
                    logging.warning(f"[QT-THREAD] Function: {qualified_name}")
                    
            except ImportError:
                pass
            
            # Regular debug logging
            logging.debug(f"[QT-OP] {qt_object_name}.{func.__name__} - Thread: {current_thread.name}")
            logging.debug(f"[QT-OP] Function: {qualified_name}")
            
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"[QT-OP] ERROR in {qt_object_name}.{func.__name__}: {e}")
                logging.error(f"[QT-OP] Thread: {current_thread.name}")
                logging.error(f"[QT-OP] Function: {qualified_name}")
                raise
                
        return wrapper
    return decorator


def debug_signal_emission(signal_name: str, log_level: int = logging.INFO):
    """Decorator für Signal-Emissionen (standardmäßig INFO-Level)"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_thread = threading.current_thread()
            
            # Vollständigen Funktionsname mit Modul erstellen
            module_name = func.__module__ or "unknown"
            qualified_name = f"{module_name}.{func.__qualname__}"
            
            # Verwende INFO-Level statt DEBUG für bessere Sichtbarkeit
            logging.log(log_level, f"[SIGNAL] EMIT {signal_name}")
            logging.log(log_level, f"[SIGNAL] Thread: {current_thread.name} (ID: {current_thread.ident})")
            logging.log(log_level, f"[SIGNAL] Function: {qualified_name}")
            logging.log(log_level, f"[SIGNAL] Args: {len(args)} args, {len(kwargs)} kwargs")
            
            try:
                result = func(*args, **kwargs)
                logging.log(log_level, f"[SIGNAL] SUCCESS {signal_name}")
                return result
            except Exception as e:
                logging.error(f"[SIGNAL] ERROR {signal_name}: {e}")
                logging.error(f"[SIGNAL] Thread: {current_thread.name}")
                logging.error(f"[SIGNAL] Function: {qualified_name}")
                raise
                
        return wrapper
    return decorator


def debug_database_operation(operation_type: str):
    """Decorator für Datenbank-Operationen"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_thread = threading.current_thread()
            start_time = time.time()
            
            # Vollständigen Funktionsname mit Modul erstellen
            module_name = func.__module__ or "unknown"
            qualified_name = f"{module_name}.{func.__qualname__}"
            
            logging.debug(f"[DB] START {operation_type}")
            logging.debug(f"[DB] Thread: {current_thread.name}")
            logging.debug(f"[DB] Function: {qualified_name}")
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                if duration > 1.0:  # Langsame DB-Operation
                    logging.warning(f"[DB] SLOW {operation_type}: {duration:.3f}s")
                    logging.warning(f"[DB] Function: {qualified_name}")
                else:
                    logging.debug(f"[DB] SUCCESS {operation_type}: {duration:.3f}s")
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logging.error(f"[DB] ERROR {operation_type} after {duration:.3f}s: {e}")
                logging.error(f"[DB] Thread: {current_thread.name}")
                logging.error(f"[DB] Function: {qualified_name}")
                raise
                
        return wrapper
    return decorator


def debug_cache_operation(cache_name: str):
    """Decorator für Cache-Operationen"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_thread = threading.current_thread()
            
            # Vollständigen Funktionsname mit Modul erstellen
            module_name = func.__module__ or "unknown"
            qualified_name = f"{module_name}.{func.__qualname__}"
            
            logging.debug(f"[CACHE] {cache_name}.{func.__name__}")
            logging.debug(f"[CACHE] Thread: {current_thread.name}")
            logging.debug(f"[CACHE] Function: {qualified_name}")
            
            try:
                result = func(*args, **kwargs)
                logging.debug(f"[CACHE] SUCCESS {cache_name}.{func.__name__}")
                return result
            except Exception as e:
                logging.error(f"[CACHE] ERROR {cache_name}.{func.__name__}: {e}")
                logging.error(f"[CACHE] Function: {qualified_name}")
                system_logger.log_current_thread_state()
                raise
                
        return wrapper
    return decorator


class CriticalSectionLogger:
    """Context Manager für kritische Code-Abschnitte"""
    
    def __init__(self, section_name: str, log_performance: bool = True):
        self.section_name = section_name
        self.log_performance = log_performance
        self.start_time = None
        self.thread_name = None
        
    def __enter__(self):
        self.start_time = time.time()
        self.thread_name = threading.current_thread().name
        
        logging.debug(f"[CRITICAL] ENTER {self.section_name}")
        logging.debug(f"[CRITICAL] Thread: {self.thread_name}")
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type is None:
            # Erfolgreicher Abschluss
            if self.log_performance and duration > 0.1:
                logging.warning(f"[CRITICAL] SLOW {self.section_name}: {duration:.3f}s")
            else:
                logging.debug(f"[CRITICAL] EXIT {self.section_name}: {duration:.3f}s")
        else:
            # Exception aufgetreten
            logging.error(f"[CRITICAL] ERROR {self.section_name} after {duration:.3f}s")
            logging.error(f"[CRITICAL] Exception: {exc_type.__name__}: {exc_val}")
            logging.error(f"[CRITICAL] Thread: {self.thread_name}")
            
            # Bei kritischen Fehlern zusätzlichen Kontext loggen
            system_logger.log_current_thread_state()


def log_function_entry_exit(func: Callable) -> Callable:
    """Einfacher Decorator für Function Entry/Exit Logging"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Vollständigen Funktionsname mit Modul erstellen
        module_name = func.__module__ or "unknown"
        qualified_name = f"{module_name}.{func.__qualname__}"
        thread_name = threading.current_thread().name
        
        logging.debug(f"[ENTRY] {qualified_name} (Thread: {thread_name})")
        
        try:
            result = func(*args, **kwargs)
            logging.debug(f"[EXIT] {qualified_name}")
            return result
        except Exception as e:
            logging.debug(f"[EXIT-ERROR] {qualified_name}: {e}")
            raise
            
    return wrapper


# Convenience-Funktionen
def log_memory_usage(context: str = ""):
    """Loggt aktuelle Memory-Usage"""
    try:
        import psutil
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        logging.info(f"[MEMORY] {context}: {memory_mb:.1f} MB")
    except ImportError:
        logging.debug(f"[MEMORY] {context}: psutil nicht verfügbar")


def log_thread_safety_warning(operation: str, reason: str):
    """Loggt Thread-Safety-Warnungen"""
    current_thread = threading.current_thread()
    logging.warning(f"[THREAD-SAFETY] {operation}")
    logging.warning(f"[THREAD-SAFETY] Reason: {reason}")
    logging.warning(f"[THREAD-SAFETY] Thread: {current_thread.name} (ID: {current_thread.ident})")
    logging.warning(f"[THREAD-SAFETY] Active threads: {threading.active_count()}")
