"""
Entities-Cache für schnelle Plan-Validierung.

Dieses Modul stellt einen Worker für das Hintergrund-Laden von Entities bereit.
Die Entities werden nach plan_period_id gecacht und können von mehreren Plänen
der gleichen PlanPeriod wiederverwendet werden.

Verwendung:
    - TabManager verwaltet den Cache: dict[UUID, Entities]
    - Beim Tab-Wechsel wird geprüft ob Entities geladen werden müssen
    - WorkerLoadEntities lädt Entities im Hintergrund
    - test_plan() verwendet gecachte Entities falls vorhanden
"""

from uuid import UUID

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class SignalsLoadEntities(QObject):
    """Signals für den Entities-Lade-Worker."""
    
    # Signal wenn Entities erfolgreich geladen wurden
    # Parameter: plan_period_id, entities
    finished = Signal(UUID, object)
    
    # Signal bei Fehler
    # Parameter: plan_period_id, error_message
    error = Signal(UUID, str)


class WorkerLoadEntities(QRunnable):
    """
    Worker für das Laden von Entities im Hintergrund.
    
    Lädt alle für die Plan-Validierung benötigten Entities:
    - event_group_tree
    - avail_day_group_tree
    - cast_group_tree
    - entities (create_data_models)
    - shifts_exclusive (populate_shifts_exclusive)
    """
    
    def __init__(self, plan_period_id: UUID):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.signals = SignalsLoadEntities()
    
    @Slot()
    def run(self):
        """Lädt Entities im Hintergrund-Thread."""
        try:
            # Lazy Import um zirkuläre Imports zu vermeiden
            from sat_solver.solver_main import (
                get_event_group_tree,
                get_avail_day_group_tree,
                get_cast_group_tree,
                create_data_models,
                populate_shifts_exclusive,
            )
            
            # Lade alle Trees und erstelle Entities
            event_group_tree = get_event_group_tree(self.plan_period_id)
            avail_day_group_tree = get_avail_day_group_tree(self.plan_period_id)
            cast_group_tree = get_cast_group_tree(self.plan_period_id)
            
            entities = create_data_models(
                event_group_tree, 
                avail_day_group_tree, 
                cast_group_tree, 
                self.plan_period_id
            )
            
            # Befülle shifts_exclusive für Verfügbarkeitsprüfungen
            populate_shifts_exclusive(entities)
            
            # Erfolg signalisieren
            self.signals.finished.emit(self.plan_period_id, entities)
            
        except Exception as e:
            # Fehler signalisieren
            self.signals.error.emit(self.plan_period_id, str(e))
