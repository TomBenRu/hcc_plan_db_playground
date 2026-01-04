"""
DifferentCastsSameDayConstraint - Hard Constraint für unterschiedliche Besetzungen am gleichen Tag.

Stellt sicher, dass Besetzungen von Events an unterschiedlichen Locations,
die am gleichen Tag stattfinden, unterschiedlich sein müssen.
"""
import datetime
import itertools
from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import UUID

from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase, Validatable

if TYPE_CHECKING:
    from database import schemas


class DifferentCastsSameDayConstraint(ConstraintBase):
    """
    Hard Constraint für unterschiedliche Besetzungen an verschiedenen Locations am gleichen Tag.
    
    Logik:
    - Ein Mitarbeiter kann an einem Tag nicht bei verschiedenen Locations arbeiten
    - Ausnahme: CombinationLocationsPossible erlaubt bestimmte Kombinationen
    - Dies ist ein Hard Constraint (keine Penalties, nur strikte Einschränkungen)
    
    TODO: Diese Funktionalität soll deaktiviert werden können:
          Entweder über Configuration oder durch zusätzliche Felder in Projekt und Team.
    """
    
    name = "different_casts_same_day"
    weight_attribute = ""  # Hard Constraint - kein Weight
    
    def apply(self) -> None:
        """
        Wendet das Different Casts Same Day Constraint an.
        
        Erstellt Constraints, die sicherstellen, dass ein Mitarbeiter an einem Tag
        nicht bei verschiedenen Locations arbeiten kann (außer bei erlaubten Kombinationen).
        """
        # Erstelle defaultdict [date][actor_plan_period_id][location_id] -> list[(key, shift_var)]
        dict_date_shift_var = self._build_date_shift_var_dict()
        
        # Erstelle Constraints
        self._create_constraints(dict_date_shift_var)
    
    def _build_date_shift_var_dict(self) -> defaultdict:
        """
        Baut das verschachtelte Dictionary für Shift-Variablen auf.
        
        Returns:
            defaultdict[date][actor_plan_period_id][location_id] -> list[(key, shift_var)]
        """
        dict_date_shift_var: defaultdict[
            datetime.date, 
            defaultdict[UUID, defaultdict[UUID, list[tuple[tuple[UUID, UUID], IntVar]]]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        
        for (adg_id, eg_id), shift_var in self.entities.shift_vars.items():
            # Nur exklusive Shifts berücksichtigen
            if not self.entities.shifts_exclusive[(adg_id, eg_id)]:
                continue
            
            date = self.entities.event_groups_with_event[eg_id].event.date
            actor_plan_period_id = (
                self.entities.avail_day_groups_with_avail_day[adg_id]
                .avail_day.actor_plan_period.id
            )
            location_id = (
                self.entities.event_groups_with_event[eg_id]
                .event.location_plan_period.location_of_work.id
            )
            
            dict_date_shift_var[date][actor_plan_period_id][location_id].append(
                ((adg_id, eg_id), shift_var)
            )
        
        return dict_date_shift_var
    
    def _create_constraints(self, dict_date_shift_var: defaultdict) -> None:
        """
        Erstellt die eigentlichen Constraints für das Model.
        
        Args:
            dict_date_shift_var: Das vorbereitete Dictionary mit Shift-Variablen
        """
        for date, dict_actor_plan_period_id in dict_date_shift_var.items():
            for actor_plan_period_id, dict_location_id in dict_actor_plan_period_id.items():
                # Nur wenn mehr als eine Location am Tag
                if len(dict_location_id) <= 1:
                    continue
                
                # Alle Location-Paare prüfen
                for loc_pair in itertools.combinations(list(dict_location_id.values()), 2):
                    # Alle Shift-Var-Kombinationen zwischen den Locations
                    for var_pair in itertools.product(*loc_pair):
                        if not self._comb_locations_possible(
                            var_pair[0][0][0], var_pair[0][0][1],
                            var_pair[1][0][0], var_pair[1][0][1]
                        ):
                            # Hard Constraint: Summe der beiden Shifts <= 1
                            self.model.Add(sum(v[1] for v in var_pair) <= 1)
    
    def _comb_locations_possible(
        self, 
        adg_id_1: UUID, 
        eg_id_1: UUID, 
        adg_id_2: UUID, 
        eg_id_2: UUID
    ) -> bool:
        """
        Prüft, ob CombinationLocationsPossibles für die AvailDays existieren
        und diese zu den Locations der Events passen.
        
        Args:
            adg_id_1: AvailDayGroup-ID des ersten Shifts
            eg_id_1: EventGroup-ID des ersten Shifts
            adg_id_2: AvailDayGroup-ID des zweiten Shifts
            eg_id_2: EventGroup-ID des zweiten Shifts
            
        Returns:
            True wenn die Kombination erlaubt ist, False sonst
        """
        avail_day_group_1 = self.entities.avail_day_groups_with_avail_day[adg_id_1]
        avail_day_group_2 = self.entities.avail_day_groups_with_avail_day[adg_id_2]
        event_1 = self.entities.event_groups_with_event[eg_id_1].event
        event_2 = self.entities.event_groups_with_event[eg_id_2].event
        
        # Zeitdifferenz berechnen
        start_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.start)
        end_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.end)
        start_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.start)
        end_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.end)
        time_diff = start_1 - end_2 if start_1 > end_2 else start_2 - end_1
        
        # Location-IDs ermitteln
        location_1_id = event_1.location_plan_period.location_of_work.id
        location_2_id = event_2.location_plan_period.location_of_work.id
        
        # CombinationLocationsPossible für beide AvailDays prüfen
        clp_1 = self._find_combination_location_possible(
            avail_day_group_1.avail_day.combination_locations_possibles,
            location_1_id,
            location_2_id
        )
        clp_2 = self._find_combination_location_possible(
            avail_day_group_2.avail_day.combination_locations_possibles,
            location_1_id,
            location_2_id
        )
        
        # Kombination ist möglich wenn beide CLPs existieren und Zeitabstand ausreicht
        return (
            clp_1 is not None 
            and clp_2 is not None 
            and time_diff >= max(clp_1.time_span_between, clp_2.time_span_between)
        )
    
    def _find_combination_location_possible(
        self, 
        combination_locations_possibles, 
        location_1_id: UUID, 
        location_2_id: UUID
    ):
        """
        Sucht eine passende CombinationLocationsPossible für zwei Locations.
        
        Args:
            combination_locations_possibles: Liste der CLPs eines AvailDays
            location_1_id: ID der ersten Location
            location_2_id: ID der zweiten Location
            
        Returns:
            Die gefundene CLP oder None
        """
        return next(
            (
                clp for clp in combination_locations_possibles
                if location_1_id in [loc.id for loc in clp.locations_of_work]
                and location_2_id in [loc.id for loc in clp.locations_of_work]
                and not clp.prep_delete
            ),
            None
        )


    def validate_plan(self, plan: 'schemas.PlanShow') -> list['ValidationError']:
        """
        Prüft ob Mitarbeiter an einem Tag bei verschiedenen Locations eingeteilt sind,
        ohne dass dies durch CombinationLocationsPossible erlaubt ist.
        """
        from database import schemas
        from sat_solver.constraints.base import ValidationError
        
        errors = []
        
        # Gruppiere Appointments nach (Datum, Person)
        # Structure: {(date, person_id): [(appointment, avail_day), ...]}
        appointments_by_date_person: dict[
            tuple[datetime.date, UUID], 
            list[tuple[schemas.Appointment, schemas.AvailDay]]
        ] = defaultdict(list)
        
        for appointment in plan.appointments:
            event = appointment.event
            date = event.date
            
            for avail_day in appointment.avail_days:
                person_id = avail_day.actor_plan_period.person.id
                appointments_by_date_person[(date, person_id)].append((appointment, avail_day))
        
        # Prüfe für jede (Datum, Person)-Kombination
        for (date, person_id), app_avd_list in appointments_by_date_person.items():
            # Gruppiere nach Location
            apps_by_location: dict[UUID, list[tuple[schemas.Appointment, schemas.AvailDay]]] = defaultdict(list)
            
            for appointment, avail_day in app_avd_list:
                location_id = appointment.event.location_plan_period.location_of_work.id
                apps_by_location[location_id].append((appointment, avail_day))
            
            # Nur prüfen wenn mehr als eine Location
            if len(apps_by_location) <= 1:
                continue
            
            # Person-Name für Fehlermeldung
            person_name = app_avd_list[0][1].actor_plan_period.person.full_name
            
            # Alle Location-Paare prüfen
            location_ids = list(apps_by_location.keys())
            for loc_id_1, loc_id_2 in itertools.combinations(location_ids, 2):
                apps_loc_1 = apps_by_location[loc_id_1]
                apps_loc_2 = apps_by_location[loc_id_2]
                
                # Alle Kombinationen von Appointments zwischen den Locations prüfen
                for (app_1, avd_1), (app_2, avd_2) in itertools.product(apps_loc_1, apps_loc_2):
                    if not self._is_combination_allowed(app_1, avd_1, app_2, avd_2):
                        loc_name_1 = (app_1.event.location_plan_period.location_of_work.name_an_city
                                      .replace("-", "&#8209;"))
                        loc_name_2 = (app_2.event.location_plan_period.location_of_work.name_an_city
                                      .replace("-", "&#8209;"))
                        time_1 = app_1.event.time_of_day.name
                        time_2 = app_2.event.time_of_day.name
                        
                        errors.append(ValidationError(
                            category="Unerlaubte Location-Kombination",
                            message=(
                                f'{date:%d.%m.%y}: {person_name}<br>'
                                f'<span style="white-space: nowrap;">'
                                f'{loc_name_1} ({time_1}) und {loc_name_2} ({time_2})</span><br>'
                                f'sind am gleichen Tag nicht erlaubt.'
                            )
                        ))
        
        return errors
    
    def _is_combination_allowed(
        self,
        app_1: 'schemas.AppointmentShow',
        avd_1: 'schemas.AvailDayShow',
        app_2: 'schemas.AppointmentShow',
        avd_2: 'schemas.AvailDayShow'
    ) -> bool:
        """
        Prüft ob die Kombination zweier Appointments an verschiedenen Locations erlaubt ist.
        
        Returns:
            True wenn erlaubt (via CombinationLocationsPossible), False sonst
        """
        event_1 = app_1.event
        event_2 = app_2.event
        
        location_1_id = event_1.location_plan_period.location_of_work.id
        location_2_id = event_2.location_plan_period.location_of_work.id
        
        # CombinationLocationsPossible für beide AvailDays suchen
        clp_1 = self._find_combination_location_possible(
            avd_1.combination_locations_possibles,
            location_1_id,
            location_2_id
        )
        clp_2 = self._find_combination_location_possible(
            avd_2.combination_locations_possibles,
            location_1_id,
            location_2_id
        )
        
        # Wenn keine CLP für einen der beiden -> nicht erlaubt
        if clp_1 is None or clp_2 is None:
            return False
        
        # Zeitabstand prüfen
        start_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.start)
        end_1 = datetime.datetime.combine(event_1.date, event_1.time_of_day.end)
        start_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.start)
        end_2 = datetime.datetime.combine(event_2.date, event_2.time_of_day.end)
        
        # Zeitdifferenz zwischen Ende des einen und Start des anderen
        if start_1 > end_2:
            time_diff = start_1 - end_2
        else:
            time_diff = start_2 - end_1
        
        # Kombination ist möglich wenn Zeitabstand ausreicht
        required_time = max(clp_1.time_span_between, clp_2.time_span_between)
        return time_diff >= required_time
