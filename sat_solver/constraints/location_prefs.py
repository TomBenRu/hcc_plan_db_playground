# sat_solver/constraints/location_prefs.py
"""
Constraint für Location-Präferenzen der Mitarbeiter.
"""

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase


class LocationPrefsConstraint(ConstraintBase):
    """
    Constraint für Location-Präferenzen (Standort-Präferenzen) der Mitarbeiter.
    
    Dieses Constraint berücksichtigt die individuellen Präferenzen der Mitarbeiter
    für bestimmte Arbeitsorte. Jeder Mitarbeiter kann für jeden Standort einen
    Präferenz-Score angeben:
    
    - Score 0: Mitarbeiter kann/will an diesem Standort NICHT arbeiten (Hard Constraint)
    - Score 0.5: Mitarbeiter arbeitet ungern an diesem Standort (Soft Constraint, hohe Penalty)
    - Score 1: Neutral (keine Präferenz)
    - Score 1.5: Mitarbeiter arbeitet gern an diesem Standort (Soft Constraint, Bonus)
    - Score 2: Mitarbeiter arbeitet sehr gern an diesem Standort (Soft Constraint, hoher Bonus)
    
    Bei Score 0 wird ein Hard Constraint gesetzt (shift_var == 0), das die Zuweisung
    komplett verhindert. Bei allen anderen Scores wird eine Penalty-Variable erstellt,
    die in die Objective-Funktion eingeht.
    
    Attributes:
        name: "location_prefs"
        weight_attribute: "constraints_location_prefs"
    
    Konfiguration:
        Die Score-Multiplikatoren werden aus der Solver-Config geladen:
        config.constraints_multipliers.sliders_location_prefs
        
        Default: {0: 100_000_000_000_000, 0.5: 10, 1: 0, 1.5: -10, 2: -20}
    """
    
    name = "location_prefs"
    weight_attribute = "constraints_location_prefs"
    
    def apply(self) -> None:
        """
        Wendet das Location-Prefs Constraint an.
        
        Iteriert über alle AvailDayGroups und deren Location-Präferenzen.
        Für jede Kombination aus Mitarbeiter-Verfügbarkeit und Event wird
        geprüft, ob eine Präferenz existiert und entsprechend behandelt.
        
        - Score 0: Hard Constraint (shift_var == 0)
        - Score > 0: Soft Constraint mit Penalty-Variable
        """
        # Hole Slider-Multiplikatoren aus Config
        multiplier_slider = self.config.constraints_multipliers.sliders_location_prefs
        
        # Erstelle Lookup-Dict für schnellen Event-Zugriff
        # Key: (date, time_index, location_id) -> Value: (event_group_id, event_group)
        event_data = self._build_event_lookup()
        
        # Iteriere über alle AvailDayGroups mit AvailDay
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups_with_avail_day.items():
            avail_day = avail_day_group.avail_day
            
            # Iteriere über alle Location-Präferenzen des AvailDays
            for loc_pref in avail_day.actor_location_prefs_defaults:
                # Überspringe gelöschte Präferenzen
                if loc_pref.prep_delete:
                    continue
                
                # Suche passendes Event für diese Präferenz
                lookup_key = (
                    avail_day.date,
                    avail_day.time_of_day.time_of_day_enum.time_index,
                    loc_pref.location_of_work.id
                )
                eg_id_and_event_group = event_data.get(lookup_key)
                
                if not eg_id_and_event_group:
                    # Kein passendes Event gefunden
                    continue
                
                eg_id, event_group = eg_id_and_event_group
                shift_var = self.entities.shift_vars[(avail_day_group_id, eg_id)]
                event = event_group.event
                
                # Score 0 = Hard Constraint: Mitarbeiter kann nicht arbeiten
                if loc_pref.score == 0:
                    self.model.Add(shift_var == 0)
                    continue
                
                # Soft Constraint: Erstelle Penalty-Variable
                penalty_var = self._create_penalty_var(
                    event=event,
                    avail_day=avail_day,
                    multiplier_slider=multiplier_slider
                )
                
                # Penalty = shift_var * event_group_var * score_multiplier
                # Die Penalty ist nur aktiv wenn sowohl die Schicht zugewiesen
                # als auch das Event aktiv ist
                self.model.AddMultiplicationEquality(
                    penalty_var,
                    [
                        shift_var,
                        self.entities.event_group_vars[eg_id],
                        multiplier_slider[loc_pref.score]
                    ]
                )
                
                self.penalty_vars.append(penalty_var)
    
    def _build_event_lookup(self) -> dict:
        """
        Erstellt ein Lookup-Dictionary für schnellen Event-Zugriff.
        
        Returns:
            Dict mit (date, time_index, location_id) als Key und
            (event_group_id, event_group) als Value
        """
        return {
            (
                event_group.event.date,
                event_group.event.time_of_day.time_of_day_enum.time_index,
                event_group.event.location_plan_period.location_of_work.id
            ): (eg_id, event_group)
            for eg_id, event_group in self.entities.event_groups_with_event.items()
        }
    
    def _create_penalty_var(
        self,
        event,
        avail_day,
        multiplier_slider: dict[float, int]
    ) -> IntVar:
        """
        Erstellt eine Penalty-Variable für eine Location-Präferenz.
        
        Args:
            event: Das Event für das die Präferenz gilt
            avail_day: Der AvailDay des Mitarbeiters
            multiplier_slider: Die Score-Multiplikatoren aus der Config
        
        Returns:
            IntVar mit aussagekräftigem Namen für Debugging
        """
        # Bestimme Wertebereich basierend auf Multiplikatoren
        # Der schlechteste Score (0.5) hat den höchsten positiven Wert
        # Der beste Score (2) hat den niedrigsten (negativen) Wert
        min_value = multiplier_slider[2]      # z.B. -20 (Bonus)
        max_value = multiplier_slider[0.5]    # z.B. 10 (Penalty)
        
        # Erstelle Variable mit aussagekräftigem Namen
        var_name = (
            f'{event.date:%d.%m.%Y} ({event.time_of_day.name}), '
            f'{event.location_plan_period.location_of_work.name}: '
            f'{avail_day.actor_plan_period.person.f_name}'
        )
        
        return self.model.NewIntVar(min_value, max_value, var_name)
