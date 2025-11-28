"""
SkillsConstraint - Soft Constraint für Mitarbeiter-Fertigkeiten.

Stellt sicher, dass Events mit ausreichend qualifizierten Mitarbeitern besetzt werden.
"""
from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase


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
    """
    
    name = "skills"
    weight_attribute = "constraints_skills"
    
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
