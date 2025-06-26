"""
SAT-Solver Results Module

Dieses Modul enthält die Ergebnisverarbeitung und Statistiken:
- ResultProcessor: Verarbeitung von Solver-Ergebnissen
- SolverStatistics: Sammlung und Darstellung von Solver-Statistiken
- ResultFormatter: Formatierung von Ergebnissen für verschiedene Ausgaben
"""

from .result_processor import ResultProcessor
from .statistics import SolverStatistics

__all__ = [
    'ResultProcessor',
    'SolverStatistics'
]
