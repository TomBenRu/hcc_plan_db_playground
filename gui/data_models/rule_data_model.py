"""Datenmodell für Event-Planungsregeln ohne GUI-Abhängigkeiten.

Dieses Modul enthält die reine Daten-Verwaltung für Event-Planungsregeln,
getrennt von der GUI-Logik für bessere Testbarkeit und Wartbarkeit.
"""

import datetime
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from configuration.event_planing_rules import EventPlanningRules, PlanningRules, EventPlanningRulesHandlerToml
from database import db_services, schemas
from gui.data_models.schemas import RulesData, Rules
from tools.helper_functions import n_th_weekday_of_period, date_to_string


@dataclass
class ValidationResult:
    """Ergebnis der Regel-Validierung."""
    is_valid: bool
    error_message: str = ""
    warning_message: str = ""


@dataclass
class RuleDataModel:
    """Reine Daten-Verwaltung für Event-Planungsregeln ohne GUI-Abhängigkeiten.
    
    Verwaltet alle Daten und Operationen für Event-Planungsregeln:
    - Laden und Speichern von Regel-Konfigurationen
    - Validierung von Regeln
    - CRUD-Operationen für einzelne Regeln
    - Zugriff auf Plan-Period-Daten
    
    Args:
        location_plan_period_id: UUID der LocationPlanPeriod
        first_day_from_weekday: Flag ob Wochentag-basierte Datumsauswahl verwendet wird
        rules_handler: Handler für Event-Planning-Rules-Persistierung
    """
    
    location_plan_period_id: UUID
    first_day_from_weekday: bool
    rules_handler: EventPlanningRulesHandlerToml
    
    # Datenstrukturen (werden automatisch initialisiert)
    rules_data: defaultdict[int, RulesData] = field(default_factory=lambda: defaultdict(RulesData))
    rules_data_from_config: defaultdict[int, RulesData] = field(default_factory=lambda: defaultdict(RulesData))
    event_planning_rules: Optional[EventPlanningRules] = None
    location_plan_period: Optional[schemas.LocationPlanPeriodShow] = None
    plan_period: Optional[db_services.PlanPeriod] = None
    
    # UI-relevante Texte und Konfiguration
    text_description_default: str = ""
    text_description: str = ""
    header_texts: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Automatische Initialisierung nach Dataclass-Erstellung."""
        if not self.header_texts:  # Nur initialisieren wenn leer
            self._initialize_basic_header_texts()
    
    @classmethod
    def load_from_config(cls, location_plan_period_id: UUID, first_day_from_weekday: bool, 
                        rules_handler: EventPlanningRulesHandlerToml) -> 'RuleDataModel':
        """Lädt RuleDataModel aus bestehender Konfiguration.
        
        Args:
            location_plan_period_id: UUID der LocationPlanPeriod
            first_day_from_weekday: Flag für Wochentag-basierte Datumsauswahl
            rules_handler: Handler für Event-Planning-Rules
            
        Returns:
            RuleDataModel: Vollständig initialisiertes Datenmodell
            
        Raises:
            Exception: Wenn LocationPlanPeriod nicht geladen werden kann
        """
        model = cls(
            location_plan_period_id=location_plan_period_id,
            first_day_from_weekday=first_day_from_weekday,
            rules_handler=rules_handler
        )
        model._load_location_plan_period()
        model._initialize_header_texts()
        model._load_existing_rules()
        return model
    
    def _load_location_plan_period(self) -> None:
        """Lädt LocationPlanPeriod und PlanPeriod Daten aus der Datenbank."""
        try:
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period_id)
            self.plan_period: schemas.PlanPeriod = self.location_plan_period.plan_period
        except Exception as e:
            raise Exception(f"Could not load location plan period: {str(e)}")
    
    def _initialize_basic_header_texts(self) -> None:
        """Initialisiert die grundlegenden Header-Texte ohne DB-Abhängigkeiten."""
        # Note: Übersetzungen werden später in der GUI-Schicht hinzugefügt
        self.header_texts = {
            'first_day': 'First Day',
            'time_of_day': 'Time of Day', 
            'interval': 'Interval',
            'repetitions': 'Repetitions',
            'possible_count': 'Possible Count'
        }
    
    def _initialize_header_texts(self) -> None:
        """Initialisiert die Header-Texte und Location-spezifische Beschreibungen."""
        # Grundlegende Header-Texte setzen
        self._initialize_basic_header_texts()
        
        # Location-spezifische Beschreibungen (nur wenn location_plan_period verfügbar)
        if self.location_plan_period and self.plan_period:
            self.text_description_default = (
                'Here you can define how to plan the events for<br>'
                '<b>"{location}"</b> in the period '
                '<b>{start_date}-{end_date}</b>.').format(
                    location=self.location_plan_period.location_of_work.name_an_city,
                    start_date=date_to_string(self.plan_period.start),
                    end_date=date_to_string(self.plan_period.end))
            
            self.text_description = self.text_description_default
        else:
            # Fallback wenn keine Location-Daten verfügbar
            self.text_description_default = "Here you can define how to plan the events."
            self.text_description = self.text_description_default
    
    def _load_existing_rules(self) -> None:
        """Lädt bestehende Regeln aus der Konfiguration."""
        self.event_planning_rules = self.rules_handler.get_event_planning_rules(
            self.location_plan_period.location_of_work.id)
        
        if self.event_planning_rules:
            self.text_description = (
                self.text_description_default +
                '<br>Rules were loaded from a previously stored configuration.')
            
            for i, rules_data in enumerate(self.event_planning_rules.planning_rules, start=1):
                try:
                    time_of_day = db_services.TimeOfDay.get(rules_data.time_of_day_id, True)
                except Exception as e:
                    raise Exception(f"Could not load time of day data: {str(e)}")
                
                self.rules_data_from_config[i] = RulesData(
                    first_day=n_th_weekday_of_period(
                        self.plan_period.start,
                        self.plan_period.end,
                        rules_data.first_day.weekday(),
                        1),
                    time_of_day=time_of_day,
                    interval=rules_data.interval,
                    repeat=rules_data.repeat,
                    num_events=rules_data.num_events)
    
    def add_rule(self, rule_data: RulesData) -> int:
        """Fügt eine neue Regel hinzu.
        
        Args:
            rule_data: Die Regel-Daten die hinzugefügt werden sollen
            
        Returns:
            int: Index der hinzugefügten Regel
        """
        # Nächsten verfügbaren Index finden
        next_index = max(self.rules_data.keys(), default=0) + 1
        self.rules_data[next_index] = rule_data
        return next_index
    
    def remove_rule(self, rule_index: int) -> bool:
        """Entfernt eine Regel.
        
        Args:
            rule_index: Index der zu entfernenden Regel
            
        Returns:
            bool: True wenn Regel entfernt wurde, False wenn Index nicht existiert
        """
        if rule_index in self.rules_data:
            del self.rules_data[rule_index]
            return True
        return False
    
    def get_rule_data(self, rule_index: int) -> Optional[RulesData]:
        """Gibt Regel-Daten für einen Index zurück.
        
        Args:
            rule_index: Index der gewünschten Regel
            
        Returns:
            Optional[RulesData]: Regel-Daten oder None wenn Index nicht existiert
        """
        return self.rules_data.get(rule_index)
    
    def update_rule_data(self, rule_index: int, rule_data: RulesData) -> bool:
        """Aktualisiert Regel-Daten für einen Index.
        
        Args:
            rule_index: Index der zu aktualisierenden Regel
            rule_data: Neue Regel-Daten
            
        Returns:
            bool: True wenn erfolgreich aktualisiert, False wenn Index nicht existiert
        """
        if rule_index in self.rules_data:
            self.rules_data[rule_index] = rule_data
            return True
        return False
    
    def get_all_rules_count(self) -> int:
        """Gibt die Anzahl aller aktuellen Regeln zurück."""
        return len(self.rules_data)
    
    def clear_all_rules(self) -> None:
        """Entfernt alle aktuellen Regeln."""
        self.rules_data.clear()
    
    def load_rules_from_config(self) -> None:
        """Lädt gespeicherte Regeln in die aktuellen Regeln."""
        self.rules_data = self.rules_data_from_config.copy()
    
    def validate_rules(self) -> ValidationResult:
        """Validiert die konfigurierten Planungsregeln.
        
        Prüft ob Events mit gleicher Tageszeit nicht doppelt am
        selben Tag erstellt werden würden.
        
        Returns:
            ValidationResult: Ergebnis der Validierung mit Details
        """
        if len(self.rules_data) <= 1:
            return ValidationResult(is_valid=True)
        
        dict_date_time_indexes: defaultdict[datetime.date, list[int]] = defaultdict(list)
        
        for rule_index, rules in self.rules_data.items():
            for i in range(rules.num_events):
                date = rules.first_day + datetime.timedelta(days=i * rules.interval)
                dict_date_time_indexes[date].append(rules.time_of_day.time_of_day_enum.time_index)
        
        for date, time_indexes in dict_date_time_indexes.items():
            if len(set(time_indexes)) < len(time_indexes):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Multiple events scheduled at the same time on {date_to_string(date)}")
        
        return ValidationResult(is_valid=True)
    
    def get_current_rules(self) -> Rules:
        """Gibt die aktuellen Planungsregeln zurück.
        
        Note: Für cast_rule_at_same_day und same_partial_days_for_all_rules
        müssen die Werte aus der GUI übergeben werden, da diese nicht Teil
        des Datenmodells sind.
        
        Returns:
            Rules: Aktuelle Regel-Konfiguration (ohne GUI-spezifische Felder)
        """
        return Rules(
            rules_data=list(self.rules_data.values()),
            cast_rule_at_same_day=None,  # Wird von GUI gesetzt
            same_partial_days_for_all_rules=False  # Wird von GUI gesetzt
        )
    
    def save_to_config(self, cast_rule_at_same_day_id: Optional[UUID] = None, 
                      same_partial_days_for_all_rules: bool = False) -> None:
        """Speichert die aktuellen Planungsregeln zur späteren Wiederverwendung.
        
        Args:
            cast_rule_at_same_day_id: Optional ID der Cast-Regel für gleiche Tage
            same_partial_days_for_all_rules: Flag für partielle Tage bei allen Regeln
        """
        self.event_planning_rules = EventPlanningRules(
            location_of_work_id=self.location_plan_period.location_of_work.id,
            planning_rules=[
                PlanningRules(
                    first_day=r.first_day,
                    time_of_day_id=r.time_of_day.id,
                    interval=r.interval,
                    repeat=r.repeat,
                    num_events=r.num_events
                ) for r in self.rules_data.values()
            ],
            cast_rule_at_same_day_id=cast_rule_at_same_day_id,
            same_partial_days_for_all_rules=same_partial_days_for_all_rules
        )
        
        self.rules_handler.set_event_planning_rules(self.event_planning_rules)
    
    def get_location_name(self) -> str:
        """Gibt den Namen der Location zurück."""
        if self.location_plan_period and hasattr(self.location_plan_period, 'location_of_work'):
            return self.location_plan_period.location_of_work.name_an_city
        return ""
    
    def get_period_start(self) -> datetime.date:
        """Gibt das Startdatum der Planungsperiode zurück."""
        if self.plan_period and hasattr(self.plan_period, 'start'):
            return self.plan_period.start
        return datetime.date.today()
    
    def get_period_end(self) -> datetime.date:
        """Gibt das Enddatum der Planungsperiode zurück."""
        if self.plan_period and hasattr(self.plan_period, 'end'):
            return self.plan_period.end
        return datetime.date.today()
