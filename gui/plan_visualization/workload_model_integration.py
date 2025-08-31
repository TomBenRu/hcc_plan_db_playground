"""
Model-Integration für Workload Heat-Maps - HCC Plan DB Playground

Erweitert bestehende Qt Models um Workload-Daten für Heat-Map-Darstellung.
Integriert mit WorkloadCalculator und Cache-System.

Erstellt: 31. August 2025
Teil von: Workload Heat-Maps Feature Implementation - Tag 2
"""

from typing import Any, Dict, List, Optional, Union
from uuid import UUID
from PySide6.QtCore import (
    QAbstractTableModel, QModelIndex, QObject, Qt, Signal,
    QAbstractItemModel, QSortFilterProxyModel
)
from PySide6.QtWidgets import QApplication

from database.models import Person, PlanPeriod, Appointment
from gui.plan_visualization.workload_calculator import WorkloadCalculator, WorkloadCache
import logging

logger = logging.getLogger(__name__)


class WorkloadDataProvider(QObject):
    """
    Provider-Klasse für Workload-Daten mit Cache-Management
    
    Zentrale Schnittstelle zwischen Models und WorkloadCalculator.
    Verwaltet Cache-Invalidation und Performance-Optimierungen.
    """
    
    # Signal für Cache-Updates
    workloadDataChanged = Signal()
    bulkDataLoaded = Signal(UUID)  # plan_period_id
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self.workload_calculator = WorkloadCalculator()
        self.workload_cache = WorkloadCache(max_cache_age_seconds=300)  # 5 Minuten
        
        # Aktuelle Planperiode für Bulk-Operationen
        self.current_plan_period: Optional[PlanPeriod] = None
        self._bulk_workload_data: Dict[UUID, float] = {}
        
        logger.debug("WorkloadDataProvider initialisiert")
    
    def set_plan_period(self, plan_period: PlanPeriod):
        """
        Setzt neue Planperiode und triggert Bulk-Datenload
        
        Args:
            plan_period: Neue Planperiode für Workload-Berechnungen
        """
        if self.current_plan_period != plan_period:
            self.current_plan_period = plan_period
            self._bulk_workload_data.clear()
            
            if plan_period:
                self._preload_bulk_workload_data()
                
            logger.info(f"Planperiode gewechselt: {plan_period.name if plan_period else None}")
    
    def get_workload_data(self, person: Person) -> Dict[str, Any]:
        """
        Holt vollständige Workload-Daten für eine Person
        
        Args:
            person: Person-Entity
            
        Returns:
            Dict: Workload-Daten für Heat-Map-Darstellung
        """
        if not self.current_plan_period:
            return self._get_empty_workload_data(person)
        
        try:
            # Workload aus Cache oder Berechnung
            workload_percentage = self._get_cached_or_calculated_workload(person)
            
            # Zusätzliche Daten sammeln
            appointment_count = self._get_appointment_count(person)
            
            return {
                'workload_percentage': workload_percentage,
                'person_name': f"{person.f_name} {person.l_name}",
                'appointment_count': appointment_count,
                'person_id': person.id,
                'plan_period_id': self.current_plan_period.id,
                'status_text': WorkloadCalculator.get_workload_status_text(workload_percentage)
            }
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Workload-Daten für {person.f_name} {person.l_name}: {e}")
            return self._get_empty_workload_data(person)
    
    def _get_cached_or_calculated_workload(self, person: Person) -> float:
        """
        Holt Workload aus Cache oder berechnet neu
        
        Args:
            person: Person-Entity
            
        Returns:
            float: Workload-Prozentsatz
        """
        # Zuerst Bulk-Cache prüfen
        if person.id in self._bulk_workload_data:
            return self._bulk_workload_data[person.id]
        
        # Dann Individual-Cache prüfen
        cached_workload = self.workload_cache.get_cached_workload(
            person.id, self.current_plan_period.id
        )
        
        if cached_workload is not None:
            return cached_workload
        
        # Neue Berechnung
        workload = self.workload_calculator.calculate_person_workload_percentage(
            person, self.current_plan_period
        )
        
        # In Cache speichern
        self.workload_cache.cache_workload(
            person.id, self.current_plan_period.id, workload
        )
        
        return workload
    
    def _get_appointment_count(self, person: Person) -> int:
        """
        Zählt Appointments für Person in aktueller Planperiode
        
        Args:
            person: Person-Entity
            
        Returns:
            int: Anzahl Appointments
        """
        try:
            from pony.orm import select
            appointments = select(
                a for a in Appointment 
                if a.person == person and a.event.plan_period == self.current_plan_period
            )
            return len(list(appointments))
        except Exception as e:
            logger.warning(f"Fehler beim Zählen der Appointments für {person.f_name}: {e}")
            return 0
    
    def _get_empty_workload_data(self, person: Person) -> Dict[str, Any]:
        """
        Erstellt leere Workload-Daten für Fehlerfall
        
        Args:
            person: Person-Entity
            
        Returns:
            Dict: Standard-Workload-Daten
        """
        return {
            'workload_percentage': 0.0,
            'person_name': f"{person.f_name} {person.l_name}",
            'appointment_count': 0,
            'person_id': person.id,
            'plan_period_id': self.current_plan_period.id if self.current_plan_period else None,
            'status_text': "Keine Daten"
        }
    
    def _preload_bulk_workload_data(self):
        """
        Lädt Workload-Daten für alle Personen der Planperiode vor
        Performance-Optimierung für große Datasets
        """
        if not self.current_plan_period:
            return
        
        try:
            # Bulk-Cache prüfen
            cached_bulk = self.workload_cache.get_cached_bulk_workload(
                self.current_plan_period.id
            )
            
            if cached_bulk is not None:
                self._bulk_workload_data = cached_bulk
                logger.debug(f"Bulk-Workload aus Cache geladen: {len(cached_bulk)} Personen")
                self.bulkDataLoaded.emit(self.current_plan_period.id)
                return
            
            # Alle Personen der Planperiode holen
            persons = self._get_persons_for_plan_period()
            
            if not persons:
                return
            
            # Bulk-Berechnung
            bulk_workload = self.workload_calculator.calculate_bulk_workload(
                persons, self.current_plan_period
            )
            
            # Cache aktualisieren
            self._bulk_workload_data = bulk_workload
            self.workload_cache.cache_bulk_workload(
                self.current_plan_period.id, bulk_workload
            )
            
            logger.info(f"Bulk-Workload berechnet: {len(bulk_workload)} Personen")
            self.bulkDataLoaded.emit(self.current_plan_period.id)
            
        except Exception as e:
            logger.error(f"Fehler beim Preload der Bulk-Workload-Daten: {e}")
    
    def _get_persons_for_plan_period(self) -> List[Person]:
        """
        Holt alle relevanten Personen für die aktuelle Planperiode
        
        Returns:
            List[Person]: Liste der Personen
        """
        try:
            from pony.orm import select
            
            # Personen die ActorPlanPeriod-Einträge für diese Periode haben
            persons = select(
                app.person for app in self.current_plan_period.actor_plan_periods
                if app.person.prep_delete is None  # Nicht soft-deleted
            )
            
            return list(persons)
            
        except Exception as e:
            logger.error(f"Fehler beim Laden der Personen für Planperiode: {e}")
            return []
    
    def invalidate_cache(self):
        """
        Invalidiert kompletten Cache - bei Datenänderungen aufrufen
        """
        self.workload_cache.clear_cache()
        self._bulk_workload_data.clear()
        self.workloadDataChanged.emit()
        logger.info("Workload-Cache invalidiert")
    
    def invalidate_person(self, person_id: UUID):
        """
        Invalidiert Cache für spezifische Person
        
        Args:
            person_id: ID der Person
        """
        self.workload_cache.invalidate_person(person_id)
        if person_id in self._bulk_workload_data:
            del self._bulk_workload_data[person_id]
        self.workloadDataChanged.emit()
        
    def refresh_data(self):
        """
        Aktualisiert alle Workload-Daten (manueller Refresh)
        """
        self.invalidate_cache()
        if self.current_plan_period:
            self._preload_bulk_workload_data()


