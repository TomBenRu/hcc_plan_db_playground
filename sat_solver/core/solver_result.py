"""
SolverResult - Datenklasse für SAT-Solver Ergebnisse

Ausgelagert aus solver.py um Circular Imports zu vermeiden.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from ortools.sat.cp_model_pb2 import CpSolverStatus
from ortools.sat.python import cp_model


@dataclass
class SolverResult:
    """Datenklasse für Solver-Ergebnisse."""
    
    status: CpSolverStatus
    is_optimal: bool
    is_feasible: bool
    objective_value: Optional[float]
    solve_time: float
    statistics: Dict[str, Any]
    appointments: List  # List[schemas.AppointmentCreate]
    solutions: List     # List[List[schemas.AppointmentCreate]]
    constraint_values: Dict[str, Any]
    
    @property
    def success(self) -> bool:
        """True wenn Solving erfolgreich war."""
        return self.is_optimal or self.is_feasible
