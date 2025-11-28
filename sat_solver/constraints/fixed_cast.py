"""
FixedCastConstraint - Feste Besetzungen für Events

Implementiert Constraints für feste Besetzungen (fixed_cast) und
prefer_fixed_cast_events Präferenzen.

Original-Funktion: add_constraints_fixed_cast()
"""

import datetime
from ast import literal_eval
from uuid import UUID

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from sat_solver.constraints.base import ConstraintBase
from tools.helper_functions import generate_fixed_cast_clear_text


# =============================================================================
# Hilfsfunktionen für fixed_cast Verarbeitung
# =============================================================================

def is_person_available_for_event(person_id: UUID, cast_group, entities) -> bool:
    """
    Prüft, ob eine Person für ein spezifisches Event verfügbar ist.
    
    Args:
        person_id: UUID der Person
        cast_group: CastGroup mit Event-Informationen
        entities: Entities-Objekt mit Solver-Daten
    
    Returns:
        True, wenn Person verfügbar ist, sonst False
    """
    if cast_group.nr_actors == 0:
        return False
    event = cast_group.event
    event_group_id = event.event_group.id

    available = next(
        (bool(val) for (adg_id, eg_id), val in entities.shifts_exclusive.items()
         if eg_id == event_group_id
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id == person_id
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.date == event.date
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.time_of_day.time_of_day_enum.time_index
         == event.time_of_day.time_of_day_enum.time_index),
        False
    )

    return available


def filter_unavailable_persons(
    fixed_cast_list: tuple | str, 
    cast_group,
    entities
) -> tuple | str | None:
    """
    Entfernt nicht verfügbare Personen aus der fixed_cast Liste.
    
    Args:
        fixed_cast_list: Die geparste fixed_cast Liste (verschachtelte Struktur)
        cast_group: Die CastGroup mit Event-Informationen
        entities: Entities-Objekt mit Solver-Daten
    
    Returns:
        Gefilterte Liste oder None wenn keine Person verfügbar ist
    """
    if isinstance(fixed_cast_list, str):
        # Einzelne Person - prüfe Verfügbarkeit
        person_id = UUID(fixed_cast_list)
        if is_person_available_for_event(person_id, cast_group, entities):
            return fixed_cast_list
        else:
            return None
    
    # Liste mit Operatoren - rekursiv filtern
    result = []
    for i, element in enumerate(fixed_cast_list):
        if i % 2 == 0:  # Person oder verschachtelte Liste
            filtered = filter_unavailable_persons(element, cast_group, entities)
            if filtered is not None:
                result.append(filtered)
        else:  # Operator
            # Operator nur hinzufügen wenn vorher und nachher Elemente existieren
            if result and i + 1 < len(fixed_cast_list):
                result.append(element)
    
    # Bereinige: Entferne trailing Operatoren
    while result and isinstance(result[-1], str) and result[-1] in ('and', 'or'):
        result.pop()
    
    # Bereinige: Entferne leading Operatoren  
    while result and isinstance(result[0], str) and result[0] in ('and', 'or'):
        result.pop(0)

    return tuple(result) if len(result) > 1 else result[0] if result else None


def is_empty_list(fixed_cast_list: tuple | str | None) -> bool:
    """
    Prüft ob eine fixed_cast Liste leer ist (rekursiv).
    """
    if fixed_cast_list is None:
        return True
    if isinstance(fixed_cast_list, str):
        return False
    if not fixed_cast_list:
        return True
    
    # Prüfe ob alle Elemente leer sind
    for element in fixed_cast_list:
        if isinstance(element, str) and element in ('and', 'or'):
            continue  # Operatoren überspringen
        if not is_empty_list(element):
            return False
    
    return True


# =============================================================================
# FixedCastConstraint Klasse
# =============================================================================

