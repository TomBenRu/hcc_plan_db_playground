"""Modul-übergreifende Hilfsfunktionen für den Web-API-Layer.

Absichtlich schlank gehalten — nur Utilities, die mindestens zwei Services
teilen und nicht in ein fachliches Modul passen.
"""

import json
from typing import Any


def guest_count(value: Any) -> int:
    """Zählt Gäste robust aus dem `Appointment.guests`-JSON-Feld.

    SQLAlchemy liefert JSON-Werte je nach Dialekt/Spalten-Typ entweder als
    bereits dekodierte Liste oder als rohen String durch. `len(str)` würde
    hier die Zeichenzahl zurückgeben — Helper dekodiert deshalb erst.
    Fallback bei leerem oder ungültigem Wert: 0.
    """
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, (list, tuple)):
                return len(parsed)
        except (ValueError, TypeError):
            pass
    return 0


def guest_list(value: Any) -> list[str]:
    """Dekodiert Gäste-Namen robust aus dem `Appointment.guests`-JSON-Feld.

    Analog zu `guest_count`: SQLAlchemy liefert je nach Dialekt entweder
    bereits dekodierte Liste oder rohen JSON-String. Nicht-String-Elemente
    werden per `str()` gecastet; Fallback bei ungültigem Wert: leere Liste.
    """
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, (list, tuple)):
                return [str(x) for x in parsed]
        except (ValueError, TypeError):
            pass
    return []