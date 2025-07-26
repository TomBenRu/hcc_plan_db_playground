"""
MainWindow Integration für Tab-Cache System
Erweitert MainWindow um Cache-Monitoring und -Management
Inkludiert Performance-Monitoring und erweiterte Statistiken
"""

import logging
import time
from uuid import UUID
from typing import Optional, Protocol, TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QMenu, QFileDialog, QStatusBar, QMenuBar
from PySide6.QtGui import QAction

from gui.tab_manager import TabManager
from tools.actions import MenuToolbarAction
from configuration import team_start_config
from gui.cache.performance_monitor import performance_monitor
from database import db_services, schemas

logger = logging.getLogger(__name__)


class TabCacheIntegration:
    """
    Mixin-Klasse für MainWindow Cache-Integration
    
    Fügt Cache-Management Funktionalität zur MainWindow hinzu:
    - Cache-Event Handler
    - Cache-Management Menü
    - Performance-Monitoring
    - Konfigurationsspeicherung
    """

    # Type hint für IDE-Unterstützung
    if TYPE_CHECKING:
        # Diese Attribute kommen von MainWindow
        tab_manager: TabManager
        main_menu: QMenuBar
        curr_team: Optional[object]

        def statusBar(self) -> QStatusBar: ...

        def setWindowTitle(self, title: str) -> None: ...
    
    def setup_cache_integration(self):
        """Initialisiert Cache-Integration für MainWindow"""
        self._setup_cache_monitoring()
        self._setup_cache_menu_actions()
    
    def _setup_cache_monitoring(self):
        """Richtet Cache-Monitoring und -Konfiguration ein"""
        try:
            # Cache-Einstellungen aus Konfiguration laden
            config = team_start_config.curr_start_config_handler.get_start_config()
            cache_enabled = getattr(config, 'tab_cache_enabled', True)
            max_cached_teams = getattr(config, 'max_cached_teams', 5)
            cache_expire_hours = getattr(config, 'cache_expire_hours', 24)
            
            # TabManager konfigurieren
            self.tab_manager.enable_cache(cache_enabled)
            self.tab_manager.update_cache_config(max_cached_teams, cache_expire_hours)
            
        except Exception as e:
            logger.warning(f"Cache-Konfiguration konnte nicht geladen werden: {e}")
            # Default: Cache aktiviert
            self.tab_manager.enable_cache(True)
    
    def _setup_cache_menu_actions(self):
        """Fügt Cache-Management Aktionen zum Menü hinzu"""
        try:
            # Cache-Aktionen erstellen
            self.cache_actions = {
                'show_stats': MenuToolbarAction(
                    self, None, 'Cache-Status anzeigen', 
                    'Zeigt Tab-Cache Statistiken und Performance-Metriken an', 
                    self.show_cache_stats
                ),
                'show_performance': MenuToolbarAction(
                    self, None, 'Performance-Analyse...', 
                    'Zeigt detaillierte Performance-Analyse und Trends an', 
                    self.show_performance_analysis
                ),
                'export_metrics': MenuToolbarAction(
                    self, None, 'Metriken exportieren...', 
                    'Exportiert Performance-Metriken als CSV-Datei', 
                    self.export_performance_metrics
                ),
                'clear_cache': MenuToolbarAction(
                    self, None, 'Cache leeren', 
                    'Leert den kompletten Tab-Cache (alle Teams)', 
                    self.clear_tab_cache
                ),
                'toggle_cache': MenuToolbarAction(
                    self, None, 'Cache aktivieren/deaktivieren', 
                    'Schaltet Tab-Caching ein oder aus', 
                    self.toggle_cache
                ),
                'cache_config': MenuToolbarAction(
                    self, None, 'Cache-Einstellungen...', 
                    'Konfiguriert Cache-Parameter (Max Teams, Ablaufzeit)', 
                    self.configure_cache
                )
            }
            
            # Debug: Alle verfügbaren Menüs auflisten
            available_menus = []
            for action in self.main_menu.actions():
                if action.menu():
                    available_menus.append(action.text())
            
            # Extras-Menü suchen (verschiedene Varianten probieren)
            extras_menu = None
            
            # Mögliche Menü-Namen
            possible_names = ['E&xtras', 'Extras', '&Extras', 'Eſtras']
            
            for menu_name in possible_names:
                # Über objectName suchen
                extras_menu = self.main_menu.findChild(QMenu, menu_name.replace('&', ''))
                if extras_menu:
                    break
                
                # Über Text suchen
                for action in self.main_menu.actions():
                    if action.menu() and action.text() == menu_name:
                        extras_menu = action.menu()
                        break
                
                if extras_menu:
                    break
            
            # Fallback: Suche nach "xtras" in Menü-Text
            if not extras_menu:
                for action in self.main_menu.actions():
                    if action.menu() and 'xtra' in action.text().lower():
                        extras_menu = action.menu()
                        break
            
            if extras_menu:
                extras_menu.addSeparator()
                cache_submenu = extras_menu.addMenu('Tab-Cache')
                cache_submenu.setToolTip('Tab-Cache Management und Performance-Analyse')
                
                # Cache-Management Aktionen hinzufügen
                cache_submenu.addAction(self.cache_actions['show_stats'])
                cache_submenu.addAction(self.cache_actions['show_performance'])
                cache_submenu.addSeparator()
                cache_submenu.addAction(self.cache_actions['export_metrics'])
                cache_submenu.addSeparator()
                cache_submenu.addAction(self.cache_actions['clear_cache'])
                cache_submenu.addAction(self.cache_actions['toggle_cache'])
                cache_submenu.addAction(self.cache_actions['cache_config'])
            else:
                logger.warning("Extras-Menü nicht gefunden - Cache-Menü wird als eigenes Hauptmenü hinzugefügt")
                
                # Fallback: Eigenes Cache-Menü in Hauptmenü
                cache_menu = self.main_menu.addMenu('Tab-Cache')
                cache_menu.setToolTip('Tab-Cache Management und Performance-Analyse')
                
                for action in self.cache_actions.values():
                    cache_menu.addAction(action)
                
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Cache-Menüs: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def connect_cache_signals(self):
        """Verbindet Cache-Signals mit Event-Handlers"""
        try:
            # Cache-Events
            self.tab_manager.cache_hit.connect(self._on_cache_hit)
            self.tab_manager.cache_miss.connect(self._on_cache_miss)
            self.tab_manager.cache_stats_updated.connect(self._on_cache_stats_updated)
            
        except Exception as e:
            logger.error(f"Fehler beim Verbinden der Cache-Signals: {e}")
    
    # === CACHE-EVENT HANDLER ===
    
    @Slot(UUID, int, int)
    def _on_cache_hit(self, team_id: UUID, plan_tabs: int, plan_period_tabs: int):
        """Handler für Cache-Treffer - zeigt Performance-Feedback"""
        self.statusBar().showMessage(
            f"Team-Tabs aus Cache geladen: {plan_tabs} Pläne, {plan_period_tabs} Masken", 
            3000
        )
    
    @Slot(UUID)
    def _on_cache_miss(self, team_id: UUID):
        """Handler für Cache-Fehlschlag"""
        self.statusBar().showMessage("Team-Tabs werden neu geladen...", 2000)
    
    @Slot(dict)
    def _on_cache_stats_updated(self, stats: dict):
        """Handler für Cache-Statistik Updates"""
        # Könnte für Live-Monitoring verwendet werden
        logger.debug(f"Cache-Statistiken aktualisiert: {stats['cached_teams']} Teams gecacht")
    
    # === CACHE-MANAGEMENT METHODEN ===
    
    def show_cache_stats(self):
        """Zeigt detaillierte Cache-Statistiken Dialog"""
        try:
            stats = self.tab_manager.get_cache_stats()
            
            # Statistik-Text formatieren
            stats_text = f"""Tab-Cache Statistiken

═══ Status ═══
Cache-Status: {'🟢 Aktiviert' if stats['cache_enabled'] else '🔴 Deaktiviert'}
Gecachte Teams: {stats['cached_teams']}/{stats['max_teams']}
Gesamt gecachte Tabs: {stats['total_cached_tabs']}
Cache-Ablaufzeit: {stats['cache_expire_hours']} Stunden

═══ Performance ═══
Cache-Treffer: {stats['statistics']['hits']}
Cache-Fehlschläge: {stats['statistics']['misses']}
Trefferquote: {stats['statistics']['hit_rate_percent']}%
Invalidierungen: {stats['statistics']['invalidations']}
Evictions (LRU): {stats['statistics']['evictions']}

═══ Gecachte Teams ═══"""
            
            if not stats['teams']:
                stats_text += "\n(Keine Teams im Cache)"
            else:
                for i, team_info in enumerate(stats['teams'], 1):
                    team_id_short = team_info['team_id'][:8] + "..."
                    stats_text += f"""
{i}. Team {team_id_short}
   📊 Pläne: {team_info['plan_tabs']}, Masken: {team_info['plan_period_tabs']} (Total: {team_info['total_tabs']})
   🕐 Letzter Zugriff: vor {team_info['age_minutes']} Min"""
            
            # Dialog anzeigen
            QMessageBox.information(self, 'Tab-Cache Statistiken', stats_text)
            
        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Cache-Statistiken: {e}")
            QMessageBox.critical(self, 'Fehler', f'Cache-Statistiken konnten nicht geladen werden:\n{e}')
    
    def clear_tab_cache(self):
        """Leert den Tab-Cache nach Benutzerbestätigung"""
        try:
            stats = self.tab_manager.get_cache_stats()
            
            if stats['cached_teams'] == 0:
                QMessageBox.information(self, 'Cache leeren', 'Der Tab-Cache ist bereits leer.')
                return
            
            # Bestätigung anfordern
            reply = QMessageBox.question(
                self, 'Tab-Cache leeren', 
                f'Tab-Cache wirklich leeren?\n\n'
                f'• {stats["cached_teams"]} Teams werden aus dem Cache entfernt\n'
                f'• {stats["total_cached_tabs"]} Tabs müssen neu geladen werden\n'
                f'• Team-Wechsel werden vorübergehend langsamer\n\n'
                f'Dieser Vorgang kann nicht rückgängig gemacht werden.',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                cleared_count = self.tab_manager.clear_cache()
                self.statusBar().showMessage(f"Tab-Cache geleert - {cleared_count} Teams entfernt", 5000)
                QMessageBox.information(
                    self, 'Cache geleert', 
                    f'Tab-Cache erfolgreich geleert.\n{cleared_count} Teams wurden entfernt.'
                )
                
        except Exception as e:
            logger.error(f"Fehler beim Leeren des Caches: {e}")
            QMessageBox.critical(self, 'Fehler', f'Cache konnte nicht geleert werden:\n{e}')
    
    def toggle_cache(self):
        """Schaltet Tab-Caching ein/aus"""
        try:
            current_state = self.tab_manager._cache_enabled
            new_state = not current_state
            
            if not new_state:
                # Cache deaktivieren - Warnung anzeigen
                stats = self.tab_manager.get_cache_stats()
                reply = QMessageBox.question(
                    self, 'Tab-Caching deaktivieren',
                    f'Tab-Caching wirklich deaktivieren?\n\n'
                    f'• Cache wird geleert ({stats["cached_teams"]} Teams)\n'
                    f'• Team-Wechsel werden deutlich langsamer\n'
                    f'• Performance-Vorteil geht verloren\n\n'
                    f'Sie können Caching jederzeit wieder aktivieren.',
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            # Caching umschalten
            self.tab_manager.enable_cache(new_state)
            
            # Einstellung speichern
            self._save_cache_setting('tab_cache_enabled', new_state)
            
            # Benutzer-Feedback
            status_text = f"Tab-Caching {'aktiviert' if new_state else 'deaktiviert'}"
            self.statusBar().showMessage(status_text, 5000)
            
            icon = '🟢' if new_state else '🔴'
            QMessageBox.information(
                self, 'Cache-Status geändert', 
                f'{icon} Tab-Caching wurde {status_text}.\n\n'
                f'Die Änderung wird sofort wirksam.'
            )
            
        except Exception as e:
            logger.error(f"Fehler beim Umschalten des Caches: {e}")
            QMessageBox.critical(self, 'Fehler', f'Cache-Status konnte nicht geändert werden:\n{e}')
    
    def configure_cache(self):
        """Öffnet Cache-Konfigurationsdialog"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton
            
            # Konfigurationsdialog erstellen
            dialog = QDialog(self)
            dialog.setWindowTitle('Tab-Cache Konfiguration')
            dialog.setModal(True)
            dialog.resize(400, 200)
            
            layout = QVBoxLayout(dialog)
            
            # Max Teams Einstellung
            max_teams_layout = QHBoxLayout()
            max_teams_layout.addWidget(QLabel('Maximale Anzahl gecachter Teams:'))
            max_teams_spinbox = QSpinBox()
            max_teams_spinbox.setRange(1, 20)
            max_teams_spinbox.setValue(self.tab_manager.cache_manager.max_cached_teams)
            max_teams_layout.addWidget(max_teams_spinbox)
            layout.addLayout(max_teams_layout)
            
            # Cache Expire Einstellung
            expire_layout = QHBoxLayout()
            expire_layout.addWidget(QLabel('Cache-Ablaufzeit (Stunden):'))
            expire_spinbox = QSpinBox()
            expire_spinbox.setRange(1, 168)  # 1 Stunde bis 1 Woche
            expire_spinbox.setValue(self.tab_manager.cache_manager.cache_expire_hours)
            expire_layout.addWidget(expire_spinbox)
            layout.addLayout(expire_layout)
            
            # Buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton('Übernehmen')
            cancel_button = QPushButton('Abbrechen')
            
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # Dialog anzeigen
            if dialog.exec():
                # Konfiguration übernehmen
                new_max_teams = max_teams_spinbox.value()
                new_expire_hours = expire_spinbox.value()
                
                self.tab_manager.update_cache_config(new_max_teams, new_expire_hours)
                
                # Einstellungen speichern
                self._save_cache_setting('max_cached_teams', new_max_teams)
                self._save_cache_setting('cache_expire_hours', new_expire_hours)
                
                QMessageBox.information(
                    self, 'Konfiguration gespeichert',
                    f'Cache-Konfiguration wurde aktualisiert:\n\n'
                    f'• Max Teams: {new_max_teams}\n'
                    f'• Ablaufzeit: {new_expire_hours} Stunden'
                )
                
        except Exception as e:
            logger.error(f"Fehler beim Konfigurieren des Caches: {e}")
            QMessageBox.critical(self, 'Fehler', f'Cache-Konfiguration fehlgeschlagen:\n{e}')
    
    def show_performance_analysis(self):
        """Zeigt detaillierte Performance-Analyse Dialog"""
        try:
            # Performance-Summary für letzte 24 Stunden
            summary_24h = performance_monitor.get_performance_summary(24)
            
            if summary_24h.get('total_switches', 0) == 0:
                QMessageBox.information(
                    self, 'Performance-Analyse', 
                    'Keine Team-Wechsel in den letzten 24 Stunden.\n'
                    'Performance-Analyse benötigt mindestens einige Team-Wechsel.'
                )
                return
            
            # Trends für letzte Woche
            trends_7d = performance_monitor.get_performance_trends(168)  # 7 Tage
            
            # Analyse-Text erstellen
            analysis_text = f"""📊 Performance-Analyse (letzte 24 Stunden)

═══ Überblick ═══
Team-Wechsel insgesamt: {summary_24h['total_switches']}
Durchschnittliche Dauer: {summary_24h['performance_statistics']['avg_duration_ms']:.1f}ms

═══ Cache-Performance ═══
Cache-Treffer: {summary_24h['cache_statistics']['hits']} ({summary_24h['cache_statistics']['hit_rate_percent']:.1f}%)
Cache-Fehlschläge: {summary_24h['cache_statistics']['misses']}
Ø Cache-Hit Dauer: {summary_24h['performance_statistics']['avg_cache_hit_ms']:.1f}ms
Ø Cache-Miss Dauer: {summary_24h['performance_statistics']['avg_cache_miss_ms']:.1f}ms

═══ Performance-Kategorien ═══"""
            
            for category, data in summary_24h['performance_categories'].items():
                icon = {"excellent": "⚡", "good": "🟢", "acceptable": "🟡", "slow": "🔴"}.get(category, "❓")
                analysis_text += f"\n{icon} {category.title()}: {data['count']} ({data['percentage']:.1f}%)"
            
            analysis_text += f"""

═══ Häufigste Teams ═══"""
            
            for team_name, count in summary_24h['most_used_teams'][:3]:
                analysis_text += f"\n• {team_name}: {count} Wechsel"
            
            if trends_7d.get('trend'):
                trend_icon = {"improving": "📈", "degrading": "📉", "stable": "➡️"}.get(trends_7d['trend'], "❓")
                analysis_text += f"""

═══ 7-Tage Trend ═══
{trend_icon} Trend: {trends_7d['trend']} ({trends_7d.get('trend_percentage', 0):.1f}%)
💡 Empfehlung: {trends_7d.get('recommendation', 'Keine verfügbar')}"""
            
            # Fehler-Information
            if summary_24h.get('errors', 0) > 0:
                analysis_text += f"\n\n⚠️ Fehler: {summary_24h['errors']} Team-Wechsel mit Fehlern"
            
            # Dialog anzeigen
            QMessageBox.information(self, 'Performance-Analyse', analysis_text)
            
        except Exception as e:
            logger.error(f"Fehler bei Performance-Analyse: {e}")
            QMessageBox.critical(self, 'Fehler', f'Performance-Analyse fehlgeschlagen:\n{e}')
    
    def export_performance_metrics(self):
        """Exportiert Performance-Metriken als CSV"""
        try:
            # Datei-Dialog
            filepath, _ = QFileDialog.getSaveFileName(
                self, 
                'Performance-Metriken exportieren',
                'hcc_plan_performance_metrics.csv',
                'CSV-Dateien (*.csv);;Alle Dateien (*)'
            )
            
            if not filepath:
                return
            
            # Export-Zeitraum Dialog
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QPushButton
            
            dialog = QDialog(self)
            dialog.setWindowTitle('Export-Zeitraum wählen')
            dialog.setModal(True)
            
            layout = QVBoxLayout(dialog)
            
            hours_layout = QHBoxLayout()
            hours_layout.addWidget(QLabel('Zeitraum (Stunden):'))
            hours_spinbox = QSpinBox()
            hours_spinbox.setRange(1, 720)  # Max 30 Tage
            hours_spinbox.setValue(24)
            hours_layout.addWidget(hours_spinbox)
            layout.addLayout(hours_layout)
            
            button_layout = QHBoxLayout()
            ok_button = QPushButton('Exportieren')
            cancel_button = QPushButton('Abbrechen')
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            if dialog.exec():
                hours = hours_spinbox.value()
                
                # Export durchführen
                success = performance_monitor.export_metrics_csv(filepath, hours)
                
                if success:
                    QMessageBox.information(
                        self, 'Export erfolgreich',
                        f'Performance-Metriken erfolgreich exportiert:\n{filepath}\n\n'
                        f'Zeitraum: {hours} Stunden'
                    )
                    
                    # Optional: Datei öffnen
                    reply = QMessageBox.question(
                        self, 'Datei öffnen', 
                        'Soll die exportierte CSV-Datei jetzt geöffnet werden?'
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        import os
                        os.startfile(filepath)  # Windows
                        # Für Linux/Mac: subprocess.call(['xdg-open', filepath])
                else:
                    QMessageBox.critical(self, 'Export fehlgeschlagen', 'Performance-Metriken konnten nicht exportiert werden.')
            
        except Exception as e:
            logger.error(f"Fehler beim Metriken-Export: {e}")
            QMessageBox.critical(self, 'Fehler', f'Metriken-Export fehlgeschlagen:\n{e}')
    
    def _save_cache_setting(self, key: str, value):
        """Speichert Cache-Einstellung in Konfiguration"""
        try:
            config = team_start_config.curr_start_config_handler.get_start_config()
            setattr(config, key, value)
            team_start_config.curr_start_config_handler.save_config_to_file(config)
        except Exception as e:
            logger.warning(f"Cache-Einstellung '{key}' konnte nicht gespeichert werden: {e}")
    
    # === ERWEITERTE TEAM-WECHSEL LOGIK ===
    
    def enhanced_goto_team(self, team_id: UUID):
        """Erweiterte Team-Wechsel-Logik mit Performance-Messung und detailliertem Feedback"""
        if not hasattr(self, 'tab_manager'):
            logger.error("TabManager nicht initialisiert")
            return
        
        try:
            team = db_services.Team.get(team_id)
            
            # TabManager übernimmt das Session-Management (jetzt mit Caching und Performance-Monitoring)
            self.tab_manager.set_current_team(team)
            self.curr_team: schemas.TeamShow = team
            
            self.setWindowTitle(f'hcc-plan  —  Team: {self.curr_team.name}')
            
            # Performance-Feedback aus letzter Metrik holen
            if performance_monitor.team_switch_metrics:
                last_metric = performance_monitor.team_switch_metrics[-1]
                if last_metric.team_id == team_id:
                    elapsed = last_metric.duration_ms / 1000.0
                    
                    # Detailliertes Performance-Feedback
                    if last_metric.cache_hit:
                        perf_icon = '⚡'
                        cache_info = 'aus Cache'
                        perf_category = 'sehr schnell'
                    else:
                        perf_icon = '🔄'
                        cache_info = 'neu geladen'
                        perf_category = last_metric.performance_category
                    
                    # Erweiterte Status-Message
                    status_message = f"{perf_icon} Team '{team.name}' {cache_info} ({elapsed:.2f}s, {perf_category})"
                    if last_metric.tab_count > 0:
                        status_message += f" - {last_metric.tab_count} Tabs"
                    
                    self.statusBar().showMessage(status_message, 4000)
                    
        except Exception as e:
            logger.error(f"Fehler beim Team-Wechsel: {e}")
            self.statusBar().showMessage(f"❌ Fehler beim Team-Wechsel: {str(e)[:50]}...", 5000)
            QMessageBox.critical(self, 'Team-Wechsel Fehler', f'Team konnte nicht gewechselt werden:\n{e}')
    
    def enhanced_close_event(self, event):
        """Erweiterte Close-Event Behandlung mit Cache-Persistierung"""
        try:
            if self.curr_team and hasattr(self, 'tab_manager'):
                # Aktuelle Tabs vor dem Schließen cachen
                if self.tab_manager._cache_enabled:
                    self.tab_manager.save_team_config(self.curr_team.id)
                else:
                    self.tab_manager.save_team_config(self.curr_team.id)
            
            # Optional: Cache für nächsten Start persistieren
            # self.tab_manager.clear_cache()  # Uncomment um Cache zu leeren
            
        except Exception as e:
            logger.error(f"Fehler beim Cache-Management vor Programmende: {e}")
        
        # Original closeEvent aufrufen falls vorhanden
        if hasattr(super(), 'closeEvent'):
            super().closeEvent(event)