class FixedCastConstraint(ConstraintBase):
    """
    Constraint für feste Besetzungen (fixed_cast) und prefer_fixed_cast_events.
    
    Dieses Constraint implementiert:
    1. fixed_cast_vars: Hard Constraints für feste Besetzungen
    2. preference_vars: Soft Constraints für bevorzugte Events (prefer_fixed_cast_events)
    
    Die fixed_cast Struktur unterstützt AND/OR-Operatoren:
    - "uuid1 and uuid2": Beide Personen müssen besetzt werden
    - "uuid1 or uuid2": Mindestens eine Person muss besetzt werden
    - Verschachtelte Strukturen wie "(uuid1 and uuid2) or uuid3"
    
    TODO: Funktioniert bislang nur für CastGroups mit Event
    """
    
    name = "fixed_cast"
    weight_attribute = "constraints_prefer_fixed_cast_events"
    
    def __init__(self):
        super().__init__()
        # fixed_cast_vars wird in apply() initialisiert (braucht model)
        self.fixed_cast_vars: dict[tuple[datetime.date, str, UUID], IntVar] = {}
        self.preference_vars: list[IntVar] = []
    
    # -------------------------------------------------------------------------
    # Private Hilfsmethoden
    # -------------------------------------------------------------------------
    
    def _check_pers_id_in_shift_vars(self, pers_id: UUID, cast_group) -> IntVar:
        """Prüft ob eine Person einer CastGroup zugewiesen ist."""
        var = self.model.NewBoolVar('')
        self.model.Add(var == sum(
            shift_var for (adg_id, eg_id), shift_var in self.entities.shift_vars.items()
            if eg_id == cast_group.event.event_group.id
            and self.entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id == pers_id
        ))
        return var
    
    def _create_var_and(self, var_list: list[IntVar]) -> IntVar:
        """Erstellt AND-Verknüpfung: Ergebnis ist 1 wenn alle Variablen 1 sind."""
        var = self.model.NewBoolVar('')
        self.model.AddMultiplicationEquality(var, var_list)
        return var
    
    def _create_var_or(self, var_list: list[IntVar]) -> IntVar:
        """Erstellt OR-Verknüpfung: Ergebnis ist >= 1 wenn mindestens eine Variable 1 ist."""
        var = self.model.NewBoolVar('')
        self.model.Add(var == sum(var_list))
        return var
    
    def _proof_recursive(self, fixed_cast_list: tuple | str, cast_group) -> IntVar:
        """
        Rekursive Bewertung der fixed_cast Struktur.
        
        Args:
            fixed_cast_list: Geparste fixed_cast Struktur (verschachtelt)
            cast_group: Die zugehörige CastGroup
        
        Returns:
            BoolVar die 1 ist wenn die Besetzung erfüllt ist
        """
        if isinstance(fixed_cast_list, str):
            return self._check_pers_id_in_shift_vars(UUID(fixed_cast_list), cast_group)
        
        pers_ids = [v for i, v in enumerate(fixed_cast_list) if not i % 2]
        operators = [v for i, v in enumerate(fixed_cast_list) if i % 2]
        
        if any(o != operators[0] for o in operators):
            raise Exception('Alle Operatoren müssen gleich sein!')  # sourcery skip: raise-specific-error
        else:
            operator = operators[0]

        if operator == 'and':
            return self._create_var_and([self._proof_recursive(p_id, cast_group) for p_id in pers_ids])
        else:
            return self._create_var_or([self._proof_recursive(p_id, cast_group) for p_id in pers_ids])
    
    def _parse_and_filter_fixed_cast(self, cast_group) -> tuple | str | None:
        """
        Parsed fixed_cast String und filtert optional nicht verfügbare Personen.
        
        Args:
            cast_group: CastGroup mit fixed_cast String
        
        Returns:
            - Parsed fixed_cast_as_list wenn verfügbare Personen vorhanden
            - None wenn keine Personen übrig bleiben (bei only_if_available)
        """
        # String wird zu Python-Objekt umgewandelt
        fixed_cast_as_list = literal_eval(
            cast_group.fixed_cast
            .replace('and', ',"and",')
            .replace('or', ',"or",')
            .replace('in team', '')
            .replace('UUID', '')
        )
        
        # Wenn only_if_available aktiviert ist, filtere nicht verfügbare Personen
        if cast_group.fixed_cast_only_if_available:
            fixed_cast_as_list = filter_unavailable_persons(
                fixed_cast_as_list, 
                cast_group,
                self.entities
            )
            
            # Falls nach dem Filtern keine Personen übrig sind
            if not fixed_cast_as_list or is_empty_list(fixed_cast_as_list):
                return None
        
        return fixed_cast_as_list
    
    def _extract_person_uuids(self, fixed_cast_list: tuple | str) -> list[UUID]:
        """
        Extrahiert alle Person-UUIDs aus der verschachtelten fixed_cast Struktur.
        
        Args:
            fixed_cast_list: Parsed fixed_cast_as_list (kann verschachtelt sein)
        
        Returns:
            Liste aller Person-UUIDs (ohne Operatoren wie 'and', 'or')
        """
        if isinstance(fixed_cast_list, str):
            # Einzelne UUID
            return [UUID(fixed_cast_list)]
        
        # Tuple mit mehreren Elementen - sammle rekursiv alle UUIDs
        result = []
        for element in fixed_cast_list:
            if isinstance(element, str):
                # Überspringe Operatoren
                if element not in ('and', 'or'):
                    result.append(UUID(element))
            else:
                # Rekursiver Aufruf für verschachtelte Strukturen
                result.extend(self._extract_person_uuids(element))
        
        return result
    
    def _has_only_and_operators(self, fixed_cast_list: tuple | str) -> bool:
        """
        Prüft ob die fixed_cast Struktur ausschließlich AND-Operatoren enthält.
        
        Wenn nur AND-Operatoren vorhanden sind, können wir pro Person eine Penalty-Variable
        erstellen. Bei OR-Operatoren ist die Semantik anders (mindestens einer muss besetzt sein),
        daher verwenden wir in dem Fall die alte Event-basierte Logik.
        
        Args:
            fixed_cast_list: Parsed fixed_cast_as_list (kann verschachtelt sein)
        
        Returns:
            True wenn nur AND-Operatoren (oder keine Operatoren), False bei OR-Operatoren
        """
        if isinstance(fixed_cast_list, str):
            # Einzelne UUID - kein Operator
            return True
        
        # Prüfe alle Operatoren in der Struktur
        for element in fixed_cast_list:
            if isinstance(element, str):
                if element == 'or':
                    return False  # OR gefunden!
                # 'and' ist ok, andere Strings sind UUIDs (ok)
            else:
                # Rekursiv in verschachtelte Strukturen
                if not self._has_only_and_operators(element):
                    return False
        
        return True
    
    # -------------------------------------------------------------------------
    # Hauptlogik
    # -------------------------------------------------------------------------
    
    def apply(self) -> None:
        """
        Erstellt alle Constraints für feste Besetzungen.
        
        Teil 1: fixed_cast_vars (Hard Constraints)
        Teil 2: preference_vars (Soft Constraints für prefer_fixed_cast_events)
        """
        # =====================================================================
        # Teil 1: fixed_cast_vars erstellen
        # =====================================================================
        # Initialisiere fixed_cast_vars mit Dummy-Eintrag (wie Original)
        self.fixed_cast_vars = {
            (datetime.date(1999, 1, 1), 'dummy', UUID('00000000-0000-0000-0000-000000000000')): self.model.NewBoolVar('')
        }
        
        for cast_group in self.entities.cast_groups_with_event.values():
            if not cast_group.fixed_cast:
                continue

            # Parsed fixed_cast und filtere optional nicht verfügbare Personen
            fixed_cast_as_list = self._parse_and_filter_fixed_cast(cast_group)
            if fixed_cast_as_list is None:
                continue

            text_fixed_cast_persons = generate_fixed_cast_clear_text(
                cast_group.fixed_cast,
                cast_group.fixed_cast_only_if_available,
                cast_group.prefer_fixed_cast_events
            )
            text_fixed_cast_var = (
                f'Datum: {cast_group.event.date: %d.%m.%y} ({cast_group.event.time_of_day.name})\n'
                f'Ort: {cast_group.event.location_plan_period.location_of_work.name_an_city}\n'
                f'Besetzung: {text_fixed_cast_persons}'
            )

            key = (cast_group.event.date, cast_group.event.time_of_day.name, cast_group.event.id)
            self.fixed_cast_vars[key] = self.model.NewBoolVar(text_fixed_cast_var)

            # Constraint: fixed_cast_vars[key] == NOT(proof_recursive(...))
            # Das bedeutet: Variable ist 1 wenn Besetzung NICHT erfüllt ist
            (self.model.Add(self.fixed_cast_vars[key] == self._proof_recursive(fixed_cast_as_list, cast_group).Not())
             .OnlyEnforceIf(self.entities.event_group_vars[cast_group.event.event_group.id]))
        
        # =====================================================================
        # Teil 2: prefer_fixed_cast_events Penalty-Variablen erstellen
        # =====================================================================
        
        print("\n" + "="*80)
        print("DEBUG: prefer_fixed_cast_events - Penalty-Variablen werden erstellt")
        print("="*80)
        
        for cast_group in self.entities.cast_groups_with_event.values():
            # 1. Grundvoraussetzungen prüfen
            if not (cast_group.fixed_cast and cast_group.prefer_fixed_cast_events):
                continue
            
            print(f"\nEvent gefunden: {cast_group.event.date:%d.%m.%y} "
                  f"({cast_group.event.time_of_day.name}), "
                  f"{cast_group.event.location_plan_period.location_of_work.name_an_city}")
            
            # 2. Relevanz-Prüfung: Ist Preference überhaupt relevant?
            parent_cast_group = cast_group.parent
            if not parent_cast_group:
                print("     ✗ Übersprungen: Keine Parent-Group (keine Auswahl)")
                continue  # Keine Parent-Group → keine Auswahl → Preference irrelevant
            
            # Hole die zugehörige EventGroup
            event_group_id = cast_group.event.event_group.id
            event_group = self.entities.event_groups_with_event.get(event_group_id)
            if not event_group or not event_group.parent:
                print("     ✗ Übersprungen: Keine Parent EventGroup")
                continue  # Keine Parent EventGroup → Preference irrelevant
            
            parent_event_group = event_group.parent
            
            # Prüfe ob Parent überhaupt eine Auswahl trifft
            nr_of_active_children = parent_event_group.nr_of_active_children
            if nr_of_active_children is None:
                print("     ✗ Übersprungen: Alle Children werden ausgewählt (nr_of_active_children=None)")
                continue  # Alle Children werden ausgewählt → Preference irrelevant
            
            # Zähle die Children der Parent-Group die Events haben
            children_with_event = [c for c in parent_event_group.children if c.event]
            if nr_of_active_children >= len(children_with_event):
                print(f"     ✗ Übersprungen: Alle Events werden ausgewählt "
                      f"(nr_of_active_children={nr_of_active_children} >= "
                      f"children_with_event={len(children_with_event)})")
                continue  # Alle Events werden ausgewählt → Preference irrelevant
            
            # 3. Verfügbarkeits-Prüfung (bei fixed_cast_only_if_available)
            fixed_cast_as_list = self._parse_and_filter_fixed_cast(cast_group)
            if fixed_cast_as_list is None:
                print("     ✗ Übersprungen: Event nicht besetzbar (keine verfügbaren Personen)")
                continue  # Keine Preference wenn Event nicht besetzbar
            
            print(f"     ✓ Relevanz-Check bestanden! nr_of_active_children={nr_of_active_children}, "
                  f"children_with_event={len(children_with_event)}")
            
            # 4. Erstelle Preference-Variable basierend auf Operator-Typ
            # TODO: Verbesserungspotential für komplexe OR-Logik
            #
            # AKTUELLES VERHALTEN:
            # - Bei reinem AND (z.B. "uuid1 AND uuid2"): Pro Mitarbeiter 1 Penalty
            #   → 2 Mitarbeiter nicht besetzt = 2 Penalties ✓
            #
            # - Bei OR-Operatoren (z.B. "uuid1 OR uuid2"): 1 Penalty pro Event
            #   → Semantisch: "Mindestens einer muss besetzt sein"
            #   → Aktuell: Event-basierte Penalty (entweder 0 oder 1)
            #
            # PROBLEM:
            # - Komplexe Strukturen wie "((uuid1 AND uuid2) OR uuid3)" werden nicht optimal behandelt
            # - Bei reinem OR: Unterscheidung nicht möglich zwischen "1 von 2 besetzt" vs "0 von 2 besetzt"
            #
            # MÖGLICHE VERBESSERUNG:
            # - Rekursive Operator-Logik analog zu proof_recursive()
            # - Zähle "erforderliche Mindestbesetzung" statt binär Event ja/nein
            # - Beispiel: "(uuid1 AND uuid2) OR uuid3" → Min 1 Slot erforderlich, nicht 3 Personen
            #
            # AUFWAND: Hoch (komplexe rekursive Logik)
            # NUTZEN: Gering (die meisten fixed_casts sind einfache ANDs)
            # ENTSCHEIDUNG: Aktuell "gut genug" - bei Bedarf später erweitern
            
            if self._has_only_and_operators(fixed_cast_as_list):
                # Strategie A: Pro-Person Penalties (bei reinem AND)
                print(f"     📊 Strategie A: Pro-Person Penalties (nur AND-Operatoren)")
                
                # Extrahiere alle Person-UUIDs aus der verschachtelten Struktur
                person_uuids = self._extract_person_uuids(fixed_cast_as_list)
                print(f"        Anzahl Personen in fixed_cast: {len(person_uuids)}")
                
                for idx, person_uuid in enumerate(person_uuids, 1):
                    # Prüfe ob diese Person dem Event zugewiesen ist
                    is_assigned_var = self._check_pers_id_in_shift_vars(person_uuid, cast_group)
                    
                    # Erstelle Penalty-Variable: 1 wenn Mitarbeiter NICHT zugewiesen
                    person = next(
                        (app.person for app in self.entities.actor_plan_periods.values() 
                         if app.person.id == person_uuid),
                        None
                    )
                    person_name = person.f_name if person else str(person_uuid)[:8]
                    
                    penalty_var = self.model.NewIntVar(0, 1, 
                        f'Prefer: {cast_group.event.date:%d.%m.%y} '
                        f'({cast_group.event.time_of_day.name}), '
                        f'{cast_group.event.location_plan_period.location_of_work.name_an_city}, '
                        f'{person_name}'
                    )
                    
                    # penalty_var = 1 wenn Mitarbeiter NICHT zugewiesen
                    # penalty_var = 0 wenn Mitarbeiter zugewiesen
                    self.model.Add(penalty_var == 1 - is_assigned_var)
                    
                    self.preference_vars.append(penalty_var)
                    print(f"        [{idx}/{len(person_uuids)}] Penalty-Variable erstellt für: {person_name}")
            else:
                # Strategie B: Event-basierte Penalty (bei OR-Operatoren)
                print(f"     📊 Strategie B: Event-basierte Penalty (enthält OR-Operatoren)")
                
                # Fallback auf alte Logik: 1 Penalty wenn Event nicht gewählt
                penalty_var = self.model.NewIntVar(0, 1, 
                    f'Prefer: {cast_group.event.date:%d.%m.%y} '
                    f'({cast_group.event.time_of_day.name}), '
                    f'{cast_group.event.location_plan_period.location_of_work.name_an_city}'
                )
                
                # penalty_var = 1 wenn Event NICHT ausgewählt (entities.event_group_vars[...] == 0)
                # penalty_var = 0 wenn Event ausgewählt (entities.event_group_vars[...] == 1)
                self.model.Add(penalty_var == 1 - self.entities.event_group_vars[event_group_id])
                
                self.preference_vars.append(penalty_var)
                print(f"        [1/1] Event-basierte Penalty-Variable erstellt")
        
        # =====================================================================
        
        print("\n" + "="*80)
        print(f"DEBUG: Zusammenfassung prefer_fixed_cast_events")
        print(f"  Gesamtanzahl Penalty-Variablen erstellt: {len(self.preference_vars)}")
        print("="*80 + "\n")
    
    def get_results(self) -> tuple[dict[tuple[datetime.date, str, UUID], IntVar], list[IntVar]]:
        """
        Gibt die Ergebnisse im Format der Original-Funktion zurück.
        
        Returns:
            tuple mit (fixed_cast_vars dict, preference_vars list)
        """
        return self.fixed_cast_vars, self.preference_vars
