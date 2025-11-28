"""
AvailDayGroupsActivityConstraint - Hard Constraint für Verfügbarkeitstag-Gruppen-Aktivität.

Stellt sicher, dass nur die konfigurierte Anzahl von Kind-Gruppen aktiv ist.
"""
from sat_solver.constraints.base import ConstraintBase


class AvailDayGroupsActivityConstraint(ConstraintBase):
    """
    Hard Constraint für die Aktivität von Avail-Day-Gruppen.
    
    Dieses Constraint stellt sicher, dass nur so viele Child-Avail-Day-Groups
    aktiv sind, wie in der Parent-Avail-Day-Group mit dem Parameter
    `nr_of_active_children` angegeben ist.
    
    Logik:
    - Für jede Avail-Day-Group mit Kindern wird geprüft
    - `nr_of_active_children` wird entweder explizit gesetzt oder berechnet
      als Anzahl der Kinder die selbst Kinder oder avail_day haben
    - Für Root-Avail-Day-Groups: sum(child_vars) == nr_of_active_children
    - Für Child-Avail-Day-Groups: sum(child_vars) == nr_of_active_children * parent_var
      (damit keine Kinder aktiv sind wenn der Parent nicht aktiv ist)
    
    Dies ist ein **Hard Constraint** ohne Penalty-Variablen.
    """
    
    name = "avail_day_groups_activity"
    weight_attribute = ""  # Hard Constraint, kein Weight benötigt
    
    def apply(self) -> None:
        """
        Wendet das Avail-Day-Groups-Activity Constraint an.
        
        Für jede Avail-Day-Group mit Kindern wird ein Constraint hinzugefügt,
        das die Anzahl aktiver Kinder begrenzt.
        """
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            # Überspringe Avail-Day-Groups ohne Kinder
            if not avail_day_group.children:
                continue
            
            # Berechne die Anzahl aktiver Kinder
            # Entweder explizit gesetzt oder Anzahl der relevanten Kinder
            relevant_children = [
                c for c in avail_day_group.children 
                if c.children or c.avail_day
            ]
            nr_of_active_children = (
                avail_day_group.nr_of_active_children
                or len(relevant_children)
            )
            
            # Hole die Variablen für alle relevanten Kinder
            child_vars = [
                self.entities.avail_day_group_vars[c.avail_day_group_id]
                for c in relevant_children
            ]
            
            # Root-Avail-Day-Groups sind garantiert aktiv
            if avail_day_group.is_root:
                self.model.Add(sum(child_vars) == nr_of_active_children)
            else:
                # Child-Avail-Day-Groups können inaktiv sein
                # In diesem Fall sollen keine Kinder aktiv sein
                self.model.Add(
                    sum(child_vars) == nr_of_active_children * self.entities.avail_day_group_vars[avail_day_group_id]
                )
