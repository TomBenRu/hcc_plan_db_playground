"""
RequiredAvailDayGroupsConstraint - Hard Constraint für erforderliche Verfügbarkeitstag-Gruppen.

Stellt sicher, dass entweder die erforderliche Mindestanzahl an Schichten
geplant wird oder gar keine.
"""
from database import schemas, db_services
from sat_solver.constraints.base import ConstraintBase


class RequiredAvailDayGroupsConstraint(ConstraintBase):
    """
    Hard Constraint: Erforderliche Verfügbarkeitstag-Gruppen.
    
    Falls die Parent-Avail-Day-Group eine Required-Avail-Day-Group hat, wird eine
    zusätzliche Bedingung hinzugefügt, dass mindestens so viele Schichten wie in 
    required_avail_day_groups geplant werden oder gar keine Schichten geplant werden.
    Falls LocationsOfWork definiert sind, werden nur Schichten an diesen Standorten gezählt.
    
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
    
    def validate_plan(self, plan: 'schemas.PlanShow') -> list['ValidationError']:
        """
        Prüft ob die Mindesteinsätze eingehalten werden.
        
        Für jeden Mitarbeiter mit required_avail_day_groups wird geprüft, ob
        entweder 0 Einsätze oder mindestens die erforderliche Anzahl geplant sind.
        """
        from uuid import UUID
        from sat_solver.constraints.base import ValidationError
        
        errors = []

        # Sammle alle im Plan verwendeten avail_day_group_ids mit zugehörigen Appointments
        adg_to_appointments: dict[UUID, list] = {}
        for appointment in plan.appointments:
            for avd in appointment.avail_days:
                adg_id = avd.avail_day_group.id
                if adg_id not in adg_to_appointments:
                    adg_to_appointments[adg_id] = []
                adg_to_appointments[adg_id].append(appointment)

        # Batch-Load aller RequiredAvailDayGroups in einer einzigen DB-Query
        # ersetzt 245+ einzelne get_from__avail_day_group()-Aufrufe (N+1-Problem).
        # Super-Root-Knoten hat avail_day_group_id=0 (int) → herausfiltern, da PostgreSQL
        # uuid=integer ablehnt.
        all_adg_ids = [adg_id for adg_id in self.entities.avail_day_groups.keys()
                       if isinstance(adg_id, UUID)]
        required_by_adg = db_services.RequiredAvailDayGroups.get_all_from__avail_day_group_ids(all_adg_ids)

        # Für jede Gruppe mit required_avail_day_groups prüfen
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups.items():
            required = required_by_adg.get(avail_day_group_id)
            if not required:
                continue
            
            # Sammle IDs der Kind-Avail-Day-Groups (rekursiv alle Nachkommen)
            child_adg_ids = self._get_all_descendant_ids(avail_day_group)
            
            # Sammle Location-IDs falls vorhanden
            location_ids = (
                {l.id for l in required.locations_of_work}
                if required.locations_of_work
                else None
            )
            
            # Zähle relevante Appointments
            relevant_appointments = []
            for adg_id in child_adg_ids:
                if adg_id not in adg_to_appointments:
                    continue
                for appointment in adg_to_appointments[adg_id]:
                    # Location-Filter anwenden falls vorhanden
                    if location_ids:
                        if appointment.event.location_plan_period.location_of_work.id not in location_ids:
                            continue
                    relevant_appointments.append(appointment)
            
            # Entferne Duplikate (ein Appointment kann mehrere avail_days haben)
            unique_appointments = list({app.id: app for app in relevant_appointments}.values())
            shift_count = len(unique_appointments)
            
            # Prüfe: Entweder 0 oder >= required
            if 0 < shift_count < required.num_avail_day_groups:
                # Ermittle den Mitarbeiter-Namen
                person_name = self._get_person_name_from_group(avail_day_group)
                
                # Sortiere Termine
                sorted_appointments = sorted(
                    unique_appointments,
                    key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index)
                )
                
                # Formatiere die Termine
                termine = [
                    f'{app.event.date:%d.%m.%y} ({app.event.time_of_day.name}) - '
                    f'{app.event.location_plan_period.location_of_work.name}'
                    for app in sorted_appointments
                ]
                termine_text = ', '.join(termine)
                
                # Location-Hinweis falls relevant
                location_hinweis = ""
                if location_ids:
                    location_names = [(f'<span style="white-space: nowrap;">{l.name_an_city.replace("-", "&#8209;")}'
                                       f'</span>')
                                      for l in required.locations_of_work]
                    location_hinweis = f" (nur für: {', '.join(location_names)})"
                
                fehlend = required.num_avail_day_groups - shift_count
                
                errors.append(ValidationError(
                    category="Mindesteinsätze nicht erreicht",
                    message=(
                        f'Betroffener Mitarbeiter: {person_name}{location_hinweis}<br>'
                        f'Aktuell {shift_count} Einsätze geplant, aber mindestens '
                        f'{required.num_avail_day_groups} erforderlich (oder keine).<br>'
                        f'Bitte {fehlend} weitere{"n" if fehlend == 1 else ""} Einsatz{"" if fehlend == 1 else "e"} '
                        f'hinzufügen oder alle entfernen.<br>'
                        f'Betroffene Termine: {termine_text}'
                    )
                ))
        
        return errors
    
    def _get_all_descendant_ids(self, avail_day_group) -> set:
        """
        Sammelt alle IDs der Nachkommen einer Gruppe (rekursiv).
        """
        ids = set()
        for child in avail_day_group.children:
            ids.add(child.avail_day_group_id)
            ids.update(self._get_all_descendant_ids(child))
        return ids
    
    def _get_person_name_from_group(self, avail_day_group) -> str:
        """
        Ermittelt den Mitarbeiter-Namen aus der AvailDayGroup-Hierarchie.
        Nutzt das erste Blatt der Gruppe, da alle Blätter zum selben Mitarbeiter gehören.
        """
        if avail_day_group.leaves and avail_day_group.leaves[0].avail_day:
            return avail_day_group.leaves[0].avail_day.actor_plan_period.person.full_name
        
        return f"Unbekannt (Gruppe {avail_day_group.avail_day_group_id})"
