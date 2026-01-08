"""
Datenmodelle für die Planbewertung.

Dieses Modul definiert die Strukturen für Bewertungsergebnisse,
die sowohl aus Solver-Läufen als auch aus manueller Berechnung entstehen können.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID


# Typ-Alias für Ampelfarben
ColorType = Literal['green', 'yellow', 'red']


@dataclass
class ObjectiveScore:
    """
    Bewertung eines einzelnen Optimierungskriteriums.

    Jedes Kriterium (z.B. Fairness, Standortpräferenzen) wird als
    ObjectiveScore repräsentiert mit normalisiertem Score (0-100%)
    und Ampelfarbe für schnelle visuelle Orientierung.

    Attributes:
        name: Interner Constraint-Name (z.B. 'rel_shift_deviations')
        display_name: Angezeigter Name (z.B. 'Fairness der Verteilung')
        icon: Emoji oder Icon für die Darstellung
        raw_value: Roher Berechnungswert (für Debugging/Details)
        normalized_score: Normalisierter Score 0-100%
        weight: Gewicht des Kriteriums aus Solver-Konfiguration
        weighted_contribution: Beitrag zum Gesamtscore (score * weight)
        description: Erklärung für Tooltip
        color: Ampelfarbe basierend auf Schwellenwerten
    """
    name: str
    display_name: str
    icon: str
    raw_value: float
    normalized_score: float
    weight: float
    weighted_contribution: float
    description: str
    color: ColorType

    def __post_init__(self):
        """Validiere und begrenze normalized_score auf 0-100."""
        self.normalized_score = max(0.0, min(100.0, self.normalized_score))


@dataclass
class PlanRating:
    """
    Gesamtbewertung eines Plans.

    Aggregiert die Einzelbewertungen aller Kriterien zu einem
    Gesamtscore und speichert Metadaten über die Berechnung.

    Attributes:
        plan_id: UUID des bewerteten Plans
        overall_score: Gewichteter Gesamtscore 0-100%
        overall_color: Ampelfarbe für Gesamtbewertung
        objective_scores: Liste aller Einzelbewertungen
        calculation_timestamp: Zeitpunkt der Berechnung
        is_from_solver: True wenn aus Solver-Lauf, False bei manueller Berechnung
    """
    plan_id: UUID
    overall_score: float
    overall_color: ColorType
    objective_scores: list[ObjectiveScore] = field(default_factory=list)
    calculation_timestamp: datetime = field(default_factory=datetime.now)
    is_from_solver: bool = False

    def __post_init__(self):
        """Validiere und begrenze overall_score auf 0-100."""
        self.overall_score = max(0.0, min(100.0, self.overall_score))

    def get_objective_by_name(self, name: str) -> ObjectiveScore | None:
        """Findet einen ObjectiveScore nach internem Namen."""
        for obj in self.objective_scores:
            if obj.name == name:
                return obj
        return None


# Konstanten für Ampel-Schwellenwerte
THRESHOLD_GREEN = 80.0  # >= 80% = Grün
THRESHOLD_YELLOW = 50.0  # >= 50% = Gelb, sonst Rot


def get_color_for_score(score: float) -> ColorType:
    """
    Bestimmt die Ampelfarbe für einen Score.

    Args:
        score: Normalisierter Score 0-100

    Returns:
        'green' für >= 80%, 'yellow' für >= 50%, sonst 'red'
    """
    if score >= THRESHOLD_GREEN:
        return 'green'
    elif score >= THRESHOLD_YELLOW:
        return 'yellow'
    return 'red'


# Objektive-Konfiguration: name -> (display_name, icon, description)
OBJECTIVE_CONFIG: dict[str, tuple[str, str, str]] = {
    'rel_shift_deviations': (
        'Fairness',
        '\u2696\ufe0f',  # Balance-Emoji
        'Misst wie gleichmäßig die Schichten auf Mitarbeiter verteilt sind. '
        '100% bedeutet perfekte Gleichverteilung entsprechend der fairen Einsätze.'
    ),
    'location_prefs': (
        'Standorte',
        '\U0001F4CD',  # Pin-Emoji
        'Berücksichtigung der Standort-Wünsche der Mitarbeiter. '
        '100% bedeutet alle Zuweisungen entsprechen den Präferenzen.'
    ),
    'partner_location_prefs': (
        'Teams',
        '\U0001F465',  # Zwei-Personen-Emoji
        'Einhaltung der Partner-Präferenzen für Standorte. '
        '100% bedeutet optimale Team-Zusammenstellungen.'
    ),
    'unsigned_shifts': (
        'Besetzung',
        '\u2713',  # Häkchen
        'Anteil der vollständig besetzten Schichten. '
        '100% bedeutet alle erforderlichen Positionen sind besetzt.'
    ),
}
