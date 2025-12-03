"""
AvailDayGroupsActivityConstraint - Hard Constraint für Verfügbarkeitstag-Gruppen-Aktivität.

Stellt sicher, dass nur die konfigurierte Anzahl von Kind-Gruppen aktiv ist.
"""
from uuid import UUID

from database.schemas import PlanShow
from sat_solver.constraints.base import ConstraintBase, ValidationError


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
    
    def validate_plan(self, plan: PlanShow) -> list[ValidationError]:
        """
        Prüft ob die Anzahl aktiver Kinder-Gruppen die Limits nicht überschreitet.
        
        Für jeden Mitarbeiter wird geprüft, ob die Anzahl der im Plan verwendeten
        Verfügbarkeitstage pro Gruppe das konfigurierte Maximum (nr_of_active_children)
        nicht überschreitet.
        """

        errors = []
        
        # Sammle alle im Plan verwendeten avail_day_group_ids mit zugehörigen Appointments
        adg_to_appointments: dict[UUID, list] = {}
        for appointment in plan.appointments:
            for avd in appointment.avail_days:
                adg_id = avd.avail_day_group.id
                if adg_id not in adg_to_appointments:
                    adg_to_appointments[adg_id] = []
                adg_to_appointments[adg_id].append(appointment)
        
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
            
            # Sammle aktive Kinder und deren Appointments (gruppiert)
            active_children_with_appointments: list[tuple] = []
            for child in relevant_children:
                child_appointments = self._get_appointments_for_group(child, adg_to_appointments)
                if child_appointments:
                    active_children_with_appointments.append((child, child_appointments))
            
            active_children_count = len(active_children_with_appointments)
            
            # Prüfe ob Limit überschritten
            if active_children_count > nr_of_active_children:
                # Ermittle den Mitarbeiter-Namen über die Gruppen-Hierarchie
                person_name = self._get_person_name_from_group(avail_day_group)
                
                # Formatiere die Termine gruppiert
                grouped_termine = []
                for child, appointments in active_children_with_appointments:
                    # Sortiere Appointments innerhalb der Gruppe
                    sorted_apps = sorted(
                        appointments,
                        key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)
                    )
                    # Entferne Duplikate innerhalb der Gruppe
                    unique_apps = list({app.id: app for app in sorted_apps}.values())
                    
                    termine_in_gruppe = [
                        f'{app.event.date:%d.%m.%y} ({app.event.time_of_day.name}) - '
                        f'{app.event.location_plan_period.location_of_work.name}'
                        for app in unique_apps
                    ]
                    grouped_termine.append(', '.join(termine_in_gruppe))
                
                # Formatiere als Bullet-Liste
                termine_text = '<br>'.join(f'• {gruppe}' for gruppe in grouped_termine)
                
                errors.append(ValidationError(
                    category="Maximale Einsätze überschritten",
                    message=(
                        f'Betroffener Mitarbeiter: {person_name}<br>'
                        f'Betroffene gruppierte Termine:<br>{termine_text}<br>'
                        f'Es {"ist nur eine Gruppe" if nr_of_active_children == 1 else f"sind nur {nr_of_active_children} Gruppen"} erlaubt.'
                    )
                ))
        
        return errors
    
    def _is_group_or_descendant_used(self, group, used_adg_ids: set[int]) -> bool:
        """
        Prüft ob diese Gruppe oder ein Nachkomme im Plan verwendet wird.
        """
        if group.avail_day_group_id in used_adg_ids:
            return True
        
        for child in group.children:
            if self._is_group_or_descendant_used(child, used_adg_ids):
                return True
        
        return False
    
    def _get_appointments_for_group(self, group, adg_to_appointments: dict[UUID, list]) -> list:
        """
        Sammelt alle Appointments für diese Gruppe und ihre Nachkommen.
        """
        appointments = []
        
        if group.avail_day_group_id in adg_to_appointments:
            appointments.extend(adg_to_appointments[group.avail_day_group_id])
        
        for child in group.children:
            appointments.extend(self._get_appointments_for_group(child, adg_to_appointments))
        
        return appointments
    
    def _get_person_name_from_group(self, avail_day_group) -> str:
        """
        Ermittelt den Mitarbeiter-Namen aus der AvailDayGroup-Hierarchie.
        Nutzt das erste Blatt der Gruppe, da alle Blätter zum selben Mitarbeiter gehören.
        """
        if avail_day_group.leaves and avail_day_group.leaves[0].avail_day:
            return avail_day_group.leaves[0].avail_day.actor_plan_period.person.full_name
        
        return f"Unbekannt (Gruppe {avail_day_group.avail_day_group_id})"
    
