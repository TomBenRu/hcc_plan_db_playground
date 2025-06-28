"""
PartnerLocationPrefsConstraint - Constraint für Partner-Standort-Präferenzen

Dieser Constraint entspricht der Funktion add_constraints_partner_location_prefs()
und behandelt Präferenzen zwischen Mitarbeitern für gemeinsame Einsätze an Standorten.
"""

import itertools
from typing import List, Tuple

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint
from sat_solver.avail_day_group_tree import AvailDayGroup


class PartnerLocationPrefsConstraint(AbstractConstraint):
    """
    Constraint für Partner-Standort-Präferenzen.
    
    Dieser Constraint behandelt die Bewertung von Präferenzen zwischen
    verschiedenen Mitarbeitern für gemeinsame Einsätze an bestimmten Standorten.
    
    Entspricht der ursprünglichen Funktion add_constraints_partner_location_prefs().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "partner_location_prefs"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt Partner-Location-Preference-Variablen.
        
        Für jede Kombination aus zwei Mitarbeitern an einem Event mit mindestens
        2 Actors werden Variablen für deren gemeinsame Präferenzen erstellt.
        
        Returns:
            Liste der erstellten Partner-Location-Preference-Variablen
        """
        partner_loc_pref_vars = []
        
        # Hole Multiplier-Konfiguration
        plp_constr_multipliers = self.config.constraint_multipliers.sliders_partner_loc_prefs
        
        constraints_added = 0
        partnerships_evaluated = 0
        
        for eg_id, event_group in self.entities.event_groups_with_event.items():
            # Überspringe Events mit weniger als 2 Actors
            if event_group.event.cast_group.nr_actors < 2:
                continue
            
            # Hole alle AvailDayGroups mit gleichem Datum und Zeitfenster
            avail_day_groups = self._get_compatible_avail_day_groups(eg_id)
            
            # Erstelle alle Kombinationen von möglichen AvailDayGroups für dieses Event
            duo_combinations = list(itertools.combinations(avail_day_groups, 2))
            
            for combo in duo_combinations:
                combo_adg_1, combo_adg_2 = combo
                
                # Überspringe wenn keine Partner-Location-Preferences existieren
                if not self._has_partner_location_preferences(combo):
                    continue
                
                # Überspringe wenn die Partner dieselbe Person sind
                if (combo_adg_1.avail_day.actor_plan_period.id == 
                    combo_adg_2.avail_day.actor_plan_period.id):
                    continue
                
                partnerships_evaluated += 1
                
                # Erstelle Partner-Location-Preference-Variable
                var_name = (f'{event_group.event.date:%d.%m.%y} '
                           f'({event_group.event.time_of_day.name}), '
                           f'{event_group.event.location_plan_period.location_of_work.name} '
                           f'{combo_adg_1.avail_day.actor_plan_period.person.f_name} + '
                           f'{combo_adg_2.avail_day.actor_plan_period.person.f_name}')
                
                partner_loc_pref_var = self.model.NewIntVar(
                    plp_constr_multipliers[2] * 2,  # Minimum (schlechtester Score * 2)
                    plp_constr_multipliers[0] * 2,  # Maximum (bester Score * 2)
                    var_name
                )
                
                partner_loc_pref_vars.append(partner_loc_pref_var)
                
                # Berechne die Scores der Partner-Location-Preferences
                score_1, score_2 = self._calculate_partner_scores(combo, event_group)
                
                # Erstelle Hilfs-Variablen für die Berechnung
                plp_weight_var, shift_active_var, all_active_var = self._create_helper_variables(
                    combo, eg_id, event_group, score_1, score_2, plp_constr_multipliers
                )
                
                # Hauptconstraint: Partner-Location-Preference-Variable
                self.model.AddMultiplicationEquality(
                    partner_loc_pref_var, [plp_weight_var, all_active_var]
                )
                
                # Exklusivitäts-Constraint falls erforderlich
                self._add_exclusivity_constraint(combo, eg_id, event_group, score_1, score_2)
                
                constraints_added += 1
                
                # Speichere Metadaten für diese Partnership
                self.add_metadata(f'partnership_{len(partner_loc_pref_vars)-1}', {
                    'event_date': event_group.event.date.strftime('%Y-%m-%d'),
                    'location': event_group.event.location_plan_period.location_of_work.name,
                    'person_1': combo_adg_1.avail_day.actor_plan_period.person.f_name,
                    'person_2': combo_adg_2.avail_day.actor_plan_period.person.f_name,
                    'score_1': score_1,
                    'score_2': score_2,
                    'cast_group_size': event_group.event.cast_group.nr_actors
                })
        
        self.add_metadata('total_partner_preferences', len(partner_loc_pref_vars))
        self.add_metadata('partnerships_evaluated', partnerships_evaluated)
        self.add_metadata('constraints_added', constraints_added)
        
        return partner_loc_pref_vars
    
    def add_constraints(self) -> None:
        """
        Fügt zusätzliche Partner-Location-Preference-Constraints hinzu.
        
        Die Hauptlogik ist bereits in create_variables() implementiert.
        """
        # Zusätzliche Constraints sind bereits in create_variables() implementiert
        pass
    
    def _get_compatible_avail_day_groups(self, eg_id) -> List[AvailDayGroup]:
        """
        Holt alle AvailDayGroups, die für ein Event kompatibel sind.
        
        Args:
            eg_id: Event Group ID
            
        Returns:
            Liste kompatibler AvailDayGroups
        """
        compatible_groups = []
        
        for adg_id, adg in self.entities.avail_day_groups_with_avail_day.items():
            if self.entities.shifts_exclusive.get((adg_id, eg_id), 0):
                compatible_groups.append(adg)
        
        return compatible_groups
    
    def _has_partner_location_preferences(self, combo: Tuple[AvailDayGroup, AvailDayGroup]) -> bool:
        """
        Prüft ob mindestens eine Person in der Kombination Partner-Location-Preferences hat.
        
        Args:
            combo: Tupel aus zwei AvailDayGroups
            
        Returns:
            True wenn Partner-Location-Preferences existieren
        """
        for adg in combo:
            if len(adg.avail_day.actor_partner_location_prefs_defaults) > 0:
                return True
        return False
    
    def _calculate_partner_scores(self, combo: Tuple[AvailDayGroup, AvailDayGroup], 
                                 event_group) -> Tuple[float, float]:
        """
        Berechnet die Partner-Scores für beide Personen in der Kombination.
        
        Args:
            combo: Tupel aus zwei AvailDayGroups
            event_group: Das Event Group Objekt
            
        Returns:
            Tupel aus (score_1, score_2)
        """
        combo_adg_1, combo_adg_2 = combo
        location_id = event_group.event.location_plan_period.location_of_work.id
        
        # Score für Person 1 (Präferenz bezüglich Person 2)
        score_1 = next(
            (plp.score for plp in combo_adg_1.avail_day.actor_partner_location_prefs_defaults
             if plp.partner.id == combo_adg_2.avail_day.actor_plan_period.person.id
             and plp.location_of_work.id == location_id),
            1  # Default Score falls keine Präferenz existiert
        )
        
        # Score für Person 2 (Präferenz bezüglich Person 1)  
        score_2 = next(
            (plp.score for plp in combo_adg_2.avail_day.actor_partner_location_prefs_defaults
             if plp.partner.id == combo_adg_1.avail_day.actor_plan_period.person.id
             and plp.location_of_work.id == location_id),
            1  # Default Score falls keine Präferenz existiert
        )
        
        return score_1, score_2
    
    def _create_helper_variables(self, combo: Tuple[AvailDayGroup, AvailDayGroup], 
                               eg_id, event_group, score_1: float, score_2: float,
                               plp_constr_multipliers: dict) -> Tuple[IntVar, IntVar, IntVar]:
        """
        Erstellt Hilfs-Variablen für Partner-Location-Preference-Berechnung.
        
        Args:
            combo: AvailDayGroup-Kombination
            eg_id: Event Group ID
            event_group: Event Group Objekt
            score_1: Score der ersten Person
            score_2: Score der zweiten Person
            plp_constr_multipliers: Multiplier-Konfiguration
            
        Returns:
            Tupel aus (plp_weight_var, shift_active_var, all_active_var)
        """
        combo_adg_1, combo_adg_2 = combo
        
        # Weight Variable basierend auf durchschnittlichem Score und Cast-Größe
        plp_weight_var = self.model.NewIntVar(
            plp_constr_multipliers[2] * 2, 
            plp_constr_multipliers[0] * 2, 
            f'plp_weight_{eg_id}'
        )
        
        # Berechne durchschnittliches Gewicht normalisiert auf Cast-Größe
        avg_weight = round(
            (plp_constr_multipliers[score_1] + plp_constr_multipliers[score_2]) /
            (event_group.event.cast_group.nr_actors - 1)
        )
        
        self.model.Add(plp_weight_var == avg_weight)
        
        # Variable für "beide Personen sind zugewiesen"
        shift_active_var = self.model.NewBoolVar(f'shift_active_{eg_id}')
        
        self.model.AddMultiplicationEquality(
            shift_active_var,
            [
                self.entities.shift_vars[(combo_adg_1.avail_day_group_id, eg_id)],
                self.entities.shift_vars[(combo_adg_2.avail_day_group_id, eg_id)]
            ]
        )
        
        # Variable für "beide Personen zugewiesen UND Event findet statt"
        all_active_var = self.model.NewBoolVar(f'all_active_{eg_id}')
        
        self.model.AddMultiplicationEquality(
            all_active_var, 
            [shift_active_var, self.entities.event_group_vars[eg_id]]
        )
        
        return plp_weight_var, shift_active_var, all_active_var
    
    def _add_exclusivity_constraint(self, combo: Tuple[AvailDayGroup, AvailDayGroup],
                                   eg_id, event_group, score_1: float, score_2: float) -> None:
        """
        Fügt Exklusivitäts-Constraint hinzu falls erforderlich.
        
        Falls eine der Personen absolut nicht mit der anderen Person besetzt werden soll
        und die Besetzungsstärke 2 ist, wird nur 1 dieser Personen besetzt.
        
        Args:
            combo: AvailDayGroup-Kombination
            eg_id: Event Group ID
            event_group: Event Group Objekt
            score_1: Score der ersten Person
            score_2: Score der zweiten Person
        """
        combo_adg_1, combo_adg_2 = combo
        
        # Prüfe Exklusivitätsbedingung
        exclusive = 0 if (score_1 and score_2) or event_group.event.cast_group.nr_actors >= 3 else 1
        
        if exclusive:
            # Nur eine der beiden Personen kann zugewiesen werden
            constraint = self.model.Add(
                self.entities.shift_vars[(combo_adg_1.avail_day_group_id, eg_id)] +
                self.entities.shift_vars[(combo_adg_2.avail_day_group_id, eg_id)] < 2
            )
            
            self.add_metadata(f'exclusivity_constraint_{eg_id}', {
                'person_1': combo_adg_1.avail_day.actor_plan_period.person.f_name,
                'person_2': combo_adg_2.avail_day.actor_plan_period.person.f_name,
                'reason': 'One or both scores are 0 and cast size is 2'
            })
    
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
            'shift_vars',
            'event_group_vars',
            'shifts_exclusive'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe Konfiguration
        if not hasattr(self.config, 'constraint_multipliers'):
            self.add_metadata('validation_error', "Missing config.constraint_multipliers")
            return False
        
        if not hasattr(self.config.constraint_multipliers, 'sliders_partner_loc_prefs'):
            self.add_metadata('validation_error', "Missing config sliders_partner_loc_prefs")
            return False
        
        return True
    
    def get_partner_prefs_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Partner-Preferences zurück.
        
        Returns:
            Dictionary mit Partner-Preference-Statistiken
        """
        if not self.entities.avail_day_groups_with_avail_day:
            return {}
        
        total_events = len(self.entities.event_groups_with_event)
        multi_actor_events = sum(
            1 for eg in self.entities.event_groups_with_event.values()
            if eg.event.cast_group.nr_actors >= 2
        )
        
        total_partnerships = 0
        partnership_scores = []
        
        # Analysiere existierende Partner-Preferences
        for adg in self.entities.avail_day_groups_with_avail_day.values():
            partner_prefs = adg.avail_day.actor_partner_location_prefs_defaults
            total_partnerships += len(partner_prefs)
            
            for pref in partner_prefs:
                partnership_scores.append(pref.score)
        
        # Score-Verteilung
        score_distribution = {}
        for score in partnership_scores:
            score_distribution[score] = score_distribution.get(score, 0) + 1
        
        return {
            'total_events': total_events,
            'multi_actor_events': multi_actor_events,
            'total_partnerships_defined': total_partnerships,
            'partnerships_evaluated': self.get_metadata('partnerships_evaluated', 0),
            'partner_preference_variables': self.get_metadata('total_partner_preferences', 0),
            'score_distribution': score_distribution,
            'unique_scores': list(score_distribution.keys())
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Partner-Preference-Daten.
        
        Returns:
            Dictionary mit Constraint- und Partner-Preference-Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_partner_prefs_summary())
        return base_summary
