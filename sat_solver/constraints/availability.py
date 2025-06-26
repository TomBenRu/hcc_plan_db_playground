"""
EmployeeAvailabilityConstraint - Constraint für Mitarbeiterverfügbarkeit

Dieser Constraint stellt sicher, dass nur verfügbare Mitarbeiter-Schicht-Kombinationen
zugewiesen werden können. Er entspricht der Funktion add_constraints_employee_availability()
aus der alten Implementation.
"""

from typing import List

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class EmployeeAvailabilityConstraint(AbstractConstraint):
    """
    Constraint für Mitarbeiterverfügbarkeit.
    
    Dieser Constraint implementiert die Logik, dass shift_vars auf 0 gesetzt werden,
    wenn sie in shifts_exclusive als nicht verfügbar (Wert 0) markiert sind.
    
    Dies entspricht der ursprünglichen Funktion add_constraints_employee_availability().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "employee_availability"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt keine zusätzlichen Variablen.
        
        Dieser Constraint arbeitet direkt mit den bereits existierenden
        shift_vars aus den Entities.
        
        Returns:
            Leere Liste, da keine neuen Variablen erstellt werden
        """
        return []
    
    def add_constraints(self) -> None:
        """
        Fügt Verfügbarkeits-Constraints hinzu.
        
        Für jede (avail_day_group_id, event_group_id) Kombination in shifts_exclusive:
        - Wenn der Wert 0 ist, wird die entsprechende shift_var auf 0 gesetzt
        - Dies verhindert unmögliche Zuweisungen basierend auf:
          * Zeitfenster-Konflikten
          * Location-Präferenz-Score von 0
          * Anderen Verfügbarkeits-Einschränkungen
        """
        constraints_added = 0
        
        for key, availability_value in self.entities.shifts_exclusive.items():
            if availability_value == 0:
                # Hole die entsprechende shift_var
                if key in self.entities.shift_vars:
                    shift_var = self.entities.shift_vars[key]
                    
                    # Setze die shift_var auf 0 (nicht verfügbar)
                    self.model.Add(shift_var == 0)
                    constraints_added += 1
        
        # Speichere Metadaten über die hinzugefügten Constraints
        self.add_metadata('constraints_added', constraints_added)
        self.add_metadata('total_shift_combinations', len(self.entities.shifts_exclusive))
        self.add_metadata('unavailable_combinations', 
                         sum(1 for val in self.entities.shifts_exclusive.values() if val == 0))
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        
        Returns:
            True wenn shifts_exclusive und shift_vars verfügbar sind
        """
        if not super().validate_context():
            return False
        
        # Prüfe, ob notwendige Daten vorhanden sind
        if not hasattr(self.entities, 'shifts_exclusive'):
            return False
        
        if not hasattr(self.entities, 'shift_vars'):
            return False
        
        # Prüfe, ob die Daten nicht leer sind
        if not self.entities.shifts_exclusive:
            return False
        
        if not self.entities.shift_vars:
            return False
        
        # Prüfe Konsistenz zwischen shifts_exclusive und shift_vars
        exclusive_keys = set(self.entities.shifts_exclusive.keys())
        shift_var_keys = set(self.entities.shift_vars.keys())
        
        if exclusive_keys != shift_var_keys:
            self.add_metadata('validation_error', 
                            f"Mismatch between shifts_exclusive keys ({len(exclusive_keys)}) "
                            f"and shift_vars keys ({len(shift_var_keys)})")
            return False
        
        return True
    
    def get_availability_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Verfügbarkeitsdaten zurück.
        
        Returns:
            Dictionary mit Verfügbarkeits-Statistiken
        """
        if not self.entities.shifts_exclusive:
            return {}
        
        total_combinations = len(self.entities.shifts_exclusive)
        available_combinations = sum(1 for val in self.entities.shifts_exclusive.values() if val == 1)
        unavailable_combinations = total_combinations - available_combinations
        
        return {
            'total_shift_combinations': total_combinations,
            'available_combinations': available_combinations,
            'unavailable_combinations': unavailable_combinations,
            'availability_ratio': available_combinations / total_combinations if total_combinations > 0 else 0
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Verfügbarkeitsdaten.
        
        Returns:
            Dictionary mit Constraint- und Verfügbarkeitsdaten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_availability_summary())
        return base_summary


# Hilfsfunktion für Backward-Compatibility mit der alten API
def add_constraints_employee_availability_legacy(model, entities):
    """
    Legacy-Wrapper für die alte add_constraints_employee_availability Funktion.
    
    Diese Funktion bietet Rückwärtskompatibilität mit der bestehenden API,
    während sie intern die neue Constraint-Architektur verwendet.
    
    Args:
        model: CP-SAT Model (wird ignoriert, da im context enthalten)
        entities: Entities-Objekt (wird ignoriert, da im context enthalten)
    
    Note:
        Diese Funktion sollte langfristig durch die neue Architektur ersetzt werden.
    """
    # TODO: Implementation für Rückwärtskompatibilität
    # Dies wird implementiert, wenn die Migration der solver_main.py erfolgt
    pass
