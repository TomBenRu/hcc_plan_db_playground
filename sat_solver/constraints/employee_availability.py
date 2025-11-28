"""
EmployeeAvailabilityConstraint - Hard Constraint für Mitarbeiter-Verfügbarkeit.

Stellt sicher, dass Mitarbeiter nur zu Schichten eingeteilt werden,
für die sie verfügbar sind.
"""
from sat_solver.constraints.base import ConstraintBase


class EmployeeAvailabilityConstraint(ConstraintBase):
    """
    Hard Constraint: Mitarbeiter können nur zu Schichten eingeteilt werden,
    für die sie verfügbar sind.
    
    Iteriert über entities.shifts_exclusive und setzt shift_vars[key] == 0
    für alle Kombinationen, bei denen der Mitarbeiter nicht verfügbar ist.
    
    Dies ist ein Hard Constraint ohne Penalty-Variablen - die Verfügbarkeit
    wird strikt erzwungen.
    """
    
    name = "employee_availability"
    weight_attribute = ""  # Hard Constraint - keine Gewichtung
    
    def apply(self) -> None:
        """
        Wendet den Verfügbarkeits-Constraint an.
        
        Für jede (actor, event)-Kombination in shifts_exclusive:
        Wenn der Wert False ist, wird die entsprechende shift_var auf 0 gesetzt,
        d.h. der Mitarbeiter kann diese Schicht nicht übernehmen.
        """
        for key, is_available in self.entities.shifts_exclusive.items():
            if not is_available:
                self.model.Add(self.entities.shift_vars[key] == 0)
