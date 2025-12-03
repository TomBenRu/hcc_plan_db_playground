"""
SkillsConstraint - Soft Constraint für Mitarbeiter-Fertigkeiten.

Stellt sicher, dass Events mit ausreichend qualifizierten Mitarbeitern besetzt werden.
"""
from typing import TYPE_CHECKING

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase, ValidationError

if TYPE_CHECKING:
    from database import schemas


class SkillsConstraint(ConstraintBase):
    """
    Soft Constraint für Mitarbeiter-Fertigkeiten (Skills).
    
    Stellt sicher, dass Events mit der geforderten Anzahl an Mitarbeitern
    besetzt werden, die über die erforderlichen Fertigkeiten verfügen.
    
    Logik:
    - Für jedes Event mit skill_groups wird geprüft
    - Die Summe der zugewiesenen Mitarbeiter mit dem jeweiligen Skill
      muss >= min(geforderte Anzahl, Besetzungsstärke) sein
    - Abweichungen werden als Penalty erfasst
    
    Implementiert das Validatable-Protocol für Plan-Validierung ohne Solver.
    """
    
    name = "skills"
    weight_attribute = "constraints_skills_match"
    
    def apply(self) -> None:
        """
        Wendet das Skills Constraint an.
        """
        for eg_id, event_group in self.entities.event_groups_with_event.items():
            # Überspringe Events ohne Skill-Anforderungen
            if not event_group.event.skill_groups:
                continue
            
            for skill_group in event_group.event.skill_groups:
                self._process_skill_group(eg_id, event_group, skill_group)
    
    def _process_skill_group(self, eg_id, event_group, skill_group) -> None:
        """
        Verarbeitet eine Skill-Group für ein Event.
        
        Args:
            eg_id: Event-Group-ID
            event_group: Event-Group-Objekt
            skill_group: Skill-Group mit Anforderungen
        """
        skill = skill_group.skill
        nr_actors = event_group.event.cast_group.nr_actors
        
        # Benötigte Anzahl Mitarbeiter mit diesem Skill
        num_employees_with_skill = min(skill_group.nr_actors, nr_actors)
        
        # Erstelle Penalty-Variable
        name = (
            f'Datum: {event_group.event.date:%d.%m.%y} ({event_group.event.time_of_day.name})\n'
            f'Ort: {event_group.event.location_plan_period.location_of_work.name_an_city}\n'
            f'benötigt: {num_employees_with_skill} Mitarbeiter mit Fertigkeit "{skill.name}"'
        )
        skill_conflict_var = self.model.NewIntVar(-10, 10, name)
        self.penalty_vars.append(skill_conflict_var)
        
        # Zähle Mitarbeiter mit diesem Skill
        num_fulfilled_cond = sum(
            self.entities.shift_vars[(adg_id, eg_id)]
            for adg_id, adg in self.entities.avail_day_groups_with_avail_day.items()
            if skill in adg.avail_day.skills
        )
        
        # Differenz der Anzahl - max(0, benötigt - erfüllt)
        self.model.AddMaxEquality(
            skill_conflict_var, 
            [0, num_employees_with_skill - num_fulfilled_cond]
        )
    
    def validate_plan(self, plan: 'schemas.PlanShow') -> list[ValidationError]:
        """
        Prüft ob alle Appointments die Skill-Anforderungen erfüllen.
        
        Für jeden Appointment wird geprüft, ob genügend Mitarbeiter mit den
        geforderten Fertigkeiten zugewiesen sind.
        """
        errors = []
        
        # Lookup-Dict für schnellen Zugriff: event_id -> event_group
        event_groups_by_event_id = {
            eg.event.id: eg 
            for eg in self.entities.event_groups_with_event.values()
        }
        
        for appointment in sorted(plan.appointments,
                                  key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)):
            event_group = event_groups_by_event_id.get(appointment.event.id)
            if not event_group:
                continue

            event = event_group.event
            
            # Überspringe Events ohne Skill-Anforderungen
            if not event.skill_groups:
                continue
            
            nr_actors = event.cast_group.nr_actors
            
            for skill_group in event.skill_groups:
                skill = skill_group.skill
                num_required = min(skill_group.nr_actors, nr_actors)
                
                # Zähle zugewiesene Mitarbeiter mit diesem Skill
                num_with_skill = 0
                for avd in appointment.avail_days:
                    adg_id = avd.avail_day_group.id
                    # Hole die Skills über entities
                    if adg_id in self.entities.avail_day_groups_with_avail_day:
                        adg = self.entities.avail_day_groups_with_avail_day[adg_id]
                        if skill in adg.avail_day.skills:
                            num_with_skill += 1
                
                # Prüfe ob genug Mitarbeiter mit dem Skill vorhanden sind
                if num_with_skill < num_required:
                    errors.append(ValidationError(
                        category="Fertigkeitskonflikt",
                        message=(
                            f'{event.date:%d.%m.%y} ({event.time_of_day.name}), '
                            f'{event.location_plan_period.location_of_work.name}: '
                            f'Benötigt {num_required} Mitarbeiter mit Fertigkeit "{skill.name}", '
                            f'aber nur {num_with_skill} zugewiesen'
                        )
                    ))
        
        return errors
