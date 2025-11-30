"""
FixedCastConflictsConstraint - Hard Constraints für feste Besetzungen.

Dieses Constraint implementiert die fixed_cast_vars Logik:
- Prüft ob vorgegebene Personen einem Event zugewiesen sind
- Erstellt Konfliktvariablen für nicht erfüllte Besetzungen

Die fixed_cast Struktur unterstützt AND/OR-Operatoren:
- "uuid1 and uuid2": Beide Personen müssen besetzt werden
- "uuid1 or uuid2": Mindestens eine Person muss besetzt werden
- Verschachtelte Strukturen wie "(uuid1 and uuid2) or uuid3"

TODO: Funktioniert bislang nur für CastGroups mit Event
"""

import datetime
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase
from sat_solver.constraints.fixed_cast_helpers import (
    parse_and_filter_fixed_cast,
    proof_recursive,
)
from tools.helper_functions import generate_fixed_cast_clear_text


class FixedCastConflictsConstraint(ConstraintBase):
    """
    Hard Constraint für feste Besetzungen (fixed_cast).
    
    Erstellt Konfliktvariablen die anzeigen, ob eine vorgegebene Besetzung
    NICHT erfüllt werden konnte. Diese Variablen werden im Solver minimiert.
    
    Attributes:
        fixed_cast_vars: Dict mit Konfliktvariablen pro Event
            Key: (date, time_of_day_name, event_id)
            Value: BoolVar (1 = Konflikt, 0 = Besetzung erfüllt)
    """
    
    name = "fixed_cast_conflicts"
    weight_attribute = "constraints_fixed_casts_conflicts"
    
    def __init__(self):
        super().__init__()
        self.fixed_cast_vars: dict[tuple[datetime.date, str, UUID], IntVar] = {}
    
    def apply(self) -> None:
        """
        Erstellt Constraints für feste Besetzungen.
        
        Für jede CastGroup mit fixed_cast wird eine Konfliktvariable erstellt,
        die 1 ist wenn die Besetzung NICHT erfüllt wurde.
        """
        # Initialisiere fixed_cast_vars mit Dummy-Eintrag (wie Original)
        self.fixed_cast_vars = {
            (datetime.date(1999, 1, 1), 'dummy', UUID('00000000-0000-0000-0000-000000000000')): 
                self.model.NewBoolVar('')
        }
        
        for cast_group in self.entities.cast_groups_with_event.values():
            if not cast_group.fixed_cast:
                continue

            # Parsed fixed_cast und filtere optional nicht verfügbare Personen
            fixed_cast_as_list = parse_and_filter_fixed_cast(cast_group, self.entities)
            if fixed_cast_as_list is None:
                continue

            text_fixed_cast_persons = generate_fixed_cast_clear_text(
                cast_group.fixed_cast,
                cast_group.fixed_cast_only_if_available,
                cast_group.prefer_fixed_cast_events
            )
            text_fixed_cast_var = (
                f'Datum: {cast_group.event.date: %d.%m.%y} ({cast_group.event.time_of_day.name})\n'
                f'Ort: {cast_group.event.location_plan_period.location_of_work.name_an_city}\n'
                f'Besetzung: {text_fixed_cast_persons}'
            )

            key = (cast_group.event.date, cast_group.event.time_of_day.name, cast_group.event.id)
            self.fixed_cast_vars[key] = self.model.NewBoolVar(text_fixed_cast_var)

            # Constraint: fixed_cast_vars[key] == NOT(proof_recursive(...))
            # Das bedeutet: Variable ist 1 wenn Besetzung NICHT erfüllt ist
            proof_var = proof_recursive(
                self.model, 
                self.entities, 
                fixed_cast_as_list, 
                cast_group
            )
            (self.model.Add(self.fixed_cast_vars[key] == proof_var.Not())
             .OnlyEnforceIf(self.entities.event_group_vars[cast_group.event.event_group.id]))
        
        # Penalty-Variablen für Registry
        self.penalty_vars = list(self.fixed_cast_vars.values())
