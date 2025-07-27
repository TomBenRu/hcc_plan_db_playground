"""
Thread-spezifisches Monitoring und Exception-Handling

Überwacht Thread-Exceptions und Race-Conditions, die besonders bei PyInstaller-Builds
zu stummen Abstürzen führen können
"""

import logging
import threading
import time
import traceback
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from .system_info import SystemInfoLogger


class ThreadMonitor:
    """Überwacht Thread-Verhalten und fängt Thread-Exceptions ab"""
    
    def __init__(self, max_thread_history: int = 100):
        self.max_thread_history = max_thread_history
        self.system_logger = SystemInfoLogger()
        
        # Thread-Tracking
        self.thread_history: deque = deque(maxlen=max_thread_history)
        self.thread_exceptions: List[Dict] = []
        self.suspicious_threads: Set[int] = set()
        
        # Performance-Tracking
        self.thread_start_times: Dict[int, float] = {}
        self.thread_performance_issues: List[Dict] = []
        
        # Race-Condition-Detection
        self.resource_access_log: defaultdict = defaultdict(list)
        
    def setup_thread_monitoring(self):
        """Richtet umfassendes Thread-Monitoring ein"""
        
        def handle_thread_exception(args):
            """Handler für unbehandelte Thread-Exceptions"""
            self._log_thread_exception(args)
            self._analyze_thread_exception(args)
            self._check_for_race_conditions(args)
        
        # Thread exception handler registrieren
        threading.excepthook = handle_thread_exception
        
        # Periodisches Thread-Monitoring starten
        self._start_periodic_monitoring()
        
        logging.info("Thread-Exception-Monitoring aktiviert")
    
    def _log_thread_exception(self, args):
        """Loggt detaillierte Thread-Exception-Informationen"""
        thread_info = {
            'timestamp': datetime.now(),
            'thread_name': args.thread.name,
            'thread_id': args.thread.ident,
            'exception_type': args.exc_type.__name__,
            'exception_value': str(args.exc_value),
            'is_daemon': args.thread.daemon,
            'is_alive': args.thread.is_alive()
        }
        
        self.thread_exceptions.append(thread_info)
        self.suspicious_threads.add(args.thread.ident)
        
        logging.critical("=== THREAD EXCEPTION ===")
        logging.critical(f"Thread: {args.thread.name} (ID: {args.thread.ident})")
        logging.critical(f"Exception type: {args.exc_type.__name__}")
        logging.critical(f"Exception value: {args.exc_value}")
        logging.critical(f"Timestamp: {datetime.now().isoformat()}")
        logging.critical(f"Thread daemon: {args.thread.daemon}")
        logging.critical(f"Thread alive: {args.thread.is_alive()}")
        
        # Thread-Performance-Analyse
        thread_id = args.thread.ident
        if thread_id in self.thread_start_times:
            runtime = time.time() - self.thread_start_times[thread_id]
            logging.critical(f"Thread runtime: {runtime:.2f} seconds")
            
            if runtime > 300:  # > 5 Minuten
                logging.warning(f"Long-running thread detected: {args.thread.name} ({runtime:.1f}s)")
        
        # Alle aktiven Threads loggen
        self.system_logger.log_current_thread_state()
        
        logging.critical("Thread stack trace:")
        logging.critical(''.join(traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback
        )))
        
        # Thread-spezifische Cleanup-Versuche
        self._attempt_thread_cleanup(args.thread)
        
        logging.critical("=" * 50)
    
    def _analyze_thread_exception(self, args):
        """Analysiert Thread-Exception auf häufige Probleme"""
        exc_type = args.exc_type
        exc_value = str(args.exc_value)
        thread_name = args.thread.name
        
        # Häufige Thread-Safety-Probleme erkennen
        thread_safety_indicators = [
            ('RuntimeError', 'dictionary changed size during iteration'),
            ('RuntimeError', 'Set changed size during iteration'),
            ('AttributeError', 'NoneType'),
            ('ValueError', 'I/O operation on closed file'),
            ('ConnectionError', 'Connection aborted'),
            ('OSError', 'handle is closed'),
        ]
        
        for error_type, error_pattern in thread_safety_indicators:
            if exc_type.__name__ == error_type and error_pattern.lower() in exc_value.lower():
                logging.warning(f"THREAD-SAFETY PROBLEM DETECTED: {error_type} - {error_pattern}")
                logging.warning(f"Thread: {thread_name}")
                logging.warning("This may indicate race conditions or shared resource conflicts")
                break
        
        # Qt-spezifische Thread-Probleme
        if 'qt' in thread_name.lower() or 'pyside' in exc_value.lower():
            logging.warning("QT THREAD ISSUE DETECTED")
            logging.warning("Qt objects may have been accessed from wrong thread")
            
        # Daemon-Thread-Probleme
        if not args.thread.daemon and 'shutdown' in exc_value.lower():
            logging.warning("NON-DAEMON THREAD SHUTDOWN ISSUE")
            logging.warning("Thread may be blocking application shutdown")
    
    def _check_for_race_conditions(self, args):
        """Prüft auf mögliche Race-Conditions"""
        # Überprüfe zeitnahe Thread-Aktivitäten
        current_time = time.time()
        recent_threads = [
            info for info in self.thread_history 
            if current_time - info['timestamp'] < 5.0  # Letzte 5 Sekunden
        ]
        
        if len(recent_threads) > 5:
            logging.warning("HIGH THREAD ACTIVITY DETECTED")
            logging.warning(f"{len(recent_threads)} threads active in last 5 seconds")
            logging.warning("Possible race condition scenario")
            
            # Thread-Namen analysieren
            thread_names = [info['name'] for info in recent_threads]
            name_counts = {}
            for name in thread_names:
                name_counts[name] = name_counts.get(name, 0) + 1
            
            for name, count in name_counts.items():
                if count > 1:
                    logging.warning(f"Multiple instances of thread type: {name} ({count})")
    
    def _attempt_thread_cleanup(self, thread):
        """Versucht Thread-Cleanup bei Problemen"""
        try:
            if not thread.daemon and thread.is_alive():
                logging.warning(f"Non-daemon thread {thread.name} has exception - may block shutdown")
                
                # Warnung loggen aber nicht forcieren - könnte zu mehr Problemen führen
                logging.warning("Consider reviewing thread lifecycle management")
                
        except Exception as e:
            logging.error(f"Error during thread cleanup attempt: {e}")
    
    def _start_periodic_monitoring(self):
        """Startet periodisches Thread-Monitoring"""
        
        def monitor_threads():
            """Überwacht Threads periodisch"""
            while True:
                try:
                    current_time = time.time()
                    
                    # Aktuelle Thread-Info sammeln
                    for thread in threading.enumerate():
                        thread_info = {
                            'timestamp': current_time,
                            'name': thread.name,
                            'ident': thread.ident,
                            'daemon': thread.daemon,
                            'alive': thread.is_alive()
                        }
                        self.thread_history.append(thread_info)
                        
                        # Neue Threads tracken
                        if thread.ident not in self.thread_start_times:
                            self.thread_start_times[thread.ident] = current_time
                    
                    # Performance-Probleme erkennen
                    self._check_thread_performance()
                    
                    # Cleanup alter Daten
                    self._cleanup_old_monitoring_data()
                    
                    time.sleep(30)  # Alle 30 Sekunden prüfen
                    
                except Exception as e:
                    logging.error(f"Error in thread monitoring: {e}")
                    time.sleep(60)  # Bei Fehlern länger warten
        
        # Monitoring-Thread starten
        monitor_thread = threading.Thread(
            target=monitor_threads, 
            name="ThreadMonitor", 
            daemon=True
        )
        monitor_thread.start()
        logging.info("Periodisches Thread-Monitoring gestartet")
    
    def _check_thread_performance(self):
        """Prüft auf Thread-Performance-Probleme"""
        current_time = time.time()
        
        for thread in threading.enumerate():
            thread_id = thread.ident
            if thread_id in self.thread_start_times:
                runtime = current_time - self.thread_start_times[thread_id]
                
                # Long-running non-daemon threads
                if not thread.daemon and runtime > 600:  # > 10 Minuten
                    issue = {
                        'timestamp': datetime.now(),
                        'thread_name': thread.name,
                        'thread_id': thread_id,
                        'issue': 'long_running_non_daemon',
                        'runtime': runtime
                    }
                    
                    if issue not in self.thread_performance_issues:
                        self.thread_performance_issues.append(issue)
                        logging.warning(f"Long-running non-daemon thread: {thread.name} ({runtime:.1f}s)")
    
    def _cleanup_old_monitoring_data(self):
        """Bereinigt alte Monitoring-Daten"""
        current_time = time.time()
        cutoff_time = current_time - 3600  # 1 Stunde
        
        # Alte Thread-Start-Zeiten entfernen
        dead_thread_ids = []
        for thread_id, start_time in self.thread_start_times.items():
            if start_time < cutoff_time:
                # Prüfen ob Thread noch existiert
                thread_exists = any(t.ident == thread_id for t in threading.enumerate())
                if not thread_exists:
                    dead_thread_ids.append(thread_id)
        
        for thread_id in dead_thread_ids:
            del self.thread_start_times[thread_id]
            self.suspicious_threads.discard(thread_id)
        
        # Alte Exceptions bereinigen (nur letzte 50 behalten)
        if len(self.thread_exceptions) > 50:
            self.thread_exceptions = self.thread_exceptions[-50:]
            
        # Alte Performance-Issues bereinigen
        if len(self.thread_performance_issues) > 20:
            self.thread_performance_issues = self.thread_performance_issues[-20:]
    
    def get_thread_summary(self) -> Dict:
        """Gibt Zusammenfassung der Thread-Aktivitäten zurück"""
        current_threads = list(threading.enumerate())
        
        return {
            'current_threads': len(current_threads),
            'daemon_threads': len([t for t in current_threads if t.daemon]),
            'non_daemon_threads': len([t for t in current_threads if not t.daemon]),
            'total_exceptions': len(self.thread_exceptions),
            'suspicious_threads': len(self.suspicious_threads),
            'performance_issues': len(self.thread_performance_issues),
            'recent_exceptions': len([
                exc for exc in self.thread_exceptions 
                if (datetime.now() - exc['timestamp']).total_seconds() < 3600
            ])
        }
    
    def log_thread_summary(self):
        """Loggt Thread-Zusammenfassung"""
        summary = self.get_thread_summary()
        
        logging.info("=== THREAD SUMMARY ===")
        logging.info(f"Current threads: {summary['current_threads']}")
        logging.info(f"  - Daemon: {summary['daemon_threads']}")
        logging.info(f"  - Non-daemon: {summary['non_daemon_threads']}")
        logging.info(f"Total exceptions: {summary['total_exceptions']}")
        logging.info(f"Recent exceptions (1h): {summary['recent_exceptions']}")
        logging.info(f"Suspicious threads: {summary['suspicious_threads']}")
        logging.info(f"Performance issues: {summary['performance_issues']}")
        logging.info("=" * 30)
