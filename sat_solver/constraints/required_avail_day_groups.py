"""
RequiredAvailDayGroupsConstraint - Hard Constraint für erforderliche Verfügbarkeitstag-Gruppen.

Stellt sicher, dass entweder die erforderliche Mindestanzahl an Schichten
geplant wird oder gar keine.
"""
from sat_solver.constraints.base import ConstraintBase


class RequiredAvailDayGroupsConstraint(ConstraintBase):
    """
    Hard Constraint: Erforderliche Verfügbarkeitstag-Gruppen.
    
    Falls die Parent-Avail-Day-Group eine Required-Avail-Day-Group hat, wird eine
    zusätzliche Bedingung hinzugefügt, dass mindestens so viele Schichten wie in 
    required_avail_day_groups geplant werden oder gar keine Schichten geplant werden.
    
    Technische Umsetzung:
    - Für jede Avail-Day-Group mit required_avail_day_groups wird geprüft
    - Eine Hilfsvariable y (BoolVar) wird erstellt
    - shift_sum wird aus allen relevanten shift_vars berechnet
    - Constraint: shift_sum == required.num_avail_day_groups * y
    - Das bedeutet: Entweder shift_sum == 0 (y=0) oder shift_sum == required (y=1)
    
    Dies ist ein **Hard Constraint** ohne Penalty-Variablen.
    """
    
    name = "required_avail_day_groups"
    weight_attribute = ""  # Hard Constraint, kein Weight benötigt
    
    def apply(self) -> None:
        """
        Wendet das RequiredAvailDayGroups Constraint an.
        
        Für jede Avail-Day-Group mit required_avail_day_groups wird ein
        Constraint hinzugefügt, das entweder die Mindestanzahl oder 0
        Schichten erzwingt.
        """
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            if required := avail_day_group.required_avail_day_groups:
                # Erstelle die Binärvariable y über NewBoolVar
                y = self.model.NewBoolVar("y")
                
                # Sammle IDs der Kind-Avail-Day-Groups
                child_adg_ids = [a.avail_day_group_id for a in avail_day_group.children]
                
                # Sammle Location-IDs falls vorhanden
                location_ids = (
                    {l.id for l in required.locations_of_work} 
                    if required.locations_of_work 
                    else None
                )
                
                # Definiere die Summe der Schichtvariablen
                shift_sum = sum(
                    shift_var
                    for (adg_id, evg_id), shift_var in self.entities.shift_vars.items()
                    if adg_id in child_adg_ids
                    and (
                        self.entities.event_groups_with_event[evg_id]
                        .event.location_plan_period.location_of_work.id in location_ids
                        if location_ids else True
                    )
                )
                
                # Füge Constraint hinzu: shift_sum entweder 0 oder required.num_avail_day_groups
                # Wenn y = 0 => shift_sum = 0, wenn y = 1 => shift_sum = required
                self.model.Add(shift_sum == required.num_avail_day_groups * y)
