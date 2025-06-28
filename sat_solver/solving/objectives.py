"""
ObjectiveBuilder - Builder für Zielfunktionen

Diese Klasse vereinfacht die Erstellung von Zielfunktionen für den SAT-Solver
und kapselt die komplexe Logik der Gewichtung verschiedener Constraint-Terme.
"""

import logging
from typing import Dict, List, Optional

from ortools.sat.python.cp_model import IntVar

from sat_solver.core.solver_context import SolverContext


logger = logging.getLogger(__name__)


class ObjectiveBuilder:
    """
    Builder für SAT-Solver Zielfunktionen.
    
    Diese Klasse bietet eine saubere Schnittstelle zur Erstellung verschiedener
    Zielfunktionen basierend auf den verfügbaren Constraint-Variablen.
    """
    
    def __init__(self, context: SolverContext):
        """
        Initialisiert den ObjectiveBuilder.
        
        Args:
            context: Der SolverContext mit allen Constraint-Variablen
        """
        self.context = context
        self.model = context.model
        self.config = context.config
        
        # Tracking der verfügbaren Constraint-Terme
        self.available_terms: Dict[str, List[IntVar]] = {}
        self.last_objective_value: Optional[float] = None
        
        logger.debug("ObjectiveBuilder initialized")
    
    def build_minimize_objective(self) -> bool:
        """
        Erstellt die Standard-Minimierungs-Zielfunktion.
        
        Diese Funktion entspricht der ursprünglichen define_objective_minimize()
        und kombiniert alle verfügbaren Constraint-Terme mit konfigurierten Gewichtungen.
        
        Returns:
            True wenn Zielfunktion erfolgreich erstellt wurde
        """
        try:
            logger.debug("Building minimize objective...")
            
            # Sammle alle verfügbaren Constraint-Terme
            self._collect_available_terms()
            
            # Baue Zielfunktions-Terme auf
            objective_terms = []
            weights = self.config.minimization_weights
            
            # 1. Unassigned Shifts (hohe Priorität)
            if unassigned_terms := self._get_unassigned_shifts_terms():
                objective_terms.append(weights.unassigned_shifts * sum(unassigned_terms))
                logger.debug(f"Added unassigned shifts term with {len(unassigned_terms)} variables")
            
            # 2. Sum Squared Deviations (Mitarbeiter-Fairness)
            if deviation_terms := self._get_sum_squared_deviations_terms():
                # Normalisiert nach Anzahl Mitarbeiter
                weight = weights.sum_squared_deviations / len(self.context.entities.actor_plan_periods)
                objective_terms.append(weight * sum(deviation_terms))
                logger.debug(f"Added sum squared deviations term with {len(deviation_terms)} variables")
            
            # 3. Weights in AvailDay Groups
            if avail_day_weight_terms := self._get_avail_day_weights_terms():
                objective_terms.append(weights.constraints_weights_in_avail_day_groups * sum(avail_day_weight_terms))
                logger.debug(f"Added avail day weights term with {len(avail_day_weight_terms)} variables")
            
            # 4. Weights in Event Groups
            if event_weight_terms := self._get_event_weights_terms():
                objective_terms.append(weights.constraints_weights_in_event_groups * sum(event_weight_terms))
                logger.debug(f"Added event weights term with {len(event_weight_terms)} variables")
            
            # 5. Location Preferences
            if location_pref_terms := self._get_location_prefs_terms():
                objective_terms.append(weights.constraints_location_prefs * sum(location_pref_terms))
                logger.debug(f"Added location prefs term with {len(location_pref_terms)} variables")
            
            # 6. Partner Location Preferences
            if partner_pref_terms := self._get_partner_location_prefs_terms():
                objective_terms.append(weights.constraints_partner_loc_prefs * sum(partner_pref_terms))
                logger.debug(f"Added partner location prefs term with {len(partner_pref_terms)} variables")
            
            # 7. Fixed Cast Conflicts (hohe Priorität)
            if fixed_cast_terms := self._get_fixed_cast_terms():
                objective_terms.append(weights.constraints_fixed_casts_conflicts * sum(fixed_cast_terms))
                logger.debug(f"Added fixed cast conflicts term with {len(fixed_cast_terms)} variables")
            
            # 8. Skills Conflicts (hohe Priorität)
            if skills_terms := self._get_skills_terms():
                objective_terms.append(weights.constraints_skills_match * sum(skills_terms))
                logger.debug(f"Added skills conflicts term with {len(skills_terms)} variables")
            
            # 9. Cast Rules
            if cast_rule_terms := self._get_cast_rules_terms():
                objective_terms.append(weights.constraints_cast_rule * sum(cast_rule_terms))
                logger.debug(f"Added cast rules term with {len(cast_rule_terms)} variables")
            
            # Erstelle finale Zielfunktion
            if objective_terms:
                self.model.Minimize(sum(objective_terms))
                logger.info(f"Minimize objective built with {len(objective_terms)} terms")
                return True
            else:
                logger.warning("No objective terms available - creating dummy objective")
                self.model.Minimize(0)  # Dummy objective
                return True
                
        except Exception as e:
            logger.error(f"Failed to build minimize objective: {e}")
            return False
    
    def build_maximize_shifts_objective(self, app_id: str) -> bool:
        """
        Erstellt Zielfunktion zur Maximierung der Shifts für einen Mitarbeiter.
        
        Diese Funktion entspricht der ursprünglichen define_objective__max_shift_of_app().
        
        Args:
            app_id: Actor Plan Period ID zur Maximierung
            
        Returns:
            True wenn Zielfunktion erfolgreich erstellt wurde
        """
        try:
            logger.debug(f"Building maximize shifts objective for {app_id}")
            
            # Finde Shift-Variablen für den spezifischen Mitarbeiter
            max_shift_terms = []
            
            for (adg_id, eg_id), shift_var in self.context.entities.shift_vars.items():
                if adg_id in self.context.entities.avail_day_groups_with_avail_day:
                    adg = self.context.entities.avail_day_groups_with_avail_day[adg_id]
                    if str(adg.avail_day.actor_plan_period.id) == app_id:
                        max_shift_terms.append(shift_var)
            
            if max_shift_terms:
                self.model.Maximize(sum(max_shift_terms))
                logger.info(f"Maximize shifts objective built for {app_id} with {len(max_shift_terms)} shifts")
                return True
            else:
                logger.warning(f"No shifts found for {app_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to build maximize shifts objective: {e}")
            return False
    
    def build_fixed_constraints_objective(self, target_values: Dict[str, int]) -> bool:
        """
        Erstellt Zielfunktion mit festen Constraint-Werten.
        
        Diese Funktion entspricht der ursprünglichen define_objective__fixed_constraint_results().
        
        Args:
            target_values: Dictionary mit Zielwerten für verschiedene Constraints
            
        Returns:
            True wenn Zielfunktion erfolgreich erstellt wurde
        """
        try:
            logger.debug("Building fixed constraints objective")
            
            # Füge Equality-Constraints für Zielwerte hinzu
            constraints_added = 0
            
            # Unassigned Shifts
            if 'unassigned_shifts' in target_values and (unassigned_terms := self._get_unassigned_shifts_terms()):
                self.model.Add(sum(unassigned_terms) == target_values['unassigned_shifts'])
                constraints_added += 1
            
            # Sum Squared Deviations
            if 'sum_squared_deviations' in target_values and (deviation_terms := self._get_sum_squared_deviations_terms()):
                self.model.Add(sum(deviation_terms) == target_values['sum_squared_deviations'])
                constraints_added += 1
            
            # Location Preferences
            if 'location_prefs' in target_values and (location_terms := self._get_location_prefs_terms()):
                self.model.Add(sum(location_terms) == target_values['location_prefs'])
                constraints_added += 1
            
            # Partner Location Preferences
            if 'partner_location_prefs' in target_values and (partner_terms := self._get_partner_location_prefs_terms()):
                self.model.Add(sum(partner_terms) == target_values['partner_location_prefs'])
                constraints_added += 1
            
            # Fixed Cast Conflicts
            if 'fixed_cast_conflicts' in target_values and (fixed_cast_terms := self._get_fixed_cast_terms()):
                self.model.Add(sum(fixed_cast_terms) == target_values['fixed_cast_conflicts'])
                constraints_added += 1
            
            # Cast Rules
            if 'cast_rules' in target_values and (cast_rule_terms := self._get_cast_rules_terms()):
                self.model.Add(sum(cast_rule_terms) == target_values['cast_rules'])
                constraints_added += 1
            
            logger.info(f"Fixed constraints objective built with {constraints_added} equality constraints")
            return True
            
        except Exception as e:
            logger.error(f"Failed to build fixed constraints objective: {e}")
            return False
    
    def _collect_available_terms(self) -> None:
        """Sammelt alle verfügbaren Constraint-Terme."""
        self.available_terms = {}
        
        for constraint_name in self.context.get_all_constraint_names():
            vars = self.context.get_constraint_vars(constraint_name)
            if vars:
                self.available_terms[constraint_name] = vars
    
    def _get_unassigned_shifts_terms(self) -> List[IntVar]:
        """Holt Unassigned Shifts Terme."""
        return self.context.get_constraint_vars("unassigned_shifts")
    
    def _get_sum_squared_deviations_terms(self) -> List[IntVar]:
        """Holt Sum Squared Deviations Terme."""
        return self.context.get_constraint_vars("sum_squared_deviations") 
    
    def _get_avail_day_weights_terms(self) -> List[IntVar]:
        """Holt AvailDay Weights Terme."""
        # WeightsConstraint registriert beide Typen unter "weights"
        weights_vars = self.context.get_constraint_vars("weights")
        # Filter für AvailDay-spezifische Variablen (falls nötig)
        return weights_vars
    
    def _get_event_weights_terms(self) -> List[IntVar]:
        """Holt Event Weights Terme."""
        # WeightsConstraint registriert beide Typen unter "weights"
        # In der aktuellen Implementation sind beide zusammen
        return []  # Bereits in _get_avail_day_weights_terms enthalten
    
    def _get_location_prefs_terms(self) -> List[IntVar]:
        """Holt Location Preferences Terme."""
        return self.context.get_constraint_vars("location_prefs")
    
    def _get_partner_location_prefs_terms(self) -> List[IntVar]:
        """Holt Partner Location Preferences Terme."""
        return self.context.get_constraint_vars("partner_location_prefs")
    
    def _get_fixed_cast_terms(self) -> List[IntVar]:
        """Holt Fixed Cast Terme."""
        return self.context.get_constraint_vars("fixed_cast")
    
    def _get_skills_terms(self) -> List[IntVar]:
        """Holt Skills Terme."""
        return self.context.get_constraint_vars("skills_matching")
    
    def _get_cast_rules_terms(self) -> List[IntVar]:
        """Holt Cast Rules Terme."""
        return self.context.get_constraint_vars("cast_rules")
    
    def get_objective_summary(self) -> Dict:
        """
        Gibt eine Zusammenfassung der Zielfunktion zurück.
        
        Returns:
            Dictionary mit Zielfunktions-Informationen
        """
        return {
            'available_constraint_types': len(self.available_terms),
            'total_constraint_variables': sum(len(vars) for vars in self.available_terms.values()),
            'constraint_terms': {name: len(vars) for name, vars in self.available_terms.items()},
            'weights_config': self.config.minimization_weights.__dict__,
            'last_objective_value': self.last_objective_value
        }
    
    def set_last_objective_value(self, value: float) -> None:
        """Setzt den letzten Zielfunktions-Wert."""
        self.last_objective_value = value
        
    def validate_terms(self) -> Dict[str, bool]:
        """
        Validiert die Verfügbarkeit aller Constraint-Terme.
        
        Returns:
            Dictionary mit Validierungs-Status für jeden Term-Typ
        """
        validation_results = {}
        
        term_checkers = {
            'unassigned_shifts': self._get_unassigned_shifts_terms,
            'sum_squared_deviations': self._get_sum_squared_deviations_terms,
            'avail_day_weights': self._get_avail_day_weights_terms,
            'event_weights': self._get_event_weights_terms,
            'location_prefs': self._get_location_prefs_terms,
            'partner_location_prefs': self._get_partner_location_prefs_terms,
            'fixed_cast': self._get_fixed_cast_terms,
            'skills': self._get_skills_terms,
            'cast_rules': self._get_cast_rules_terms
        }
        
        for term_name, checker_func in term_checkers.items():
            try:
                terms = checker_func()
                validation_results[term_name] = bool(terms)
            except Exception as e:
                logger.error(f"Error validating {term_name}: {e}")
                validation_results[term_name] = False
        
        return validation_results
