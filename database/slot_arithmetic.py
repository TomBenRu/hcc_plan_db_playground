"""Helper für Datums-/Zeit-Berechnungen über mehrere Tageszeit-Slots.

`TimeOfDay` im Datenmodell speichert einen Slot als (start: time, end: time)
ohne Datums-Bezug. Bei `end < start` ist die Konvention, dass der Slot
über Mitternacht reicht (z.B. start=22:00, end=02:00 = 4h Dauer am
Folgetag).

Dieses Modul löst den Wrap auf datetime-Ebene auf:
- `slot_to_range` liefert für einen einzelnen Slot ein garantiert
  monotones (start_dt, end_dt)-Paar (end_dt >= start_dt).
- `slots_overlap` und `slot_gap` rechnen für zwei Slots am gleichen
  oder verschiedenen Datum korrekt — auch wenn beide oder einer wrappt.

Coexistenz mit `web_api.common.interval_minutes`:
  `interval_minutes` löst den Wrap eines *einzelnen* Slots in Minuten
  auf und wird für Slot-Containment verwendet ("umschließt Slot A den
  Slot B?"). Für Slot-zu-Slot-Differenzen am gleichen Datum ist
  `interval_minutes` defekt, weil die Minuten-Repräsentation den
  Datums-Bezug verliert — dafür ist dieses Modul gedacht.

Der Klassenname ist `TimeSlot` (nicht `Slot`), weil `Slot` in
PyQt/PySide6 als Decorator für Signal-Slot-Verbindungen besetzt ist
und der Helper auch von GUI-nahem Code importiert wird.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta


@dataclass(frozen=True)
class TimeSlot:
    """Ein Tageszeit-Slot an einem konkreten Datum.

    `end < start` ist erlaubt und bedeutet eine Mitternachts-Spanne
    (Wrap in den Folgetag). `end == start` bedeutet 0-Dauer
    (Konvention konsistent mit `web_api.common.interval_minutes`).
    Maximale Dauer ist 24h.
    """

    date: date
    start: time
    end: time


def slot_to_range(slot: TimeSlot) -> tuple[datetime, datetime]:
    """Wandelt einen Slot in eine echte datetime-Range um.

    Bei `end < start` wird das Ende auf den Folgetag verlegt, sodass
    das zurückgegebene Paar garantiert `end_dt >= start_dt` erfüllt.
    """
    start_dt = datetime.combine(slot.date, slot.start)
    end_dt = datetime.combine(slot.date, slot.end)
    if slot.end < slot.start:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def slots_overlap(a: TimeSlot, b: TimeSlot) -> bool:
    """True wenn zwei Slots zeitlich überlappen (halboffen).

    Halboffene Konvention: ein gemeinsamer Endpunkt (`a.end == b.start`)
    zählt nicht als Überlappung — direkt anschließende Slots sind erlaubt.
    """
    a_start, a_end = slot_to_range(a)
    b_start, b_end = slot_to_range(b)
    return a_start < b_end and b_start < a_end


def slot_gap(a: TimeSlot, b: TimeSlot) -> timedelta:
    """Zeit zwischen Ende des einen und Start des anderen Slots.

    Bei Überlappung → `timedelta(0)`. Sonst die positive Differenz
    zwischen späterem Start und früherem Ende. Reihenfolge der
    Argumente ist irrelevant.
    """
    a_start, a_end = slot_to_range(a)
    b_start, b_end = slot_to_range(b)
    if a_start < b_end and b_start < a_end:
        return timedelta(0)
    if a_end <= b_start:
        return b_start - a_end
    return a_start - b_end
