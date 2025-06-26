"""
LocationPrefsConstraint - Constraint für Standort-Präferenzen

Dieser Constraint entspricht der Funktion add_constraints_location_prefs()
und behandelt die Bewertung von Mitarbeiter-Präferenzen für verschiedene Standorte.
"""

from typing import List, Dict, Tuple

from ortools.sat.python.cp_model import IntVar

from .base import AbstractConstraint


class LocationPrefsConstraint(AbstractConstraint):
    """
    Constraint für Standort-Präferenzen der Mitarbeiter.
    
    Dieser Constraint erstellt Variablen für die Bewertung von Standort-Präferenzen
    und fügt entsprechende Constraints hinzu, um die Präferenzen in der Zielfunktion
    zu berücksichtigen.
    
    Entspricht der ursprünglichen Funktion add_constraints_location_prefs().
    """
    
    @property
    def constraint_name(self) -> str:
        """Name dieses Constraints."""
        return "location_prefs"
    
    def create_variables(self) -> List[IntVar]:
        """
        Erstellt Location-Preference-Variablen.
        
        Für jede Kombination aus AvailDay und entsprechendem Event wird eine
        Variable erstellt, die die gewichtete Präferenz repräsentiert.
        
        Returns:
            Liste der erstellten Location-Preference-Variablen
        """
        loc_pref_vars = []
        
        # Hole Multiplier-Konfiguration
        multiplier_slider = self.config.constraint_multipliers.sliders_location_prefs
        
        # Erstelle Event-Daten-Cache für bessere Performance
        event_data = self._create_event_data_cache()
        
        for avail_day_group_id, avail_day_group in self.entities.avail_day_groups_with_avail_day.items():
            avail_day = avail_day_group.avail_day
            
            # Iteriere über alle Location-Präferenzen dieses AvailDays
            for loc_pref in avail_day.actor_location_prefs_defaults:
                if loc_pref.prep_delete:
                    continue
                
                # Finde das entsprechende Event
                eg_id_event_group = event_data.get(
                    (avail_day.date, 
                     avail_day.time_of_day.time_of_day_enum.time_index, 
                     loc_pref.location_of_work.id)
                )
                
                if not eg_id_event_group:
                    continue
                
                eg_id, event_group = eg_id_event_group
                shift_var = self.entities.shift_vars.get((avail_day_group_id, eg_id))
                
                if shift_var is None:
                    continue
                
                event = event_group.event
                
                # Score 0 bedeutet absolutes Verbot - wird direkt behandelt
                if loc_pref.score == 0:
                    self.model.Add(shift_var == 0)
                    continue
                
                # Erstelle Location-Preference-Variable
                var_name = (f'{event.date:%d.%m.%Y} ({event.time_of_day.name}), '
                           f'{event.location_plan_period.location_of_work.name}: '
                           f'{avail_day.actor_plan_period.person.f_name}')
                
                loc_pref_var = self.model.NewIntVar(
                    multiplier_slider[2],  # Minimum (schlechtester Score)
                    multiplier_slider[0.5],  # Maximum (bester Score)
                    var_name
                )
                
                loc_pref_vars.append(loc_pref_var)
                
                # Constraint für Location-Preference-Variable
                # loc_pref_var = shift_var * event_group_var * multiplier[score]
                self.model.AddMultiplicationEquality(
                    loc_pref_var,
                    [
                        shift_var,
                        self.entities.event_group_vars[eg_id],
                        multiplier_slider[loc_pref.score]
                    ]
                )
                
                # Speichere Metadaten für diese Preference
                self.add_metadata(f'loc_pref_{len(loc_pref_vars)-1}', {
                    'avail_day_group_id': str(avail_day_group_id),
                    'event_group_id': str(eg_id),
                    'location_name': event.location_plan_period.location_of_work.name,
                    'person_name': avail_day.actor_plan_period.person.f_name,
                    'score': loc_pref.score,
                    'multiplier_value': multiplier_slider[loc_pref.score]
                })
        
        self.add_metadata('total_location_preferences', len(loc_pref_vars))
        return loc_pref_vars
    
    def add_constraints(self) -> None:
        """
        Fügt zusätzliche Location-Preference-Constraints hinzu.
        
        Die Hauptlogik ist bereits in create_variables() implementiert.
        Diese Methode kann für zusätzliche Validierungs-Constraints verwendet werden.
        """
        constraints_added = 0
        
        # Zusätzliche Constraints können hier hinzugefügt werden
        # Zum Beispiel: Konsistenz-Checks, Validierungen, etc.
        
        self.add_metadata('additional_constraints_added', constraints_added)
    
    def _create_event_data_cache(self) -> Dict[Tuple, Tuple]:
        """
        Erstellt einen Cache für Event-Daten zur Performance-Optimierung.
        
        Returns:
            Dictionary mit (date, time_index, location_id) -> (event_group_id, event_group)
        """
        event_data = {}
        
        for eg_id, event_group in self.entities.event_groups_with_event.items():
            event = event_group.event
            key = (
                event.date,
                event.time_of_day.time_of_day_enum.time_index,
                event.location_plan_period.location_of_work.id
            )
            event_data[key] = (eg_id, event_group)
        
        return event_data
    
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
            'avail_day_groups_with_avail_day',
            'event_groups_with_event',
            'shift_vars',
            'event_group_vars'
        ]
        
        for attr in required_attrs:
            if not hasattr(self.entities, attr):
                self.add_metadata('validation_error', f"Missing entities.{attr}")
                return False
        
        # Prüfe Konfiguration
        if not hasattr(self.config, 'constraint_multipliers'):
            self.add_metadata('validation_error', "Missing config.constraint_multipliers")
            return False
        
        if not hasattr(self.config.constraint_multipliers, 'sliders_location_prefs'):
            self.add_metadata('validation_error', "Missing config sliders_location_prefs")
            return False
        
        return True
    
    def get_location_prefs_summary(self) -> dict:
        """
        Gibt eine Zusammenfassung der Location-Preferences zurück.
        
        Returns:
            Dictionary mit Location-Preference-Statistiken
        """
        if not self.entities.avail_day_groups_with_avail_day:
            return {}
        
        total_avail_days = len(self.entities.avail_day_groups_with_avail_day)
        total_preferences = 0
        preferences_by_score = {}
        forbidden_preferences = 0
        
        for avail_day_group in self.entities.avail_day_groups_with_avail_day.values():
            for loc_pref in avail_day_group.avail_day.actor_location_prefs_defaults:
                if loc_pref.prep_delete:
                    continue
                    
                total_preferences += 1
                score = loc_pref.score
                
                if score == 0:
                    forbidden_preferences += 1
                
                if score not in preferences_by_score:
                    preferences_by_score[score] = 0
                preferences_by_score[score] += 1
        
        return {
            'total_avail_days': total_avail_days,
            'total_location_preferences': total_preferences,
            'forbidden_preferences': forbidden_preferences,
            'preferences_by_score': preferences_by_score,
            'unique_scores': list(preferences_by_score.keys())
        }
    
    def get_summary(self) -> dict:
        """
        Erweiterte Zusammenfassung mit Location-Preference-Daten.
        
        Returns:
            Dictionary mit Constraint- und Location-Preference-Daten
        """
        base_summary = super().get_summary()
        base_summary.update(self.get_location_prefs_summary())
        return base_summary
