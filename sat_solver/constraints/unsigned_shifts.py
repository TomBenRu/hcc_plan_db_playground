"""
UnsignedShiftsConstraint - Soft Constraint für unbesetzte Schichten.

Erfasst und minimiert die Anzahl unbesetzter Schichten pro Event.
"""
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase


class UnsignedShiftsConstraint(ConstraintBase):
    """
    Soft Constraint für unbesetzte Schichten.
    
    Für jedes Event wird eine Variable erstellt, die die Anzahl der
    unbesetzten Schichten erfasst. Diese werden im Solver minimiert.
    
    Zusätzlich wird sichergestellt, dass die Summe der zugewiesenen
    Mitarbeiter nicht größer als die Besetzungsstärke sein kann.
    
    Attributes:
        unassigned_shifts_per_event: Dict mit Event-ID -> Penalty-Variable
    """
    
    name = "unsigned_shifts"
    weight_attribute = "constraints_unsigned_shifts"
    
    def __init__(self):
        super().__init__()
        self.unassigned_shifts_per_event: dict[UUID, IntVar] = {}
    
    def apply(self) -> None:
        """
        Wendet das UnsignedShifts Constraint an.
        """
        # Berechne maximale Besetzungsstärke für Variablen-Bounds
        max_nr_actors = max(
            evg.event.cast_group.nr_actors
            for evg in self.entities.event_groups_with_event.values()
        )
        
        # Erstelle Variablen für jedes Event
        self.unassigned_shifts_per_event = {
            event_group_id: self.model.NewIntVar(
                0, max_nr_actors, f'unassigned {event_group.event.date}'
            )
            for event_group_id, event_group in self.entities.event_groups_with_event.items()
        }
        
        # Füge Constraints hinzu
        for event_group_id, event_group in self.entities.event_groups_with_event.items():
            self._add_constraints_for_event(event_group_id, event_group)
        
        # Penalty-Variablen als Liste für die Registry
        self.penalty_vars = list(self.unassigned_shifts_per_event.values())
    
    def _add_constraints_for_event(self, event_group_id, event_group) -> None:
        """
        Fügt Constraints für ein einzelnes Event hinzu.
        
        Args:
            event_group_id: Event-Group-ID
            event_group: Event-Group-Objekt
        """
        nr_actors = event_group.event.cast_group.nr_actors
        event_group_var = self.entities.event_group_vars[event_group.event_group_id]
        
        # Summe aller zugewiesenen Mitarbeiter zum Event
        num_assigned_employees = sum(
            self.entities.shift_vars[(adg_id, event_group_id)]
            for adg_id in self.entities.avail_day_groups_with_avail_day
        )
        
        # Constraint: Zugewiesene <= Besetzungsstärke * Event-Aktiv
        self.model.Add(num_assigned_employees <= event_group_var * nr_actors)
        
        # Unassigned = (Event-Aktiv * Besetzungsstärke) - Zugewiesene
        # Wenn Event nicht stattfindet (event_group_var == 0), ist unassigned == 0
        self.model.Add(
            self.unassigned_shifts_per_event[event_group_id] == (
                event_group_var * nr_actors - num_assigned_employees
            )
        )
