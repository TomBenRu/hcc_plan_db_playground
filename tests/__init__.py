"""
Unit-Tests für SAT-Solver Architektur

Diese Test-Suite validiert die neue 4-Layer-Architektur:
- Core-Module (SolverContext, Entities, Config, SolverResult)
- Constraints (AbstractConstraint, Factory, individuelle Constraints)
- Solving (SATSolver, ObjectiveBuilder, Callbacks)
- Results (ResultProcessor)
- Integration (solver_main.py API-Kompatibilität)
"""
