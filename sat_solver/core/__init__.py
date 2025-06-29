"""
SAT-Solver Core Module

Dieses Modul enthält die Kern-Klassen des SAT-Solvers:
- SolverContext: Zentraler Kontext für alle Solver-Operationen
- Entities: Datenstrukturen für Solver-Entitäten  
- SolverConfig: Konfigurationsklassen
- SolverResult: Ergebnis-Datenklasse
"""

from .solver_context import SolverContext
from .entities import Entities
from .solver_config import SolverConfig
from .solver_result import SolverResult

__all__ = [
    'SolverContext',
    'Entities', 
    'SolverConfig',
    'SolverResult'
]
