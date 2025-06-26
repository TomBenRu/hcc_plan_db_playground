"""
Entities-Datenstrukturen für den SAT-Solver

Diese Datei enthält die Entities-Klasse, die alle Datenstrukturen
für den Solver kapselt. Ersetzt die globale entities-Variable.
"""

import dataclasses
from typing import Dict, Any
from uuid import UUID
from ortools.sat.python.cp_model import IntVar

from database import schemas
from sat_solver.avail_day_group_tree import AvailDayGroup
from sat_solver.event_group_tree import EventGroup
from sat_solver.cast_group_tree import CastGroup


@dataclasses.dataclass
class Entities:
    """
    Zentrale Datenstruktur für alle Solver-Entitäten.
    
    Diese Klasse kapselt alle Daten, die zuvor in der globalen 
    'entities'-Variable gespeichert wurden.
    """
    
    # Actor Plan Periods
    actor_plan_periods: Dict[UUID, schemas.ActorPlanPeriodShow] = dataclasses.field(default_factory=dict)
    
    # Avail Day Groups
    avail_day_groups: Dict[UUID, AvailDayGroup] = dataclasses.field(default_factory=dict)
    avail_day_groups_with_avail_day: Dict[UUID, AvailDayGroup] = dataclasses.field(default_factory=dict)
    avail_day_group_vars: Dict[UUID, IntVar] = dataclasses.field(default_factory=dict)
    
    # Event Groups
    event_groups: Dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_groups_with_event: Dict[UUID, EventGroup] = dataclasses.field(default_factory=dict)
    event_group_vars: Dict[UUID, IntVar] = dataclasses.field(default_factory=dict)
    
    # Cast Groups
    cast_groups: Dict[UUID, CastGroup] = dataclasses.field(default_factory=dict)
    cast_groups_with_event: Dict[UUID, CastGroup] = dataclasses.field(default_factory=dict)
    
    # Shift Variables
    shift_vars: Dict[tuple[UUID, UUID], IntVar] = dataclasses.field(default_factory=dict)
    shifts_exclusive: Dict[tuple[UUID, UUID], int] = dataclasses.field(default_factory=dict)
    # wenn value==0, kann shift mit key (adg_id, eg_id) nicht gesetzt werden
    
    def reset(self) -> None:
        """Setzt alle Entities zurück auf leere Dictionaries."""
        self.actor_plan_periods.clear()
        self.avail_day_groups.clear()
        self.avail_day_groups_with_avail_day.clear()
        self.avail_day_group_vars.clear()
        self.event_groups.clear()
        self.event_groups_with_event.clear()
        self.event_group_vars.clear()
        self.cast_groups.clear()
        self.cast_groups_with_event.clear()
        self.shift_vars.clear()
        self.shifts_exclusive.clear()
    
    def is_initialized(self) -> bool:
        """Prüft, ob die Entities initialisiert wurden."""
        return bool(self.actor_plan_periods and self.event_groups)
    
    def get_summary(self) -> Dict[str, int]:
        """Gibt eine Zusammenfassung der Entitäten-Größen zurück."""
        return {
            'actor_plan_periods': len(self.actor_plan_periods),
            'avail_day_groups': len(self.avail_day_groups),
            'avail_day_groups_with_avail_day': len(self.avail_day_groups_with_avail_day),
            'event_groups': len(self.event_groups),
            'event_groups_with_event': len(self.event_groups_with_event),
            'cast_groups': len(self.cast_groups),
            'cast_groups_with_event': len(self.cast_groups_with_event),
            'shift_vars': len(self.shift_vars),
            'shifts_exclusive': len(self.shifts_exclusive)
        }
