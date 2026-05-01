"""Service-Schicht fuer den Disponenten-Periodenview unter /dispatcher/periods.

Enthaelt Domain-Logik, die ueber den HTTP-Layer hinweg wiederverwendbar ist:
Status-Filterung der Period-Liste und Validierung der vier Datumsregeln einer
Plan-Periode.
"""

import datetime
import uuid

from database import db_services


def filter_periods(periods, status_filter: str | None):
    """Status-Filter: aktiv | geschlossen | papierkorb.

    Annahme: `periods` enthaelt sowohl aktive als auch soft-deletete PPs
    (Aufrufer laedt mit `include_deleted=True`). Soft-Deletete werden nur
    bei `status_filter='papierkorb'` zurueckgegeben.
    """
    if status_filter == "papierkorb":
        return [p for p in periods if p.prep_delete is not None]
    active = [p for p in periods if p.prep_delete is None]
    if status_filter == "geschlossen":
        return [p for p in active if p.closed]
    if status_filter == "aktiv":
        return [p for p in active if not p.closed]
    return active


def validate_period_dates(
    team_id: uuid.UUID,
    start: datetime.date,
    end: datetime.date,
    deadline: datetime.date,
    exclude_id: uuid.UUID | None = None,
) -> str | None:
    """Prueft die vier Datumsregeln einer Plan-Periode. Gibt eine deutsche
    Fehlermeldung zurueck oder None, wenn alle Regeln erfuellt sind.

    Regeln:
        1. start < end
        2. today < deadline
        3. deadline < start
        4. keine Ueberlappung mit anderen non-deleted PPs des Teams
           (eigene Periode optional via `exclude_id` ausgenommen)
    """
    if start >= end:
        return "Das Ende der Periode muss nach dem Start liegen."
    today = datetime.date.today()
    if deadline <= today:
        return "Die Deadline muss nach dem heutigen Tag liegen."
    if deadline >= start:
        return "Die Deadline muss vor dem Start der Periode liegen."
    overlap = db_services.PlanPeriod.find_overlapping_period(
        team_id, start, end, exclude_id=exclude_id
    )
    if overlap:
        return (
            f"Die Periode überschneidet eine bestehende Periode "
            f"({overlap.start.strftime('%d.%m.%Y')} – {overlap.end.strftime('%d.%m.%Y')})."
        )
    return None