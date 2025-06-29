"""
Helper-Funktionen für SAT-Solver

Diese Datei enthält gemeinsame Helper-Funktionen, die von verschiedenen
Solver-Komponenten verwendet werden.
"""

from database import schemas


def check_time_span_avail_day_fits_event(
        event: schemas.Event, avail_day: schemas.AvailDay, only_time_index: bool = True) -> bool:
    """
    Helper-Funktion: Prüft ob AvailDay zeitlich zu Event passt.
    
    Args:
        event: Das Event für das geprüft wird
        avail_day: Der AvailDay der geprüft wird
        only_time_index: Ob nur der Time-Index oder die exakte Zeit geprüft wird
        
    Returns:
        True wenn AvailDay zeitlich zu Event passt, False sonst
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
