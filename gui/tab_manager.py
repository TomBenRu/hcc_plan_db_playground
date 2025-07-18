"""
TabManager - Verwaltung aller Tabs in hcc-plan
Extrahiert Tab-Verwaltungslogik aus MainWindow
"""

import logging
from uuid import UUID
from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot, QPoint
from PySide6.QtWidgets import QWidget, QMessageBox, QInputDialog, QMenu
from pydantic_core import ValidationError

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
        """Setzt das aktuelle Team"""
        if self.current_team != team:
            if self.current_team:
                self.save_team_config(self.current_team.id)
                self.close_all_tabs()
            
            self.current_team = team
            self.load_team_config(team.id)
            
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
        """Schließt einen Plan-Tab"""
        if 0 <= index < self.tabs_plans.count():
            widget = self.tabs_plans.widget(index)
            self.tabs_plans.close_tab_and_delete_widget(index)
            self.tab_closed.emit("plan", widget)
            return True
        return False
    
    def close_plan_period_tab(self, index: int) -> bool:
        """Schließt einen Planungsmasken-Tab"""
        if 0 <= index < self.tabs_planungsmasken.count():
            widget = self.tabs_planungsmasken.widget(index)
            self.tabs_planungsmasken.close_tab_and_delete_widget(index)
            self.tab_closed.emit("plan_period", widget)
            return True
        return False
    
    def close_all_tabs(self):
        """Schließt alle Tabs"""
        # Alle Plan-Tabs schließen
        while self.tabs_plans.count() > 0:
            self.close_plan_tab(0)
            
        # Alle Planungsmasken-Tabs schließen  
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
