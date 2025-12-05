"""
PartnerLocationPrefsConstraint - Soft Constraint für Partner-Standort-Präferenzen.

Bewertet und optimiert die Zusammenarbeit von Mitarbeitern basierend auf
ihren gegenseitigen Präferenzen für bestimmte Standorte.
"""
import itertools
from typing import TYPE_CHECKING
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase, Validatable

if TYPE_CHECKING:
    from database import schemas


class PartnerLocationPrefsConstraint(ConstraintBase):
    """
    Soft Constraint für Partner-Standort-Präferenzen.
    
    Bewertet Kombinationen von Mitarbeitern, die gemeinsam an einem Event arbeiten,
    basierend auf ihren gegenseitigen Partner-Location-Präferenzen.
    
    Logik:
    - Für jedes Event mit mindestens 2 Mitarbeitern werden alle Duo-Kombinationen geprüft
    - Jede Kombination erhält eine Penalty-Variable basierend auf den Präferenz-Scores
    - Score 0 bedeutet: Diese Kombination sollte vermieden werden
    - Score 1-2 sind neutrale/positive Bewertungen
    
    Bei Besetzungsstärke 2 und Score 0 wird eine zusätzliche Hard-Constraint hinzugefügt,
    um die Kombination zu verhindern.
    """
    
    name = "partner_location_prefs"
    weight_attribute = "constraints_partner_loc_prefs"
    
    def apply(self) -> None:
        """
        Wendet das Partner-Location-Prefs Constraint an.
        """
        plp_multipliers = self.config.constraints_multipliers.sliders_partner_loc_prefs
        
        for eg_id, event_group in self.entities.event_groups_with_event.items():
            # Nur Events mit mindestens 2 Mitarbeitern
            if event_group.event.cast_group.nr_actors < 2:
                continue
            
            # Hole alle verfügbaren AvailDayGroups für dieses Event
            avail_day_groups = [
                adg for adg_id, adg in self.entities.avail_day_groups_with_avail_day.items()
                if self.entities.shifts_exclusive[adg_id, eg_id]
            ]
            
            # Alle Duo-Kombinationen prüfen
            for combo in itertools.combinations(avail_day_groups, 2):
                self._process_duo_combination(combo, eg_id, event_group, plp_multipliers)
    
    def _process_duo_combination(self, combo, eg_id, event_group, plp_multipliers) -> None:
        """
        Verarbeitet eine Duo-Kombination von Mitarbeitern.
        
        Args:
            combo: Tuple von zwei AvailDayGroup-Objekten
            eg_id: Event-Group-ID
            event_group: Event-Group-Objekt
            plp_multipliers: Multiplikatoren für die Penalty-Berechnung
        """
        # Überspringe wenn keine Partner-Location-Präferenzen vorhanden
        if not any(len(adg.avail_day.actor_partner_location_prefs_defaults) for adg in combo):
            return
        
        # Überspringe wenn es sich um dieselbe Person handelt
        if combo[0].avail_day.actor_plan_period.id == combo[1].avail_day.actor_plan_period.id:
            return
        
        # Erstelle Penalty-Variable
        penalty_var = self._create_penalty_var(combo, event_group, plp_multipliers)
        self.penalty_vars.append(penalty_var)
        
        # Berechne Scores
        score_0 = self._get_partner_score(combo[0], combo[1], event_group)
        score_1 = self._get_partner_score(combo[1], combo[0], event_group)
        
        # Erstelle Constraint-Logik
        self._add_penalty_constraints(combo, eg_id, event_group, penalty_var, score_0, score_1, plp_multipliers)
        
        # Hard Constraint für Exclusion bei Score 0
        self._add_exclusion_constraint(combo, eg_id, event_group, score_0, score_1)
    
    def _create_penalty_var(self, combo, event_group, plp_multipliers) -> IntVar:
        """Erstellt eine Penalty-Variable für die Duo-Kombination."""
        name = (
            f'{event_group.event.date:%d.%m.%y} ({event_group.event.time_of_day.name}), '
            f'{event_group.event.location_plan_period.location_of_work.name} '
            f'{combo[0].avail_day.actor_plan_period.person.f_name} + '
            f'{combo[1].avail_day.actor_plan_period.person.f_name}'
        )
        return self.model.NewIntVar(
            plp_multipliers[2] * 2, 
            plp_multipliers[0] * 2,
            name
        )
    
    def _get_partner_score(self, adg_from, adg_to, event_group) -> int:
        """
        Ermittelt den Partner-Präferenz-Score.
        
        Args:
            adg_from: AvailDayGroup der Person, deren Präferenz geprüft wird
            adg_to: AvailDayGroup des Partners
            event_group: Event-Group für den Standort
        
        Returns:
            Score (0-2), Standard ist 1 wenn keine Präferenz definiert
        """
        partner_id = adg_to.avail_day.actor_plan_period.person.id
        location_id = event_group.event.location_plan_period.location_of_work.id
        
        for plp in adg_from.avail_day.actor_partner_location_prefs_defaults:
            if plp.partner.id == partner_id and plp.location_of_work.id == location_id:
                return plp.score
        return 1  # Standard-Score
    
    def _add_penalty_constraints(self, combo, eg_id, event_group, penalty_var, score_0, score_1, plp_multipliers) -> None:
        """
        Fügt die Penalty-Berechnungs-Constraints hinzu.
        """
        nr_actors = event_group.event.cast_group.nr_actors
        
        # Weight basierend auf den Scores
        plp_weight_var = self.model.NewIntVar(plp_multipliers[2] * 2, plp_multipliers[0] * 2, '')
        self.model.Add(
            plp_weight_var == round(
                (plp_multipliers[score_0] + plp_multipliers[score_1]) / (nr_actors - 1)
            )
        )
        
        # shift_active_var: 1 wenn beide Personen besetzt, sonst 0
        shift_active_var = self.model.NewBoolVar('')
        self.model.AddMultiplicationEquality(
            shift_active_var,
            [
                self.entities.shift_vars[(combo[0].avail_day_group_id, eg_id)],
                self.entities.shift_vars[(combo[1].avail_day_group_id, eg_id)]
            ]
        )
        
        # all_active_var: 1 wenn zudem das Event stattfindet
        all_active_var = self.model.NewBoolVar('')
        self.model.AddMultiplicationEquality(
            all_active_var, 
            [shift_active_var, self.entities.event_group_vars[eg_id]]
        )
        
        # Finale Penalty-Berechnung
        self.model.AddMultiplicationEquality(penalty_var, [plp_weight_var, all_active_var])
    
    def _add_exclusion_constraint(self, combo, eg_id, event_group, score_0, score_1) -> None:
        """
        Fügt bei Score 0 und Besetzungsstärke 2 einen Hard Constraint hinzu.
        
        Wenn eine Person absolut nicht mit der anderen arbeiten soll und nur
        2 Personen benötigt werden, wird nur eine der beiden besetzt.
        """
        nr_actors = event_group.event.cast_group.nr_actors
        
        # Exclusion nur wenn mindestens ein Score 0 ist UND Besetzungsstärke < 3
        exclusive = 0 if (score_0 and score_1) or nr_actors >= 3 else 1
        
        if exclusive:
            self.model.Add(
                self.entities.shift_vars[(combo[0].avail_day_group_id, eg_id)]
                + self.entities.shift_vars[(combo[1].avail_day_group_id, eg_id)] < 2
            ).OnlyEnforceIf(exclusive)


    def validate_plan(self, plan: 'schemas.PlanShow') -> list['ValidationError']:
        """
        Prüft ob Personen mit Score 0 bei Besetzungsstärke 2 gemeinsam besetzt wurden.
        
        Dies ist ein Hard-Constraint-Verstoß: Bei Score 0 (Person will absolut nicht
        mit Partner arbeiten) und nur 2 benötigten Personen dürfen beide nicht
        gemeinsam besetzt sein.
        """
        from database import schemas
        from sat_solver.constraints.base import ValidationError
        
        errors = []
        
        # Lookup: event_id -> cast_group (für nr_actors)
        cast_group_by_event_id = {
            cg.event.id: cg 
            for cg in self.entities.cast_groups_with_event.values()
            if cg.event is not None
        }
        
        for appointment in plan.appointments:
            event = appointment.event
            avail_days = list(appointment.avail_days)
            
            # Nur prüfen wenn genau 2 Personen zugewiesen sind (Besetzungsstärke 2)
            if len(avail_days) != 2:
                continue
            
            # nr_actors über cast_group_by_event_id holen
            cast_group = cast_group_by_event_id.get(event.id)
            nr_actors = cast_group.nr_actors if cast_group else None
            if nr_actors is None or nr_actors >= 3:
                continue
            
            location_id = event.location_plan_period.location_of_work.id
            location_name = event.location_plan_period.location_of_work.name
            
            # Prüfe beide Richtungen der Partner-Präferenz
            avd_0, avd_1 = avail_days[0], avail_days[1]
            person_0 = avd_0.actor_plan_period.person
            person_1 = avd_1.actor_plan_period.person
            
            score_0_to_1 = self._get_partner_score_from_avail_day(avd_0, person_1.id, location_id)
            score_1_to_0 = self._get_partner_score_from_avail_day(avd_1, person_0.id, location_id)
            
            # Fehler wenn mindestens ein Score 0 ist
            if score_0_to_1 == 0 or score_1_to_0 == 0:
                # Bestimme wer wen ausschließt
                exclusion_details = []
                if score_0_to_1 == 0:
                    exclusion_details.append(f'{person_0.full_name} schließt {person_1.full_name} aus')
                if score_1_to_0 == 0:
                    exclusion_details.append(f'{person_1.full_name} schließt {person_0.full_name} aus')
                
                errors.append(ValidationError(
                    category="Partner-Ausschluss verletzt",
                    message=(
                        f'{event.date:%d.%m.%y} ({event.time_of_day.name}), {location_name}:<br>'
                        f'{" / ".join(exclusion_details)}<br>'
                        f'Bei Besetzungsstärke 2 dürfen beide nicht gemeinsam besetzt sein.'
                    )
                ))
        
        return errors
    
    def _get_partner_score_from_avail_day(
        self, 
        avail_day: 'schemas.AvailDay',
        partner_id: UUID, 
        location_id: UUID
    ) -> int:
        """
        Ermittelt den Partner-Präferenz-Score aus einem AvailDay.
        
        Args:
            avail_day: AvailDay der Person, deren Präferenz geprüft wird
            partner_id: ID des Partners
            location_id: ID der Location
        
        Returns:
            Score (0-2), Standard ist 1 wenn keine Präferenz definiert
        """
        for plp in avail_day.actor_partner_location_prefs_defaults:
            if plp.partner.id == partner_id and plp.location_of_work.id == location_id:
                return int(plp.score)
        return 1  # Standard-Score
