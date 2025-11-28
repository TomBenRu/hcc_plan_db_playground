# sat_solver/constraints/test_integration.py
"""
Integrationstest für die neue Constraint-Registry-Architektur.

Dieser Test vergleicht die Ergebnisse der alten add_constraints_location_prefs()
Funktion mit der neuen LocationPrefsConstraint-Klasse.

Ausführen mit: python -m sat_solver.constraints.test_integration
"""

import sys
import os

# Projekt-Root zum Path hinzufügen
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from uuid import UUID

from ortools.sat.python import cp_model

# Importiere die bestehende Infrastruktur
from sat_solver.solver_main import (
    Entities,
    entities as global_entities,
    create_data_models,
    create_vars,
    add_constraints_location_prefs,
    add_constraints_employee_availability,
    add_constraints_avail_day_groups_activity,
    add_constraints_num_shifts_in_avail_day_groups,
    add_constraints_partner_location_prefs,
    add_constraints_weights_in_avail_day_groups,
    add_constraints_weights_in_event_groups,
    add_constraints_skills,
    add_constraints_unsigned_shifts,
    add_constraints_required_avail_day_groups,
    add_constraints_different_casts_on_shifts_with_different_locations_on_same_day,
    add_constraints_rel_shift_deviations,
    add_constraints_cast_rules,
    add_constraints_fixed_cast,
)
from sat_solver.event_group_tree import get_event_group_tree
from sat_solver.avail_day_group_tree import get_avail_day_group_tree
from sat_solver.cast_group_tree import get_cast_group_tree

# Importiere die neue Registry-Architektur
from sat_solver.constraints.registry import ConstraintRegistry
from sat_solver.constraints.location_prefs import LocationPrefsConstraint
from sat_solver.constraints.employee_availability import EmployeeAvailabilityConstraint
from sat_solver.constraints.avail_day_groups_activity import AvailDayGroupsActivityConstraint
from sat_solver.constraints.num_shifts_in_avail_day_groups import NumShiftsInAvailDayGroupsConstraint
from sat_solver.constraints.partner_location_prefs import PartnerLocationPrefsConstraint
from sat_solver.constraints.weights_in_avail_day_groups import WeightsInAvailDayGroupsConstraint
from sat_solver.constraints.weights_in_event_groups import WeightsInEventGroupsConstraint
from sat_solver.constraints.skills import SkillsConstraint
from sat_solver.constraints.unsigned_shifts import UnsignedShiftsConstraint
from sat_solver.constraints.required_avail_day_groups import RequiredAvailDayGroupsConstraint
from sat_solver.constraints.different_casts_same_day import DifferentCastsSameDayConstraint
from sat_solver.constraints.rel_shift_deviations import RelShiftDeviationsConstraint
from sat_solver.constraints.cast_rules import CastRulesConstraint
from sat_solver.constraints.fixed_cast import FixedCastConstraint

# Für Datenbankzugriff
from database import db_services


