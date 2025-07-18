"""
TabManager - Verwaltung aller Tabs in hcc-plan
Extrahiert Tab-Verwaltungslogik aus MainWindow
Erweitert um intelligentes Tab-Caching für bessere Performance
"""

import logging
from uuid import UUID
from typing import Optional, Dict, Any, List

from PySide6.QtCore import QObject, Signal, Slot, QPoint
from PySide6.QtWidgets import QWidget, QMessageBox, QInputDialog, QMenu
from pydantic_core import ValidationError

from gui.cache import CachedTab, TeamTabCache, TabCacheManager
from gui.cache.performance_monitor import performance_monitor

from configuration import team_start_config
from database import db_services, schemas
from gui.custom_widgets.tabbars import TabBar
from tools.actions import MenuToolbarAction
from tools.helper_functions import date_to_string

logger = logging.getLogger(__name__)


class TabManager(QObject):
    """
    Verwaltet alle Tab-Operationen der MainWindow:
    - Öffnen/Schließen von Plan- und Planungsmasken-Tabs
    - Session-Management (Speichern/Laden)
    - Tab-Navigation und -Zustand
    - Intelligentes Tab-Caching für bessere Performance
    """
    
    # === SIGNALS FÜR MAINWINDOW KOMMUNIKATION ===
    
    # Tab-Events
    tab_opened = Signal(str, object)  # tab_type: str, widget: object
    tab_closed = Signal(str, object)  # tab_type: str, widget: object
    tab_activated = Signal(str, object)  # tab_type: str, widget: object
    
    # Config-Events  
    team_config_needed = Signal(UUID)  # team_id: UUID
    team_config_saved = Signal(UUID)   # team_id: UUID
    
    # UI-Update Events
    menu_toolbar_update_needed = Signal(str)  # active_tab_type: str
    status_message = Signal(str)  # message: str
    
    # Error-Events
    error_occurred = Signal(str, str)  # title: str, message: str

    # === SIGNALS FÜR INTERNE KOMMUNIKATION ===
    plan_export_requested = Signal(int)
    
    # === NEUE CACHE-SIGNALS ===
    cache_hit = Signal(UUID, int, int)  # team_id, plan_tabs_count, plan_period_tabs_count
    cache_miss = Signal(UUID)  # team_id
    cache_invalidated = Signal(UUID)  # team_id
    cache_stats_updated = Signal(dict)  # cache_stats
    
    def __init__(self, parent: QWidget, controller, global_update_plan_tabs_progress_manager):
        super().__init__(parent)
        self.parent = parent
        self.controller = controller
        self.global_update_plan_tabs_progress_manager = global_update_plan_tabs_progress_manager
        
        # TabBar-Widgets (werden von MainWindow übergeben)
        self.tabs_left: Optional[TabBar] = None
        self.tabs_planungsmasken: Optional[TabBar] = None 
        self.tabs_plans: Optional[TabBar] = None
        
        # Aktuelles Team
        self.current_team: Optional[schemas.TeamShow] = None
        
        # === CACHE-SYSTEM ===
        self.cache_manager = TabCacheManager(max_cached_teams=5, cache_expire_hours=24)
        self._cache_enabled = True  # Kann zur Laufzeit deaktiviert werden
        
        # Cache-Invalidierung bei Datenänderungen
        self._setup_cache_invalidation_signals()
        
    def _setup_cache_invalidation_signals(self):
        """Verbindet Signals für automatische Cache-Invalidierung"""
        try:
            # Wenn Controller command_executed Signal hat, verbinden
            if hasattr(self.controller, 'command_executed'):
                self.controller.command_executed.connect(self._on_command_executed)
            else:
                logger.debug("Controller hat kein command_executed Signal - Cache-Invalidierung manuell")
        except Exception as e:
            logger.warning(f"Cache-Invalidierung Signals konnten nicht verbunden werden: {e}")
    
    @Slot(object)
    def _on_command_executed(self, command):
        """Invalidiert Cache bei relevanten Datenänderungen"""
        if not self._cache_enabled:
            return
            
        try:
            command_name = command.__class__.__name__
            
            # Plan-bezogene Kommandos
            if hasattr(command, 'plan_id') and 'Plan' in command_name:
                invalidated_teams = self.cache_manager.invalidate_plan_cache(command.plan_id)
                for team_id in invalidated_teams:
                    self.cache_invalidated.emit(team_id)
            
            # PlanPeriod-bezogene Kommandos
            elif hasattr(command, 'plan_period_id') and 'PlanPeriod' in command_name:
                invalidated_teams = self.cache_manager.invalidate_plan_period_cache(command.plan_period_id)
                for team_id in invalidated_teams:
                    self.cache_invalidated.emit(team_id)
            
            # Team-Änderungen invalidieren kompletten Team-Cache
            elif hasattr(command, 'team_id') and 'Team' in command_name:
                if self.cache_manager.invalidate_team_cache(command.team_id):
                    self.cache_invalidated.emit(command.team_id)
                    
        except Exception as e:
            logger.error(f"Fehler bei Cache-Invalidierung: {e}")
            
    def initialize_tabs(self, tabs_left: TabBar, tabs_planungsmasken: TabBar, tabs_plans: TabBar):
        """
        Initialisiert die TabBar-Widgets und verbindet Signals
        """
        self.tabs_left = tabs_left
        self.tabs_planungsmasken = tabs_planungsmasken
        self.tabs_plans = tabs_plans
        
        # Tab-Navigation Events verbinden
        self.tabs_left.currentChanged.connect(self._on_left_tabs_changed)
        
        # Kontextmenü für Plan-Tabs
        # Note: Das muss in der MainWindow-Integration angepasst werden
        # da TabBar möglicherweise nicht set_context_menu_handler hat
        
    def set_current_team(self, team: schemas.TeamShow):
        """Erweiterte Team-Wechsel-Logik mit intelligentem Caching und Performance-Monitoring"""
        if self.current_team == team:
            return
        
        # Performance-Monitoring starten
        performance_monitor.start_team_switch(team.id, team.name)
        cache_hit = False
        tab_count = 0
        error = None
        
        try:
            # Aktuelles Team cachen falls vorhanden
            if self.current_team and self._cache_enabled:
                self.save_team_config(self.current_team.id)
                self._cache_current_team_tabs()
            elif self.current_team:
                # Ohne Cache: normale Speicherung
                self.save_team_config(self.current_team.id)
            
            # Alle sichtbaren Tabs schließen
            if self._cache_enabled:
                self._close_all_visible_tabs()  # Widgets behalten für Cache
            else:
                self.close_all_tabs()  # Widgets wirklich löschen
            
            # Zu neuem Team wechseln
            self.current_team = team
            
            # Aus Cache laden oder neu erstellen
            if self._cache_enabled and (cached_tabs := self.cache_manager.get_team_tabs(team.id)):
                self._restore_tabs_from_cache(cached_tabs)
                cache_hit = True
                tab_count = cached_tabs.get_total_tabs()
                self.cache_hit.emit(team.id, len(cached_tabs.plan_tabs), len(cached_tabs.plan_period_tabs))
            else:
                self.load_team_config(team.id)  # Fallback auf originale Logik
                # Tab-Count nach dem Laden ermitteln
                tab_count = self.tabs_plans.count() + self.tabs_planungsmasken.count()
                if self._cache_enabled:
                    self.cache_miss.emit(team.id)
                    
        except Exception as e:
            error = str(e)
            logger.error(f"Fehler beim Team-Wechsel zu {team.name}: {e}")
            raise
        finally:
            # Performance-Monitoring beenden
            metric = performance_monitor.end_team_switch(team.id, team.name, cache_hit, tab_count, error)
            
            # Cache-Snapshot erstellen
            if self._cache_enabled:
                cache_stats = self.cache_manager.get_cache_stats()
                performance_monitor.capture_cache_snapshot(cache_stats)
            
    # === CACHE-MANAGEMENT METHODEN ===
    
    def _cache_current_team_tabs(self):
        """Speichert aktuelle Tabs im Cache"""
        if not self.current_team or not self._cache_enabled:
            return
            
        try:
            logger.info(f"=== CACHE START für Team {self.current_team.name} ===")
            logger.info(f"Plan-Tabs vor Caching: {self.tabs_plans.count()}")
            logger.info(f"Masken-Tabs vor Caching: {self.tabs_planungsmasken.count()}")
            
            # Plan-Tabs sammeln
            plan_tabs = []
            for i in range(self.tabs_plans.count()):
                widget = self.tabs_plans.widget(i)
                tab_text = self.tabs_plans.tabText(i)
                tooltip = self.tabs_plans.tabToolTip(i) if self.tabs_plans.tabToolTip(i) else None
                
                logger.info(f"Caching Plan-Tab {i}: '{tab_text}' Widget: {widget}")
                
                cached_tab = CachedTab(
                    widget=widget,
                    tab_text=tab_text,
                    tooltip=tooltip
                )
                plan_tabs.append(cached_tab)
            
            # Planungsmasken-Tabs sammeln
            plan_period_tabs = []
            for i in range(self.tabs_planungsmasken.count()):
                widget = self.tabs_planungsmasken.widget(i)
                tab_text = self.tabs_planungsmasken.tabText(i)
                tooltip = self.tabs_planungsmasken.tabToolTip(i) if self.tabs_planungsmasken.tabToolTip(i) else None
                
                logger.info(f"Caching Masken-Tab {i}: '{tab_text}' Widget: {widget}")
                
                cached_tab = CachedTab(
                    widget=widget,
                    tab_text=tab_text,
                    tooltip=tooltip
                )
                plan_period_tabs.append(cached_tab)
            
            # Tab-Indizes sammeln
            tab_indices = {
                'plans': self.tabs_plans.currentIndex(),
                'planungsmasken': self.tabs_planungsmasken.currentIndex(),
                'left': self.tabs_left.currentIndex() if self.tabs_left else 0
            }
            
            logger.info(f"Tab-Indizes: {tab_indices}")
            logger.info(f"Gecachte Plan-Tabs: {len(plan_tabs)}")
            logger.info(f"Gecachte Masken-Tabs: {len(plan_period_tabs)}")
            
            # Im Cache speichern
            success = self.cache_manager.store_team_tabs(
                self.current_team.id, plan_tabs, plan_period_tabs, tab_indices
            )
            
            if success:
                # Cache-Statistiken aktualisieren
                self.cache_stats_updated.emit(self.cache_manager.get_cache_stats())
                logger.info(f"Team {self.current_team.id} erfolgreich gecacht")
            else:
                logger.error(f"Fehler beim Cachen von Team {self.current_team.id}")
            
            logger.info(f"=== CACHE END ===")
            
        except Exception as e:
            logger.error(f"Fehler beim Cachen von Team {self.current_team.id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _close_all_visible_tabs(self):
        """Schließt Tabs nur visuell, ohne Widgets zu löschen (für Caching) - Verbesserte Version"""
        try:
            logger.info(f"=== CLOSE VISIBLE TABS START ===")
            logger.info(f"Plan-Tabs zu schließen: {self.tabs_plans.count()}")
            logger.info(f"Masken-Tabs zu schließen: {self.tabs_planungsmasken.count()}")
            
            # Plan-Tabs aus TabBar entfernen - RÜCKWÄRTS iterieren um Index-Probleme zu vermeiden
            plan_widgets_removed = []
            plan_count = self.tabs_plans.count()
            for i in range(plan_count - 1, -1, -1):  # Rückwärts von letztem zu erstem
                widget = self.tabs_plans.widget(i)
                tab_text = self.tabs_plans.tabText(i)
                logger.info(f"Entferne Plan-Tab {i}: '{tab_text}' Widget: {widget}")
                
                # Widget vom TabBar trennen BEVOR wir removeTab aufrufen
                if widget:
                    widget.setParent(None)  # Erstmal Parent entfernen
                
                self.tabs_plans.removeTab(i)  # Tab entfernen
                plan_widgets_removed.append((widget, tab_text))
                
            logger.info(f"Plan-Widgets entfernt: {len(plan_widgets_removed)}")
            
            # Planungsmasken-Tabs aus TabBar entfernen - RÜCKWÄRTS iterieren
            masken_widgets_removed = []
            masken_count = self.tabs_planungsmasken.count()
            for i in range(masken_count - 1, -1, -1):  # Rückwärts von letztem zu erstem
                widget = self.tabs_planungsmasken.widget(i)
                tab_text = self.tabs_planungsmasken.tabText(i)
                logger.info(f"Entferne Masken-Tab {i}: '{tab_text}' Widget: {widget}")
                
                # Widget vom TabBar trennen BEVOR wir removeTab aufrufen
                if widget:
                    widget.setParent(None)  # Erstmal Parent entfernen
                    
                self.tabs_planungsmasken.removeTab(i)  # Tab entfernen
                masken_widgets_removed.append((widget, tab_text))
                
            logger.info(f"Masken-Widgets entfernt: {len(masken_widgets_removed)}")
            logger.info(f"Verbleibende Plan-Tabs: {self.tabs_plans.count()}")
            logger.info(f"Verbleibende Masken-Tabs: {self.tabs_planungsmasken.count()}")
            logger.info(f"=== CLOSE VISIBLE TABS END ===")
                
        except Exception as e:
            logger.error(f"Fehler beim Schließen der sichtbaren Tabs: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _restore_tabs_from_cache(self, cached_team: TeamTabCache):
        """Stellt Tabs aus dem Cache wieder her - Verbesserte Version"""
        try:
            logger.info(f"=== RESTORE TABS START für Team {cached_team.team_id} ===")
            logger.info(f"Zu restorende Plan-Tabs: {len(cached_team.plan_tabs)}")
            logger.info(f"Zu restorende Masken-Tabs: {len(cached_team.plan_period_tabs)}")
            
            # Sicherstellen, dass TabBars leer sind
            if self.tabs_plans.count() > 0:
                logger.warning(f"TabBar Plans nicht leer vor Restore: {self.tabs_plans.count()} Tabs")
            if self.tabs_planungsmasken.count() > 0:
                logger.warning(f"TabBar Masken nicht leer vor Restore: {self.tabs_planungsmasken.count()} Tabs")
            
            # Plan-Tabs wiederherstellen
            restored_plan_tabs = 0
            for i, cached_tab in enumerate(cached_team.plan_tabs):
                widget = cached_tab.widget
                tab_text = cached_tab.tab_text
                
                logger.info(f"Restore Plan-Tab {i}: '{tab_text}' Widget: {widget}")
                
                # Widget-Zustand prüfen
                if widget is None:
                    logger.error(f"Plan-Tab {i}: Widget ist None!")
                    continue
                
                # Widget-Zustand validieren
                if hasattr(widget, 'isVisible') and widget.isVisible():
                    logger.warning(f"Plan-Tab {i}: Widget ist sichtbar (sollte nicht sein)")
                    
                current_parent = widget.parent()
                if current_parent is not None:
                    logger.info(f"Plan-Tab {i}: Widget hat Parent: {current_parent}, entferne...")
                    widget.setParent(None)
                
                # Widget korrekt zu TabBar hinzufügen
                try:
                    widget.setParent(self.tabs_plans)
                    tab_index = self.tabs_plans.addTab(widget, tab_text)
                    
                    if cached_tab.tooltip:
                        self.tabs_plans.setTabToolTip(tab_index, cached_tab.tooltip)
                    
                    logger.info(f"Plan-Tab {i} erfolgreich wiederhergestellt als Index {tab_index}")
                    restored_plan_tabs += 1
                    
                except Exception as tab_error:
                    logger.error(f"Fehler beim Hinzufügen von Plan-Tab {i}: {tab_error}")
                    continue
            
            logger.info(f"Plan-Tabs wiederhergestellt: {restored_plan_tabs}/{len(cached_team.plan_tabs)}")
            
            # Planungsmasken-Tabs wiederherstellen  
            restored_period_tabs = 0
            for i, cached_tab in enumerate(cached_team.plan_period_tabs):
                widget = cached_tab.widget
                tab_text = cached_tab.tab_text
                
                logger.info(f"Restore Masken-Tab {i}: '{tab_text}' Widget: {widget}")
                
                # Widget-Zustand prüfen
                if widget is None:
                    logger.error(f"Masken-Tab {i}: Widget ist None!")
                    continue
                
                # Widget-Zustand validieren
                if hasattr(widget, 'isVisible') and widget.isVisible():
                    logger.warning(f"Masken-Tab {i}: Widget ist sichtbar (sollte nicht sein)")
                    
                current_parent = widget.parent()
                if current_parent is not None:
                    logger.info(f"Masken-Tab {i}: Widget hat Parent: {current_parent}, entferne...")
                    widget.setParent(None)
                
                # Widget korrekt zu TabBar hinzufügen
                try:
                    widget.setParent(self.tabs_planungsmasken)
                    tab_index = self.tabs_planungsmasken.addTab(widget, tab_text)
                    
                    if cached_tab.tooltip:
                        self.tabs_planungsmasken.setTabToolTip(tab_index, cached_tab.tooltip)
                        
                    logger.info(f"Masken-Tab {i} erfolgreich wiederhergestellt als Index {tab_index}")
                    restored_period_tabs += 1
                    
                except Exception as tab_error:
                    logger.error(f"Fehler beim Hinzufügen von Masken-Tab {i}: {tab_error}")
                    continue
            
            logger.info(f"Masken-Tabs wiederhergestellt: {restored_period_tabs}/{len(cached_team.plan_period_tabs)}")
            
            # Prüfung ob alle Tabs korrekt wiederhergestellt wurden
            if restored_plan_tabs != len(cached_team.plan_tabs):
                logger.error(f"NICHT ALLE Plan-Tabs wiederhergestellt! Erwartet: {len(cached_team.plan_tabs)}, Erhalten: {restored_plan_tabs}")
            
            if restored_period_tabs != len(cached_team.plan_period_tabs):
                logger.error(f"NICHT ALLE Masken-Tabs wiederhergestellt! Erwartet: {len(cached_team.plan_period_tabs)}, Erhalten: {restored_period_tabs}")
            
            # Tab-Indizes wiederherstellen
            if 'plans' in cached_team.tab_indices and cached_team.tab_indices['plans'] >= 0:
                max_index = max(0, self.tabs_plans.count() - 1)
                index = min(cached_team.tab_indices['plans'], max_index)
                logger.info(f"Setze Plan-Tab Index: {index} (verfügbar: 0-{max_index})")
                if self.tabs_plans.count() > 0:
                    self.tabs_plans.setCurrentIndex(index)
                
            if 'planungsmasken' in cached_team.tab_indices and cached_team.tab_indices['planungsmasken'] >= 0:
                max_index = max(0, self.tabs_planungsmasken.count() - 1)
                index = min(cached_team.tab_indices['planungsmasken'], max_index)
                logger.info(f"Setze Masken-Tab Index: {index} (verfügbar: 0-{max_index})")
                if self.tabs_planungsmasken.count() > 0:
                    self.tabs_planungsmasken.setCurrentIndex(index)
                
            if 'left' in cached_team.tab_indices and self.tabs_left and cached_team.tab_indices['left'] >= 0:
                max_index = max(0, self.tabs_left.count() - 1)
                index = min(cached_team.tab_indices['left'], max_index)
                logger.info(f"Setze Left-Tab Index: {index} (verfügbar: 0-{max_index})")
                if self.tabs_left.count() > 0:
                    self.tabs_left.setCurrentIndex(index)
            
            # Final-Status loggen
            logger.info(f"Finale Tab-Counts: Plans={self.tabs_plans.count()}, Masken={self.tabs_planungsmasken.count()}")
            
            # Erfolgsmeldung nur wenn alle Tabs korrekt wiederhergestellt wurden
            if restored_plan_tabs == len(cached_team.plan_tabs) and restored_period_tabs == len(cached_team.plan_period_tabs):
                logger.info(f"✅ Alle Tabs für Team {cached_team.team_id} erfolgreich aus Cache wiederhergestellt")
            else:
                logger.error(f"❌ NICHT ALLE Tabs für Team {cached_team.team_id} wiederhergestellt!")
                
            logger.info(f"=== RESTORE TABS END ===")
            
        except Exception as e:
            logger.error(f"Fehler beim Wiederherstellen der Tabs aus Cache: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fallback: Cache invalidieren und normal laden
            logger.info(f"Fallback: Invalidiere Cache und lade normal für Team {cached_team.team_id}")
            self.cache_manager.invalidate_team_cache(cached_team.team_id)
            self.load_team_config(cached_team.team_id)
    
    def enable_cache(self, enabled: bool = True):
        """Aktiviert/deaktiviert das Tab-Caching"""
        if not enabled and self._cache_enabled:
            # Cache leeren wenn deaktiviert
            cleared_count = self.cache_manager.clear_all_cache()
            logger.info(f"Tab-Caching deaktiviert - {cleared_count} Teams aus Cache entfernt")
        
        self._cache_enabled = enabled
        logger.info(f"Tab-Caching {'aktiviert' if enabled else 'deaktiviert'}")
    
    def clear_cache(self):
        """Leert den kompletten Tab-Cache"""
        cleared_count = self.cache_manager.clear_all_cache()
        self.cache_stats_updated.emit(self.cache_manager.get_cache_stats())
        logger.info(f"Tab-Cache geleert - {cleared_count} Teams entfernt")
        return cleared_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Gibt Cache-Statistiken zurück"""
        stats = self.cache_manager.get_cache_stats()
        stats['cache_enabled'] = self._cache_enabled
        return stats
    
    def test_cache_widget_lifecycle(self):
        """Test-Methode für Widget-Lifecycle beim Caching"""
        if not self._cache_enabled:
            logger.warning("Cache ist deaktiviert - Test nicht möglich")
            return False
            
        if not self.current_team:
            logger.warning("Kein aktuelles Team - Test nicht möglich")
            return False
            
        logger.info("=== CACHE WIDGET LIFECYCLE TEST START ===")
        
        try:
            # Status vor Test
            initial_plan_count = self.tabs_plans.count()
            initial_masken_count = self.tabs_planungsmasken.count()
            
            logger.info(f"Initial: Plans={initial_plan_count}, Masken={initial_masken_count}")
            
            # 1. Caching testen
            logger.info("1. Cache aktuelles Team...")
            self._cache_current_team_tabs()
            
            # 2. Tabs schließen (damit Widgets unsichtbar werden für Validierung)
            logger.info("2. Schließe alle sichtbaren Tabs...")
            self._close_all_visible_tabs()
            
            after_close_plan_count = self.tabs_plans.count()
            after_close_masken_count = self.tabs_planungsmasken.count()
            
            logger.info(f"Nach Schließen: Plans={after_close_plan_count}, Masken={after_close_masken_count}")
            
            if after_close_plan_count != 0 or after_close_masken_count != 0:
                logger.error("Tabs wurden nicht korrekt geschlossen!")
                return False
            
            # 3. Cache-Inhalt prüfen (jetzt sind Widgets unsichtbar)
            cached_team = self.cache_manager.get_team_tabs(self.current_team.id)
            if not cached_team:
                logger.error("Team wurde nicht gecacht!")
                return False
                
            logger.info(f"Gecacht: {len(cached_team.plan_tabs)} Plan-Tabs, {len(cached_team.plan_period_tabs)} Masken-Tabs")
            
            # 4. Tabs wiederherstellen
            logger.info("3. Stelle Tabs aus Cache wieder her...")
            self._restore_tabs_from_cache(cached_team)
            
            final_plan_count = self.tabs_plans.count()
            final_masken_count = self.tabs_planungsmasken.count()
            
            logger.info(f"Nach Restore: Plans={final_plan_count}, Masken={final_masken_count}")
            
            # 5. Ergebnis prüfen
            success = (final_plan_count == initial_plan_count and 
                      final_masken_count == initial_masken_count)
            
            if success:
                logger.info("✅ Cache Widget Lifecycle Test ERFOLGREICH!")
            else:
                logger.error(f"❌ Cache Widget Lifecycle Test FEHLGESCHLAGEN!")
                logger.error(f"Erwartet: Plans={initial_plan_count}, Masken={initial_masken_count}")
                logger.error(f"Erhalten: Plans={final_plan_count}, Masken={final_masken_count}")
            
            logger.info("=== CACHE WIDGET LIFECYCLE TEST END ===")
            return success
            
        except Exception as e:
            logger.error(f"Cache Widget Lifecycle Test fehlgeschlagen: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def update_cache_config(self, max_cached_teams: Optional[int] = None, 
                           cache_expire_hours: Optional[int] = None):
        """Aktualisiert Cache-Konfiguration zur Laufzeit"""
        self.cache_manager.update_config(max_cached_teams, cache_expire_hours)
        self.cache_stats_updated.emit(self.cache_manager.get_cache_stats())
            
    # === TAB-ÖFFNUNG ===
    
    def open_plan_tab(self, plan_id: UUID) -> bool:
        """
        Öffnet einen Plan-Tab
        Returns: True wenn erfolgreich geöffnet
        """
        try:
            # Prüfen ob Tab bereits offen
            if self._is_plan_tab_open(plan_id):
                self._activate_plan_tab(plan_id)
                return True
                
            plan = db_services.Plan.get(plan_id)
            
            # Import hier um zirkuläre Abhängigkeiten zu vermeiden
            from .frm_plan import FrmTabPlan
            
            new_widget = FrmTabPlan(
                self.tabs_plans, 
                plan, 
                self.global_update_plan_tabs_progress_manager
            )
            
            tab_index = self.tabs_plans.addTab(new_widget, plan.name)
            self.tabs_plans.setTabToolTip(tab_index, 'Rechtsklick: weitere Aktionen')
            self.tabs_plans.setCurrentIndex(tab_index)
            
            self.tab_opened.emit("plan", new_widget)
            logger.info(f"Plan-Tab geöffnet: {plan.name}")
            return True
            
        except ValidationError:
            self.error_occurred.emit(
                'Plan öffnen', 
                f'Der Plan mit der ID {plan_id} konnte nicht geöffnet werden.'
            )
            return False
        except Exception as e:
            self.error_occurred.emit('Plan öffnen', f'Unerwarteter Fehler: {e}')
            return False
    
    def open_plan_period_tab(self, plan_period_id: UUID, 
                           current_index_actors_locals_tabs: int = 0,
                           curr_person_id: Optional[UUID] = None, 
                           curr_location_id: Optional[UUID] = None) -> bool:
        """
        Öffnet einen Planungsmasken-Tab
        """
        try:
            # Prüfen ob Tab bereits offen
            if self._is_plan_period_tab_open(plan_period_id):
                self._activate_plan_period_tab(plan_period_id)
                return True
                
            plan_period = db_services.PlanPeriod.get(plan_period_id)
            
            # Import hier um zirkuläre Abhängigkeiten zu vermeiden
            from .frm_plan_period_tab_widget import PlanPeriodTabWidget
            from .frm_actor_plan_period import FrmTabActorPlanPeriods
            from .frm_location_plan_period import FrmTabLocationPlanPeriods
            
            widget_pp_tab = PlanPeriodTabWidget(self.parent, plan_period_id)
            string_start = date_to_string(plan_period.start)
            string_end = date_to_string(plan_period.end)
            
            tab_index = self.tabs_planungsmasken.addTab(
                widget_pp_tab, 
                f'{string_start} - {string_end}'
            )
            
            # Sub-Tabs erstellen
            tabs_period = TabBar(
                widget_pp_tab, 'north', 10, None, None,
                True, False, None, 'tab_bar_locations_employees'
            )

            tab_actor_plan_periods = FrmTabActorPlanPeriods(tabs_period, plan_period)
            if curr_person_id:
                tab_actor_plan_periods.data_setup(person_id=curr_person_id)
                
            tab_location_plan_periods = FrmTabLocationPlanPeriods(tabs_period, plan_period)
            if curr_location_id:
                tab_location_plan_periods.data_setup(location_id=curr_location_id)
                
            tabs_period.addTab(tab_actor_plan_periods, self.parent.tr('Employees'))
            tabs_period.addTab(tab_location_plan_periods, self.parent.tr('Facilities'))
            tabs_period.setCurrentIndex(current_index_actors_locals_tabs)
            
            self.tabs_planungsmasken.setCurrentIndex(tab_index)
            self.tab_opened.emit("plan_period", widget_pp_tab)
            
            logger.info(f"Planungsmasken-Tab geöffnet: {string_start} - {string_end}")
            return True
            
        except Exception as e:
            self.error_occurred.emit('Planungsmaske öffnen', f'Fehler: {e}')
            return False
    
    def open_plan_from_dialog(self) -> bool:
        """
        Öffnet Plan-Auswahl-Dialog und öffnet gewählten Plan
        """
        if not self.current_team:
            self.error_occurred.emit('Aktuelles Team', 'Sie müssen zuerst ein Team auswählen.')
            return False
            
        # Verfügbare Pläne ermitteln (nicht bereits geöffnete)
        opened_plan_ids = {
            self.tabs_plans.widget(i).plan.id 
            for i in range(self.tabs_plans.count())
        }
        
        available_plans = {
            name: p_id
            for name, p_id in db_services.Plan.get_all_from__team(self.current_team.id, True).items()
            if p_id not in opened_plan_ids
        }
        
        if not available_plans:
            self.error_occurred.emit(
                'Plan öffnen',
                f'Es sind keine weiteren Pläne des Teams {self.current_team.name} vorhanden.'
            )
            return False

        # Dialog anzeigen
        chosen_plan_name, ok = QInputDialog.getItem(
            self.parent, "Plan auswählen", "Wähle einen Plan aus:",
            list(reversed(list(available_plans))), editable=False
        )
        
        if ok:
            plan_id = available_plans[chosen_plan_name]
            return self.open_plan_tab(plan_id)
            
        return False
    
    # === TAB-SCHLIESSSUNG ===
    
    def close_plan_tab(self, index: int) -> bool:
        """Erweiterte Plan-Tab-Schließung mit Cache-Invalidierung"""
        if 0 <= index < self.tabs_plans.count():
            widget = self.tabs_plans.widget(index)
            
            # Cache invalidieren falls der Plan betroffen ist
            if hasattr(widget, 'plan') and self._cache_enabled:
                invalidated_teams = self.cache_manager.invalidate_plan_cache(widget.plan.id)
                for team_id in invalidated_teams:
                    self.cache_invalidated.emit(team_id)
            
            self.tabs_plans.close_tab_and_delete_widget(index)
            self.tab_closed.emit("plan", widget)
            return True
        return False
    
    def close_plan_period_tab(self, index: int) -> bool:
        """Erweiterte Planungsmasken-Tab-Schließung mit Cache-Invalidierung"""
        if 0 <= index < self.tabs_planungsmasken.count():
            widget = self.tabs_planungsmasken.widget(index)
            
            # Cache invalidieren falls die PlanPeriod betroffen ist
            if hasattr(widget, 'plan_period_id') and self._cache_enabled:
                invalidated_teams = self.cache_manager.invalidate_plan_period_cache(widget.plan_period_id)
                for team_id in invalidated_teams:
                    self.cache_invalidated.emit(team_id)
            
            self.tabs_planungsmasken.close_tab_and_delete_widget(index)
            self.tab_closed.emit("plan_period", widget)
            return True
        return False
    
    def close_all_tabs(self):
        """Erweiterte close_all_tabs mit Cache-Berücksichtigung"""
        if self._cache_enabled and self.current_team:
            # Bei aktivem Caching: Tabs cachen statt löschen
            self._cache_current_team_tabs()
            self._close_all_visible_tabs()
        else:
            # Original-Verhalten: Alle Tabs wirklich schließen
            while self.tabs_plans.count() > 0:
                self.close_plan_tab(0)
            while self.tabs_planungsmasken.count() > 0:
                self.close_plan_period_tab(0)
    
    def delete_plan_tab(self, index: int):
        """Löscht einen Plan (mit Bestätigung)"""
        if index < 0 or index >= self.tabs_plans.count():
            return
            
        from .frm_plan import FrmTabPlan
        widget: FrmTabPlan = self.tabs_plans.widget(index)
        
        confirmation = QMessageBox.question(
            self.parent, 'Plan löschen',
            f'Möchten Sie den Plan {widget.plan.name} wirklich löschen?'
        )
        
        if confirmation == QMessageBox.StandardButton.Yes:
            plan_id = widget.plan.id
            self.close_plan_tab(index)
            
            # Plan aus Datenbank löschen
            from commands.database_commands import plan_commands
            self.controller.execute(plan_commands.Delete(plan_id))
    
    # === TAB-NAVIGATION ===
    
    @Slot()
    def _on_left_tabs_changed(self):
        """Handler für Wechsel zwischen Plans/Masks"""
        current_tab_type = self.tabs_left.currentWidget().objectName()
        self.menu_toolbar_update_needed.emit(current_tab_type)
        
        # Aktuellen Tab aktivieren
        if current_tab_type == 'plans' and self.tabs_plans.count() > 0:
            current_widget = self.tabs_plans.currentWidget()
            self.tab_activated.emit("plan", current_widget)
        elif current_tab_type == 'masks' and self.tabs_planungsmasken.count() > 0:
            current_widget = self.tabs_planungsmasken.currentWidget()
            self.tab_activated.emit("plan_period", current_widget)
    
    def show_plans(self):
        """Wechselt zur Plan-Ansicht"""
        for i in range(self.tabs_left.count()):
            if self.tabs_left.widget(i).objectName() == 'plans':
                self.tabs_left.setCurrentIndex(i)
                break
    
    # === PROPERTIES ===
    
    @property 
    def current_plan_widget(self):
        """Aktueller Plan-Tab Widget"""
        return self.tabs_plans.currentWidget() if self.tabs_plans.count() > 0 else None
    
    @property
    def current_plan_period_widget(self):
        """Aktueller Planungsmasken-Tab Widget"""
        return self.tabs_planungsmasken.currentWidget() if self.tabs_planungsmasken.count() > 0 else None
    
    @property
    def current_tab_type(self) -> str:
        """Typ des aktuell aktiven Tabs ('plans' oder 'masks')"""
        if self.tabs_left and self.tabs_left.currentWidget():
            return self.tabs_left.currentWidget().objectName()
        return ""
    
    def show_masks(self):
        """Wechselt zur Planungsmasken-Ansicht"""
        for i in range(self.tabs_left.count()):
            if self.tabs_left.widget(i).objectName() == 'masks':
                self.tabs_left.setCurrentIndex(i)
                break
    
    # === PROPERTIES ===
    
    @property 
    def current_plan_widget(self):
        """Aktueller Plan-Tab Widget"""
        return self.tabs_plans.currentWidget() if self.tabs_plans.count() > 0 else None
    
    @property
    def current_plan_period_widget(self):
        """Aktueller Planungsmasken-Tab Widget"""
        return self.tabs_planungsmasken.currentWidget() if self.tabs_planungsmasken.count() > 0 else None
    
    @property
    def current_tab_type(self) -> str:
        """Typ des aktuell aktiven Tabs ('plans' oder 'masks')"""
        if self.tabs_left and self.tabs_left.currentWidget():
            return self.tabs_left.currentWidget().objectName()
        return ""
    
    # === KONTEXTMENÜ ===
    
    def create_plan_context_menu(self, point: QPoint, index: int):
        """Erstellt Kontextmenü für Plan-Tabs"""
        context_menu = QMenu()
        
        context_menu.addAction(MenuToolbarAction(
            context_menu, None, 'Plan löschen...', None,
            lambda: self.delete_plan_tab(index)
        ))
        
        context_menu.addAction(MenuToolbarAction(
            context_menu, None, 'Plan als Excel-File exportieren...', None,
            lambda: self._export_plan_to_excel(index)
        ))
        
        context_menu.exec(self.tabs_plans.mapToGlobal(point))
    
    def _export_plan_to_excel(self, index: int):
        """Delegiert Excel-Export an MainWindow"""
        # Signal könnte hinzugefügt werden: plan_export_requested = Signal(int)
        self.plan_export_requested.emit(index)
    
    # === SESSION-MANAGEMENT ===
    
    def save_team_config(self, team_id: UUID):
        """Speichert Tab-Konfiguration für Team"""
        if not team_id:
            return
            
        try:
            start_config_handler = team_start_config.curr_start_config_handler
            
            # Tab-Zustand sammeln
            tabs_planungsmasken = {}
            for i in range(self.tabs_planungsmasken.count()):
                widget = self.tabs_planungsmasken.widget(i)
                plan_period_id = widget.plan_period_id
                
                # Sub-Tab-Zustand ermitteln
                from .frm_actor_plan_period import FrmTabActorPlanPeriods  
                from .frm_location_plan_period import FrmTabLocationPlanPeriods
                
                actor_tab = widget.findChild(FrmTabActorPlanPeriods)
                location_tab = widget.findChild(FrmTabLocationPlanPeriods)
                sub_tab_bar = widget.findChild(TabBar)
                
                tabs_planungsmasken[plan_period_id] = {
                    'person_id': actor_tab.person_id if actor_tab else None,
                    'location_id': location_tab.location_id if location_tab else None,
                    'curr_index_actors_locals_tabs': sub_tab_bar.currentIndex() if sub_tab_bar else 0
                }
            
            tabs_plans = [
                self.tabs_plans.widget(i).plan.id 
                for i in range(self.tabs_plans.count())
            ]
            
            # Konfiguration speichern
            config = team_start_config.StartConfigTeam(
                team_id=team_id,
                tabs_planungsmasken=tabs_planungsmasken,
                tabs_plans=tabs_plans,
                current_index_planungsmasken_tabs=self.tabs_planungsmasken.currentIndex(),
                current_index_plans_tabs=self.tabs_plans.currentIndex(),
                current_index_left_tabs=self.tabs_left.currentIndex()
            )
            
            start_config_handler.save_config_for_team(team_id, config)
            self.team_config_saved.emit(team_id)
            logger.info(f"Team-Konfiguration gespeichert für Team {team_id}")
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Team-Konfiguration: {e}")
    
    def load_team_config(self, team_id: UUID):
        """Lädt Tab-Konfiguration für Team"""
        if not team_id:
            return
            
        try:
            start_config_handler = team_start_config.curr_start_config_handler
            config = start_config_handler.get_start_config_for_team(team_id)
            
            # Planungsmasken-Tabs wiederherstellen
            for plan_period_id, pp_tab_config in config.tabs_planungsmasken.items():
                self.open_plan_period_tab(
                    plan_period_id,
                    pp_tab_config['curr_index_actors_locals_tabs'],
                    pp_tab_config.get('person_id'), 
                    pp_tab_config.get('location_id')
                )
            
            # Plan-Tabs wiederherstellen
            for plan_id in config.tabs_plans:
                self.open_plan_tab(plan_id)
            
            # Tab-Indizes wiederherstellen
            self.tabs_planungsmasken.setCurrentIndex(config.current_index_planungsmasken_tabs)
            self.tabs_plans.setCurrentIndex(config.current_index_plans_tabs)
            self.tabs_left.setCurrentIndex(config.current_index_left_tabs)
            
            logger.info(f"Team-Konfiguration geladen für Team {team_id}")
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Team-Konfiguration: {e}")
    
    def restore_startup_tabs(self):
        """Lädt Tabs beim Programmstart"""
        try:
            curr_team_id = team_start_config.curr_start_config_handler.get_start_config().default_team_id
            if curr_team_id:
                team = db_services.Team.get(curr_team_id)
                self.set_current_team(team)
                
        except ValidationError:
            # Team existiert nicht mehr
            config = team_start_config.curr_start_config_handler.load_config_from_file()
            config.default_team_id = None
            config.teams = []
            team_start_config.curr_start_config_handler.save_config_to_file(config)
        except Exception as e:
            logger.error(f"Fehler beim Wiederherstellen der Startup-Tabs: {e}")
    
    # === HILFSMETHODEN ===
    
    def _is_plan_tab_open(self, plan_id: UUID) -> bool:
        """Prüft ob Plan-Tab bereits geöffnet ist"""
        for i in range(self.tabs_plans.count()):
            if self.tabs_plans.widget(i).plan.id == plan_id:
                return True
        return False
    
    def _is_plan_period_tab_open(self, plan_period_id: UUID) -> bool:
        """Prüft ob Planungsmasken-Tab bereits geöffnet ist"""
        for i in range(self.tabs_planungsmasken.count()):
            if self.tabs_planungsmasken.widget(i).plan_period_id == plan_period_id:
                return True
        return False
    
    def _activate_plan_tab(self, plan_id: UUID):
        """Aktiviert existierenden Plan-Tab"""
        for i in range(self.tabs_plans.count()):
            if self.tabs_plans.widget(i).plan.id == plan_id:
                self.tabs_plans.setCurrentIndex(i)
                break
    
    # === PROPERTIES ===
    
    @property 
    def current_plan_widget(self):
        """Aktueller Plan-Tab Widget"""
        return self.tabs_plans.currentWidget() if self.tabs_plans.count() > 0 else None
    
    @property
    def current_plan_period_widget(self):
        """Aktueller Planungsmasken-Tab Widget"""
        return self.tabs_planungsmasken.currentWidget() if self.tabs_planungsmasken.count() > 0 else None
    
    @property
    def current_tab_type(self) -> str:
        """Typ des aktuell aktiven Tabs ('plans' oder 'masks')"""
        if self.tabs_left and self.tabs_left.currentWidget():
            return self.tabs_left.currentWidget().objectName()
        return ""
    
    def _activate_plan_period_tab(self, plan_period_id: UUID):
        """Aktiviert existierenden Planungsmasken-Tab"""
        for i in range(self.tabs_planungsmasken.count()):
            if self.tabs_planungsmasken.widget(i).plan_period_id == plan_period_id:
                self.tabs_planungsmasken.setCurrentIndex(i)
                break
    
    # === PROPERTIES ===
    
    @property 
    def current_plan_widget(self):
        """Aktueller Plan-Tab Widget"""
        return self.tabs_plans.currentWidget() if self.tabs_plans.count() > 0 else None
    
    @property
    def current_plan_period_widget(self):
        """Aktueller Planungsmasken-Tab Widget"""
        return self.tabs_planungsmasken.currentWidget() if self.tabs_planungsmasken.count() > 0 else None
    
    @property
    def current_tab_type(self) -> str:
        """Typ des aktuell aktiven Tabs ('plans' oder 'masks')"""
        if self.tabs_left and self.tabs_left.currentWidget():
            return self.tabs_left.currentWidget().objectName()
        return ""
    
    def show_location_plan_period_mask(self, plan_period_id: UUID, location_id: UUID):
        """Öffnet/aktiviert Planungsmasken-Tab und lädt Location-Daten"""
        if not self._is_plan_period_tab_open(plan_period_id):
            self.open_plan_period_tab(plan_period_id, 1, None, location_id)
        else:
            # Tab ist bereits offen, aktivieren und Location setzen
            plan_period_tab_widget = self._activate_tab_by_plan_period_id(plan_period_id)
            self._load_location_plan_period_mask(plan_period_tab_widget, location_id)

    def show_actor_plan_period_mask(self, plan_period_id: UUID, person_id: UUID):
        """Öffnet/aktiviert Planungsmasken-Tab und lädt Actor-Daten"""
        if not self._is_plan_period_tab_open(plan_period_id):
            self.open_plan_period_tab(plan_period_id, 0, person_id, None)
        else:
            plan_period_tab_widget = self._activate_tab_by_plan_period_id(plan_period_id)
            self._load_actor_plan_period_mask(plan_period_tab_widget, person_id)
    
    def _activate_tab_by_plan_period_id(self, plan_period_id: UUID):
        """Aktiviert existierenden Planungsmasken-Tab"""
        for i in range(self.tabs_planungsmasken.count()):
            if (pp_widget := self.tabs_planungsmasken.widget(i)).plan_period_id == plan_period_id:
                self.tabs_planungsmasken.setCurrentIndex(i)
                return pp_widget
        return None

    def _load_location_plan_period_mask(self, plan_period_tab_widget, location_id: UUID):
        """
        Aktiviert den Tab "Einrichtungen" im PlanPeriodTabWidget und zeigt die Events-Maske der gewählten Einrichtung an.
        """
        tab_locations_employees = plan_period_tab_widget.findChild(TabBar, 'tab_bar_locations_employees')
        for i in range(tab_locations_employees.count()):
            if (tab_locations := tab_locations_employees.widget(i)).objectName() == 'tab_location_plan_periods':
                tab_locations_employees.setCurrentIndex(i)
                # Import hier um zirkuläre Abhängigkeiten zu vermeiden
                from .frm_location_plan_period import FrmTabLocationPlanPeriods
                tab_locations: FrmTabLocationPlanPeriods
                tab_locations.data_setup(location_id=location_id)
                break
    
    # === PROPERTIES ===
    
    @property 
    def current_plan_widget(self):
        """Aktueller Plan-Tab Widget"""
        return self.tabs_plans.currentWidget() if self.tabs_plans.count() > 0 else None
    
    @property
    def current_plan_period_widget(self):
        """Aktueller Planungsmasken-Tab Widget"""
        return self.tabs_planungsmasken.currentWidget() if self.tabs_planungsmasken.count() > 0 else None
    
    @property
    def current_tab_type(self) -> str:
        """Typ des aktuell aktiven Tabs ('plans' oder 'masks')"""
        if self.tabs_left and self.tabs_left.currentWidget():
            return self.tabs_left.currentWidget().objectName()
        return ""

    def _load_actor_plan_period_mask(self, plan_period_tab_widget, person_id: UUID):
        """
        Aktiviert den Tab "Mitarbeiter" im PlanPeriodTabWidget und zeigt AvailDays-Maske der gewählten Person an.
        """
        tab_locations_employees = plan_period_tab_widget.findChild(TabBar, 'tab_bar_locations_employees')
        for i in range(tab_locations_employees.count()):
            if (tab_persons := tab_locations_employees.widget(i)).objectName() == 'tab_actor_plan_periods':
                tab_locations_employees.setCurrentIndex(i)
                # Import hier um zirkuläre Abhängigkeiten zu vermeiden
                from .frm_actor_plan_period import FrmTabActorPlanPeriods
                tab_persons: FrmTabActorPlanPeriods
                tab_persons.data_setup(None, None, person_id)
                break
    
    # === PROPERTIES ===
    
    @property 
    def current_plan_widget(self):
        """Aktueller Plan-Tab Widget"""
        return self.tabs_plans.currentWidget() if self.tabs_plans.count() > 0 else None
    
    @property
    def current_plan_period_widget(self):
        """Aktueller Planungsmasken-Tab Widget"""
        return self.tabs_planungsmasken.currentWidget() if self.tabs_planungsmasken.count() > 0 else None
    
    @property
    def current_tab_type(self) -> str:
        """Typ des aktuell aktiven Tabs ('plans' oder 'masks')"""
        if self.tabs_left and self.tabs_left.currentWidget():
            return self.tabs_left.currentWidget().objectName()
        return ""
