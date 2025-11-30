"""
FixedCast Constraints - Rückwärtskompatibilität.

HINWEIS: Dieses Modul wurde in zwei separate Constraints aufgeteilt:
- FixedCastConflictsConstraint: Hard-Constraints für feste Besetzungen
- PreferFixedCastConstraint: Soft-Preferences für bevorzugte Events

Die alte FixedCastConstraint Klasse ist deprecated und wird hier nur
für Rückwärtskompatibilität bereitgestellt.

Für neue Implementierungen bitte die neuen Klassen verwenden:
    from sat_solver.constraints import (
        FixedCastConflictsConstraint,
        PreferFixedCastConstraint,
    )
"""

import warnings

# Re-Export der neuen Constraints
from sat_solver.constraints.fixed_cast_conflicts import FixedCastConflictsConstraint
from sat_solver.constraints.prefer_fixed_cast import PreferFixedCastConstraint

# Re-Export der Helper-Funktionen für Rückwärtskompatibilität
from sat_solver.constraints.fixed_cast_helpers import (
    is_person_available_for_event,
    filter_unavailable_persons,
    is_empty_list,
    parse_fixed_cast_string,
    parse_and_filter_fixed_cast,
    check_pers_id_in_shift_vars,
    create_var_and,
    create_var_or,
    proof_recursive,
    extract_person_uuids,
    has_only_and_operators,
)


# =============================================================================
# Deprecated: Alte FixedCastConstraint Klasse
# =============================================================================

class FixedCastConstraint:
    """
    DEPRECATED: Bitte FixedCastConflictsConstraint und PreferFixedCastConstraint verwenden.
    
    Diese Klasse existiert nur für Rückwärtskompatibilität mit altem Code.
    """
    
    def __init__(self):
        warnings.warn(
            "FixedCastConstraint ist deprecated. Verwende stattdessen "
            "FixedCastConflictsConstraint und PreferFixedCastConstraint.",
            DeprecationWarning,
            stacklevel=2
        )
        raise NotImplementedError(
            "FixedCastConstraint wurde aufgeteilt in:\n"
            "  - FixedCastConflictsConstraint (Hard-Constraints)\n"
            "  - PreferFixedCastConstraint (Soft-Preferences)\n"
            "Bitte aktualisiere deinen Code."
        )


__all__ = [
    # Neue Constraints
    'FixedCastConflictsConstraint',
    'PreferFixedCastConstraint',
    # Helper-Funktionen
    'is_person_available_for_event',
    'filter_unavailable_persons',
    'is_empty_list',
    'parse_fixed_cast_string',
    'parse_and_filter_fixed_cast',
    'check_pers_id_in_shift_vars',
    'create_var_and',
    'create_var_or',
    'proof_recursive',
    'extract_person_uuids',
    'has_only_and_operators',
    # Deprecated
    'FixedCastConstraint',
]
