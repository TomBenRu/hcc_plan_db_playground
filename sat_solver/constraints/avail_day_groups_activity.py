"""
AvailDayGroupsActivityConstraint - Hard Constraint für Verfügbarkeitstag-Gruppen-Aktivität.

Stellt sicher, dass nur die konfigurierte Anzahl von Kind-Gruppen aktiv ist.
"""
from uuid import UUID

from database import schemas
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
    
    def validate_plan(self, plan: schemas.PlanShow) -> list['ValidationError']:
        """
        Prüft ob die Anzahl aktiver Kinder-Gruppen die Limits nicht überschreitet.
        
        Für jeden Mitarbeiter wird geprüft, ob die Anzahl der im Plan verwendeten
        Verfügbarkeitstage pro Gruppe das konfigurierte Maximum (nr_of_active_children)
        nicht überschreitet.
        """
        from sat_solver.constraints.base import ValidationError
        
        errors = []
        
        # Sammle alle im Plan verwendeten avail_day_group_ids
        used_adg_ids: set[UUID] = set()
        for appointment in plan.appointments:
            for avd in appointment.avail_days:
                used_adg_ids.add(avd.avail_day_group.id)
        
        # Für jede Gruppe mit Kindern prüfen
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            # Überspringe Gruppen ohne Kinder
            if not avail_day_group.children:
                continue
            
            # Gleiche Logik wie in apply(): relevante Kinder ermitteln
            relevant_children = [
                c for c in avail_day_group.children 
                if c.children or c.avail_day
            ]
            
            # Limit ermitteln
            nr_of_active_children = (
                avail_day_group.nr_of_active_children
                or len(relevant_children)
            )
            
            # Zähle wie viele relevante Kinder tatsächlich verwendet werden
            # Ein Kind gilt als "verwendet" wenn es selbst oder ein Nachkomme im Plan ist
            active_children_count = 0
            for child in relevant_children:
                if self._is_group_or_descendant_used(child, used_adg_ids):
                    active_children_count += 1
            
            # Prüfe ob Limit überschritten
            if active_children_count > nr_of_active_children:
                # Ermittle den Mitarbeiter-Namen über die Hierarchie
                person_name = self._get_person_name_from_group(avail_day_group)
                
                errors.append(ValidationError(
                    category="Maximale Einsätze überschritten",
                    message=(
                        f'{person_name}: {active_children_count} Einsätze geplant, '
                        f'aber maximal {nr_of_active_children} erlaubt'
                    )
                ))
        
        return errors
    
    def _is_group_or_descendant_used(self, group, used_adg_ids: set[UUID]) -> bool:
        """
        Prüft ob diese Gruppe oder ein Nachkomme im Plan verwendet wird.
        """
        if group.avail_day_group_id in used_adg_ids:
            return True
        
        for child in group.children:
            if self._is_group_or_descendant_used(child, used_adg_ids):
                return True
        
        return False
    
    def _get_person_name_from_group(self, avail_day_group) -> str:
        """
        Ermittelt den Mitarbeiter-Namen aus der AvailDayGroup-Hierarchie.
        """
        # Traversiere nach oben zur Root-Gruppe
        current = avail_day_group
        while current.parent:
            current = current.parent
        
        # Die Root-Gruppe sollte die actor_plan_period Info haben
        if current.avail_day_group_db and current.avail_day_group_db.actor_plan_period:
            return current.avail_day_group_db.actor_plan_period.person.full_name
        
        return f"Unbekannt (Gruppe {avail_day_group.avail_day_group_id})"
