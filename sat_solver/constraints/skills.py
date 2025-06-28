"""
SkillsConstraint - Constraint für Fertigkeiten-Matching

Dieser Constraint entspricht der Funktion add_constraints_skills()
und stellt sicher, dass Events mit der erforderlichen Anzahl von
Mitarbeitern mit spezifischen Fertigkeiten besetzt werden.
"""

from typing import List

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class SkillsConstraint(AbstractConstraint):
    """
    Constraint für Fertigkeiten-Matching.
    
    Dieser Constraint stellt sicher, dass Events, die spezifische Fertigkeiten
    erfordern, mit der entsprechenden Anzahl von Mitarbeitern besetzt werden,
    die diese Fertigkeiten besitzen.
    
    Entspricht der ursprünglichen Funktion add_constraints_skills().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "skills_matching"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt Skill-Conflict-Variablen.
        
        Für jedes Event mit Skill-Anforderungen wird eine Variable erstellt,
        die die Anzahl der fehlenden Mitarbeiter mit erforderlichen Skills anzeigt.
        
        Returns:
            Liste der erstellten Skill-Conflict-Variablen
        """
        skill_conflict_vars = []
        
        for eg_id, event_group in self.entities.event_groups_with_event.items():
            event = event_group.event
            
            # Überspringe Events ohne Skill-Anforderungen
            if not event.skill_groups:
                continue
            
            # Erstelle Skill-Conflict-Variablen für jede Skill-Group
            for skill_group in event.skill_groups:
                skill = skill_group.skill
                
                # Bestimme benötigte Anzahl Mitarbeiter mit diesem Skill
                # Minimum aus geforderter Anzahl und Besetzungsstärke
                num_employees_with_skill = min(
                    skill_group.nr_actors, 
                    event.cast_group.nr_actors
                )
                
                # Erstelle Skill-Conflict-Variable
                var_name = (f'Datum: {event.date:%d.%m.%y} ({event.time_of_day.name})\n'
                           f'Ort: {event.location_plan_period.location_of_work.name_an_city}\n'
                           f'benötigt: {num_employees_with_skill} Mitarbeiter '
                           f'mit Fertigkeit "{skill.name}"')
                
                skill_conflict_var = self.model.NewIntVar(
                    -10, 10,  # Negative Werte = Übererfüllung, Positive = Mangel
                    var_name
                )
                
                skill_conflict_vars.append(skill_conflict_var)
                
                # Berechne Anzahl zugewiesener Mitarbeiter mit diesem Skill
                num_fulfilled_condition = sum(
                    self.entities.shift_vars[(adg_id, eg_id)]
                    for adg_id, adg in self.entities.avail_day_groups_with_avail_day.items()
                    if skill in adg.avail_day.skills
                    and (adg_id, eg_id) in self.entities.shift_vars
                )
                
                # Constraint: skill_conflict_var = max(0, benötigt - erfüllt)
                # Wenn mehr Mitarbeiter mit Skill zugewiesen sind als benötigt: 0
                # Wenn weniger zugewiesen sind als benötigt: positive Differenz
                self.model.AddMaxEquality(
                    skill_conflict_var, 
                    [0, num_employees_with_skill - num_fulfilled_condition]
                )
                
                # Speichere Metadaten für diesen Skill-Constraint
                self.add_metadata(f'skill_{len(skill_conflict_vars)-1}', {
                    'event_id': str(event.id),
                    'event_date': event.date.strftime('%Y-%m-%d'),
                    'location': event.location_plan_period.location_of_work.name,
                    'skill_name': skill.name,
                    'required_count': num_employees_with_skill,
                    'skill_group_id': str(skill_group.id) if hasattr(skill_group, 'id') else 'unknown'
                })
        
        self.add_metadata('total_skill_conflicts', len(skill_conflict_vars))
        return skill_conflict_vars
    
    def add_constraints(self) -> None:
        """
        Fügt zusätzliche Skills-Constraints hinzu.
        
        Die Hauptlogik ist bereits in create_variables() implementiert.
        Diese Methode kann für zusätzliche Validierungs-Constraints verwendet werden.
        """
        constraints_added = 0
        
        # Zusätzliche Skills-Constraints können hier hinzugefügt werden
        # Zum Beispiel: Skill-Kombinationen, Minimum-Skills pro Event, etc.
        
        self.add_metadata('additional_skills_constraints', constraints_added)
    
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
            'event_groups_with_event',
            'avail_day_groups_with_avail_day',
            'shift_vars'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe ob Events und AvailDays vorhanden sind
        if not self.entities.event_groups_with_event:
            self.add_metadata('validation_error', "No events found")
            return False
        
        if not self.entities.avail_day_groups_with_avail_day:
            self.add_metadata('validation_error', "No avail days found")
            return False
        
        return True
    
    def get_skills_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Skills-Daten zurück.
        
        Returns:
            Dictionary mit Skills-Statistiken
        """
        if not self.entities.event_groups_with_event:
            return {}
        
        # Analysiere Events mit Skill-Anforderungen
        total_events = len(self.entities.event_groups_with_event)
        events_with_skills = 0
        skill_requirements = []
        required_skills = set()
        
        for event_group in self.entities.event_groups_with_event.values():
            event = event_group.event
            if event.skill_groups:
                events_with_skills += 1
                
                for skill_group in event.skill_groups:
                    skill_requirements.append({
                        'skill_name': skill_group.skill.name,
                        'required_count': skill_group.nr_actors,
                        'event_cast_size': event.cast_group.nr_actors
                    })
                    required_skills.add(skill_group.skill.name)
        
        # Analysiere verfügbare Skills der Mitarbeiter
        available_skills = set()
        employee_skill_counts = {}
        
        for adg in self.entities.avail_day_groups_with_avail_day.values():
            avail_day = adg.avail_day
            person_name = avail_day.actor_plan_period.person.f_name
            
            for skill in avail_day.skills:
                available_skills.add(skill.name)
                
                if skill.name not in employee_skill_counts:
                    employee_skill_counts[skill.name] = set()
                employee_skill_counts[skill.name].add(person_name)
        
        # Konvertiere Sets zu Counts
        employee_skill_counts = {
            skill: len(employees) for skill, employees in employee_skill_counts.items()
        }
        
        # Skill-Abdeckung analysieren
        covered_skills = required_skills.intersection(available_skills)
        missing_skills = required_skills - available_skills
        
        return {
            'total_events': total_events,
            'events_with_skill_requirements': events_with_skills,
            'total_skill_requirements': len(skill_requirements),
            'unique_required_skills': len(required_skills),
            'unique_available_skills': len(available_skills),
            'skill_coverage_ratio': len(covered_skills) / len(required_skills) if required_skills else 1.0,
            'covered_skills': list(covered_skills),
            'missing_skills': list(missing_skills),
            'employee_skill_counts': employee_skill_counts,
            'skill_conflict_variables': self.get_metadata('total_skill_conflicts', 0)
        }
    
    def get_skill_requirements_details(self) -> List[dict]:
        """
        Gibt detaillierte Informationen über Skill-Anforderungen zurück.
        
        Returns:
            Liste mit Details zu jeder Skill-Anforderung
        """
        requirements = []
        
        for event_group in self.entities.event_groups_with_event.values():
            event = event_group.event
            if not event.skill_groups:
                continue
                
            for skill_group in event.skill_groups:
                requirements.append({
                    'event_date': event.date.strftime('%Y-%m-%d'),
                    'event_time': event.time_of_day.name,
                    'location': event.location_plan_period.location_of_work.name,
                    'skill_name': skill_group.skill.name,
                    'required_actors': skill_group.nr_actors,
                    'total_cast_size': event.cast_group.nr_actors,
                    'effective_requirement': min(skill_group.nr_actors, event.cast_group.nr_actors)
                })
        
        return requirements
    
    def get_available_skills_details(self) -> dict:
        """
        Gibt detaillierte Informationen über verfügbare Skills zurück.
        
        Returns:
            Dictionary mit Skills pro Mitarbeiter
        """
        skills_by_employee = {}
        
        for adg in self.entities.avail_day_groups_with_avail_day.values():
            avail_day = adg.avail_day
            person_name = avail_day.actor_plan_period.person.f_name
            
            if person_name not in skills_by_employee:
                skills_by_employee[person_name] = set()
            
            for skill in avail_day.skills:
                skills_by_employee[person_name].add(skill.name)
        
        # Konvertiere Sets zu Listen
        return {
            employee: list(skills) for employee, skills in skills_by_employee.items()
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Skills-Daten.
        
        Returns:
            Dictionary mit Constraint- und Skills-Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_skills_summary())
        return base_summary
