"""
Performance-Monitoring für Tab-Cache System
Überwacht und protokolliert Cache-Performance-Metriken
"""

import logging
from tools.logging.debug_helpers import debug_thread_safe, CriticalSectionLogger, log_thread_safety_warning
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class TeamSwitchMetric:
    """Metrik für einen Team-Wechsel"""
    team_id: UUID
    team_name: str
    start_time: datetime
    end_time: datetime
    duration_ms: float
    cache_hit: bool
    tab_count: int
    error: Optional[str] = None
    
    @property
    def duration_seconds(self) -> float:
        return self.duration_ms / 1000.0
    
    @property
    def performance_category(self) -> str:
        """Kategorisiert Performance"""
        if self.duration_ms < 200:
            return "excellent"
        elif self.duration_ms < 500:
            return "good"
        elif self.duration_ms < 1000:
            return "acceptable"
        else:
            return "slow"


@dataclass
class CacheMetricsSnapshot:
    """Snapshot der Cache-Metriken zu einem Zeitpunkt"""
    timestamp: datetime
    cache_enabled: bool
    cached_teams: int
    total_cached_tabs: int
    hits: int
    misses: int
    hit_rate: float
    invalidations: int
    evictions: int


class PerformanceMonitor:
    """
    Überwacht und analysiert Tab-Cache Performance
    
    Features:
    - Team-Wechsel Performance-Tracking
    - Cache-Metriken Sammlung
    - Performance-Trends Analyse
    - Automatische Anomalie-Erkennung
    """
    
    def __init__(self, max_metrics: int = 1000):
        self.max_metrics = max_metrics
        self.team_switch_metrics: List[TeamSwitchMetric] = []
        self.cache_snapshots: List[CacheMetricsSnapshot] = []
        
        # Aktuelle Team-Wechsel (für Timing)
        self._active_switches: Dict[UUID, float] = {}
    
    def start_team_switch(self, team_id: UUID, team_name: str) -> None:
        """Startet Performance-Messung für Team-Wechsel"""
        self._active_switches[team_id] = time.time()
        logger.debug(f"Team-Wechsel Performance-Messung gestartet: {team_name}")
    
    def end_team_switch(self, team_id: UUID, team_name: str, cache_hit: bool, 
                       tab_count: int, error: Optional[str] = None) -> TeamSwitchMetric:
        """
        Beendet Performance-Messung für Team-Wechsel
        
        Returns:
            TeamSwitchMetric: Gesammelte Performance-Daten
        """
        if team_id not in self._active_switches:
            logger.warning(f"Team-Wechsel-Timing nicht gestartet für {team_name}")
            start_time = time.time()
        else:
            start_time = self._active_switches.pop(team_id)
        
        end_time = time.time()
        duration_ms = (end_time - start_time) * 1000
        
        metric = TeamSwitchMetric(
            team_id=team_id,
            team_name=team_name,
            start_time=datetime.fromtimestamp(start_time),
            end_time=datetime.fromtimestamp(end_time),
            duration_ms=duration_ms,
            cache_hit=cache_hit,
            tab_count=tab_count,
            error=error
        )
        
        # Metrik speichern
        self.team_switch_metrics.append(metric)
        self._cleanup_old_metrics()
        
        # Performance-Logging
        perf_emoji = self._get_performance_emoji(metric)
        cache_status = "Cache Hit" if cache_hit else "Cache Miss"
        
        # Anomalie-Erkennung
        self._check_for_anomalies(metric)
        
        return metric
    
    def capture_cache_snapshot(self, cache_stats: Dict) -> CacheMetricsSnapshot:
        """Erstellt Snapshot der aktuellen Cache-Metriken"""
        try:
            snapshot = CacheMetricsSnapshot(
                timestamp=datetime.now(),
                cache_enabled=cache_stats.get('cache_enabled', False),
                cached_teams=cache_stats.get('cached_teams', 0),
                total_cached_tabs=cache_stats.get('total_cached_tabs', 0),
                hits=cache_stats.get('statistics', {}).get('hits', 0),
                misses=cache_stats.get('statistics', {}).get('misses', 0),
                hit_rate=cache_stats.get('statistics', {}).get('hit_rate_percent', 0.0),
                invalidations=cache_stats.get('statistics', {}).get('invalidations', 0),
                evictions=cache_stats.get('statistics', {}).get('evictions', 0)
            )
            
            self.cache_snapshots.append(snapshot)
            self._cleanup_old_snapshots()
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Fehler beim Cache-Snapshot: {e}")
            return None
    
    def get_performance_summary(self, hours: int = 24) -> Dict:
        """
        Erstellt Performance-Zusammenfassung für die letzten X Stunden
        
        Args:
            hours: Zeitraum für Analyse
            
        Returns:
            Dict mit Performance-Statistiken
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Relevante Team-Wechsel filtern
        recent_switches = [
            m for m in self.team_switch_metrics 
            if m.start_time >= cutoff_time
        ]
        
        if not recent_switches:
            return {
                'period_hours': hours,
                'total_switches': 0,
                'message': 'Keine Team-Wechsel im Zeitraum'
            }
        
        # Statistiken berechnen
        cache_hits = [m for m in recent_switches if m.cache_hit]
        cache_misses = [m for m in recent_switches if not m.cache_hit]
        
        hit_durations = [m.duration_ms for m in cache_hits] if cache_hits else [0]
        miss_durations = [m.duration_ms for m in cache_misses] if cache_misses else [0]
        
        # Performance-Kategorien
        categories = {}
        for category in ["excellent", "good", "acceptable", "slow"]:
            count = len([m for m in recent_switches if m.performance_category == category])
            categories[category] = {
                'count': count,
                'percentage': (count / len(recent_switches)) * 100 if recent_switches else 0
            }
        
        # Häufigste Teams
        team_counts = {}
        for switch in recent_switches:
            team_counts[switch.team_name] = team_counts.get(switch.team_name, 0) + 1
        
        most_used_teams = sorted(team_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        summary = {
            'period_hours': hours,
            'total_switches': len(recent_switches),
            'cache_statistics': {
                'hits': len(cache_hits),
                'misses': len(cache_misses),
                'hit_rate_percent': (len(cache_hits) / len(recent_switches)) * 100 if recent_switches else 0
            },
            'performance_statistics': {
                'avg_duration_ms': sum(m.duration_ms for m in recent_switches) / len(recent_switches),
                'avg_cache_hit_ms': sum(hit_durations) / len(hit_durations),
                'avg_cache_miss_ms': sum(miss_durations) / len(miss_durations),
                'min_duration_ms': min(m.duration_ms for m in recent_switches),
                'max_duration_ms': max(m.duration_ms for m in recent_switches)
            },
            'performance_categories': categories,
            'most_used_teams': most_used_teams,
            'errors': len([m for m in recent_switches if m.error])
        }
        
        return summary
    
    def get_performance_trends(self, hours: int = 168) -> Dict:
        """Analysiert Performance-Trends über Zeit"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        recent_switches = [
            m for m in self.team_switch_metrics 
            if m.start_time >= cutoff_time
        ]
        
        if len(recent_switches) < 10:
            return {'message': 'Nicht genügend Daten für Trend-Analyse'}
        
        # Aufteilen in Zeitbereiche (12 Stunden-Blöcke)
        time_blocks = []
        current_time = cutoff_time
        block_hours = 12
        
        while current_time < datetime.now():
            block_end = current_time + timedelta(hours=block_hours)
            block_switches = [
                m for m in recent_switches 
                if current_time <= m.start_time < block_end
            ]
            
            if block_switches:
                avg_duration = sum(m.duration_ms for m in block_switches) / len(block_switches)
                hit_rate = (len([m for m in block_switches if m.cache_hit]) / len(block_switches)) * 100
                
                time_blocks.append({
                    'start_time': current_time.isoformat(),
                    'end_time': block_end.isoformat(),
                    'switch_count': len(block_switches),
                    'avg_duration_ms': avg_duration,
                    'cache_hit_rate': hit_rate
                })
            
            current_time = block_end
        
        # Trend-Analyse
        if len(time_blocks) >= 2:
            recent_avg = sum(block['avg_duration_ms'] for block in time_blocks[-3:]) / min(3, len(time_blocks))
            earlier_avg = sum(block['avg_duration_ms'] for block in time_blocks[:3]) / min(3, len(time_blocks))
            
            trend = "improving" if recent_avg < earlier_avg else "degrading" if recent_avg > earlier_avg else "stable"
            trend_percentage = abs((recent_avg - earlier_avg) / earlier_avg) * 100 if earlier_avg > 0 else 0
        else:
            trend = "insufficient_data"
            trend_percentage = 0
        
        return {
            'period_hours': hours,
            'time_blocks': time_blocks,
            'trend': trend,
            'trend_percentage': trend_percentage,
            'recommendation': self._get_performance_recommendation(trend, trend_percentage)
        }
    
    def _get_performance_emoji(self, metric: TeamSwitchMetric) -> str:
        """Gibt Performance-Emoji basierend auf Dauer zurück"""
        if metric.error:
            return "❌"
        elif metric.duration_ms < 200:
            return "⚡"
        elif metric.duration_ms < 500:
            return "🟢"
        elif metric.duration_ms < 1000:
            return "🟡"
        else:
            return "🔴"
    
    def _check_for_anomalies(self, metric: TeamSwitchMetric):
        """Prüft auf Performance-Anomalien"""
        if len(self.team_switch_metrics) < 10:
            return
        
        # Durchschnittliche Performance der letzten 10 Wechsel
        recent_metrics = self.team_switch_metrics[-10:]
        avg_duration = sum(m.duration_ms for m in recent_metrics) / len(recent_metrics)
        
        # Anomalie wenn >2x langsamer als Durchschnitt
        if metric.duration_ms > avg_duration * 2 and metric.duration_ms > 1000:
            logger.warning(f"Performance-Anomalie erkannt: {metric.team_name} ({metric.duration_ms:.1f}ms vs avg {avg_duration:.1f}ms)")
        
        # Cache-Hit Rate Anomalie
        cache_hits_recent = len([m for m in recent_metrics if m.cache_hit])
        expected_hit_rate = cache_hits_recent / len(recent_metrics)
        
        if not metric.cache_hit and expected_hit_rate > 0.7:
            logger.warning(f"Unerwarteter Cache-Miss: {metric.team_name} (Hit-Rate normalerweise {expected_hit_rate:.1%})")
    
    def _get_performance_recommendation(self, trend: str, trend_percentage: float) -> str:
        """Gibt Performance-Empfehlungen basierend auf Trends"""
        if trend == "degrading" and trend_percentage > 20:
            return "Performance verschlechtert sich. Cache-Konfiguration prüfen oder Cache leeren."
        elif trend == "improving":
            return "Performance verbessert sich. Cache arbeitet optimal."
        elif trend == "stable":
            return "Performance ist stabil. Keine Aktion erforderlich."
        else:
            return "Nicht genügend Daten für Empfehlung."
    
    def _cleanup_old_metrics(self):
        """Entfernt alte Metriken um Memory zu begrenzen"""
        if len(self.team_switch_metrics) > self.max_metrics:
            # Älteste Metriken entfernen
            excess = len(self.team_switch_metrics) - self.max_metrics
            self.team_switch_metrics = self.team_switch_metrics[excess:]
    
    def _cleanup_old_snapshots(self):
        """Entfernt alte Cache-Snapshots"""
        if len(self.cache_snapshots) > self.max_metrics:
            excess = len(self.cache_snapshots) - self.max_metrics
            self.cache_snapshots = self.cache_snapshots[excess:]
    
    def export_metrics_csv(self, filepath: str, hours: int = 24) -> bool:
        """Exportiert Performance-Metriken als CSV"""
        try:
            import csv
            from datetime import datetime, timedelta
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_switches = [
                m for m in self.team_switch_metrics 
                if m.start_time >= cutoff_time
            ]
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'timestamp', 'team_name', 'duration_ms', 'cache_hit', 
                    'tab_count', 'performance_category', 'error'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for metric in recent_switches:
                    writer.writerow({
                        'timestamp': metric.start_time.isoformat(),
                        'team_name': metric.team_name,
                        'duration_ms': metric.duration_ms,
                        'cache_hit': metric.cache_hit,
                        'tab_count': metric.tab_count,
                        'performance_category': metric.performance_category,
                        'error': metric.error or ''
                    })

            return True
            
        except Exception as e:
            logger.error(f"Fehler beim CSV-Export: {e}")
            return False


# Globale Performance-Monitor Instanz
performance_monitor = PerformanceMonitor()
