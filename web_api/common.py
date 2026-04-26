"""Modul-übergreifende Hilfsfunktionen für den Web-API-Layer.

Absichtlich schlank gehalten — nur Utilities, die mindestens zwei Services
teilen und nicht in ein fachliches Modul passen.
"""

import json
from datetime import date, time, timedelta
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


def location_display_name(name: str, city: str | None) -> str:
    """Baut den UI-Anzeigenamen einer LocationOfWork als "Name City".

    Fällt auf "Name" allein zurück, wenn die City None oder leer ist —
    wir zeigen niemals "Name None" oder einen hängenden Leerschlag.
    """
    if city and city.strip():
        return f"{name} {city.strip()}"
    return name


def interval_minutes(start: time, end: time) -> tuple[int, int]:
    """Normalisiert ein TimeOfDay-Intervall auf Minuten seit Tages-Start.

    Slots können über Mitternacht reichen (z. B. 22:00–02:00). Wenn
    `end < start`, wird `end += 24h` addiert — so ist der Vergleich
    monoton und das übliche `a_start <= b_start AND a_end >= b_end`-
    Containment funktioniert korrekt für alle Fälle.

    Aus dem Rückgabewert lässt sich auch die Mitternachts-Erkennung
    ableiten: `end_min > 1440` ⇔ TOD reicht in den Folgetag.
    """
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    if end_min < start_min:
        end_min += 24 * 60
    return start_min, end_min


def fc_event_start_iso(event_date: date, time_start: time | None) -> str:
    """ISO-Datetime-String für den Start eines FullCalendar-Events.

    Bei `time_start is None` liefert nur das Datum (allDay-Event).
    """
    if time_start is None:
        return event_date.isoformat()
    return f"{event_date.isoformat()}T{time_start.strftime('%H:%M:%S')}"


def fc_event_end_iso(event_date: date, time_start: time | None, time_end: time | None) -> str:
    """ISO-Datetime-String für das Ende eines FullCalendar-Events.

    Berücksichtigt TODs über Mitternacht: wenn das Intervall den Tag
    überschreitet (erkennbar an `interval_minutes`), wird das End-Datum
    auf den Folgetag gesetzt. Sonst rendert FullCalendar den Termin als
    negative Dauer (1px-Linie) — bekannter Fallstrick, siehe Memory
    `feedback_time_slot_comparison.md`.
    """
    if time_start is None or time_end is None:
        return event_date.isoformat()
    _, end_min = interval_minutes(time_start, time_end)
    end_date = event_date + timedelta(days=1) if end_min > 24 * 60 else event_date
    return f"{end_date.isoformat()}T{time_end.strftime('%H:%M:%S')}"


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