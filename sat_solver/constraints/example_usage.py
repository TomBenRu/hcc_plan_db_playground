"""
Beispiel für die Verwendung der Constraint-Registry-Architektur.

Diese Datei zeigt, wie die Registry-Architektur in solver_main.py verwendet wird.
Sie dient als Dokumentation und Referenz.
"""

from ortools.sat.python import cp_model

from configuration.solver import curr_config_handler
from sat_solver.constraints import (
    ConstraintRegistry,
    LocationPrefsConstraint,
    EmployeeAvailabilityConstraint,
    EventGroupsActivityConstraint,
    AvailDayGroupsActivityConstraint,
    NumShiftsInAvailDayGroupsConstraint,
    PartnerLocationPrefsConstraint,
    WeightsInAvailDayGroupsConstraint,
    WeightsInEventGroupsConstraint,
    SkillsConstraint,
    UnsignedShiftsConstraint,
    RequiredAvailDayGroupsConstraint,
    DifferentCastsSameDayConstraint,
    RelShiftDeviationsConstraint,
    CastRulesConstraint,
    FixedCastConflictsConstraint,
    PreferFixedCastConstraint,
)
from sat_solver.constraints.registry import Entities


def example_registry_architecture():
    """
    Zeigt die Registry-Architektur.
    
    ARCHITEKTUR (mit Registry):
    ---------------------------
    
    ```python
    def _create_constraints_with_registry(model, creating_test_constraints=False):
        # Imports
        from sat_solver.constraints import ConstraintRegistry, ...
        
        # Registry erstellen
        registry = ConstraintRegistry(model, entities)
        
        # Alle 16 Constraints registrieren
        registry.register(EmployeeAvailabilityConstraint)
        registry.register(EventGroupsActivityConstraint)
        registry.register(AvailDayGroupsActivityConstraint)
        if not creating_test_constraints:
            registry.register(RequiredAvailDayGroupsConstraint)
        registry.register(NumShiftsInAvailDayGroupsConstraint)
        
        weights_adg = registry.register(WeightsInAvailDayGroupsConstraint)
        location_prefs = registry.register(LocationPrefsConstraint)
        partner_loc = registry.register(PartnerLocationPrefsConstraint)
        unsigned = registry.register(UnsignedShiftsConstraint)
        weights_eg = registry.register(WeightsInEventGroupsConstraint)
        cast_rules = registry.register(CastRulesConstraint)
        skills = registry.register(SkillsConstraint)
        fixed_cast_conflicts = registry.register(FixedCastConflictsConstraint)
        prefer_fixed_cast = registry.register(PreferFixedCastConstraint)
        
        registry.register(DifferentCastsSameDayConstraint)
        rel_deviations = registry.register(RelShiftDeviationsConstraint)
        
        # Alle Constraints anwenden
        registry.apply_all()
        
        # Ergebnisse extrahieren für API-Kompatibilität
        return (
            unsigned.unassigned_shifts_per_event,
            rel_deviations.sum_assigned_shifts,
            rel_deviations.sum_squared_deviations,
            weights_adg.penalty_vars,
            weights_eg.penalty_vars,
            location_prefs.penalty_vars,
            partner_loc.penalty_vars,
            fixed_cast_conflicts.fixed_cast_vars,
            skills.penalty_vars,
            cast_rules.penalty_vars,
            prefer_fixed_cast.penalty_vars,
        )
    ```
    """
    pass


def demo_registry_usage():
    """
    Lauffähiges Demo der Registry-Architektur.
    
    HINWEIS: Dies ist ein vereinfachtes Beispiel. In der echten Implementierung
    müssen die Entities mit echten Daten gefüllt werden.
    """
    # 1. Model und Entities erstellen
    model = cp_model.CpModel()
    entities = Entities()
    
    # 2. Registry erstellen
    config = curr_config_handler.get_solver_config()
    registry = ConstraintRegistry(entities, model, config)
    
    # 3. Alle 16 Constraints registrieren
    registry.register(EmployeeAvailabilityConstraint)
    registry.register(EventGroupsActivityConstraint)
    registry.register(AvailDayGroupsActivityConstraint)
    registry.register(RequiredAvailDayGroupsConstraint)
    registry.register(NumShiftsInAvailDayGroupsConstraint)
    registry.register(WeightsInAvailDayGroupsConstraint)
    registry.register(LocationPrefsConstraint)
    registry.register(PartnerLocationPrefsConstraint)
    registry.register(UnsignedShiftsConstraint)
    registry.register(WeightsInEventGroupsConstraint)
    registry.register(CastRulesConstraint)
    registry.register(SkillsConstraint)
    registry.register(FixedCastConflictsConstraint)
    registry.register(PreferFixedCastConstraint)
    registry.register(DifferentCastsSameDayConstraint)
    registry.register(RelShiftDeviationsConstraint)
    
    # 4. Alle Constraints anwenden
    # HINWEIS: Würde fehlschlagen ohne echte Daten in entities
    # registry.apply_all()
    
    # 5. Objective-Funktion definieren
    # model.Minimize(registry.get_total_weighted_penalty())
    
    # 6. Solver ausführen
    # solver = cp_model.CpSolver()
    # status = solver.solve(model)
    
    # 7. Ergebnisse analysieren
    # registry.log_penalty_summary(solver)
    
    print("Registry erstellt:", registry)
    print("Registrierte Constraints:", [c.name for c in registry.constraints])


