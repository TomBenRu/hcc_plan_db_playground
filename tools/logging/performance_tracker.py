"""
Erweiterte Performance-Tracking für Thread-kritische Operationen
Speziell für Team-Switching und Cache-Performance
"""

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from uuid import UUID

@dataclass
class PerformanceEvent:
    """Einzelnes Performance-Event"""
    timestamp: datetime
    operation: str
    duration_ms: float
    thread_name: str
    thread_id: int
    success: bool
    context: Dict
    

class PerformanceTracker:
    """Erweiterte Performance-Verfolgung für kritische Operationen"""
    
    def __init__(self, max_events: int = 1000):
        self.max_events = max_events
        self.events: deque = deque(maxlen=max_events)
        self.operation_stats: Dict = defaultdict(list)
        self.thread_performance: Dict = defaultdict(list)
        
        # Threshold für Warnungen
        self.slow_operation_threshold = 500  # ms
        self.very_slow_threshold = 2000  # ms
        
    def start_operation(self, operation_name: str, context: Dict = None) -> str:
        """Startet Performance-Tracking für eine Operation"""
        tracking_id = f"{operation_name}_{time.time()}_{threading.current_thread().ident}"
        
        # Context für spätere Analyse
        if not hasattr(self, '_active_operations'):
            self._active_operations = {}
            
        self._active_operations[tracking_id] = {
            'operation': operation_name,
            'start_time': time.time(),
            'thread_name': threading.current_thread().name,
            'thread_id': threading.current_thread().ident,
            'context': context or {}
        }
        
        logging.debug(f"[PERF] START {operation_name} (ID: {tracking_id})")
        return tracking_id
    
    def end_operation(self, tracking_id: str, success: bool = True, 
                     additional_context: Dict = None) -> PerformanceEvent:
        """Beendet Performance-Tracking"""
        if not hasattr(self, '_active_operations') or tracking_id not in self._active_operations:
            logging.warning(f"[PERF] Unknown tracking ID: {tracking_id}")
            return None
        
        op_data = self._active_operations.pop(tracking_id)
        duration_ms = (time.time() - op_data['start_time']) * 1000
        
        # Context erweitern
        context = op_data['context'].copy()
        if additional_context:
            context.update(additional_context)
        
        # Event erstellen
        event = PerformanceEvent(
            timestamp=datetime.now(),
            operation=op_data['operation'],
            duration_ms=duration_ms,
            thread_name=op_data['thread_name'],
            thread_id=op_data['thread_id'],
            success=success,
            context=context
        )
        
        # Event speichern
        self.events.append(event)
        self.operation_stats[op_data['operation']].append(duration_ms)
        self.thread_performance[op_data['thread_name']].append(duration_ms)
        
        # Performance-Analyse
        self._analyze_performance(event)
        
        logging.debug(f"[PERF] END {op_data['operation']}: {duration_ms:.1f}ms")
        return event
    
    def _analyze_performance(self, event: PerformanceEvent):
        """Analysiert Performance-Event auf Anomalien"""
        
        # Langsame Operationen
        if event.duration_ms > self.very_slow_threshold:
            logging.warning(f"[PERF] VERY SLOW: {event.operation} took {event.duration_ms:.1f}ms")
            logging.warning(f"[PERF] Thread: {event.thread_name}")
            if event.context:
                logging.warning(f"[PERF] Context: {event.context}")
                
        elif event.duration_ms > self.slow_operation_threshold:
            logging.info(f"[PERF] SLOW: {event.operation} took {event.duration_ms:.1f}ms")
        
        # Thread-Performance-Analyse
        thread_operations = self.thread_performance[event.thread_name]
        if len(thread_operations) >= 5:
            recent_avg = sum(thread_operations[-5:]) / 5
            if recent_avg > self.slow_operation_threshold:
                logging.warning(f"[PERF] Thread {event.thread_name} showing degraded performance: {recent_avg:.1f}ms avg")
        
        # Operation-spezifische Analyse  
        op_history = self.operation_stats[event.operation]
        if len(op_history) >= 10:
            avg_duration = sum(op_history) / len(op_history)
            
            # Anomalie-Detection: >150% des Durchschnitts
            if event.duration_ms > avg_duration * 1.5 and event.duration_ms > 100:
                logging.warning(f"[PERF] ANOMALY: {event.operation} took {event.duration_ms:.1f}ms (avg: {avg_duration:.1f}ms)")
    
    def get_operation_summary(self, hours: int = 24) -> Dict:
        """Erstellt Zusammenfassung der Operation-Performance"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_events = [e for e in self.events if e.timestamp >= cutoff]
        
        if not recent_events:
            return {'message': 'Keine Events im Zeitraum'}
        
        # Gruppiere nach Operationen
        by_operation = defaultdict(list)
        for event in recent_events:
            by_operation[event.operation].append(event.duration_ms)
        
        summary = {}
        for operation, durations in by_operation.items():
            summary[operation] = {
                'count': len(durations),
                'avg_ms': sum(durations) / len(durations),
                'min_ms': min(durations),
                'max_ms': max(durations),
                'slow_count': len([d for d in durations if d > self.slow_operation_threshold]),
                'very_slow_count': len([d for d in durations if d > self.very_slow_threshold])
            }
        
        return summary
    
    def get_thread_summary(self, hours: int = 24) -> Dict:
        """Erstellt Thread-Performance-Zusammenfassung"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_events = [e for e in self.events if e.timestamp >= cutoff]
        
        by_thread = defaultdict(list)
        for event in recent_events:
            by_thread[event.thread_name].append(event.duration_ms)
        
        summary = {}
        for thread_name, durations in by_thread.items():
            summary[thread_name] = {
                'operation_count': len(durations),
                'avg_duration_ms': sum(durations) / len(durations),
                'total_time_ms': sum(durations),
                'problematic_operations': len([d for d in durations if d > self.slow_operation_threshold])
            }
        
        return summary
    
    def log_performance_report(self):
        """Loggt Performance-Report"""
        logging.info("=== PERFORMANCE REPORT ===")
        
        # Operation Summary
        op_summary = self.get_operation_summary()
        logging.info("Operation Performance (24h):")
        for operation, stats in op_summary.items():
            if isinstance(stats, dict):
                logging.info(f"  {operation}: {stats['count']} calls, {stats['avg_ms']:.1f}ms avg")
                if stats['slow_count'] > 0:
                    logging.info(f"    -> {stats['slow_count']} slow operations")
        
        # Thread Summary  
        thread_summary = self.get_thread_summary()
        logging.info("Thread Performance (24h):")
        for thread_name, stats in thread_summary.items():
            if isinstance(stats, dict):
                logging.info(f"  {thread_name}: {stats['operation_count']} ops, {stats['avg_duration_ms']:.1f}ms avg")
        
        logging.info("=" * 30)


# Globale Performance-Tracker Instanz
performance_tracker = PerformanceTracker()


# Decorator für automatisches Performance-Tracking
def track_performance(operation_name: str = None):
    """Decorator für automatisches Performance-Tracking"""
    def decorator(func):
        import functools
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            # Context aus Argumenten extrahieren (wenn möglich)
            context = {}
            if args:
                # Versuche nützliche Context-Informationen zu extrahieren
                for i, arg in enumerate(args[:3]):  # Erste 3 Argumente
                    if hasattr(arg, '__class__'):
                        context[f'arg_{i}_type'] = arg.__class__.__name__
            
            tracking_id = performance_tracker.start_operation(op_name, context)
            
            try:
                result = func(*args, **kwargs)
                performance_tracker.end_operation(tracking_id, success=True)
                return result
            except Exception as e:
                additional_context = {'error': str(e), 'error_type': type(e).__name__}
                performance_tracker.end_operation(tracking_id, success=False, 
                                                 additional_context=additional_context)
                raise
        
        return wrapper
    return decorator
