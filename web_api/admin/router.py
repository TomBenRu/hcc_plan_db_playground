"""Admin-Router: projektweite Einstellungen."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import Person, Project
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.dependencies import get_db_session
from web_api.models.web_models import WebUser
from web_api.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_admin_project(session: Session, user: WebUser) -> Project:
    """Lädt das vom Admin-User verwaltete Projekt.

    Vertrag: Genau ein Projekt pro Admin, erreichbar über
    `user.person_id → Person.admin_of_project_id`. Wirft 403, wenn der
    User keine Person-Verknüpfung oder keine Admin-Projekt-Zuordnung
    hat.
    """
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )
    person = session.get(Person, user.person_id)
    if person is None or person.admin_of_project_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Diesem Konto ist kein Projekt als Administrator zugeordnet",
        )
    project = session.get(Project, person.admin_of_project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Projekt nicht gefunden",
        )
    return project


# ── Projekt-Einstellungen ────────────────────────────────────────────────────


@router.get("/project-settings", response_class=HTMLResponse)
def admin_project_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Vollständige Einstellungs-Seite (erste Navigation)."""
    project = _get_admin_project(session, user)
    return templates.TemplateResponse(
        "admin/project_settings.html",
        {"request": request, "user": user, "project": project, "saved": False},
    )


@router.post("/project-settings", response_class=HTMLResponse)
def admin_update_project_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    use_simple_time_slots: str | None = Form(default=None),
):
    """HTMX-Swap-Ziel: speichert Toggle-Zustand und liefert Settings-Card zurück."""
    project = _get_admin_project(session, user)
    project.use_simple_time_slots = use_simple_time_slots is not None
    session.commit()
    session.refresh(project)
    return templates.TemplateResponse(
        "admin/partials/settings_card.html",
        {"request": request, "project": project, "saved": True},
    )