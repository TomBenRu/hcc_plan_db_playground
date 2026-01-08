"""
Planbewertungs-Modul für HCC Plan.

Dieses Modul ermöglicht die Bewertung von Plänen basierend auf
verschiedenen Optimierungskriterien wie Fairness, Standortpräferenzen,
Partner-Präferenzen und Besetzungsgrad.

Hauptkomponenten:
- PlanRatingCalculator: Berechnet die Bewertung
- PlanRatingWidget: UI-Widget für das Slide-In-Menu
- PlanRating, ObjectiveScore: Datenmodelle für Bewertungsergebnisse
"""

from .rating_data import (
    ObjectiveScore,
    PlanRating,
    OBJECTIVE_CONFIG,
    THRESHOLD_GREEN,
    THRESHOLD_YELLOW,
    get_color_for_score,
)

from .rating_calculator import PlanRatingCalculator

from .rating_widgets import (
    ScoreRing,
    ObjectiveCard,
    PlanRatingWidget,
)

__all__ = [
    # Datenmodelle
    'ObjectiveScore',
    'PlanRating',
    'OBJECTIVE_CONFIG',
    'THRESHOLD_GREEN',
    'THRESHOLD_YELLOW',
    'get_color_for_score',
    # Calculator
    'PlanRatingCalculator',
    # Widgets
    'ScoreRing',
    'ObjectiveCard',
    'PlanRatingWidget',
]
