"""
Berechnungslogik für die Planbewertung.

Dieses Modul berechnet Plan-Bewertungen unabhängig vom Solver,
indem es die Metriken direkt aus den Appointment-Daten ermittelt.
"""

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from configuration.solver import MinimizationWeights
from database import db_services

from .rating_data import (
    ObjectiveScore,
    PlanRating,
    OBJECTIVE_CONFIG,
    get_color_for_score,
)

if TYPE_CHECKING:
    from database import schemas


class PlanRatingCalculator:
    """
    Berechnet Plan-Bewertungen unabhängig vom Solver.

    Die Bewertung basiert auf vier Haupt-Kriterien:
    1. Fairness: Gleichmäßige Verteilung der Schichten
    2. Standort-Präferenzen: Einhaltung der Mitarbeiter-Wünsche
    3. Partner-Präferenzen: Einhaltung der Team-Wünsche
    4. Besetzungsgrad: Vollständigkeit der Besetzung

    Usage:
        calculator = PlanRatingCalculator(plan)
        rating = calculator.calculate()
    """

    def __init__(self, plan: 'schemas.PlanShow'):
        """
        Initialisiert den Calculator.

        Args:
            plan: Der zu bewertende Plan mit allen Appointments
        """
        self.plan = plan
        # Statt self._load_config()
        # Bessere Gewichte für die Bewertung:
        self.weights = MinimizationWeights(sum_squared_deviations=1, constraints_location_prefs=1,
                                           constraints_partner_loc_prefs=1, unassigned_shifts=5)

    def _load_config(self):
        """Lädt die Solver-Konfiguration für die Gewichtung."""
        from configuration.solver import curr_config_handler
        self.config = curr_config_handler.get_solver_config()
        self.weights = self.config.minimization_weights

    def calculate(self) -> PlanRating:
        """
        Berechnet die vollständige Plan-Bewertung.

        Returns:
            PlanRating mit Gesamt-Score und Einzel-Bewertungen
        """
        objective_scores = [
            self._calculate_fairness_score(),
            self._calculate_location_prefs_score(),
            self._calculate_partner_prefs_score(),
            self._calculate_coverage_score(),
        ]

        # Gewichteter Durchschnitt
        overall_score = self._calculate_weighted_average(objective_scores)

        return PlanRating(
            plan_id=self.plan.id,
            overall_score=overall_score,
            overall_color=get_color_for_score(overall_score),
            objective_scores=objective_scores,
            calculation_timestamp=datetime.now(),
            is_from_solver=False
        )

    def _calculate_weighted_average(self, scores: list[ObjectiveScore]) -> float:
        """Berechnet den gewichteten Durchschnitt aller Scores."""
        total_weight = sum(abs(s.weight) for s in scores if s.weight != 0)
        if total_weight == 0:
            # Falls keine Gewichte: einfacher Durchschnitt
            return sum(s.normalized_score for s in scores) / len(scores) if scores else 0

        weighted_sum = sum(s.normalized_score * abs(s.weight) for s in scores)
        return weighted_sum / total_weight

    def _calculate_fairness_score(self) -> ObjectiveScore:
        """
        Berechnet den Fairness-Score basierend auf der Schichtverteilung.

        Logik:
        1. Sammle pro Mitarbeiter: zugewiesene Schichten und faire Schichten
        2. Berechne relative Abweichung: (zugewiesen - gewünscht) / gewünscht
        3. Berechne Varianz der relativen Abweichungen
        4. Normalisiere: 100% bei Varianz=0, sinkt bei steigender Varianz
        """
        name = 'rel_shift_deviations'
        display_name, icon, description = OBJECTIVE_CONFIG[name]
        weight = getattr(self.weights, 'sum_squared_deviations', 0.5)

        # Sammle Schichten pro Mitarbeiter
        actor_shifts: dict[UUID, int] = defaultdict(int)
        max_fair_shifts_of_app_ids = db_services.MaxFairShiftsOfApp.get_all_from__plan_period_minimal(
            self.plan.plan_period.id)
        actor_fair_shifts = {app_id: fair_shifts for app_id, (_, fair_shifts) in max_fair_shifts_of_app_ids.items()}

        for appointment in self.plan.appointments:
            for avail_day in appointment.avail_days:
                actor_id = avail_day.actor_plan_period.id
                actor_shifts[actor_id] += 1

        if not actor_shifts:
            # Keine Zuweisungen -> perfekter Score (nichts zu verteilen)
            return self._create_score(name, display_name, icon, description, 100.0, 0.0, weight)

        # Berechne relative Abweichungen
        relative_deviations = []
        for actor_id, assigned in actor_shifts.items():
            fair = actor_fair_shifts.get(actor_id, 1)
            if fair == 0:
                relative_dev = assigned / 0.1
            else:
                relative_dev = (assigned - fair) / fair
            relative_deviations.append(relative_dev)

        # Berechne Varianz
        if len(relative_deviations) < 2:
            variance = 0.0
        else:
            mean_dev = sum(relative_deviations) / len(relative_deviations)
            variance = sum((d - mean_dev) ** 2 for d in relative_deviations) / len(relative_deviations)

        # Normalisierung: Varianz von 0-0.25 auf Score 100-0
        # Bei Standardabweichung 0.5 (50% Abweichung): Score ~0
        std_dev = variance ** 0.5
        normalized_score = max(0.0, 100.0 - std_dev * 200.0)

        return self._create_score(name, display_name, icon, description, normalized_score, variance, weight)

    def _calculate_location_prefs_score(self) -> ObjectiveScore:
        """
        Berechnet den Score für Standort-Präferenzen.

        Logik:
        1. Für jede Zuweisung: Finde die Location-Präferenz des Mitarbeiters
        2. Score-Mapping: 0=verboten, 0.5=ungern, 1=neutral, 1.5=gern, 2=sehr gern
        3. Normalisiere Durchschnitt: avg * 100
        """
        name = 'location_prefs'
        display_name, icon, description = OBJECTIVE_CONFIG[name]
        weight = getattr(self.weights, 'constraints_location_prefs', 0.001)

        pref_scores = []

        for appointment in self.plan.appointments:
            # Location des Events
            location_id = appointment.event.location_plan_period.location_of_work.id

            for avail_day in appointment.avail_days:
                # Suche Location-Präferenz für diesen Standort
                pref_score = 1.0  # Default: neutral

                for pref in avail_day.actor_location_prefs_defaults:
                    if pref.location_of_work.id == location_id and not pref.prep_delete:
                        pref_score = pref.score
                        break

                pref_scores.append(pref_score)

        if not pref_scores:
            return self._create_score(name, display_name, icon, description, 100.0, 0.0, weight)

        # Durchschnitt berechnen und normalisieren (0-2 -> 0-100)
        avg_score = sum(pref_scores) / len(pref_scores)
        normalized_score = avg_score * 100.0

        return self._create_score(name, display_name, icon, description, normalized_score, avg_score, weight)

    def _calculate_partner_prefs_score(self) -> ObjectiveScore:
        """
        Berechnet den Score für Partner-Präferenzen.

        Analysiert, ob Team-Partner bevorzugt zusammen eingeteilt wurden.
        """
        name = 'partner_location_prefs'
        display_name, icon, description = OBJECTIVE_CONFIG[name]
        weight = getattr(self.weights, 'constraints_partner_loc_prefs', 0.1)

        pref_scores = []

        for appointment in self.plan.appointments:
            if len(appointment.avail_days) < 2:
                continue
            location_id = appointment.event.location_plan_period.location_of_work.id
            avail_days = list(appointment.avail_days)

            # Für jedes Paar von Mitarbeitern im selben Termin
            for i, avail_day in enumerate(avail_days):
                for partner_avail_day in avail_days[i + 1:]:
                    # Suche Partner-Präferenz
                    pref_score = 1.0  # Default: neutral

                    person_id = avail_day.actor_plan_period.person.id
                    partner_id = partner_avail_day.actor_plan_period.person.id
                    curr_pref_scores = []
                    for pref in avail_day.actor_partner_location_prefs_defaults:
                        if (pref.partner.id == partner_id and
                                pref.location_of_work.id == location_id and
                                not pref.prep_delete):
                            curr_pref_scores.append(pref.score)
                            break
                    else:
                        curr_pref_scores.append(1.0)
                    for pref in partner_avail_day.actor_partner_location_prefs_defaults:
                        if (pref.partner.id == person_id and
                                pref.location_of_work.id == location_id and
                                not pref.prep_delete):
                            curr_pref_scores.append(pref.score)
                            break
                    else:
                        curr_pref_scores.append(1.0)
                    pref_score = ((sum(curr_pref_scores) if curr_pref_scores else 2.0)
                                  / (len(appointment.avail_days) + len(appointment.guests)))

                    pref_scores.append(pref_score)

        if not pref_scores:
            # Keine Paare -> perfekter Score
            return self._create_score(name, display_name, icon, description, 100.0, 0.0, weight)

        avg_score = sum(pref_scores) / len(pref_scores)
        normalized_score = avg_score * 100.0

        return self._create_score(name, display_name, icon, description, normalized_score, avg_score, weight)

    def _calculate_coverage_score(self) -> ObjectiveScore:
        """
        Berechnet den Besetzungsgrad.

        Vergleicht die Anzahl benötigter Positionen mit tatsächlich besetzten.
        """
        name = 'unsigned_shifts'
        display_name, icon, description = OBJECTIVE_CONFIG[name]
        weight = getattr(self.weights, 'unassigned_shifts', 100_000)

        total_required = 0
        total_assigned = 0

        event_ids = [a.event.id for a in self.plan.appointments]
        nr_actors_by_event = db_services.CastGroup.get_nr_actors_by_event_ids(event_ids)

        for appointment in self.plan.appointments:
            required = nr_actors_by_event.get(appointment.event.id, 1)

            # Anzahl zugewiesener Mitarbeiter + Gäste
            assigned = len(appointment.avail_days)
            if hasattr(appointment, 'guests') and appointment.guests:
                assigned += len(appointment.guests)

            total_required += required
            total_assigned += min(assigned, required)  # Nicht mehr als benötigt zählen

        if total_required == 0:
            return self._create_score(name, display_name, icon, description, 100.0, 0.0, weight)

        # Score = Besetzungsgrad in Prozent
        normalized_score = (total_assigned / total_required) * 100.0
        unassigned_count = total_required - total_assigned

        return self._create_score(name, display_name, icon, description, normalized_score, unassigned_count, weight)

    def _create_score(
            self,
            name: str,
            display_name: str,
            icon: str,
            description: str,
            normalized_score: float,
            raw_value: float,
            weight: float
    ) -> ObjectiveScore:
        """Erzeugt einen ObjectiveScore mit allen berechneten Werten."""
        return ObjectiveScore(
            name=name,
            display_name=display_name,
            icon=icon,
            raw_value=raw_value,
            normalized_score=normalized_score,
            weight=weight,
            weighted_contribution=normalized_score * abs(weight),
            description=description,
            color=get_color_for_score(normalized_score)
        )

    @classmethod
    def from_solver_results(
            cls,
            plan_id: UUID,
            penalty_summary: dict[str, dict]
    ) -> PlanRating:
        """
        Erstellt eine PlanRating aus Solver-Ergebnissen.

        Diese Methode wird aufgerufen, nachdem der Solver einen Plan
        berechnet hat. Die penalty_summary kommt von
        ConstraintRegistry.get_penalty_summary().

        Args:
            plan_id: UUID des berechneten Plans
            penalty_summary: Dict mit Penalty-Daten pro Constraint

        Returns:
            PlanRating basierend auf Solver-Ergebnissen
        """
        from configuration.solver import curr_config_handler
        config = curr_config_handler.get_solver_config()
        weights = config.minimization_weights

        objective_scores = []

        # Mapping: constraint_name -> (weight_attr, max_reasonable_penalty)
        constraint_mapping = {
            'rel_shift_deviations': ('sum_squared_deviations', 1.0),
            'location_prefs': ('constraints_location_prefs', 100),
            'partner_location_prefs': ('constraints_partner_loc_prefs', 100),
            'unsigned_shifts': ('unassigned_shifts', 50),
        }

        for constraint_name, (weight_attr, max_penalty) in constraint_mapping.items():
            if constraint_name not in OBJECTIVE_CONFIG:
                continue

            display_name, icon, description = OBJECTIVE_CONFIG[constraint_name]
            weight = getattr(weights, weight_attr, 1.0)

            # Hole Penalty-Daten aus Summary
            summary = penalty_summary.get(constraint_name, {})
            penalty_sum = summary.get('penalty_sum', 0)

            # Normalisiere: 0 Penalty = 100%, max_penalty = 0%
            if max_penalty > 0:
                normalized_score = max(0.0, 100.0 - (penalty_sum / max_penalty) * 100.0)
            else:
                normalized_score = 100.0 if penalty_sum == 0 else 0.0

            objective_scores.append(ObjectiveScore(
                name=constraint_name,
                display_name=display_name,
                icon=icon,
                raw_value=penalty_sum,
                normalized_score=normalized_score,
                weight=weight,
                weighted_contribution=normalized_score * abs(weight),
                description=description,
                color=get_color_for_score(normalized_score)
            ))

        # Berechne Gesamtscore
        total_weight = sum(abs(s.weight) for s in objective_scores if s.weight != 0)
        if total_weight > 0:
            overall_score = sum(s.normalized_score * abs(s.weight) for s in objective_scores) / total_weight
        else:
            overall_score = sum(s.normalized_score for s in objective_scores) / len(objective_scores) if objective_scores else 0

        return PlanRating(
            plan_id=plan_id,
            overall_score=overall_score,
            overall_color=get_color_for_score(overall_score),
            objective_scores=objective_scores,
            calculation_timestamp=datetime.now(),
            is_from_solver=True
        )
