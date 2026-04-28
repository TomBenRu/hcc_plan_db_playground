"""Tests fuer database.slot_arithmetic.

Schwerpunkt: Mitternachts-Spannen am gleichen Datum, weil dort der
Bug-Pfad lag, der die Existenz dieses Helpers erst noetig gemacht hat.
Der direkte Vorgaenger (datetime.combine + manuelle Differenz) lieferte
bei zwei wrappenden Slots am gleichen Datum falsche Ergebnisse.
"""

from datetime import date, datetime, time, timedelta

from database.slot_arithmetic import (
    TimeSlot,
    slot_gap,
    slot_to_range,
    slots_overlap,
)

D = date(2026, 4, 28)


def _slot(start_h: int, start_m: int, end_h: int, end_m: int) -> TimeSlot:
    return TimeSlot(date=D, start=time(start_h, start_m), end=time(end_h, end_m))


# --- slot_to_range ---------------------------------------------------------


def test_slot_to_range_standard_slot_no_wrap():
    s = _slot(9, 0, 12, 0)
    start, end = slot_to_range(s)
    assert start == datetime(2026, 4, 28, 9, 0)
    assert end == datetime(2026, 4, 28, 12, 0)


def test_slot_to_range_midnight_wrap_pushes_end_to_next_day():
    s = _slot(22, 0, 2, 0)
    start, end = slot_to_range(s)
    assert start == datetime(2026, 4, 28, 22, 0)
    assert end == datetime(2026, 4, 29, 2, 0)


def test_slot_to_range_zero_duration_when_start_equals_end():
    s = _slot(8, 0, 8, 0)
    start, end = slot_to_range(s)
    assert start == end


# --- slots_overlap ---------------------------------------------------------


def test_slots_overlap_disjoint_slots_same_day():
    a = _slot(9, 0, 12, 0)
    b = _slot(14, 0, 16, 0)
    assert slots_overlap(a, b) is False


def test_slots_overlap_touching_endpoint_is_not_overlap():
    """Halboffene Konvention: a.end == b.start zaehlt nicht."""
    a = _slot(9, 0, 12, 0)
    b = _slot(12, 0, 14, 0)
    assert slots_overlap(a, b) is False


def test_slots_overlap_partial_overlap():
    a = _slot(9, 0, 12, 0)
    b = _slot(11, 0, 13, 0)
    assert slots_overlap(a, b) is True


def test_slots_overlap_one_wraps_other_does_not_no_overlap():
    """Wrap (22:00-02:00) und Normal (10:00-12:00) am gleichen Datum.

    Sollte nicht ueberlappen: Wrap-Event laeuft 22:00-02:00 d+1, der
    Normal-Slot ist 10:00-12:00 d - 10 Stunden vorher.
    """
    a = _slot(22, 0, 2, 0)
    b = _slot(10, 0, 12, 0)
    assert slots_overlap(a, b) is False


def test_slots_overlap_two_wrapping_slots_same_day_DO_overlap():
    """Bug-Reproducer.

    Mit dem alten Inline-Code (datetime.combine ohne Wrap-Korrektur)
    wurde dies als Nicht-Ueberlappung gemeldet, weil end_1 (02:00) am
    selben Datum lag wie start_1 (22:00) — und start_1 > end_2 — der
    Differenz-Code rechnete dann wirre Werte.

    Korrekt ist: beide Slots laufen 22:00-02:00 d+1 und 23:00-01:00 d+1.
    Sie ueberlappen sich zwischen 23:00 d und 01:00 d+1.
    """
    a = _slot(22, 0, 2, 0)
    b = _slot(23, 0, 1, 0)
    assert slots_overlap(a, b) is True


# --- slot_gap --------------------------------------------------------------


def test_slot_gap_disjoint_slots_returns_positive_difference():
    a = _slot(9, 0, 12, 0)
    b = _slot(14, 0, 16, 0)
    assert slot_gap(a, b) == timedelta(hours=2)


def test_slot_gap_overlapping_slots_returns_zero():
    a = _slot(9, 0, 12, 0)
    b = _slot(11, 0, 13, 0)
    assert slot_gap(a, b) == timedelta(0)


def test_slot_gap_argument_order_irrelevant():
    a = _slot(9, 0, 12, 0)
    b = _slot(14, 0, 16, 0)
    assert slot_gap(a, b) == slot_gap(b, a)


def test_slot_gap_two_wrapping_slots_same_day_returns_zero():
    """Bug-Reproducer fuer slot_gap.

    Mit dem alten Inline-Code lieferte dieser Fall ~21h time_diff —
    obwohl die Slots tatsaechlich ueberlappten und gap 0 sein muss.
    """
    a = _slot(22, 0, 2, 0)
    b = _slot(23, 0, 1, 0)
    assert slot_gap(a, b) == timedelta(0)


def test_slot_gap_wrap_then_next_day_slot_uses_correct_anchor():
    """Wrap-Event endet 02:00 d+1; folgender Slot 03:00-06:00 startet d.

    Erwartung: gap = 22:00 d - 06:00 d = 16h (b liegt VOR a).
    Mit dem alten Inline-Code wurde end_1 falsch auf 02:00 d gesetzt,
    was hier zufaellig denselben Wert (16h) liefert — aber nur, weil
    b nicht wrappt und a vor b im Datums-Sinne liegt.
    """
    a = _slot(22, 0, 2, 0)
    b = _slot(3, 0, 6, 0)
    assert slot_gap(a, b) == timedelta(hours=16)


def test_slot_gap_touching_endpoint_returns_zero():
    a = _slot(9, 0, 12, 0)
    b = _slot(12, 0, 14, 0)
    assert slot_gap(a, b) == timedelta(0)