def demo_adding_new_constraint():
    """
    Zeigt wie einfach es ist, ein neues Constraint hinzuzufügen.
    
    Mit der Registry-Architektur:
    1. Neue Klasse erstellen die von ConstraintBase erbt
    2. name und weight_attribute definieren
    3. apply() implementieren
    4. In der Registry registrieren
    
    Das war's! Keine Änderungen an:
    - create_constraints() Signatur
    - define_objective_minimize() Signatur  
    - Tupel-Returns
    - Dutzenden von Aufrufstellen
    """
    from sat_solver.constraints.base import ConstraintBase
    
    class MyNewConstraint(ConstraintBase):
        """Beispiel für ein neues Constraint."""
        
        name = "my_new_constraint"
        weight_attribute = "constraints_my_new_feature"  # Muss in MinimizationWeights existieren
        
        def apply(self) -> None:
            # Constraint-Logik hier
            # self.model, self.entities, self.config sind verfügbar
            
            # Beispiel: Erstelle eine Penalty-Variable
            penalty = self.model.NewIntVar(0, 100, "my_penalty")
            
            # Füge zur Penalty-Liste hinzu
            self.penalty_vars.append(penalty)
    
    # Verwendung:
    model = cp_model.CpModel()
    entities = Entities()
    registry = ConstraintRegistry(entities, model)
    
    # Einfach registrieren - fertig!
    registry.register(MyNewConstraint)
    
    print("Neues Constraint registriert!")


def list_all_constraints():
    """Listet alle 16 verfügbaren Constraint-Klassen auf."""
    constraints = [
        ("EmployeeAvailabilityConstraint", "Hard", "Mitarbeiter-Verfügbarkeit"),
        ("EventGroupsActivityConstraint", "Hard", "Event-Gruppen-Aktivität"),
        ("AvailDayGroupsActivityConstraint", "Hard", "Verfügbarkeitstag-Gruppen-Aktivität"),
        ("RequiredAvailDayGroupsConstraint", "Hard", "Erforderliche Verfügbarkeitstag-Gruppen"),
        ("NumShiftsInAvailDayGroupsConstraint", "Hard", "Schichten in Verfügbarkeitstag-Gruppen"),
        ("WeightsInAvailDayGroupsConstraint", "Soft", "Gewichtungen in Verfügbarkeitstag-Gruppen"),
        ("LocationPrefsConstraint", "Soft", "Standort-Präferenzen"),
        ("PartnerLocationPrefsConstraint", "Soft", "Partner-Standort-Präferenzen"),
        ("UnsignedShiftsConstraint", "Soft", "Unbesetzte Schichten"),
        ("WeightsInEventGroupsConstraint", "Soft", "Gewichtungen in Event-Gruppen"),
        ("CastRulesConstraint", "Soft/Hard", "Besetzungsregeln"),
        ("SkillsConstraint", "Soft", "Fähigkeiten"),
        ("FixedCastConflictsConstraint", "Hard", "Feste Besetzungen - Konflikte"),
        ("PreferFixedCastConstraint", "Soft", "Feste Besetzungen - Präferenzen"),
        ("DifferentCastsSameDayConstraint", "Hard", "Verschiedene Besetzungen am selben Tag"),
        ("RelShiftDeviationsConstraint", "Soft", "Relative Schichtabweichungen (Fairness)"),
    ]
    
    print("\n" + "=" * 70)
    print("Alle 16 Constraint-Klassen:")
    print("=" * 70)
    for i, (name, typ, beschreibung) in enumerate(constraints, 1):
        print(f"  {i:2}. {name:<40} [{typ:<9}] - {beschreibung}")
    print("=" * 70)


if __name__ == "__main__":
    print("=" * 60)
    print("Demo: Registry Usage")
    print("=" * 60)
    demo_registry_usage()
    
    print("\n" + "=" * 60)
    print("Demo: Adding New Constraint")
    print("=" * 60)
    demo_adding_new_constraint()
    
    print("\n" + "=" * 60)
    print("Liste aller Constraints")
    print("=" * 60)
    list_all_constraints()
