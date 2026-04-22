"""Dispatcher-spezifische FastAPI-Dependencies."""

import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import Appointment, Plan, PlanPeriod, Team
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.dependencies import get_db_session
from web_api.models.web_models import WebUser


def require_team_dispatcher_for_appointment(
    appointment_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
) -> Appointment:
    """Lädt den Appointment und validiert Dispatcher-Zuständigkeit.

    Prüft über den Pfad Appointment → Plan → PlanPeriod → Team, dass
    `Team.dispatcher_id == user.person_id`. Gibt die geladene
    Appointment-Instanz zurück, damit nachgelagerter Handler-Code sie
    direkt mutieren kann — spart eine zweite Query.

    Response-Codes:
    - 403 wenn User keine Person-Verknüpfung hat oder nicht Dispatcher ist.
    - 404 wenn der Appointment nicht existiert.
    """
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )

    row = session.execute(
        sa_select(Appointment, Team.dispatcher_id)
        .select_from(Appointment)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(Team, Team.id == PlanPeriod.team_id)
        .where(Appointment.id == appointment_id)
    ).first()

    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")

    appointment, dispatcher_id = row
    if dispatcher_id != user.person_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Keine Dispatcher-Rechte für dieses Team",
        )

    return appointment