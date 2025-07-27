"""
Windows-spezifische Crash-Handler

Behandelt Windows-spezifische Abstürze wie Exit-Code -1073740791 (0xC0000409)
die bei PyInstaller-Anwendungen häufig auftreten
"""

import ctypes
import ctypes.wintypes
import logging
import os
import platform
import sys
import threading
from datetime import datetime
from typing import Optional

from .system_info import SystemInfoLogger


class WindowsExceptionHandler:
    """Windows-spezifischer Exception-Handler für schwere Abstürze"""
    
    def __init__(self, log_file_path: str):
        self.log_file_path = log_file_path
        self.system_logger = SystemInfoLogger()
        self._handler_installed = False
        
        # Windows Exception Codes (häufige Abstürze)
        self.exception_codes = {
            0xC0000005: "ACCESS_VIOLATION",
            0xC0000409: "STATUS_STACK_BUFFER_OVERRUN",  # Thomas' spezifischer Fall!
            0xC000001D: "ILLEGAL_INSTRUCTION", 
            0xC0000094: "INTEGER_DIVIDE_BY_ZERO",
            0xC00000FD: "STACK_OVERFLOW",
            0xC0000096: "PRIVILEGED_INSTRUCTION",
            0xC000013A: "CTRL_C_EXIT",
            0xC0000142: "DLL_INIT_FAILED",
            0x80000003: "BREAKPOINT",
            0x80000004: "SINGLE_STEP"
        }
    
    def setup_windows_crash_handler(self):
        """Richtet Windows-spezifische Crash-Handler ein"""
        if platform.system() != "Windows":
            logging.info("Nicht auf Windows - Windows-Crash-Handler übersprungen")
            return
        
        try:
            self._install_exception_filter()
            self._setup_console_ctrl_handler()
            logging.info("Windows-Crash-Handler erfolgreich installiert")
            self._handler_installed = True
            
        except Exception as e:
            logging.error(f"Fehler beim Installieren des Windows-Crash-Handlers: {e}")
    
    def _install_exception_filter(self):
        """Installiert Windows Exception Filter für schwere Crashes"""
        
        def windows_exception_filter(exception_pointers):
            """Filter für Windows-Exceptions wie Access Violations"""
            try:
                # Exception-Record aus Pointer extrahieren
                exception_record = exception_pointers.contents.ExceptionRecord.contents
                exception_code = exception_record.ExceptionCode
                exception_address = exception_record.ExceptionAddress
                
                # Crash-Kontext loggen
                self.system_logger.log_crash_context("Windows Critical Exception")
                
                logging.critical("=== WINDOWS CRITICAL EXCEPTION ===")
                logging.critical(f"Exception Code: 0x{exception_code:08X}")
                
                # Exception-Name ermitteln
                exception_name = self.exception_codes.get(exception_code, "UNKNOWN")
                logging.critical(f"Exception Name: {exception_name}")
                logging.critical(f"Exception Address: 0x{exception_address:016X}")
                logging.critical(f"Timestamp: {datetime.now().isoformat()}")
                logging.critical(f"Process ID: {os.getpid()}")
                
                # Thread-Informationen sammeln
                self._log_critical_thread_info()
                
                # Spezifische Analyse basierend auf Exception-Code
                self._analyze_windows_exception(exception_code, exception_name)
                
                # Exception-Parameter (falls vorhanden)
                try:
                    param_count = exception_record.NumberParameters
                    if param_count > 0:
                        logging.critical(f"Exception Parameters ({param_count}):")
                        for i in range(min(param_count, 15)):  # Max 15 Parameter loggen
                            param = exception_record.ExceptionInformation[i]
                            logging.critical(f"  [{i}]: 0x{param:016X}")
                except:
                    pass
                
                logging.critical("=" * 50)
                
                # Emergency backup log
                self._write_emergency_log(f"Windows Exception 0x{exception_code:08X} ({exception_name})")
                
                # Zusätzliche Debugging-Informationen sammeln
                self._collect_crash_artifacts(exception_code)
                
            except Exception as e:
                # Fallback logging wenn der Handler selbst fehlschlägt
                self._write_emergency_log(f"Critical Windows exception handler failed: {e}")
            
            return 1  # EXCEPTION_EXECUTE_HANDLER - Exception als behandelt markieren
        
        # Exception Filter registrieren
        try:
            kernel32 = ctypes.windll.kernel32
            EXCEPTION_HANDLER = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p)
            kernel32.SetUnhandledExceptionFilter.argtypes = [EXCEPTION_HANDLER]
            kernel32.SetUnhandledExceptionFilter.restype = EXCEPTION_HANDLER
            
            self._previous_filter = kernel32.SetUnhandledExceptionFilter(
                EXCEPTION_HANDLER(windows_exception_filter)
            )
            
        except Exception as e:
            logging.error(f"Konnte Windows Exception Filter nicht registrieren: {e}")
            raise
    
    def _setup_console_ctrl_handler(self):
        """Richtet Console Control Handler für Ctrl+C, etc. ein"""
        
        def console_ctrl_handler(ctrl_type):
            """Handler für Console Control Events"""
            ctrl_types = {
                0: "CTRL_C_EVENT",
                1: "CTRL_BREAK_EVENT", 
                2: "CTRL_CLOSE_EVENT",
                5: "CTRL_LOGOFF_EVENT",
                6: "CTRL_SHUTDOWN_EVENT"
            }
            
            ctrl_name = ctrl_types.get(ctrl_type, f"UNKNOWN_{ctrl_type}")
            
            logging.warning(f"=== CONSOLE CONTROL EVENT ===")
            logging.warning(f"Control Type: {ctrl_name} ({ctrl_type})")
            logging.warning(f"Timestamp: {datetime.now().isoformat()}")
            
            self.system_logger.log_crash_context(f"Console control: {ctrl_name}")
            
            # Graceful shutdown versuchen
            if ctrl_type in [0, 1, 2]:  # CTRL_C, CTRL_BREAK, CTRL_CLOSE
                logging.warning("Attempting graceful shutdown...")
                return True  # Wir behandeln es
            
            return False  # System soll es behandeln
        
        try:
            kernel32 = ctypes.windll.kernel32
            HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_ulong)
            
            kernel32.SetConsoleCtrlHandler.argtypes = [HANDLER_ROUTINE, ctypes.c_bool]
            kernel32.SetConsoleCtrlHandler.restype = ctypes.c_bool
            
            success = kernel32.SetConsoleCtrlHandler(
                HANDLER_ROUTINE(console_ctrl_handler), True
            )
            
            if not success:
                logging.warning("Console Control Handler konnte nicht installiert werden")
                
        except Exception as e:
            logging.error(f"Fehler beim Setup des Console Control Handlers: {e}")
    
    def _log_critical_thread_info(self):
        """Loggt Thread-Informationen bei kritischen Windows-Exceptions"""
        try:
            logging.critical(f"Active threads: {threading.active_count()}")
            main_thread = threading.main_thread()
            logging.critical(f"Main thread alive: {main_thread.is_alive()}")
            
            # Detaillierte Thread-Informationen
            for thread in threading.enumerate():
                status = "alive" if thread.is_alive() else "dead"
                logging.critical(f"  - {thread.name}: {status} (daemon: {thread.daemon}, ident: {thread.ident})")
                
        except Exception as e:
            logging.critical(f"Error collecting thread info: {e}")
    
    def _analyze_windows_exception(self, exception_code: int, exception_name: str):
        """Analysiert spezifische Windows-Exceptions und gibt Hinweise"""
        
        if exception_code == 0xC0000409:  # STATUS_STACK_BUFFER_OVERRUN
            logging.critical("*** STACK BUFFER OVERRUN DETECTED ***")
            logging.critical("Dies deutet auf einen der folgenden Probleme hin:")
            logging.critical("  - Thread-Safety-Probleme (Race Conditions)")
            logging.critical("  - Speicher-Korruption durch unsichere Pointer-Operationen")
            logging.critical("  - Buffer Overflows in nativen Code-Aufrufen")
            logging.critical("  - Probleme mit PySide6/Qt Thread-Zugriff")
            logging.critical("  - Fehlerhafte ctypes/DLL-Aufrufe")
            
        elif exception_code == 0xC0000005:  # ACCESS_VIOLATION
            logging.critical("*** ACCESS VIOLATION DETECTED ***")
            logging.critical("Mögliche Ursachen:")
            logging.critical("  - Zugriff auf ungültigen Speicherbereich")
            logging.critical("  - Verwendung von bereits freigegebenen Objekten")
            logging.critical("  - Thread-unsichere Zugriffe auf Qt-Objekte")
            
        elif exception_code == 0xC00000FD:  # STACK_OVERFLOW
            logging.critical("*** STACK OVERFLOW DETECTED ***")
            logging.critical("Mögliche Ursachen:")
            logging.critical("  - Endlose Rekursion")
            logging.critical("  - Zu tiefe Thread-Verschachtelung")
            logging.critical("  - Übermäßige lokale Variablen")
            
        elif exception_code == 0xC0000142:  # DLL_INIT_FAILED
            logging.critical("*** DLL INITIALIZATION FAILED ***")
            logging.critical("Mögliche Ursachen:")
            logging.critical("  - Probleme mit PyInstaller-Bundle")
            logging.critical("  - Fehlende oder inkompatible DLLs")
            logging.critical("  - PySide6-Initialisierungsprobleme")
    
    def _collect_crash_artifacts(self, exception_code: int):
        """Sammelt zusätzliche Crash-Artifacts für Debugging"""
        try:
            # Process-Informationen
            try:
                import psutil
                process = psutil.Process(os.getpid())
                
                logging.critical("Process Information:")
                logging.critical(f"  Memory: {process.memory_info().rss / 1024 / 1024:.1f} MB")
                logging.critical(f"  CPU: {process.cpu_percent()}%")
                logging.critical(f"  Open files: {len(process.open_files())}")
                logging.critical(f"  Connections: {len(process.connections())}")
                
            except ImportError:
                pass
            except Exception as e:
                logging.critical(f"Error collecting process info: {e}")
            
            # PyInstaller-spezifische Informationen
            if hasattr(sys, '_MEIPASS'):
                logging.critical(f"PyInstaller bundle directory: {sys._MEIPASS}")
                
                # Bundle-Inhalt prüfen (bei DLL-Problemen hilfreich)
                try:
                    bundle_files = os.listdir(sys._MEIPASS)
                    dll_files = [f for f in bundle_files if f.endswith('.dll')]
                    logging.critical(f"DLL files in bundle: {len(dll_files)}")
                    if len(dll_files) < 50:  # Nur bei wenigen DLLs alle auflisten
                        logging.critical(f"DLLs: {dll_files}")
                except:
                    pass
            
            # Windows-Version
            try:
                import platform
                logging.critical(f"Windows version: {platform.win32_ver()}")
            except:
                pass
                
        except Exception as e:
            logging.critical(f"Error collecting crash artifacts: {e}")
    
    def _write_emergency_log(self, message: str):
        """Schreibt Emergency-Log falls normales Logging fehlschlägt"""
        try:
            log_dir = os.path.dirname(self.log_file_path)
            emergency_file = os.path.join(log_dir, 'windows_crash_emergency.log')
            
            with open(emergency_file, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()}: {message}\n")
                f.write(f"PID: {os.getpid()}\n")
                f.write(f"Thread Count: {threading.active_count()}\n")
                f.write("="*50 + "\n")
                
        except Exception as e:
            # Letzter Ausweg: Windows Event Log oder stderr
            try:
                print(f"WINDOWS EMERGENCY: {message}", file=sys.stderr)
                print(f"Emergency log failed: {e}", file=sys.stderr)
            except:
                pass
    
    def is_handler_installed(self) -> bool:
        """Prüft ob der Windows-Handler erfolgreich installiert wurde"""
        return self._handler_installed
    
    def get_windows_crash_stats(self) -> dict:
        """Gibt Windows-spezifische Crash-Statistiken zurück"""
        return {
            'handler_installed': self._handler_installed,
            'is_windows': platform.system() == "Windows",
            'is_pyinstaller': hasattr(sys, '_MEIPASS'),
            'is_frozen': getattr(sys, 'frozen', False),
            'known_exception_codes': len(self.exception_codes)
        }
