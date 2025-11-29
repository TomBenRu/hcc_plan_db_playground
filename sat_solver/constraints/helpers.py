# sat_solver/constraints/helpers.py
"""
Hilfsfunktionen für Constraint-Klassen.

Diese Funktionen wurden aus solver_main.py ausgelagert, um Circular Imports
zu vermeiden.
"""

from database import schemas


def check_actor_location_prefs_fits_event(
    avail_day: schemas.AvailDayShow,
    location_of_work: schemas.LocationOfWork
) -> bool:
    """
    Prüft, ob die actor_location_prefs des avail_days die location_of_work des Events zulassen.
    
    Args:
        avail_day: Der Verfügbarkeitstag mit seinen Location-Präferenzen
        location_of_work: Der Arbeitsort des Events
        
    Returns:
        True wenn der Arbeitsort erlaubt ist (Score > 0), sonst False
    """
    if found_alf := next((alf for alf in avail_day.actor_location_prefs_defaults
                          if alf.location_of_work.id == location_of_work.id), None):
        if found_alf.score == 0:
            return False
    return True


def check_time_span_avail_day_fits_event(
    event: schemas.Event, 
    avail_day: schemas.AvailDay, 
    only_time_index: bool = True
) -> bool:
    """
    Prüft, ob der Zeitraum des avail_days den Zeitraum des Events enthält.
    
    Args:
        event: Das Event mit Datum und Zeitraum
        avail_day: Der Verfügbarkeitstag
        only_time_index: Wenn True, wird nur der time_index verglichen,
                        sonst die exakten Start-/Endzeiten
                        
    Returns:
        True wenn der Verfügbarkeitstag das Event zeitlich abdeckt
    """
    if only_time_index:
        return (
            avail_day.date == event.date
            and avail_day.time_of_day.time_of_day_enum.time_index
            == event.time_of_day.time_of_day_enum.time_index
        )
    else:
        return (
            avail_day.date == event.date
            and avail_day.time_of_day.start <= event.time_of_day.start
            and avail_day.time_of_day.end >= event.time_of_day.end
        )