class WorkloadModelMixin:
    """
    Mixin-Klasse für Integration von Workload-Daten in bestehende Models
    
    Kann in bestehende QAbstractTableModel/QAbstractItemModel integriert werden
    ohne strukturelle Änderungen an der bestehenden Architektur.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # WorkloadDataProvider initialisieren
        self.workload_provider = WorkloadDataProvider(parent=self)
        
        # Signals verbinden
        self.workload_provider.workloadDataChanged.connect(self._on_workload_data_changed)
        self.workload_provider.bulkDataLoaded.connect(self._on_bulk_data_loaded)
        
        # Heat-Map aktiviert Status
        self.heat_map_enabled = False
        
    def set_heat_map_enabled(self, enabled: bool):
        """
        Aktiviert/deaktiviert Heat-Map-Daten im Model
        
        Args:
            enabled: True für Heat-Map-Aktivierung
        """
        if self.heat_map_enabled != enabled:
            self.heat_map_enabled = enabled
            
            if enabled and hasattr(self, '_current_plan_period'):
                self.workload_provider.set_plan_period(self._current_plan_period)
            
            # Model-Update triggern
            self.layoutChanged.emit()
            
            logger.debug(f"Heat-Map-Modus: {'aktiviert' if enabled else 'deaktiviert'}")
    
    def set_plan_period_for_workload(self, plan_period: PlanPeriod):
        """
        Setzt Planperiode für Workload-Berechnungen
        
        Args:
            plan_period: Planperiode-Entity
        """
        self._current_plan_period = plan_period
        
        if self.heat_map_enabled:
            self.workload_provider.set_plan_period(plan_period)
    
    def data_with_workload_support(self, index: QModelIndex, role: int, 
                                  get_person_func) -> Any:
        """
        Erweiterte data-Methode mit Workload-Unterstützung
        
        Args:
            index: Model-Index
            role: Qt-Role
            get_person_func: Funktion die Person-Entity für Index zurückgibt
            
        Returns:
            Any: Data für gegebene Role, inkl. Workload-Daten
        """
        # Heat-Map-Workload-Daten (Custom Role)
        if role == Qt.ItemDataRole.UserRole + 1 and self.heat_map_enabled:
            try:
                person = get_person_func(index)
                if person:
                    return self.workload_provider.get_workload_data(person)
            except Exception as e:
                logger.error(f"Fehler beim Holen der Workload-Daten: {e}")
                return None
        
        # Standard-Verhalten für alle anderen Rollen
        return None  # Calling model should handle standard roles
    
    def _on_workload_data_changed(self):
        """
        Callback für Workload-Daten-Änderungen
        """
        if self.heat_map_enabled:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1)
            )
    
    def _on_bulk_data_loaded(self, plan_period_id: UUID):
        """
        Callback für Bulk-Daten-Load-Completion
        
        Args:
            plan_period_id: ID der geladenen Planperiode
        """
        if self.heat_map_enabled:
            # Model-Refresh triggern
            self.layoutChanged.emit()
            logger.debug(f"Model-Update nach Bulk-Daten-Load für Planperiode {plan_period_id}")
    
    def invalidate_workload_cache(self):
        """
        Invalidiert Workload-Cache (bei Datenänderungen aufrufen)
        """
        self.workload_provider.invalidate_cache()


class WorkloadEnabledTableModel(QAbstractTableModel, WorkloadModelMixin):
    """
    Beispiel-Implementation einer Tabellen-Model-Klasse mit Workload-Support
    
    Diese Klasse zeigt wie bestehende Models erweitert werden können.
    Für die Integration in bestehende frm_plan.py Models kann das Mixin-Pattern
    verwendet werden.
    """
    
    def __init__(self, plan_period: Optional[PlanPeriod] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._persons: List[Person] = []
        self._headers: List[str] = ["Name", "Vorname", "Auslastung", "Status"]
        
        if plan_period:
            self.set_plan_period_for_workload(plan_period)
    
    def set_persons(self, persons: List[Person]):
        """
        Setzt Personen-Liste für das Model
        
        Args:
            persons: Liste der Person-Entities
        """
        self.beginResetModel()
        self._persons = persons
        self.endResetModel()
        
        # Workload-Daten neu laden wenn Heat-Map aktiv
        if self.heat_map_enabled:
            self.workload_provider.refresh_data()
    
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._persons)
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)
    
    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return self._headers[section] if section < len(self._headers) else ""
        return None
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or index.row() >= len(self._persons):
            return None
        
        person = self._persons[index.row()]
        
        # Workload-Daten Support
        workload_data = self.data_with_workload_support(
            index, role, lambda idx: self._persons[idx.row()]
        )
        if workload_data is not None:
            return workload_data
        
        # Standard Display-Daten
        if role == Qt.ItemDataRole.DisplayRole:
            column = index.column()
            if column == 0:
                return person.l_name
            elif column == 1:
                return person.f_name
            elif column == 2 and self.heat_map_enabled:
                workload_data = self.workload_provider.get_workload_data(person)
                return f"{workload_data['workload_percentage']:.0f}%"
            elif column == 3 and self.heat_map_enabled:
                workload_data = self.workload_provider.get_workload_data(person)
                return workload_data['status_text']
        
        return None


# Factory-Function für einfache Integration
def add_workload_support_to_model(model_instance: QAbstractItemModel, 
                                plan_period: Optional[PlanPeriod] = None) -> WorkloadDataProvider:
    """
    Factory-Funktion für einfache Integration von Workload-Support in bestehende Models
    
    Args:
        model_instance: Bestehende Model-Instanz
        plan_period: Optional Planperiode
        
    Returns:
        WorkloadDataProvider: Provider-Instanz für weitere Konfiguration
    """
    # WorkloadDataProvider an Model anhängen
    if not hasattr(model_instance, 'workload_provider'):
        provider = WorkloadDataProvider(parent=model_instance)
        model_instance.workload_provider = provider
        
        # Heat-Map Status
        model_instance.heat_map_enabled = False
        
        # Helper-Methoden hinzufügen
        def set_heat_map_enabled(enabled: bool):
            model_instance.heat_map_enabled = enabled
            if enabled and plan_period:
                provider.set_plan_period(plan_period)
            model_instance.layoutChanged.emit()
        
        def get_workload_data_for_index(index: QModelIndex, get_person_func):
            if model_instance.heat_map_enabled and index.isValid():
                person = get_person_func(index)
                if person:
                    return provider.get_workload_data(person)
            return None
        
        # Methoden an Model-Instanz binden
        model_instance.set_heat_map_enabled = set_heat_map_enabled
        model_instance.get_workload_data_for_index = get_workload_data_for_index
        
        logger.info(f"Workload-Support zu Model {type(model_instance).__name__} hinzugefügt")
        
        return provider
    
    return model_instance.workload_provider
