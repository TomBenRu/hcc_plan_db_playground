"""Admin-Service: Domain-Logik fuer Admin-Routes.

Enthaelt Helper, die ueber den HTTP-Layer hinweg wiederverwendbar sind und
keine FastAPI-/Template-Spezifika besitzen.
"""

from fastapi import HTTPException, status
from sqlmodel import Session

from database.models import Person, Project
from web_api.models.web_models import WebUser


def get_admin_project(session: Session, user: WebUser) -> Project:
    """Laedt das vom Admin-User verwaltete Projekt.

    Vertrag: Genau ein Projekt pro Admin, erreichbar ueber
    `user.person_id -> Person.admin_of_project_id`. Wirft 403, wenn der
    User keine Person-Verknuepfung oder keine Admin-Projekt-Zuordnung hat;
    404, wenn die FK ins Leere zeigt.
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