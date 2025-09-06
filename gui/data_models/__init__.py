"""Datenmodelle für GUI-Komponenten ohne direkte GUI-Abhängigkeiten.

Dieses Package enthält reine Datenmodelle die von GUI-Komponenten verwendet werden,
aber selbst keine GUI-Abhängigkeiten haben. Dies verbessert Testbarkeit und
ermöglicht bessere Trennung von Daten- und Präsentationslogik.
"""

from .rule_data_model import RuleDataModel, ValidationResult
from .schemas import RulesData, Rules

__all__ = ['RuleDataModel', 'ValidationResult', 'RulesData', 'Rules']
