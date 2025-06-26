"""
SAT-Solver Core Module

Dieses Modul enthält die Kern-Klassen des SAT-Solvers:
- SolverContext: Zentraler Kontext für alle Solver-Operationen
- Entities: Datenstrukturen für Solver-Entitäten  
- SolverConfig: Konfigurationsklassen
"""

from .solver_context import SolverContext
from .entities import Entities
from .solver_config import SolverConfig

__all__ = [
    'SolverContext',
    'Entities', 
    'SolverConfig'
]
