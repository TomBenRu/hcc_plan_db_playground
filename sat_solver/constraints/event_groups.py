"""
EventGroupsConstraint - Constraint für Event-Group-Aktivität

Dieser Constraint entspricht der Funktion add_constraints_event_groups_activity()
und stellt sicher, dass nur die korrekte Anzahl von Child-Event-Groups aktiv sind.
"""

from typing import List

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class EventGroupsConstraint(AbstractConstraint):
    """
    Constraint für Event-Group-Aktivität.
    
    Dieser Constraint implementiert die Logik, dass nur so viele Child-Event-Groups 
    aktiv sind, wie in der Parent-Event-Group mit dem Parameter 'nr_of_active_children' 
    angegeben ist.
    
    Entspricht der ursprünglichen Funktion add_constraints_event_groups_activity().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "event_groups_activity"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt keine zusätzlichen Variablen.
        
        Dieser Constraint arbeitet direkt mit den bereits existierenden
        event_group_vars aus den Entities.
        
        Returns:
            Leere Liste, da keine neuen Variablen erstellt werden
        """
        return []
    
    def add_constraints(self) -> None:
        """
        Fügt Event-Group-Aktivitäts-Constraints hinzu.
        
        Für jede Event-Group mit Children:
        - Wenn es eine Root-Event-Group ist: sum(child_vars) == nr_of_active_children
        - Wenn es eine Child-Event-Group ist: sum(child_vars) == nr_of_active_children * parent_var
        
        Dies stellt sicher, dass nur die gewünschte Anzahl von Events in jeder Gruppe aktiv ist.
        """
        constraints_added = 0
        root_groups = 0
        child_groups = 0
        
        for event_group_id, event_group in self.entities.event_groups.items():
            # Überspringe Event-Groups ohne Children
            if not event_group.children:
                continue
                
            # Bestimme die Anzahl aktiver Children
            nr_of_active_children = (
                event_group.nr_of_active_children or 
                len([c for c in event_group.children if c.children or c.event])
            )
            
            # Sammle Child-Variablen
            child_vars = [
                self.entities.event_group_vars[c.event_group_id] 
                for c in event_group.children 
                if (c.children or c.event) and c.event_group_id in self.entities.event_group_vars
            ]
            
            if not child_vars:
                continue
                
            if event_group.is_root:
                # Root-Event-Group: garantiert aktiv
                self.model.Add(sum(child_vars) == nr_of_active_children)
                constraints_added += 1
                root_groups += 1
                
                self.add_metadata(f'root_group_{event_group_id}', {
                    'nr_of_active_children': nr_of_active_children,
                    'total_children': len(child_vars)
                })
                
            else:
                # Child-Event-Group: eventuell nicht aktiv
                # Wenn die Parent-Group nicht aktiv ist, sollen keine Children aktiv sein
                if event_group_id in self.entities.event_group_vars:
                    parent_var = self.entities.event_group_vars[event_group_id]
                    self.model.Add(sum(child_vars) == nr_of_active_children * parent_var)
                    constraints_added += 1
                    child_groups += 1
                    
                    self.add_metadata(f'child_group_{event_group_id}', {
                        'nr_of_active_children': nr_of_active_children,
                        'total_children': len(child_vars)
                    })
        
        # Speichere Gesamt-Metadaten
        self.add_metadata('constraints_added', constraints_added)
        self.add_metadata('root_groups_processed', root_groups)
        self.add_metadata('child_groups_processed', child_groups)
        self.add_metadata('total_event_groups', len(self.entities.event_groups))
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        
        Returns:
            True wenn event_groups und event_group_vars verfügbar sind
        """
        if not super().validate_context():
            return False
        
        # Prüfe notwendige Datenstrukturen
        required_attrs = ['event_groups', 'event_group_vars']
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe, ob Daten vorhanden sind
        if not self.entities.event_groups:
            self.add_metadata('validation_error', "No event_groups found")
            return False
        
        if not self.entities.event_group_vars:
            self.add_metadata('validation_error', "No event_group_vars found")
            return False
        
        return True
    
    def get_event_groups_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Event-Groups zurück.
        
        Returns:
            Dictionary mit Event-Group-Statistiken
        """
        if not self.entities.event_groups:
            return {}
        
        total_groups = len(self.entities.event_groups)
        groups_with_children = sum(1 for eg in self.entities.event_groups.values() if eg.children)
        root_groups = sum(1 for eg in self.entities.event_groups.values() if eg.is_root)
        groups_with_events = sum(1 for eg in self.entities.event_groups.values() if eg.event)
        
        return {
            'total_event_groups': total_groups,
            'groups_with_children': groups_with_children,
            'root_groups': root_groups,
            'groups_with_events': groups_with_events,
            'groups_with_vars': len(self.entities.event_group_vars)
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Event-Group-Daten.
        
        Returns:
            Dictionary mit Constraint- und Event-Group-Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_event_groups_summary())
        return base_summary
