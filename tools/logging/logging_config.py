"""
Erweiterte Logging-Konfiguration für verschiedene Debugging-Level
"""

import logging
import os
from datetime import datetime


class DebugLevelManager:
    """Verwaltet verschiedene Debug-Level für verschiedene Bereiche"""
    
    # Debug-Level definieren
    LEVELS = {
        'MINIMAL': {
            'root': logging.WARNING,
            'thread': logging.ERROR,
            'performance': logging.WARNING,
            'qt': logging.ERROR,
            'db': logging.ERROR
        },
        'NORMAL': {
            'root': logging.INFO,
            'thread': logging.WARNING,
            'performance': logging.INFO,
            'qt': logging.WARNING,
            'db': logging.WARNING
        },
        'DEBUG': {
            'root': logging.DEBUG,
            'thread': logging.DEBUG,
            'performance': logging.DEBUG,
            'qt': logging.DEBUG,
            'db': logging.DEBUG
        },
        'THREAD_FOCUS': {
            'root': logging.INFO,
            'thread': logging.DEBUG,
            'performance': logging.DEBUG,
            'qt': logging.WARNING,
            'db': logging.WARNING
        },
        'PERFORMANCE_FOCUS': {
            'root': logging.WARNING,
            'thread': logging.WARNING,
            'performance': logging.DEBUG,
            'qt': logging.WARNING,
            'db': logging.INFO
        }
    }
    
    @classmethod
    def setup_debug_logging(cls, log_dir: str, debug_level: str = 'NORMAL'):
        """
        Richtet erweiterte Debug-Logging-Konfiguration ein
        
        Args:
            log_dir: Verzeichnis für Log-Dateien
            debug_level: DEBUG, NORMAL, MINIMAL, THREAD_FOCUS, PERFORMANCE_FOCUS
        """
        if debug_level not in cls.LEVELS:
            debug_level = 'NORMAL'
        
        levels = cls.LEVELS[debug_level]
        
        # Ensure log directory exists
        os.makedirs(log_dir, exist_ok=True)
        
        # Separate log files for different categories
        timestamp = datetime.now().strftime("%Y%m%d")
        
        # Main application log
        main_log = os.path.join(log_dir, f'hcc-dispo-{timestamp}.log')
        
        # Thread-specific log (for debugging thread issues)
        thread_log = os.path.join(log_dir, f'threads-{timestamp}.log')
        
        # Performance log
        perf_log = os.path.join(log_dir, f'performance-{timestamp}.log')
        
        # Qt-specific log
        qt_log = os.path.join(log_dir, f'qt-{timestamp}.log')
        
        # Clear existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Main application logger
        cls._setup_file_logger('', main_log, levels['root'])
        
        # Thread logger
        cls._setup_file_logger('THREAD', thread_log, levels['thread'],
                              filter_pattern='[THREAD')
        
        # Performance logger  
        cls._setup_file_logger('PERF', perf_log, levels['performance'],
                              filter_pattern='[PERF')
        
        # Qt logger
        cls._setup_file_logger('QT', qt_log, levels['qt'],
                              filter_pattern='[QT')
        
        # Console output (always show important messages)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        logging.info(f"Debug logging setup complete - Level: {debug_level}")
        logging.info(f"Log files in: {log_dir}")
        
        return {
            'main_log': main_log,
            'thread_log': thread_log,
            'performance_log': perf_log,
            'qt_log': qt_log,
            'debug_level': debug_level
        }
    
    @classmethod
    def _setup_file_logger(cls, name: str, filename: str, level: int, 
                          filter_pattern: str = None):
        """Richtet einen spezifischen File-Logger ein"""
        
        # Create handler
        handler = logging.FileHandler(filename, mode='a', encoding='utf-8')
        handler.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n'
        )
        handler.setFormatter(formatter)
        
        # Add filter if specified
        if filter_pattern:
            handler.addFilter(LogMessageFilter(filter_pattern))
        
        # Add to root logger
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(min(level, logging.DEBUG))


class LogMessageFilter:
    """Filter für Log-Messages basierend auf Pattern"""
    
    def __init__(self, pattern: str):
        self.pattern = pattern
    
    def filter(self, record):
        return self.pattern in record.getMessage()


# Convenience-Funktionen
def enable_thread_debugging(log_dir: str):
    """Aktiviert intensive Thread-Debugging"""
    return DebugLevelManager.setup_debug_logging(log_dir, 'THREAD_FOCUS')


def enable_performance_debugging(log_dir: str):
    """Aktiviert intensive Performance-Debugging"""
    return DebugLevelManager.setup_debug_logging(log_dir, 'PERFORMANCE_FOCUS')


def enable_full_debugging(log_dir: str):
    """Aktiviert vollständiges Debugging (Vorsicht: viele Logs!)"""
    return DebugLevelManager.setup_debug_logging(log_dir, 'DEBUG')


def setup_crash_investigation_logging(log_dir: str):
    """Spezielle Konfiguration für Crash-Untersuchungen"""
    levels = {
        'root': logging.DEBUG,
        'thread': logging.DEBUG,
        'performance': logging.DEBUG,
        'qt': logging.DEBUG,
        'db': logging.DEBUG
    }
    
    # Zusätzliche Emergency-Logs
    emergency_log = os.path.join(log_dir, 'crash_investigation.log')
    
    handler = logging.FileHandler(emergency_log, mode='a', encoding='utf-8')
    handler.setLevel(logging.DEBUG)
    
    # Sehr detaillierte Formatierung für Crash-Investigation
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d - PID:%(process)d - %(threadName)s - %(name)s\n'
        'LEVEL: %(levelname)s - FUNCTION: %(funcName)s:%(lineno)d\n'
        'MESSAGE: %(message)s\n'
        '=' * 80 + '\n'
    )
    handler.setFormatter(formatter)
    
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.DEBUG)
    
    logging.critical("CRASH INVESTIGATION LOGGING AKTIVIERT")
    logging.critical(f"Emergency log: {emergency_log}")
    
    return emergency_log
