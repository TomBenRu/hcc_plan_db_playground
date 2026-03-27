"""
Hilfsfunktionen für FixedCast-Constraints.

Gemeinsam genutzte Funktionen für:
- FixedCastConflictsConstraint (Hard-Constraints)
- PreferFixedCastConstraint (Soft-Preferences)
"""

from ast import literal_eval
from uuid import UUID

from ortools.sat.python import cp_model
from ortools.sat.python.cp_model import IntVar

from tools.helper_functions import generate_fixed_cast_clear_text


# =============================================================================
# Verfügbarkeitsprüfung
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
    # event.event_group_id ist direkter FK auf der Event-Tabelle (schemas.Event);
    # event.event_group.id (EventShow) ist nicht mehr verfügbar seit get_batch_for_solver → Event-Schema
    event_group_id = cast_group.event.event_group_id

    # O(1)-Lookup über person_event_availability (aufgebaut in populate_shifts_exclusive)
    if entities.person_event_availability:
        return entities.person_event_availability.get((person_id, event_group_id), False)

    # Fallback für den Fall dass person_event_availability nicht befüllt wurde
    available = next(
        (bool(val) for (adg_id, eg_id), val in entities.shifts_exclusive.items()
         if eg_id == event_group_id
         and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id == person_id),
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
# Parsing
# =============================================================================

def parse_fixed_cast_string(fixed_cast: str) -> tuple | str:
    """
    Parsed einen fixed_cast String in eine Python-Struktur.
    
    Args:
        fixed_cast: Der fixed_cast String (z.B. "UUID(...) and UUID(...)")
    
    Returns:
        Tuple oder String mit geparstem Inhalt
    """
    return literal_eval(
        fixed_cast
        .replace('and', ',"and",')
        .replace('or', ',"or",')
        .replace('in team', '')
        .replace('UUID', '')
    )


def parse_and_filter_fixed_cast(cast_group, entities) -> tuple | str | None:
    """
    Parsed fixed_cast String und filtert optional nicht verfügbare Personen.
    
    Args:
        cast_group: CastGroup mit fixed_cast String
        entities: Entities-Objekt mit Solver-Daten
    
    Returns:
        - Parsed fixed_cast_as_list wenn verfügbare Personen vorhanden
        - None wenn keine Personen übrig bleiben (bei only_if_available)
    """
    fixed_cast_as_list = parse_fixed_cast_string(cast_group.fixed_cast)
    
    # Wenn only_if_available aktiviert ist, filtere nicht verfügbare Personen
    if cast_group.fixed_cast_only_if_available:
        fixed_cast_as_list = filter_unavailable_persons(
            fixed_cast_as_list, 
            cast_group,
            entities
        )
        
        # Falls nach dem Filtern keine Personen übrig sind
        if not fixed_cast_as_list or is_empty_list(fixed_cast_as_list):
            return None
    
    return fixed_cast_as_list


# =============================================================================
# Solver-Variable Hilfsfunktionen
# =============================================================================

def check_pers_id_in_shift_vars(
    model: cp_model.CpModel,
    entities,
    pers_id: UUID, 
    cast_group
) -> IntVar:
    """
    Prüft ob eine Person einer CastGroup zugewiesen ist.
    
    Args:
        model: Das CP-SAT Model
        entities: Entities-Objekt mit shift_vars
        pers_id: UUID der Person
        cast_group: Die CastGroup
    
    Returns:
        BoolVar die 1 ist wenn Person zugewiesen, sonst 0
    """
    var = model.NewBoolVar('')
    model.Add(var == sum(
        shift_var for (adg_id, eg_id), shift_var in entities.shift_vars.items()
        if eg_id == cast_group.event.event_group_id
        and entities.avail_day_groups_with_avail_day[adg_id].avail_day.actor_plan_period.person.id == pers_id
    ))
    return var


def create_var_and(model: cp_model.CpModel, var_list: list[IntVar]) -> IntVar:
    """
    Erstellt AND-Verknüpfung: Ergebnis ist 1 wenn alle Variablen 1 sind.
    
    Args:
        model: Das CP-SAT Model
        var_list: Liste von BoolVars
    
    Returns:
        BoolVar mit AND-Verknüpfung
    """
    var = model.NewBoolVar('')
    model.AddMultiplicationEquality(var, var_list)
    return var


def create_var_or(model: cp_model.CpModel, var_list: list[IntVar]) -> IntVar:
    """
    Erstellt OR-Verknüpfung: Ergebnis ist >= 1 wenn mindestens eine Variable 1 ist.
    
    Args:
        model: Das CP-SAT Model
        var_list: Liste von BoolVars
    
    Returns:
        BoolVar mit OR-Verknüpfung
    """
    var = model.NewBoolVar('')
    model.Add(var == sum(var_list))
    return var


def proof_recursive(
    model: cp_model.CpModel,
    entities,
    fixed_cast_list: tuple | str, 
    cast_group
) -> IntVar:
    """
    Rekursive Bewertung der fixed_cast Struktur.
    
    Args:
        model: Das CP-SAT Model
        entities: Entities-Objekt
        fixed_cast_list: Geparste fixed_cast Struktur (verschachtelt)
        cast_group: Die zugehörige CastGroup
    
    Returns:
        BoolVar die 1 ist wenn die Besetzung erfüllt ist
    """
    if isinstance(fixed_cast_list, str):
        return check_pers_id_in_shift_vars(model, entities, UUID(fixed_cast_list), cast_group)
    
    pers_ids = [v for i, v in enumerate(fixed_cast_list) if not i % 2]
    operators = [v for i, v in enumerate(fixed_cast_list) if i % 2]
    
    if any(o != operators[0] for o in operators):
        raise Exception('Alle Operatoren müssen gleich sein!')
    else:
        operator = operators[0]

    if operator == 'and':
        return create_var_and(model, [proof_recursive(model, entities, p_id, cast_group) for p_id in pers_ids])
    else:
        return create_var_or(model, [proof_recursive(model, entities, p_id, cast_group) for p_id in pers_ids])


# =============================================================================
# Struktur-Analyse
# =============================================================================

def extract_person_uuids(fixed_cast_list: tuple | str) -> list[UUID]:
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
            result.extend(extract_person_uuids(element))
    
    return result


def has_only_and_operators(fixed_cast_list: tuple | str) -> bool:
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
            if not has_only_and_operators(element):
                return False
    
    return True


def evaluate_fixed_cast(fixed_cast_list: tuple | str, assigned_persons: set[UUID]) -> bool:
    """
    Evaluiert rekursiv die fixed_cast AND/OR-Logik.
    
    Prüft ob die Besetzungsanforderungen einer fixed_cast Struktur erfüllt sind,
    basierend auf den tatsächlich zugewiesenen Personen.
    
    Args:
        fixed_cast_list: Geparste fixed_cast Struktur (verschachtelt)
                         Ergebnis von parse_fixed_cast_string()
        assigned_persons: Set der zugewiesenen Person-UUIDs
    
    Returns:
        True wenn die Besetzungsanforderung erfüllt ist, sonst False
    """
    if isinstance(fixed_cast_list, str):
        # Einzelne Person-UUID
        return UUID(fixed_cast_list) in assigned_persons
    
    # Liste mit Operatoren
    # Struktur: (person_or_nested, operator, person_or_nested, operator, ...)
    elements = [v for i, v in enumerate(fixed_cast_list) if not i % 2]  # Personen/verschachtelte
    operators = [v for i, v in enumerate(fixed_cast_list) if i % 2]      # Operatoren
    
    if not operators:
        # Nur ein Element
        return evaluate_fixed_cast(elements[0], assigned_persons) if elements else True
    
    # Alle Operatoren müssen gleich sein (laut Parsing-Logik)
    operator = operators[0]
    
    # Evaluiere rekursiv alle Elemente
    results = [evaluate_fixed_cast(elem, assigned_persons) for elem in elements]
    
    if operator == 'and':
        # AND: Alle müssen True sein
        return all(results)
    else:
        # OR: Mindestens einer muss True sein
        return any(results)
