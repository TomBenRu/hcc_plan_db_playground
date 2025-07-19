"""
Tab-Cache System für hcc-plan
Intelligentes Caching von Tab-Widgets für bessere Performance beim Team-Wechsel
"""

import logging
from uuid import UUID
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


@dataclass
class CachedTab:
    """Repräsentiert einen gecachten Tab mit Metadaten"""
    widget: QWidget
    tab_text: str
    tooltip: Optional[str] = None
    cached_at: datetime = field(default_factory=datetime.now)


@dataclass
class TeamTabCache:
    """Cache für alle Tabs eines Teams"""
    team_id: UUID
    plan_tabs: List[CachedTab] = field(default_factory=list)
    plan_period_tabs: List[CachedTab] = field(default_factory=list)
    tab_indices: Dict[str, int] = field(default_factory=dict)
    last_accessed: datetime = field(default_factory=datetime.now)
    
    def get_total_tabs(self) -> int:
        """Gibt die Gesamtanzahl der gecachten Tabs zurück"""
        return len(self.plan_tabs) + len(self.plan_period_tabs)


class TabCacheManager:
    """
    Zentrale Verwaltung des Tab-Caches
    
    Features:
    - LRU-basierte Cache-Eviction
    - Automatische Bereinigung abgelaufener Einträge
    - Memory-Management
    - Cache-Statistiken
    """
    
    def __init__(self, max_cached_teams: int = 5, cache_expire_hours: int = 24):
        self.cache: Dict[UUID, TeamTabCache] = {}
        self.max_cached_teams = max_cached_teams
        self.cache_expire_hours = cache_expire_hours
        
        # Statistiken
        self.stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0,
            'evictions': 0
        }
        
        logger.info(f"TabCacheManager initialisiert: max_teams={max_cached_teams}, expire_hours={cache_expire_hours}")
    
    def store_team_tabs(self, team_id: UUID, plan_tabs: List[CachedTab], 
                       plan_period_tabs: List[CachedTab], tab_indices: Dict[str, int]) -> bool:
        """
        Speichert Tabs für ein Team im Cache
        
        Returns:
            bool: True wenn erfolgreich gecacht
        """
        try:
            # Cleanup vor dem Speichern
            self._cleanup_expired_cache()
            
            # LRU-Eviction wenn Cache voll
            if len(self.cache) >= self.max_cached_teams and team_id not in self.cache:
                evicted = self._evict_oldest_team()
                if evicted:
                    self.stats['evictions'] += 1
            
            # Team-Cache erstellen/aktualisieren
            team_cache = TeamTabCache(
                team_id=team_id,
                plan_tabs=plan_tabs.copy(),
                plan_period_tabs=plan_period_tabs.copy(),
                tab_indices=tab_indices.copy(),
                last_accessed=datetime.now()
            )
            
            self.cache[team_id] = team_cache
            
            total_tabs = team_cache.get_total_tabs()
            logger.info(f"Team {team_id} gecacht: {total_tabs} Tabs")
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Cachen von Team {team_id}: {e}")
            return False
    
    def get_team_tabs(self, team_id: UUID) -> Optional[TeamTabCache]:
        """
        Lädt Tabs für ein Team aus dem Cache
        
        Returns:
            TeamTabCache oder None wenn nicht im Cache
        """
        if team_id not in self.cache:
            self.stats['misses'] += 1
            return None
        
        cached_team = self.cache[team_id]
        
        # LRU-Update
        cached_team.last_accessed = datetime.now()
        self.stats['hits'] += 1
        
        return cached_team
    
    def invalidate_team_cache(self, team_id: UUID) -> bool:
        """
        Invalidiert Cache für ein spezifisches Team
        
        Returns:
            bool: True wenn Team im Cache war
        """
        if team_id not in self.cache:
            return False
        
        cached_team = self.cache[team_id]
        
        # Widgets explizit löschen um Memory-Leaks zu vermeiden
        self._cleanup_cached_widgets(cached_team)
        
        del self.cache[team_id]
        self.stats['invalidations'] += 1
        
        logger.info(f"Cache für Team {team_id} invalidiert")
        return True
    
    def invalidate_plan_cache(self, plan_id: UUID) -> List[UUID]:
        """
        Invalidiert Cache-Einträge, die einen bestimmten Plan enthalten
        
        Returns:
            List[UUID]: IDs der Teams deren Cache invalidiert wurde
        """
        teams_to_invalidate = []
        
        for team_id, cached_team in self.cache.items():
            for cached_tab in cached_team.plan_tabs:
                if (hasattr(cached_tab.widget, 'plan') and 
                    cached_tab.widget.plan.id == plan_id):
                    teams_to_invalidate.append(team_id)
                    break
        
        # Cache invalidieren
        for team_id in teams_to_invalidate:
            self.invalidate_team_cache(team_id)
        
        return teams_to_invalidate
    
    def invalidate_plan_period_cache(self, plan_period_id: UUID) -> List[UUID]:
        """
        Invalidiert Cache-Einträge, die eine bestimmte PlanPeriod enthalten
        
        Returns:
            List[UUID]: IDs der Teams deren Cache invalidiert wurde
        """
        teams_to_invalidate = []
        
        for team_id, cached_team in self.cache.items():
            for cached_tab in cached_team.plan_period_tabs:
                if (hasattr(cached_tab.widget, 'plan_period_id') and 
                    cached_tab.widget.plan_period_id == plan_period_id):
                    teams_to_invalidate.append(team_id)
                    break
        
        # Cache invalidieren
        for team_id in teams_to_invalidate:
            self.invalidate_team_cache(team_id)
        
        return teams_to_invalidate
    
    def clear_all_cache(self) -> int:
        """
        Leert den kompletten Cache
        
        Returns:
            int: Anzahl der gelöschten Teams
        """
        count = len(self.cache)
        
        # Alle Widgets bereinigen
        for cached_team in self.cache.values():
            self._cleanup_cached_widgets(cached_team)
        
        self.cache.clear()
        
        # Statistiken zurücksetzen
        self.stats = {
            'hits': 0,
            'misses': 0,
            'invalidations': 0,
            'evictions': 0
        }
        
        logger.info(f"Kompletter Cache geleert: {count} Teams entfernt")
        return count
    
    def _cleanup_expired_cache(self) -> int:
        """
        Entfernt abgelaufene Cache-Einträge
        
        Returns:
            int: Anzahl der bereinigten Einträge
        """
        cutoff_time = datetime.now() - timedelta(hours=self.cache_expire_hours)
        expired_teams = [
            team_id for team_id, cached_team in self.cache.items() 
            if cached_team.last_accessed < cutoff_time
        ]
        
        for team_id in expired_teams:
            self.invalidate_team_cache(team_id)
        
        return len(expired_teams)
    
    def _evict_oldest_team(self) -> Optional[UUID]:
        """
        Entfernt das am längsten nicht genutzte Team (LRU)
        
        Returns:
            UUID: ID des entfernten Teams oder None
        """
        if not self.cache:
            return None
        
        oldest_team_id = min(
            self.cache.keys(), 
            key=lambda tid: self.cache[tid].last_accessed
        )
        
        self.invalidate_team_cache(oldest_team_id)
        
        return oldest_team_id
    
    def _cleanup_cached_widgets(self, cached_team: TeamTabCache):
        """Bereinigt Widgets eines gecachten Teams"""
        for cached_tab in cached_team.plan_tabs + cached_team.plan_period_tabs:
            if cached_tab.widget and not cached_tab.widget.parent():
                try:
                    cached_tab.widget.deleteLater()
                except Exception as e:
                    logger.warning(f"Fehler beim Widget-Cleanup: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Gibt Cache-Statistiken zurück
        
        Returns:
            Dict mit Cache-Metriken
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        teams_info = []
        total_cached_tabs = 0
        
        for team_id, cache in self.cache.items():
            tab_count = cache.get_total_tabs()
            total_cached_tabs += tab_count
            
            teams_info.append({
                'team_id': str(team_id),
                'plan_tabs': len(cache.plan_tabs),
                'plan_period_tabs': len(cache.plan_period_tabs),
                'total_tabs': tab_count,
                'last_accessed': cache.last_accessed.isoformat(),
                'age_minutes': int((datetime.now() - cache.last_accessed).total_seconds() / 60)
            })
        
        return {
            'enabled': True,
            'cached_teams': len(self.cache),
            'max_teams': self.max_cached_teams,
            'total_cached_tabs': total_cached_tabs,
            'cache_expire_hours': self.cache_expire_hours,
            'statistics': {
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate_percent': round(hit_rate, 1),
                'invalidations': self.stats['invalidations'],
                'evictions': self.stats['evictions']
            },
            'teams': teams_info
        }
    
    def update_config(self, max_cached_teams: Optional[int] = None, 
                     cache_expire_hours: Optional[int] = None):
        """Aktualisiert Cache-Konfiguration zur Laufzeit"""
        if max_cached_teams is not None:
            old_max = self.max_cached_teams
            self.max_cached_teams = max_cached_teams
            
            # Cache verkleinern falls nötig
            while len(self.cache) > max_cached_teams:
                self._evict_oldest_team()
            
            logger.info(f"Max cached teams: {old_max} -> {max_cached_teams}")
        
        if cache_expire_hours is not None:
            old_expire = self.cache_expire_hours
            self.cache_expire_hours = cache_expire_hours
            
            # Expired Einträge sofort bereinigen
            self._cleanup_expired_cache()
            
            logger.info(f"Cache expire hours: {old_expire} -> {cache_expire_hours}")
