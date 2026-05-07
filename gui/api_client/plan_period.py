"""Desktop-API-Client: PlanPeriod-Operationen."""

import datetime
import uuid

from database import schemas
from gui.api_client.client import get_api_client


def create(start: datetime.date, end: datetime.date, team_id: uuid.UUID,
           notes: str | None = None, notes_for_employees: str | None = None) -> schemas.PlanPeriodShow:
    data = get_api_client().post("/api/v1/plan-periods", json={
        "start": start.isoformat(),
        "end": end.isoformat(),
        "notes": notes,
        "notes_for_employees": notes_for_employees,
        "team_id": str(team_id),
    })
    return schemas.PlanPeriodShow.model_validate(data)


def create_with_children(start: datetime.date, end: datetime.date, team_id: uuid.UUID,
                         notes: str | None = None,
                         notes_for_employees: str | None = None) -> schemas.PlanPeriodShow:
    """Atomarer Create: PP + LPP+EventGroup-Master + APP+AvailDayGroup-Master in
    einer Server-Session/Transaktion. Ersetzt die alte 1+2N+2M-Schleife des
    Desktop-Dialogs durch genau einen API-Call."""
    data = get_api_client().post("/api/v1/plan-periods/with-children", json={
        "start": start.isoformat(),
        "end": end.isoformat(),
        "notes": notes,
        "notes_for_employees": notes_for_employees,
        "team_id": str(team_id),
    })
    return schemas.PlanPeriodShow.model_validate(data)


def set_closed(plan_period_id: uuid.UUID, closed: bool) -> schemas.PlanPeriodMinimal:
    """Schließt (closed=True) oder öffnet (closed=False) eine PlanPeriod.
    Re-Open ist serverseitig nur für Admins erlaubt.

    Antwort ist PlanPeriodMinimal — kein PlanPeriodShow, weil die Mutation sonst
    bei großen Perioden 30 s+ dauert (hunderte Lazy-Queries durch model_validate).
    """
    endpoint = "close" if closed else "reopen"
    data = get_api_client().post(f"/api/v1/plan-periods/{plan_period_id}/{endpoint}")
    return schemas.PlanPeriodMinimal.model_validate(data)


def get_notification_group(plan_period_id: uuid.UUID) -> schemas.NotificationGroupInfo | None:
    """Liefert die Reminder-Gruppe einer PP plus alle Mit-PPs.

    `None`, wenn die PP keiner NG zugeordnet ist (PP ohne Reminder).
    Server filtert soft-deletete Mit-PPs aus der Liste raus.
    """
    data = get_api_client().get(f"/api/v1/plan-periods/{plan_period_id}/notification-group")
    if data is None:
        return None
    return schemas.NotificationGroupInfo.model_validate(data)


def find_takeover_candidates(plan_period_id: uuid.UUID) -> schemas.TakeoverPreview:
    data = get_api_client().get(f"/api/v1/plan-periods/{plan_period_id}/takeover-candidates")
    return schemas.TakeoverPreview.model_validate(data)


def execute_takeover(plan_period_id: uuid.UUID) -> schemas.TakeoverReport:
    data = get_api_client().post(f"/api/v1/plan-periods/{plan_period_id}/takeover")
    return schemas.TakeoverReport.model_validate(data)


def update(plan_period: schemas.PlanPeriod) -> schemas.PlanPeriodShow:
    data = get_api_client().put(f"/api/v1/plan-periods/{plan_period.id}",
                                json=plan_period.model_dump(mode="json"))
    return schemas.PlanPeriodShow.model_validate(data)


def update_notes(plan_period_id: uuid.UUID, notes: str) -> schemas.PlanPeriodShow:
    data = get_api_client().patch(f"/api/v1/plan-periods/{plan_period_id}/notes",
                                  json={"notes": notes})
    return schemas.PlanPeriodShow.model_validate(data)


def delete(plan_period_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/plan-periods/{plan_period_id}")


def undelete(plan_period_id: uuid.UUID) -> None:
    get_api_client().post(f"/api/v1/plan-periods/{plan_period_id}/undelete")


def delete_prep_deletes(team_id: uuid.UUID) -> None:
    get_api_client().delete(f"/api/v1/teams/{team_id}/plan-periods/prep-deleted")