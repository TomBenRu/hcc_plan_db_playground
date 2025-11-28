# sat_solver/constraints/example_usage.py
"""
Beispiel für die Verwendung der neuen Constraint-Registry-Architektur.

Diese Datei zeigt, wie die neue Architektur in solver_main.py integriert werden kann.
Sie ist NICHT für den Produktionseinsatz gedacht, sondern dient als Dokumentation
und Referenz für das Refactoring.
"""

from uuid import UUID

from ortools.sat.python import cp_model

from configuration.solver import curr_config_handler
from sat_solver.constraints import ConstraintRegistry, LocationPrefsConstraint
from sat_solver.constraints.registry import Entities


def example_new_architecture():
    """
    Zeigt die neue Architektur im Vergleich zur alten.
    
    ALTE ARCHITEKTUR (solver_main.py):
    ----------------------------------
    
    ```python
    def create_constraints(model: cp_model.CpModel):
        add_constraints_employee_availability(model)
        add_constraints_event_groups_activity(model)
        # ... viele weitere Aufrufe ...
        constraints_location_prefs = add_constraints_location_prefs(model)
        constraints_partner_loc_prefs = add_constraints_partner_location_prefs(model)
        # ... noch mehr Aufrufe ...
        
        # Riesiges Tupel zurückgeben
        return (unassigned_shifts_per_event, sum_assigned_shifts, sum_squared_deviations,
                constraints_weights_in_avail_day_groups, constraints_weights_in_event_groups,
                constraints_location_prefs, constraints_partner_loc_prefs,
                constraints_fixed_cast_conflicts, skill_conflict_vars, 
                constraints_cast_rule, constraints_prefer_fixed_cast)
    
    def solve(...):
        model = cp_model.CpModel()
        create_vars(model, ...)
        
        # Unübersichtliches Tupel-Unpacking
        (a, b, c, d, e, f, g, h, i, j, k) = create_constraints(model)
        
        # Manuelles Zusammenbauen der Objective-Funktion
        define_objective_minimize(model, a, c, d, e, f, g, h, i, j, k)
    ```
    
    
    NEUE ARCHITEKTUR (mit Registry):
    --------------------------------
    
    ```python
    def create_constraints(model: cp_model.CpModel, entities: Entities) -> ConstraintRegistry:
        registry = ConstraintRegistry(model, entities)
        
        # Constraints registrieren (Reihenfolge kann wichtig sein)
        registry.register(EmployeeAvailabilityConstraint)
        registry.register(EventGroupsActivityConstraint)
        registry.register(AvailDayGroupsActivityConstraint)
        registry.register(WeightsInAvailDayGroupsConstraint)
        registry.register(WeightsInEventGroupsConstraint)
        registry.register(LocationPrefsConstraint)
        registry.register(PartnerLocationPrefsConstraint)
        registry.register(CastRulesConstraint)
        registry.register(FixedCastConstraint)
        registry.register(SkillsConstraint)
        registry.register(UnsignedShiftsConstraint)
        registry.register(RelShiftDeviationsConstraint)
        
        # Alle Constraints anwenden
        registry.apply_all()
        
        return registry
    
    def solve(...):
        model = cp_model.CpModel()
        entities = Entities()
        
        create_data_models(entities, ...)
        create_vars(model, entities, ...)
        
        # Saubere API
        registry = create_constraints(model, entities)
        
        # Automatische Objective-Berechnung
        model.Minimize(registry.get_total_weighted_penalty())
        
        # Solver ausführen
        solver = cp_model.CpSolver()
        status = solver.Solve(model)
        
        # Einfaches Debugging
        registry.log_penalty_summary(solver)
    ```
    """
    pass


def demo_registry_usage():
    """
    Lauffähiges Demo der neuen Registry-Architektur.
    
    HINWEIS: Dies ist ein vereinfachtes Beispiel. In der echten Implementierung
    müssen die Entities mit echten Daten gefüllt werden.
    """
    # 1. Model und Entities erstellen
    model = cp_model.CpModel()
    entities = Entities()
    
    # 2. Registry erstellen
    config = curr_config_handler.get_solver_config()
    registry = ConstraintRegistry(model, entities, config)
    
    # 3. Constraints registrieren
    location_prefs = registry.register(LocationPrefsConstraint)
    # registry.register(PartnerLocationPrefsConstraint)  # Noch nicht implementiert
    # registry.register(FixedCastConstraint)             # Noch nicht implementiert
    # ... weitere Constraints ...
    
    # 4. Alle Constraints anwenden
    # HINWEIS: Würde fehlschlagen ohne echte Daten in entities
    # registry.apply_all()
    
    # 5. Objective-Funktion definieren
    # model.Minimize(registry.get_total_weighted_penalty())
    
    # 6. Solver ausführen
    # solver = cp_model.CpSolver()
    # status = solver.Solve(model)
    
    # 7. Ergebnisse analysieren
    # registry.log_penalty_summary(solver)
    
    print("Registry erstellt:", registry)
    print("Registrierte Constraints:", [c.name for c in registry.constraints])
    print("Location Prefs Weight:", location_prefs.get_weight())


def demo_adding_new_constraint():
    """
    Zeigt wie einfach es ist, ein neues Constraint hinzuzufügen.
    
    Mit der neuen Architektur:
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
    registry = ConstraintRegistry(model, entities)
    
    # Einfach registrieren - fertig!
    registry.register(MyNewConstraint)
    
    print("Neues Constraint registriert!")


if __name__ == "__main__":
    print("=" * 60)
    print("Demo: Registry Usage")
    print("=" * 60)
    demo_registry_usage()
    
    print("\n" + "=" * 60)
    print("Demo: Adding New Constraint")
    print("=" * 60)
    demo_adding_new_constraint()
