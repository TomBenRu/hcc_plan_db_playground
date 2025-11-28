# sat_solver/constraints/event_groups_activity.py
"""
Hard Constraint für Event-Gruppen-Aktivität.
"""

from sat_solver.constraints.base import ConstraintBase


class EventGroupsActivityConstraint(ConstraintBase):
    """
    Hard Constraint für die Aktivität von Event-Gruppen.
    
    Dieses Constraint stellt sicher, dass nur so viele Child-Event-Groups
    aktiv sind, wie in der Parent-Event-Group mit dem Parameter
    `nr_of_active_children` angegeben ist.
    
    Logik:
    - Für jede Event-Group mit Kindern wird geprüft
    - `nr_of_active_children` wird entweder explizit gesetzt oder berechnet
      als Anzahl der Kinder die selbst Kinder oder Events haben
    - Für Root-Event-Groups: sum(child_vars) == nr_of_active_children
    - Für Child-Event-Groups: sum(child_vars) == nr_of_active_children * parent_var
      (damit keine Kinder aktiv sind wenn der Parent nicht aktiv ist)
    
    Dies ist ein **Hard Constraint** ohne Penalty-Variablen.
    
    Attributes:
        name: "event_groups_activity"
        weight_attribute: "" (leer, da Hard Constraint ohne Weight)
    """
    
    name = "event_groups_activity"
    weight_attribute = ""  # Hard Constraint, kein Weight benötigt
    
    def apply(self) -> None:
        """
        Wendet das Event-Groups-Activity Constraint an.
        
        Für jede Event-Group mit Kindern wird ein Constraint hinzugefügt,
        das die Anzahl aktiver Kinder begrenzt.
        """
        for event_group_id, event_group in self.entities.event_groups.items():
            # Überspringe Event-Groups ohne Kinder
            if not event_group.children:
                continue
            
            # Berechne die Anzahl aktiver Kinder
            # Entweder explizit gesetzt oder Anzahl der relevanten Kinder
            relevant_children = [c for c in event_group.children if c.children or c.event]
            nr_of_active_children = (
                event_group.nr_of_active_children
                or len(relevant_children)
            )
            
            # Hole die Variablen für alle relevanten Kinder
            child_vars = [
                self.entities.event_group_vars[c.event_group_id]
                for c in relevant_children
            ]
            
            # Root-Event-Groups sind garantiert aktiv
            if event_group.is_root:
                self.model.Add(sum(child_vars) == nr_of_active_children)
            else:
                # Child-Event-Groups können inaktiv sein
                # In diesem Fall sollen keine Kinder aktiv sein
                self.model.Add(
                    sum(child_vars) == nr_of_active_children * self.entities.event_group_vars[event_group_id]
                )
