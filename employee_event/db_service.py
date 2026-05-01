"""
Service-Layer für Employee Event Management.

Stellt eine saubere Business Logic API bereit, die nur noch mit
typsicheren Pydantic-Schemas arbeitet.
"""

from datetime import datetime
from typing import List, Optional, Union
from uuid import UUID

from sqlmodel import select

from database import models
from database.database import get_session
from database.models import Team, Person, Project, _utcnow
from .schemas import (
    EventDetail,
    EventCreate,
    EventUpdate,
    Category,
    CategoryCreate,
    CategoryUpdate,
    CategoryDetail,
    StatisticsSchema,
    SuccessResponseSchema,
    ErrorResponseSchema
)
from .exceptions import (
    EmployeeEventError,
    EmployeeEventNotFoundError,
    EmployeeEventValidationError,
    EmployeeEventCategoryError,
    EmployeeEventParticipantError,
    EmployeeEventTeamError
)


class EmployeeEventService:
    """
    Service-Klasse für Employee Event Management.

    Stellt High-Level-Operationen bereit und arbeitet ausschließlich
    mit typsicheren Pydantic-Schemas.
    """

    def __init__(self):
        ...

    # Employee Event Operations

    def create_event(self, event_create: EventCreate) -> Union[EventDetail, ErrorResponseSchema]:
        """
        Erstellt ein neues Employee Event.

        Args:
            event_create: Pydantic-Schema mit Event-Daten

        Returns:
            Union[EventDetail, ErrorResponseSchema]: Event oder Fehler
        """
        try:
            with get_session() as session:
                project_db = session.get(models.Project, event_create.project_id)
                categories_db = [session.get(models.EmployeeEventCategory, cat_id) for cat_id in event_create.category_ids]
                teams_db = [session.get(models.Team, team_id) for team_id in event_create.team_ids]
                participants_db = [session.get(models.Person, person_id) for person_id in event_create.participant_ids]

                # Adresse optional laden
                address_db = None
                if event_create.address_id:
                    address_db = session.get(models.Address, event_create.address_id)

                event_db = models.EmployeeEvent(
                    title=event_create.title,
                    description=event_create.description,
                    start=event_create.start,
                    end=event_create.end,
                    project_id=project_db.id,
                    address_id=address_db.id if address_db else None,
                )
                session.add(event_db)
                session.flush()
                event_db.employee_event_categories.extend([c for c in categories_db if c is not None])
                event_db.teams.extend([t for t in teams_db if t is not None])
                event_db.participants.extend([p for p in participants_db if p is not None])
                return EventDetail.model_validate(event_db)

        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Erstellen des Employee Events: {str(e)}",
                details=str(e)
            )

    def get_event(self, event_id: UUID) -> Union[EventDetail, ErrorResponseSchema]:
        """
        Holt Details zu einem Employee Event.

        Args:
            event_id: ID des Events

        Returns:
            Union[EventDetail, ErrorResponseSchema]: Event oder Fehler
        """
        try:
            with get_session() as session:
                event_db = session.get(models.EmployeeEvent, event_id)
                return EventDetail.model_validate(event_db)

        except EmployeeEventNotFoundError as e:
            return ErrorResponseSchema(
                error="EventNotFound",
                message=f"Employee Event nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden des Employee Events",
                details=str(e)
            )

    def get_all_events(
            self, project_id: UUID,
            last_modified: datetime | None = None,
            include_prep_delete: bool = False
    ) -> list[EventDetail]:
        """
        Holt alle Employee Events, optional gefiltert nach Projekt.

        Args:
            project_id: Nur Events dieses Projekts
            last_modified: Optional - Nur Events nach diesem Zeitpunkt
            include_prep_delete: Optional - True, um gelöschte Events einzutragen

        Returns:
            list[EventDetail]: Liste aller Events
        """
        with get_session() as session:
            query = select(models.EmployeeEvent).where(
                models.EmployeeEvent.project_id == project_id
            )
            if not include_prep_delete:
                query = query.where(models.EmployeeEvent.prep_delete.is_(None))
            if last_modified:
                query = query.where(models.EmployeeEvent.last_modified > last_modified)

            events = session.exec(query).all()
            return [EventDetail.model_validate(event) for event in events]

    def get_events_by_team_name(
        self,
        team_name: str,
        project_id: UUID,
        include_prep_delete: bool = False
    ) -> list[EventDetail] | ErrorResponseSchema:
        """
        Holt alle Employee Events eines Teams anhand des Team-Namens.

        Args:
            team_name: Name des Teams
            project_id: ID des Projekts
            include_prep_delete: Optional - True, um gelöschte Events einzutragen

        Returns:
            Union[list[EventDetail], ErrorResponseSchema]: Events oder Fehler
        """
        try:
            with get_session() as session:
                # Team ermitteln
                project_db = session.get(models.Project, project_id)
                if not project_db:
                    return ErrorResponseSchema(
                        error="ProjectNotFound",
                        message=f"Projekt mit ID {project_id} nicht gefunden"
                    )
                team_db = session.exec(
                    select(models.Team).where(
                        models.Team.name == team_name,
                        models.Team.project_id == project_db.id,
                        models.Team.prep_delete.is_(None),
                    )
                ).first()
                if not team_db:
                    return ErrorResponseSchema(
                        error="TeamNotFound",
                        message=f"Team '{team_name}' nicht gefunden"
                    )

                query = select(models.EmployeeEvent).where(
                    models.EmployeeEvent.project_id == project_id
                )
                if not include_prep_delete:
                    query = query.where(models.EmployeeEvent.prep_delete.is_(None))

                events_db = session.exec(query).all()
                # M:N Filter in Python
                filtered = [e for e in events_db if team_db in e.teams]
                return [EventDetail.model_validate(event) for event in filtered]

        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden der Team-Events",
                details=str(e)
            )


    def get_events_by_team_id(
        self,
        team_id: UUID | None,
        project_id: UUID,
        include_prep_delete: bool = False,
        last_modified: datetime | None = None
    ) -> list[EventDetail] | ErrorResponseSchema:
        """
        Holt alle Employee Events eines Teams anhand der Team-ID.

        Args:
            team_id: ID des Teams (None für "no team" Events)
            project_id: ID des Projekts
            include_prep_delete: Optional - True, um gelöschte Events einzutragen
            last_modified: Optional - Nur Events nach diesem Zeitpunkt

        Returns:
            Union[list[EventDetail], ErrorResponseSchema]: Events oder Fehler
        """
        try:
            with get_session() as session:
                # Projekt validieren
                project_db = session.get(models.Project, project_id)
                if not project_db:
                    return ErrorResponseSchema(
                        error="ProjectNotFound",
                        message=f"Projekt mit ID {project_id} nicht gefunden"
                    )

                # Base-Query: Alle Events des Projekts
                query = select(models.EmployeeEvent).where(
                    models.EmployeeEvent.project_id == project_id
                )

                # Soft-Delete Filter
                if not include_prep_delete:
                    query = query.where(models.EmployeeEvent.prep_delete.is_(None))

                # Last-Modified Filter
                if last_modified:
                    query = query.where(models.EmployeeEvent.last_modified > last_modified)

                events_db = session.exec(query).all()

                # Team-Filter anwenden
                if team_id is None:
                    # "No team" - Events ohne Team-Zuordnung
                    filtered_events = [event for event in events_db if len(event.teams) == 0]
                else:
                    # Team-spezifisch - Events die diesem Team zugeordnet sind
                    team_db = session.get(models.Team, team_id)
                    if not team_db:
                        return ErrorResponseSchema(
                            error="TeamNotFound",
                            message=f"Team mit ID {team_id} nicht gefunden"
                        )
                    filtered_events = [event for event in events_db if team_db in event.teams]

                return [EventDetail.model_validate(event) for event in filtered_events]

        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden der Team-Events nach ID",
                details=str(e)
            )

    def get_events_for_google_calendar_sync(
        self,
        project_id: UUID,
        team_id: UUID | None = None,
        last_modified: datetime | None = None
    ) -> list[EventDetail]:
        """
        Holt Employee Events für Google Calendar Synchronisation.
        Optimiert für Performance und Fehlerbehandlung.

        Args:
            project_id: ID des Projekts
            team_id: None für "no team", UUID für team-spezifisch
            last_modified: Nur Events nach diesem Zeitpunkt (für Performance)

        Returns:
            list[EventDetail]: Liste der zu synchronisierenden Events
        """
        try:
            result = self.get_events_by_team_id(
                team_id=team_id,
                project_id=project_id,
                include_prep_delete=False,
                last_modified=last_modified
            )

            # Fehler-Ergebnis zu leerer Liste konvertieren (für robuste Sync-Behandlung)
            if isinstance(result, ErrorResponseSchema):
                return []

            return result

        except Exception:
            # Bei allen Fehlern leere Liste zurückgeben (robuste Sync-Behandlung)
            return []

    def update_event(self, event_update_data: EventUpdate) -> Union[EventDetail, ErrorResponseSchema]:
        """
        Aktualisiert ein Employee Event.

        Args:
            event_update_data: Pydantic-Schema mit Update-Daten

        Returns:
            Union[EventDetail, ErrorResponseSchema]: Event oder Fehler
        """
        try:
            with get_session() as session:
                event_db = session.get(models.EmployeeEvent, event_update_data.id)
                if not event_db:
                    raise EmployeeEventNotFoundError(str(event_update_data.id))

                # Updates anwenden
                if event_update_data.title is not None:
                    event_db.title = event_update_data.title
                if event_update_data.description is not None:
                    event_db.description = event_update_data.description
                if event_update_data.start is not None:
                    event_db.start = event_update_data.start
                if event_update_data.end is not None:
                    event_db.end = event_update_data.end
                if event_update_data.address_id is not None:
                    if event_update_data.address_id:
                        address_db = session.get(models.Address, event_update_data.address_id)
                        event_db.address_id = address_db.id if address_db else None
                    else:
                        event_db.address_id = None
                if event_update_data.category_ids is not None:
                    event_db.employee_event_categories.clear()
                    for cat_id in event_update_data.category_ids:
                        category_db = session.get(models.EmployeeEventCategory, cat_id)
                        if category_db:
                            event_db.employee_event_categories.append(category_db)
                if event_update_data.team_ids is not None:
                    event_db.teams.clear()
                    for tid in event_update_data.team_ids:
                        team_db = session.get(models.Team, tid)
                        if team_db:
                            event_db.teams.append(team_db)
                if event_update_data.participant_ids is not None:
                    event_db.participants.clear()
                    for person_id in event_update_data.participant_ids:
                        person_db = session.get(models.Person, person_id)
                        if person_db:
                            event_db.participants.append(person_db)

                return EventDetail.model_validate(event_db)

        except EmployeeEventNotFoundError as e:
            return ErrorResponseSchema(
                error="EventNotFound",
                message=f"Employee Event nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Aktualisieren des Employee Events",
                details=str(e)
            )

    def delete_event(self, event_id: UUID, soft_delete: bool = True) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Löscht ein Employee Event.

        Args:
            event_id: ID des zu löschenden Events

        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            with get_session() as session:
                # Event-Titel für Meldung holen
                event_db = session.get(models.EmployeeEvent, event_id)
                title = event_db.title

                if soft_delete:
                    event_db.prep_delete = _utcnow()
                else:
                    session.delete(event_db)

                return SuccessResponseSchema(
                    message=f"Employee Event '{title}' erfolgreich gelöscht",
                    data={"event_id": str(event_id), "title": title}
                )

        except EmployeeEventNotFoundError as e:
            return ErrorResponseSchema(
                error="EventNotFound",
                message=f"Employee Event nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Löschen des Employee Events",
                details=str(e)
            )

    def undelete_event(self, event_id: UUID) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Wiederherstellung eines gelöschten Employee Events.

        Args:
            event_id: ID des zu wiederherstellenden Events

        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            with get_session() as session:
                event_db = session.get(models.EmployeeEvent, event_id)
                event_db.prep_delete = None
                return SuccessResponseSchema(
                    message=f"Employee Event '{event_db.title}' erfolgreich wiederhergestellt",
                    data={"event_id": str(event_id), "title": event_db.title}
                )

        except EmployeeEventNotFoundError as e:
            return ErrorResponseSchema(
                error="EventNotFound",
                message=f"Employee Event nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Wiederherstellen des Employee Events",
                details=str(e)
            )

    # Employee Event Category Operations

    def get_category(self, category_id: UUID) -> Union[CategoryDetail, ErrorResponseSchema]:
        """
        Holt Details zu einer Employee Event Category.

        Args:
            category_id: ID der Kategorie

        Returns:
            Union[CategoryDetail, ErrorResponseSchema]: Kategorie oder Fehler
        """
        try:
            with get_session() as session:
                category_db = session.get(models.EmployeeEventCategory, category_id)
                return CategoryDetail.model_validate(category_db)

        except EmployeeEventCategoryError as e:
            return ErrorResponseSchema(
                error="CategoryNotFound",
                message=f"Employee Event Category nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden der Employee Event Category",
                details=str(e)
            )

    def create_category(self, category_create: CategoryCreate) -> Union[Category, ErrorResponseSchema]:
        """
        Erstellt eine neue Employee Event Category.

        Args:
            category_create: Pydantic-Schema mit Kategorie-Daten

        Returns:
            Union[Category, ErrorResponseSchema]: Kategorie oder Fehler
        """
        try:
            with get_session() as session:
                # Erstelle CreateCategorySchema
                project_db = session.get(models.Project, category_create.project_id)
                if not project_db:
                    raise EmployeeEventValidationError(
                        "project_id",
                        str(category_create.project_id),
                        "Projekt nicht gefunden"
                    )

                # Kategorie erstellen
                category_db = models.EmployeeEventCategory(
                    name=category_create.name,
                    description=category_create.description,
                    project_id=project_db.id
                )
                session.add(category_db)

                return Category.model_validate(category_db)

        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Erstellen der Employee Event Category",
                details=str(e)
            )

    def get_all_categories_by_project(self, project_id: UUID, include_prep_delete: bool = False) -> list[Category]:
        """
        Holt alle Employee Event Categories, optional gefiltert nach Projekt.

        Args:
            project_id: Nur Kategorien dieses Projekts
            include_prep_delete: Optional - True, um gelöschte Kategorien einzutragen

        Returns:
            list[Category]: Liste aller Kategorien
        """
        try:
            with get_session() as session:
                project_db = session.get(models.Project, project_id)
                if not project_db:
                    raise EmployeeEventValidationError(
                        "project_id",
                        str(project_id),
                        "Projekt nicht gefunden"
                    )
                query = select(models.EmployeeEventCategory).where(
                    models.EmployeeEventCategory.project_id == project_id
                )
                if not include_prep_delete:
                    query = query.where(models.EmployeeEventCategory.prep_delete.is_(None))

                categories_db = session.exec(query).all()
                return [Category.model_validate(category) for category in categories_db]

        except Exception as e:
            return []

    def update_category(self, category_data: CategoryUpdate) -> Union[Category, ErrorResponseSchema]:
        """
        Aktualisiert eine Employee Event Category.

        Args:
            category_data: Pydantic-Schema mit Update-Daten

        Returns:
            Union[Category, ErrorResponseSchema]: Kategorie oder Fehler
        """
        try:
            with get_session() as session:
                # Erstelle UpdateCategorySchema
                category_db = session.get(models.EmployeeEventCategory, category_data.id)
                if not category_db:
                    raise EmployeeEventCategoryError(
                        message=f"Kategorie mit ID {category_data.id} nicht gefunden"
                    )

                # Updates anwenden
                if category_data.name is not None:
                    category_db.name = category_data.name
                if category_data.description is not None:
                    category_db.description = category_data.description

                return Category.model_validate(category_db)

        except EmployeeEventCategoryError as e:
            return ErrorResponseSchema(
                error="CategoryNotFound",
                message=f"Employee Event Category nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Aktualisieren der Employee Event Category",
                details=str(e)
            )

    def delete_category(self, category_id: UUID, soft_delete: bool = True) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Löscht eine Employee Event Category.

        Args:
            category_id: ID der zu löschenden Kategorie
            soft_delete: Optional - True, um Soft-Delete zu verwenden

        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            with get_session() as session:
                # Kategorie-Name für Meldung holen
                category_db = session.get(models.EmployeeEventCategory, category_id)
                name = category_db.name

                if soft_delete:
                    category_db.prep_delete = _utcnow()
                else:
                    session.delete(category_db)
                return SuccessResponseSchema(
                    message=f"Employee Event Category '{name}' erfolgreich gelöscht",
                    data={"category_id": str(category_id), "name": name}
                )

        except EmployeeEventCategoryError as e:
            return ErrorResponseSchema(
                error="CategoryNotFound",
                message=f"Employee Event Category nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Löschen der Employee Event Category",
                details=str(e)
            )

    def undelete_category(self, category_id: UUID) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Wiederherstellung einer gelöschten Employee Event Category.

        Args:
            category_id: ID der zu wiederherstellenden Kategorie

        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            with get_session() as session:
                category_db = session.get(models.EmployeeEventCategory, category_id)
                category_db.prep_delete = None
                return SuccessResponseSchema(
                    message=f"Employee Event Category '{category_db.name}' erfolgreich wiederhergestellt",
                    data={"category_id": str(category_id), "name": category_db.name}
                )

        except EmployeeEventCategoryError as e:
            return ErrorResponseSchema(
                error="CategoryNotFound",
                message=f"Employee Event Category nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Wiederherstellen der Employee Event Category",
                details=str(e)
            )

    def update_google_calendar_event_id(
            self, event_id: UUID, google_calendar_event_id: str) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Aktualisiert die Google Calendar Event ID für ein Employee Event.

        Args:
            event_id: ID des Events
            google_calendar_event_id: Neue Google Calendar Event ID

        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            with get_session() as session:
                event_db = session.get(models.EmployeeEvent, event_id)
                event_db.google_calendar_event_id = google_calendar_event_id
                return SuccessResponseSchema(
                    message=f"Google Calendar Event ID für Employee Event '{event_db.title}' erfolgreich aktualisiert",
                    data={"event_id": str(event_id), "google_calendar_event_id": google_calendar_event_id}
                )

        except EmployeeEventNotFoundError as e:
            return ErrorResponseSchema(
                error="EventNotFound",
                message=f"Employee Event nicht gefunden",
                details=str(e)
            )
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Aktualisieren der Google Calendar Event ID",
                details=str(e)
            )

    # Private Helper Methods

    def _get_team_id_by_name(self, name: str, project_id: UUID) -> Optional[UUID]:
        """Ermittelt Team-ID anhand des Namens (nur aktive Teams)."""
        with get_session() as session:
            team = session.exec(
                select(Team).where(
                    Team.name == name,
                    Team.project_id == project_id,
                    Team.prep_delete.is_(None),
                )
            ).first()
            return team.id if team else None

    def _get_person_id_by_username(self, username: str, project_id: UUID) -> Optional[UUID]:
        """Ermittelt Person-ID anhand des Benutzernamens."""
        with get_session() as session:
            person = session.exec(
                select(Person).where(Person.username == username, Person.project_id == project_id)
            ).first()
            return person.id if person else None