def get_test_plan_period_id() -> UUID | None:
    """
    Holt eine PlanPeriod-ID aus der Datenbank für den Test.
    
    Returns:
        Eine PlanPeriod-UUID oder None wenn keine gefunden
    """
    try:
        # Hole alle Projekte
        projects = db_services.Project.get_all()
        if not projects:
            print("   Keine Projekte gefunden")
            return None
        
        # Hole alle PlanPeriods vom ersten Projekt
        plan_periods = db_services.PlanPeriod.get_all_from__project(projects[0].id)
        
        if not plan_periods:
            print("   Keine PlanPeriods gefunden")
            return None
        
        # Nimm die erste PlanPeriod die Events hat
        for pp in plan_periods:
            # Hole vollständige PlanPeriod mit allen Relationen
            pp_full = db_services.PlanPeriod.get(pp.id)
            if pp_full.location_plan_periods:
                for lpp in pp_full.location_plan_periods:
                    # LocationPlanPeriod aus db_services holen für events
                    lpp_full = db_services.LocationPlanPeriod.get(lpp.id)
                    if lpp_full.events:
                        print(f"   Verwende PlanPeriod: {pp.start} - {pp.end}")
                        return pp.id
        
        print("   Keine PlanPeriod mit Events gefunden")
        return None
    except Exception as e:
        print(f"   Fehler beim Laden der PlanPeriod: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_location_prefs_constraint_equivalence(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue LocationPrefsConstraint-Klasse die gleichen
    Ergebnisse liefert wie die alte add_constraints_location_prefs() Funktion.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: LocationPrefsConstraint vs add_constraints_location_prefs()")
    print("=" * 70)
    
    # ===== SETUP: Gemeinsame Datenstrukturen =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== TEST 1: Alte Implementierung =====
    print("\n[2] Teste ALTE Implementierung (add_constraints_location_prefs)...")
    
    # Globale entities initialisieren (wie in solver_main.py)
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_penalty_vars = add_constraints_location_prefs(model_old)
    
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== TEST 2: Neue Implementierung =====
    print("\n[3] Teste NEUE Implementierung (LocationPrefsConstraint)...")
    
    # Entities neu initialisieren
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    location_prefs_constraint = registry.register(LocationPrefsConstraint)
    location_prefs_constraint.apply()
    
    new_penalty_vars = location_prefs_constraint.penalty_vars
    
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt überein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen (als Proxy für die Constraint-Logik)
    old_names = sorted([v.Name() for v in old_penalty_vars])
    new_names = sorted([v.Name() for v in new_penalty_vars])
    
    if old_names != new_names:
        print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
        # Zeige Unterschiede
        old_set = set(old_names)
        new_set = set(new_names)
        only_old = old_set - new_set
        only_new = new_set - old_set
        if only_old:
            print(f"      Nur in alt: {list(only_old)[:5]}...")
        if only_new:
            print(f"      Nur in neu: {list(only_new)[:5]}...")
        success = False
    else:
        print(f"   [OK] Variablen-Namen stimmen überein")
    
    # Vergleiche Wertebereiche
    old_bounds = [(v.Proto().domain[0], v.Proto().domain[-1]) for v in old_penalty_vars]
    new_bounds = [(v.Proto().domain[0], v.Proto().domain[-1]) for v in new_penalty_vars]
    
    if sorted(old_bounds) != sorted(new_bounds):
        print(f"   [FAIL] FEHLER: Wertebereiche unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] Wertebereiche stimmen überein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist äquivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_registry_integration(plan_period_id: UUID) -> bool:
    """
    Testet die vollständige Registry-Integration.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: Registry-Integration")
    print("=" * 70)
    
    # Setup
    print("\n[1] Setup...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model = cp_model.CpModel()
    create_vars(model, event_group_tree, avail_day_group_tree)
    
    # Registry erstellen
    print("\n[2] Registry erstellen und Constraint registrieren...")
    
    registry = ConstraintRegistry(model, solver_main.entities)
    
    # Constraint registrieren
    constraint = registry.register(LocationPrefsConstraint)
    
    print(f"   Registry: {registry}")
    print(f"   Constraint: {constraint}")
    print(f"   Weight: {constraint.get_weight()}")
    
    # Constraint anwenden
    print("\n[3] Constraint anwenden...")
    
    registry.apply_all()
    
    print(f"   Penalty-Variablen erstellt: {len(constraint.penalty_vars)}")
    
    # Weighted Penalty testen
    print("\n[4] Weighted Penalty berechnen...")
    
    total_penalty = registry.get_total_weighted_penalty()
    print(f"   Total weighted penalty expression erstellt: {type(total_penalty)}")
    
    # Penalty Summary testen (ohne echtes Solving)
    print("\n[5] Penalty-Variablen Info...")
    
    all_penalties = registry.get_all_penalty_vars()
    for name, vars in all_penalties.items():
        print(f"   {name}: {len(vars)} Variablen")
    
    print("\n" + "-" * 70)
    print("[OK] Registry-Integration funktioniert!")
    print("-" * 70)
    
    return True



def test_employee_availability_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue EmployeeAvailabilityConstraint-Klasse korrekt funktioniert.
    
    Da dies ein Hard Constraint ohne Penalty-Variablen ist, vergleichen wir:
    1. Anzahl der nicht-verfügbaren Shifts
    2. Ob beide Implementierungen die gleichen Constraints setzen
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: EmployeeAvailabilityConstraint vs add_constraints_employee_availability()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Zähle nicht-verfügbare Shifts VOR dem Constraint
    unavailable_count = sum(1 for v in solver_main.entities.shifts_exclusive.values() if not v)
    print(f"   Nicht-verfügbare Shift-Kombinationen: {unavailable_count}")
    
    # Alte Funktion aufrufen
    add_constraints_employee_availability(model_old)
    old_constraint_count = model_old.Proto().constraints.__len__()
    print(f"   Constraints im Model nach alter Implementierung: {old_constraint_count}")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(EmployeeAvailabilityConstraint)
    constraint.apply()
    
    new_constraint_count = model_new.Proto().constraints.__len__()
    print(f"   Constraints im Model nach neuer Implementierung: {new_constraint_count}")
    
    # Verifiziere: Keine Penalty-Variablen (Hard Constraint)
    print(f"   Penalty-Variablen (erwartet 0): {len(constraint.penalty_vars)}")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Constraints
    if old_constraint_count != new_constraint_count:
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Constraints!")
        print(f"      Alt: {old_constraint_count}, Neu: {new_constraint_count}")
        success = False
    else:
        print(f"   [OK] Anzahl Constraints stimmt überein: {old_constraint_count}")
    
    # Verifiziere keine Penalty-Variablen
    if len(constraint.penalty_vars) != 0:
        print(f"   [FAIL] FEHLER: Hard Constraint sollte keine Penalty-Variablen haben!")
        success = False
    else:
        print(f"   [OK] Keine Penalty-Variablen (korrekt für Hard Constraint)")
    
    # Verifiziere dass unavailable_count == Anzahl neuer Constraints
    # (jeder nicht-verfügbare Shift erzeugt ein Constraint)
    if unavailable_count != old_constraint_count:
        print(f"   [INFO] Hinweis: {unavailable_count} nicht-verfügbare Shifts, {old_constraint_count} Constraints")
        print(f"      (Differenz kann durch vorherige Constraints entstehen)")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_avail_day_groups_activity_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue AvailDayGroupsActivityConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: AvailDayGroupsActivityConstraint vs add_constraints_avail_day_groups_activity()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Zähle Avail-Day-Groups mit Kindern
    groups_with_children = sum(
        1 for adg in solver_main.entities.avail_day_groups.values() 
        if adg.children
    )
    print(f"   Avail-Day-Groups mit Kindern: {groups_with_children}")
    
    # Alte Funktion aufrufen
    add_constraints_avail_day_groups_activity(model_old)
    old_constraint_count = model_old.Proto().constraints.__len__()
    print(f"   Constraints im Model nach alter Implementierung: {old_constraint_count}")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(AvailDayGroupsActivityConstraint)
    constraint.apply()
    
    new_constraint_count = model_new.Proto().constraints.__len__()
    print(f"   Constraints im Model nach neuer Implementierung: {new_constraint_count}")
    
    # Verifiziere: Keine Penalty-Variablen (Hard Constraint)
    print(f"   Penalty-Variablen (erwartet 0): {len(constraint.penalty_vars)}")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Constraints
    if old_constraint_count != new_constraint_count:
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Constraints!")
        print(f"      Alt: {old_constraint_count}, Neu: {new_constraint_count}")
        success = False
    else:
        print(f"   [OK] Anzahl Constraints stimmt überein: {old_constraint_count}")
    
    # Verifiziere keine Penalty-Variablen
    if len(constraint.penalty_vars) != 0:
        print(f"   [FAIL] FEHLER: Hard Constraint sollte keine Penalty-Variablen haben!")
        success = False
    else:
        print(f"   [OK] Keine Penalty-Variablen (korrekt für Hard Constraint)")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_num_shifts_in_avail_day_groups_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue NumShiftsInAvailDayGroupsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: NumShiftsInAvailDayGroupsConstraint vs add_constraints_num_shifts_in_avail_day_groups()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Zähle shift_vars
    shift_vars_count = len(solver_main.entities.shift_vars)
    print(f"   Anzahl shift_vars: {shift_vars_count}")
    
    # Alte Funktion aufrufen
    add_constraints_num_shifts_in_avail_day_groups(model_old)
    old_constraint_count = model_old.Proto().constraints.__len__()
    print(f"   Constraints im Model nach alter Implementierung: {old_constraint_count}")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(NumShiftsInAvailDayGroupsConstraint)
    constraint.apply()
    
    new_constraint_count = model_new.Proto().constraints.__len__()
    print(f"   Constraints im Model nach neuer Implementierung: {new_constraint_count}")
    
    # Verifiziere: Keine Penalty-Variablen (Hard Constraint)
    print(f"   Penalty-Variablen (erwartet 0): {len(constraint.penalty_vars)}")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Constraints
    if old_constraint_count != new_constraint_count:
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Constraints!")
        print(f"      Alt: {old_constraint_count}, Neu: {new_constraint_count}")
        success = False
    else:
        print(f"   [OK] Anzahl Constraints stimmt überein: {old_constraint_count}")
    
    # Verifiziere keine Penalty-Variablen
    if len(constraint.penalty_vars) != 0:
        print(f"   [FAIL] FEHLER: Hard Constraint sollte keine Penalty-Variablen haben!")
        success = False
    else:
        print(f"   [OK] Keine Penalty-Variablen (korrekt für Hard Constraint)")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_partner_location_prefs_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue PartnerLocationPrefsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: PartnerLocationPrefsConstraint vs add_constraints_partner_location_prefs()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_penalty_vars = add_constraints_partner_location_prefs(model_old)
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(PartnerLocationPrefsConstraint)
    constraint.apply()
    
    new_penalty_vars = constraint.penalty_vars
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt überein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen
    old_names = sorted([v.Name() for v in old_penalty_vars])
    new_names = sorted([v.Name() for v in new_penalty_vars])
    
    if old_names != new_names:
        print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] Variablen-Namen stimmen überein")
    
    # Vergleiche Wertebereiche
    if old_penalty_vars and new_penalty_vars:
        old_bounds = [(v.Proto().domain[0], v.Proto().domain[-1]) for v in old_penalty_vars]
        new_bounds = [(v.Proto().domain[0], v.Proto().domain[-1]) for v in new_penalty_vars]
        
        if sorted(old_bounds) != sorted(new_bounds):
            print(f"   [FAIL] FEHLER: Wertebereiche unterscheiden sich!")
            success = False
        else:
            print(f"   [OK] Wertebereiche stimmen überein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_weights_in_avail_day_groups_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue WeightsInAvailDayGroupsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: WeightsInAvailDayGroupsConstraint vs add_constraints_weights_in_avail_day_groups()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_penalty_vars = add_constraints_weights_in_avail_day_groups(model_old)
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(WeightsInAvailDayGroupsConstraint)
    constraint.apply()
    
    new_penalty_vars = constraint.penalty_vars
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt überein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen
    old_names = sorted([v.Name() for v in old_penalty_vars])
    new_names = sorted([v.Name() for v in new_penalty_vars])
    
    if old_names != new_names:
        print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] Variablen-Namen stimmen überein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_weights_in_event_groups_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue WeightsInEventGroupsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: WeightsInEventGroupsConstraint vs add_constraints_weights_in_event_groups()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_penalty_vars = add_constraints_weights_in_event_groups(model_old)
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(WeightsInEventGroupsConstraint)
    constraint.apply()
    
    new_penalty_vars = constraint.penalty_vars
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt überein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen
    old_names = sorted([v.Name() for v in old_penalty_vars])
    new_names = sorted([v.Name() for v in new_penalty_vars])
    
    if old_names != new_names:
        print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] Variablen-Namen stimmen überein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_skills_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue SkillsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: SkillsConstraint vs add_constraints_skills()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_penalty_vars = add_constraints_skills(model_old)
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(SkillsConstraint)
    constraint.apply()
    
    new_penalty_vars = constraint.penalty_vars
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt überein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen (wenn vorhanden)
    if old_penalty_vars and new_penalty_vars:
        old_names = sorted([v.Name() for v in old_penalty_vars])
        new_names = sorted([v.Name() for v in new_penalty_vars])
        
        if old_names != new_names:
            print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
            success = False
        else:
            print(f"   [OK] Variablen-Namen stimmen überein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_unsigned_shifts_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue UnsignedShiftsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: UnsignedShiftsConstraint vs add_constraints_unsigned_shifts()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen (gibt dict zurück)
    old_result_dict = add_constraints_unsigned_shifts(model_old)
    old_penalty_vars = list(old_result_dict.values())
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(UnsignedShiftsConstraint)
    constraint.apply()
    
    new_penalty_vars = constraint.penalty_vars
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt überein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen
    old_names = sorted([v.Name() for v in old_penalty_vars])
    new_names = sorted([v.Name() for v in new_penalty_vars])
    
    if old_names != new_names:
        print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] Variablen-Namen stimmen überein")
    
    # Vergleiche Dict-Keys (für UnsignedShiftsConstraint spezifisch)
    old_keys = set(old_result_dict.keys())
    new_keys = set(constraint.unassigned_shifts_per_event.keys())
    
    if old_keys != new_keys:
        print(f"   [FAIL] FEHLER: Dict-Keys unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] Dict-Keys stimmen überein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_required_avail_day_groups_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue RequiredAvailDayGroupsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: RequiredAvailDayGroupsConstraint vs add_constraints_required_avail_day_groups()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Zähle Avail-Day-Groups mit required_avail_day_groups
    groups_with_required = sum(
        1 for adg in solver_main.entities.avail_day_groups.values() 
        if adg.required_avail_day_groups
    )
    print(f"   Avail-Day-Groups mit required_avail_day_groups: {groups_with_required}")
    
    # Alte Funktion aufrufen
    add_constraints_required_avail_day_groups(model_old)
    old_constraint_count = model_old.Proto().constraints.__len__()
    print(f"   Constraints im Model nach alter Implementierung: {old_constraint_count}")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(RequiredAvailDayGroupsConstraint)
    constraint.apply()
    
    new_constraint_count = model_new.Proto().constraints.__len__()
    print(f"   Constraints im Model nach neuer Implementierung: {new_constraint_count}")
    
    # Verifiziere: Keine Penalty-Variablen (Hard Constraint)
    print(f"   Penalty-Variablen (erwartet 0): {len(constraint.penalty_vars)}")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Constraints
    if old_constraint_count != new_constraint_count:
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Constraints!")
        print(f"      Alt: {old_constraint_count}, Neu: {new_constraint_count}")
        success = False
    else:
        print(f"   [OK] Anzahl Constraints stimmt überein: {old_constraint_count}")
    
    # Verifiziere keine Penalty-Variablen
    if len(constraint.penalty_vars) != 0:
        print(f"   [FAIL] FEHLER: Hard Constraint sollte keine Penalty-Variablen haben!")
        success = False
    else:
        print(f"   [OK] Keine Penalty-Variablen (korrekt für Hard Constraint)")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_different_casts_same_day_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue DifferentCastsSameDayConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: DifferentCastsSameDayConstraint vs add_constraints_different_casts_on_shifts...")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    add_constraints_different_casts_on_shifts_with_different_locations_on_same_day(model_old)
    old_constraint_count = model_old.Proto().constraints.__len__()
    print(f"   Constraints im Model nach alter Implementierung: {old_constraint_count}")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(DifferentCastsSameDayConstraint)
    constraint.apply()
    
    new_constraint_count = model_new.Proto().constraints.__len__()
    print(f"   Constraints im Model nach neuer Implementierung: {new_constraint_count}")
    
    # Verifiziere: Keine Penalty-Variablen (Hard Constraint)
    print(f"   Penalty-Variablen (erwartet 0): {len(constraint.penalty_vars)}")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Constraints
    if old_constraint_count != new_constraint_count:
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Constraints!")
        print(f"      Alt: {old_constraint_count}, Neu: {new_constraint_count}")
        success = False
    else:
        print(f"   [OK] Anzahl Constraints stimmt überein: {old_constraint_count}")
    
    # Verifiziere keine Penalty-Variablen
    if len(constraint.penalty_vars) != 0:
        print(f"   [FAIL] FEHLER: Hard Constraint sollte keine Penalty-Variablen haben!")
        success = False
    else:
        print(f"   [OK] Keine Penalty-Variablen (korrekt für Hard Constraint)")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success



def test_rel_shift_deviations_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue RelShiftDeviationsConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: RelShiftDeviationsConstraint vs add_constraints_rel_shift_deviations()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_sum_assigned_shifts, old_sum_squared_deviations = add_constraints_rel_shift_deviations(model_old)
    old_constraint_count = model_old.Proto().constraints.__len__()
    print(f"   Constraints im Model nach alter Implementierung: {old_constraint_count}")
    print(f"   sum_assigned_shifts Eintraege: {len(old_sum_assigned_shifts)}")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(RelShiftDeviationsConstraint)
    constraint.apply()
    
    new_constraint_count = model_new.Proto().constraints.__len__()
    new_sum_assigned_shifts, new_sum_squared_deviations = constraint.get_results()
    print(f"   Constraints im Model nach neuer Implementierung: {new_constraint_count}")
    print(f"   sum_assigned_shifts Eintraege: {len(new_sum_assigned_shifts)}")
    print(f"   Penalty-Variablen: {len(constraint.penalty_vars)}")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Constraints
    if old_constraint_count != new_constraint_count:
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Constraints!")
        print(f"      Alt: {old_constraint_count}, Neu: {new_constraint_count}")
        success = False
    else:
        print(f"   [OK] Anzahl Constraints stimmt ueberein: {old_constraint_count}")
    
    # Vergleiche sum_assigned_shifts Keys
    if set(old_sum_assigned_shifts.keys()) != set(new_sum_assigned_shifts.keys()):
        print(f"   [FAIL] FEHLER: sum_assigned_shifts Keys unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] sum_assigned_shifts Keys stimmen ueberein")
    
    # Vergleiche Variablen-Namen der sum_assigned_shifts
    old_names = sorted([v.Name() for v in old_sum_assigned_shifts.values()])
    new_names = sorted([v.Name() for v in new_sum_assigned_shifts.values()])
    
    if old_names != new_names:
        print(f"   [FAIL] FEHLER: sum_assigned_shifts Namen unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] sum_assigned_shifts Namen stimmen ueberein")
    
    # Verifiziere Penalty-Variable
    if len(constraint.penalty_vars) != 1:
        print(f"   [FAIL] FEHLER: Erwartet 1 Penalty-Variable, gefunden: {len(constraint.penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Eine Penalty-Variable vorhanden (sum_squared_deviations)")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success



def test_cast_rules_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue CastRulesConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: CastRulesConstraint vs add_constraints_cast_rules()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    from sat_solver import solver_variables
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    solver_variables.cast_rules.reset_fields()
    
    # Alte Funktion aufrufen
    old_penalty_vars = add_constraints_cast_rules(model_old)
    print(f"   Alte Implementierung: {len(old_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    solver_variables.cast_rules.reset_fields()
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(CastRulesConstraint)
    constraint.apply()
    
    new_penalty_vars = constraint.penalty_vars
    print(f"   Neue Implementierung: {len(new_penalty_vars)} Penalty-Variablen erstellt")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der Penalty-Variablen
    if len(old_penalty_vars) != len(new_penalty_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl Penalty-Variablen!")
        print(f"      Alt: {len(old_penalty_vars)}, Neu: {len(new_penalty_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl Penalty-Variablen stimmt ueberein: {len(old_penalty_vars)}")
    
    # Vergleiche Variablen-Namen (wenn vorhanden)
    if old_penalty_vars and new_penalty_vars:
        old_names = sorted([v.Name() for v in old_penalty_vars])
        new_names = sorted([v.Name() for v in new_penalty_vars])
        
        if old_names != new_names:
            print(f"   [FAIL] FEHLER: Variablen-Namen unterscheiden sich!")
            success = False
        else:
            print(f"   [OK] Variablen-Namen stimmen ueberein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def test_fixed_cast_constraint(plan_period_id: UUID) -> bool:
    """
    Testet ob die neue FixedCastConstraint-Klasse korrekt funktioniert.
    
    Args:
        plan_period_id: UUID der zu testenden PlanPeriod
    
    Returns:
        True wenn die Tests erfolgreich sind
    """
    print("\n" + "=" * 70)
    print("TEST: FixedCastConstraint vs add_constraints_fixed_cast()")
    print("=" * 70)
    
    # ===== SETUP =====
    print("\n[1] Lade Datenstrukturen...")
    
    event_group_tree = get_event_group_tree(plan_period_id)
    avail_day_group_tree = get_avail_day_group_tree(plan_period_id)
    cast_group_tree = get_cast_group_tree(plan_period_id)
    
    # ===== ALTE IMPLEMENTIERUNG =====
    print("\n[2] Teste ALTE Implementierung...")
    
    import sat_solver.solver_main as solver_main
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_old = cp_model.CpModel()
    create_vars(model_old, event_group_tree, avail_day_group_tree)
    
    # Alte Funktion aufrufen
    old_fixed_cast_vars, old_preference_vars = add_constraints_fixed_cast(model_old)
    print(f"   Alte Implementierung: {len(old_fixed_cast_vars)} fixed_cast_vars, {len(old_preference_vars)} preference_vars")
    
    # ===== NEUE IMPLEMENTIERUNG =====
    print("\n[3] Teste NEUE Implementierung...")
    
    solver_main.entities = Entities()
    create_data_models(event_group_tree, avail_day_group_tree, cast_group_tree, plan_period_id)
    
    model_new = cp_model.CpModel()
    create_vars(model_new, event_group_tree, avail_day_group_tree)
    
    # Neue Registry-basierte Implementierung
    registry = ConstraintRegistry(model_new, solver_main.entities)
    constraint = registry.register(FixedCastConstraint)
    constraint.apply()
    
    # Ergebnisse holen (via get_results() für Kompatibilität)
    new_fixed_cast_vars, new_preference_vars = constraint.get_results()
    print(f"   Neue Implementierung: {len(new_fixed_cast_vars)} fixed_cast_vars, {len(new_preference_vars)} preference_vars")
    
    # ===== VERGLEICH =====
    print("\n[4] Vergleiche Ergebnisse...")
    
    success = True
    
    # Vergleiche Anzahl der fixed_cast_vars
    if len(old_fixed_cast_vars) != len(new_fixed_cast_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl fixed_cast_vars!")
        print(f"      Alt: {len(old_fixed_cast_vars)}, Neu: {len(new_fixed_cast_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl fixed_cast_vars stimmt ueberein: {len(old_fixed_cast_vars)}")
    
    # Vergleiche Keys der fixed_cast_vars
    old_keys = sorted(old_fixed_cast_vars.keys(), key=str)
    new_keys = sorted(new_fixed_cast_vars.keys(), key=str)
    
    if old_keys != new_keys:
        print(f"   [FAIL] FEHLER: fixed_cast_vars Keys unterscheiden sich!")
        success = False
    else:
        print(f"   [OK] fixed_cast_vars Keys stimmen ueberein")
    
    # Vergleiche Anzahl der preference_vars
    if len(old_preference_vars) != len(new_preference_vars):
        print(f"   [FAIL] FEHLER: Unterschiedliche Anzahl preference_vars!")
        print(f"      Alt: {len(old_preference_vars)}, Neu: {len(new_preference_vars)}")
        success = False
    else:
        print(f"   [OK] Anzahl preference_vars stimmt ueberein: {len(old_preference_vars)}")
    
    # Vergleiche Variablen-Namen der preference_vars
    if old_preference_vars and new_preference_vars:
        old_names = sorted([v.Name() for v in old_preference_vars])
        new_names = sorted([v.Name() for v in new_preference_vars])
        
        if old_names != new_names:
            print(f"   [FAIL] FEHLER: preference_vars Namen unterscheiden sich!")
            success = False
        else:
            print(f"   [OK] preference_vars Namen stimmen ueberein")
    
    # ===== ERGEBNIS =====
    print("\n" + "-" * 70)
    if success:
        print("[OK] TEST ERFOLGREICH: Neue Implementierung ist aequivalent zur alten!")
    else:
        print("[FAIL] TEST FEHLGESCHLAGEN: Implementierungen unterscheiden sich!")
    print("-" * 70)
    
    return success


def main():
    """Hauptfunktion für den Integrationstest."""
    print("\n" + "#" * 70)
    print("# INTEGRATIONSTEST: Constraint-Registry-Architektur")
    print("#" * 70)
    
    # Hole Test-PlanPeriod
    plan_period_id = get_test_plan_period_id()
    
    if not plan_period_id:
        print("\n[FAIL] Keine PlanPeriod mit Events gefunden!")
        print("   Bitte stelle sicher, dass die Datenbank Testdaten enthält.")
        return False
    
    # Tests ausführen
    all_passed = True
    
    try:
        # Test 1: Äquivalenz der Implementierungen
        if not test_location_prefs_constraint_equivalence(plan_period_id):
            all_passed = False
        
        # Test 2: EmployeeAvailabilityConstraint
        if not test_employee_availability_constraint(plan_period_id):
            all_passed = False
        
        # Test 3: AvailDayGroupsActivityConstraint
        if not test_avail_day_groups_activity_constraint(plan_period_id):
            all_passed = False
        
        # Test 4: NumShiftsInAvailDayGroupsConstraint
        if not test_num_shifts_in_avail_day_groups_constraint(plan_period_id):
            all_passed = False
        
        # Test 5: PartnerLocationPrefsConstraint
        if not test_partner_location_prefs_constraint(plan_period_id):
            all_passed = False
        
        # Test 6: WeightsInAvailDayGroupsConstraint
        if not test_weights_in_avail_day_groups_constraint(plan_period_id):
            all_passed = False
        
        # Test 7: WeightsInEventGroupsConstraint
        if not test_weights_in_event_groups_constraint(plan_period_id):
            all_passed = False
        
        # Test 8: SkillsConstraint
        if not test_skills_constraint(plan_period_id):
            all_passed = False
        
        # Test 9: UnsignedShiftsConstraint
        if not test_unsigned_shifts_constraint(plan_period_id):
            all_passed = False
        
        # Test 10: RequiredAvailDayGroupsConstraint
        if not test_required_avail_day_groups_constraint(plan_period_id):
            all_passed = False
        
        # Test 11: DifferentCastsSameDayConstraint
        if not test_different_casts_same_day_constraint(plan_period_id):
            all_passed = False
        
        # Test 12: RelShiftDeviationsConstraint
        if not test_rel_shift_deviations_constraint(plan_period_id):
            all_passed = False
        
        # Test 13: CastRulesConstraint
        if not test_cast_rules_constraint(plan_period_id):
            all_passed = False
        
        # Test 14: FixedCastConstraint
        if not test_fixed_cast_constraint(plan_period_id):
            all_passed = False
        
        # Test 15: Registry-Integration
        if not test_registry_integration(plan_period_id):
            all_passed = False
            
    except Exception as e:
        print(f"\n[FAIL] FEHLER während der Tests: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Zusammenfassung
    print("\n" + "#" * 70)
    if all_passed:
        print("# ALLE TESTS ERFOLGREICH [OK]")
    else:
        print("# EINIGE TESTS FEHLGESCHLAGEN [FAIL]")
    print("#" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
