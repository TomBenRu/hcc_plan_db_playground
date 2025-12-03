"""
EmployeeAvailabilityConstraint - Hard Constraint für Mitarbeiter-Verfügbarkeit.

Stellt sicher, dass Mitarbeiter nur zu Schichten eingeteilt werden,
für die sie verfügbar sind.
"""
from typing import TYPE_CHECKING

from database import db_services
from sat_solver.constraints.base import ConstraintBase, ValidationError

if TYPE_CHECKING:
    from database import schemas


class EmployeeAvailabilityConstraint(ConstraintBase):
    """
    Hard Constraint: Mitarbeiter können nur zu Schichten eingeteilt werden,
    für die sie verfügbar sind.
    
    Iteriert über entities.shifts_exclusive und setzt shift_vars[key] == 0
    für alle Kombinationen, bei denen der Mitarbeiter nicht verfügbar ist.
    
    Dies ist ein Hard Constraint ohne Penalty-Variablen - die Verfügbarkeit
    wird strikt erzwungen.
    
    Implementiert das Validatable-Protocol für Plan-Validierung ohne Solver.
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
    
    def validate_plan(self, plan: 'schemas.PlanShow') -> list[ValidationError]:
        """
        Prüft ob alle Zuweisungen im Plan die Verfügbarkeit respektieren.
        
        Für jeden Appointment wird geprüft, ob die zugewiesenen Mitarbeiter
        für das Event verfügbar sind (shifts_exclusive).
        """
        errors = []
        
        for appointment in sorted(plan.appointments,
                                  key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
            event = appointment.event
            event_group_id = db_services.Event.get(event.id).event_group.id
            
            for avd in appointment.avail_days:
                adg_id = avd.avail_day_group.id
                key = (adg_id, event_group_id)
                
                # Prüfe ob diese Kombination in shifts_exclusive existiert und verfügbar ist
                if key in self.entities.shifts_exclusive:
                    if not self.entities.shifts_exclusive[key]:
                        person_name = avd.actor_plan_period.person.full_name
                        errors.append(ValidationError(
                            category="Mitarbeiter-Verfügbarkeit",
                            message=(
                                f'{person_name} ist am {event.date:%d.%m.%y} '
                                f'({event.time_of_day.name}) nicht verfügbar für '
                                f'{event.location_plan_period.location_of_work.name}'
                            )
                        ))
        
        return errors
