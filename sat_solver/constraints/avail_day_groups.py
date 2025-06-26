"""
AvailDayGroupsConstraint - Constraint für AvailDay-Group-Aktivität

Dieser Constraint entspricht den Funktionen:
- add_constraints_avail_day_groups_activity()
- add_constraints_required_avail_day_groups()
- add_constraints_num_shifts_in_avail_day_groups()
"""

from typing import List

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class AvailDayGroupsConstraint(AbstractConstraint):
    """
    Constraint für AvailDay-Group-Aktivität und zugehörige Regeln.
    
    Dieser Constraint kombiniert mehrere ursprüngliche Funktionen:
    1. Aktivitäts-Constraints für AvailDay-Groups
    2. Required AvailDay-Groups Constraints
    3. Schicht-Constraints in inaktiven AvailDay-Groups
    
    Entspricht den ursprünglichen Funktionen:
    - add_constraints_avail_day_groups_activity()
    - add_constraints_required_avail_day_groups()  
    - add_constraints_num_shifts_in_avail_day_groups()
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "avail_day_groups"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt zusätzliche Variablen für required_avail_day_groups.
        
        Returns:
            Liste der erstellten Variablen für Required-AvailDay-Groups
        """
        required_vars = []
        
        # Erstelle Variablen für Required AvailDay Groups
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            if required := avail_day_group.required_avail_day_groups:
                # Erstelle die Binärvariable y über NewBoolVar
                y_var = self.model.NewBoolVar(f"required_adg_{avail_day_group_id}")
                required_vars.append(y_var)
                
                # Speichere Variable für späteren Zugriff
                self.add_metadata(f'required_var_{avail_day_group_id}', y_var)
        
        return required_vars
    
    def add_constraints(self) -> None:
        """
        Fügt alle AvailDay-Group-Constraints hinzu.
        
        1. Aktivitäts-Constraints
        2. Required AvailDay-Groups Constraints  
        3. Schicht-Constraints für inaktive Groups
        """
        self._add_activity_constraints()
        self._add_required_constraints() 
        self._add_shift_constraints()
    
    def _add_activity_constraints(self) -> None:
        """
        Fügt AvailDay-Group-Aktivitäts-Constraints hinzu.
        
        Entspricht add_constraints_avail_day_groups_activity().
        """
        constraints_added = 0
        
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            # Überspringe Groups ohne Children
            if not avail_day_group.children:
                continue
                
            # Bestimme Anzahl aktiver Children
            nr_of_active_children = (
                avail_day_group.nr_of_active_children or
                len([c for c in avail_day_group.children if c.children or c.avail_day])
            )
            
            # Sammle Child-Variablen
            child_vars = [
                self.entities.avail_day_group_vars[c.avail_day_group_id]
                for c in avail_day_group.children
                if (c.children or c.avail_day) and c.avail_day_group_id in self.entities.avail_day_group_vars
            ]
            
            if not child_vars:
                continue
                
            if avail_day_group.is_root:
                # Root-AvailDay-Group: garantiert aktiv
                self.model.Add(sum(child_vars) == nr_of_active_children)
                constraints_added += 1
                
            else:
                # Child-AvailDay-Group: eventuell nicht aktiv
                if avail_day_group_id in self.entities.avail_day_group_vars:
                    parent_var = self.entities.avail_day_group_vars[avail_day_group_id]
                    self.model.Add(sum(child_vars) == nr_of_active_children * parent_var)
                    constraints_added += 1
        
        self.add_metadata('activity_constraints_added', constraints_added)
    
    def _add_required_constraints(self) -> None:
        """
        Fügt Required-AvailDay-Groups-Constraints hinzu.
        
        Entspricht add_constraints_required_avail_day_groups().
        """
        constraints_added = 0
        
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            if required := avail_day_group.required_avail_day_groups:
                # Hole die zuvor erstellte y-Variable
                y_var = self.get_metadata(f'required_var_{avail_day_group_id}')
                if y_var is None:
                    continue
                
                # Definiere die Summe der Schichtvariablen
                shift_sum = sum(
                    shift_var
                    for (adg_id, evg_id), shift_var in self.entities.shift_vars.items()
                    if adg_id in [a.avail_day_group_id for a in avail_day_group.children]
                    and (
                        self.entities.event_groups_with_event[evg_id].event.location_plan_period.location_of_work.id
                        in {l.id for l in required.locations_of_work} 
                        if required.locations_of_work 
                        else True
                    )
                )
                
                # Constraint: shift_sum == required.num_avail_day_groups * y
                self.model.Add(shift_sum == required.num_avail_day_groups * y_var)
                constraints_added += 1
                
                self.add_metadata(f'required_constraint_{avail_day_group_id}', {
                    'num_required': required.num_avail_day_groups,
                    'locations_count': len(required.locations_of_work) if required.locations_of_work else 0
                })
        
        self.add_metadata('required_constraints_added', constraints_added)
    
    def _add_shift_constraints(self) -> None:
        """
        Fügt Schicht-Constraints für inaktive AvailDay-Groups hinzu.
        
        Entspricht add_constraints_num_shifts_in_avail_day_groups().
        """
        constraints_added = 0
        
        # Wenn eine AvailDay-Group-Variable auf False gesetzt ist,
        # müssen auch die zugehörigen Shift-Variablen auf False gesetzt sein
        for (adg_id, event_group_id), shift_var in self.entities.shift_vars.items():
            if adg_id in self.entities.avail_day_group_vars:  # not_sure: diese Prüfung ist nicht nötig
                avail_day_group_var = self.entities.avail_day_group_vars[adg_id]
                
                # shift_var * (NOT avail_day_group_var) == 0
                # Das bedeutet: wenn avail_day_group_var == False, dann shift_var == False
                self.model.AddMultiplicationEquality(0, [shift_var, avail_day_group_var.Not()])
                constraints_added += 1
        
        self.add_metadata('shift_constraints_added', constraints_added)
    
    def validate_context(self) -> bool:
        """
        Validiert, ob der Kontext für diesen Constraint geeignet ist.
        
        Returns:
            True wenn alle notwendigen Datenstrukturen verfügbar sind
        """
        if not super().validate_context():
            return False
        
        # Prüfe notwendige Datenstrukturen
        required_attrs = [
            'avail_day_groups', 
            'avail_day_group_vars', 
            'shift_vars',
            'event_groups_with_event'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe, ob Daten vorhanden sind
        if not self.entities.avail_day_groups:
            self.add_metadata('validation_error', "No avail_day_groups found")
            return False
        
        return True
    
    def get_avail_day_groups_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der AvailDay-Groups zurück.
        
        Returns:
            Dictionary mit AvailDay-Group-Statistiken
        """
        if not self.entities.avail_day_groups:
            return {}
        
        total_groups = len(self.entities.avail_day_groups)
        groups_with_children = sum(1 for adg in self.entities.avail_day_groups.values() if adg.children)
        root_groups = sum(1 for adg in self.entities.avail_day_groups.values() if adg.is_root)
        groups_with_avail_days = sum(1 for adg in self.entities.avail_day_groups.values() if adg.avail_day)
        groups_with_required = sum(1 for adg in self.entities.avail_day_groups.values() if adg.required_avail_day_groups)
        
        return {
            'total_avail_day_groups': total_groups,
            'groups_with_children': groups_with_children,
            'root_groups': root_groups,
            'groups_with_avail_days': groups_with_avail_days,
            'groups_with_required': groups_with_required,
            'groups_with_vars': len(self.entities.avail_day_group_vars)
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit AvailDay-Group-Daten.
        
        Returns:
            Dictionary mit Constraint- und AvailDay-Group-Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_avail_day_groups_summary())
        return base_summary
