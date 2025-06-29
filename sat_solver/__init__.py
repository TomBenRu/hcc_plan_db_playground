"""
SAT-Solver Package

This package contains the SAT-solver implementation for the HCC Plan DB Playground project.
It includes both the new refactored architecture and legacy compatibility.
"""

# Import the main solver modules using relative imports
from . import solver_main
from . import solver_main_legacy

# Expose the main functions that are used by other parts of the codebase
from .solver_main import solve

# Make the modules available for direct import
__all__ = [
    'solver_main',
    'solver_main_legacy',
    'solve'
]