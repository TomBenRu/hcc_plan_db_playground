"""
Emergency File-Logging Setup
Garantiert File-Logging auch wenn das komplexe System fehlschlägt
"""

import logging
import os
from datetime import datetime


def setup_emergency_file_logging(log_dir: str, app_name: str = "hcc-dispo") -> str:
    """
    Setzt garantiertes File-Logging auf - funktioniert IMMER
    
    Args:
        log_dir: Verzeichnis für Log-Dateien
        app_name: Name der Anwendung für Log-Datei
        
    Returns:
        str: Pfad zur erstellten Log-Datei
    """
    
    # Verzeichnis erstellen falls nicht vorhanden
    os.makedirs(log_dir, exist_ok=True)
    
    # Log-Datei mit Timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"{app_name}_{timestamp}.log")
    
    # Alle existierenden Handler entfernen
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)
    
    # Garantierter File-Handler
    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # Console-Handler (für sichtbare Ausgabe)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    # Handler hinzufügen
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    root_logger.setLevel(logging.DEBUG)
    
    # Test-Nachrichten
    logging.info(f"Emergency File-Logging aktiviert: {log_file}")
    logging.debug("DEBUG-Level aktiv")
    logging.warning("File-Logging funktioniert!")
    
    return log_file


def add_emergency_file_handler(existing_log_file: str = None) -> str:
    """
    Fügt zusätzlichen File-Handler zum bestehenden Setup hinzu
    Für den Fall dass das komplexe System Console-Handler hat aber keine File-Handler
    """
    
    if existing_log_file and os.path.exists(os.path.dirname(existing_log_file)):
        log_file = existing_log_file
    else:
        # Fallback im aktuellen Verzeichnis
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"emergency_debug_{timestamp}.log"
    
    # Prüfe ob bereits File-Handler existiert
    root_logger = logging.getLogger()
    has_file_handler = any(
        hasattr(handler, 'baseFilename') 
        for handler in root_logger.handlers
    )
    
    if not has_file_handler:
        # File-Handler hinzufügen
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d\n%(message)s\n'
        )
        file_handler.setFormatter(formatter)
        
        root_logger.addHandler(file_handler)
        
        logging.info(f"🔧 Emergency File-Handler hinzugefügt: {os.path.abspath(log_file)}")
        logging.debug("File-Logging ist jetzt aktiv!")
        
        return log_file
    else:
        logging.info("File-Handler bereits vorhanden")
        return "already_exists"


def test_file_logging():
    """Testet ob File-Logging wirklich funktioniert"""
    
    # Test-Nachrichten mit verschiedenen Levels
    test_messages = [
        (logging.DEBUG, "TEST DEBUG: File-Logging funktioniert"),
        (logging.INFO, "TEST INFO: Signal-Debugging aktiv"),
        (logging.WARNING, "TEST WARNING: Performance-Monitoring"),
        (logging.ERROR, "TEST ERROR: Exception-Handling")
    ]
    
    for level, message in test_messages:
        logging.log(level, message)
    
    # Prüfe File-Handler
    root_logger = logging.getLogger()
    file_handlers = [
        handler for handler in root_logger.handlers 
        if hasattr(handler, 'baseFilename')
    ]
    
    if file_handlers:
        for handler in file_handlers:
            log_file = handler.baseFilename
            try:
                # Force flush
                handler.flush()
                
                # Prüfe File-Inhalt
                with open(log_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "TEST DEBUG" in content or "TEST INFO" in content:
                        logging.info(f"✅ File-Logging verified: {log_file}")
                        return log_file
                    else:
                        logging.warning(f"⚠️ File existiert aber Tests nicht gefunden: {log_file}")
            except Exception as e:
                logging.error(f"❌ File-Logging Test fehlgeschlagen: {e}")
    
    return None
