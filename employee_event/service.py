"""
Service-Layer für Employee Event Management.

Stellt eine saubere Business Logic API bereit, die nur noch mit
typsicheren Pydantic-Schemas arbeitet.
"""

from typing import List, Optional, Union
from uuid import UUID

from pony.orm import db_session

from database.models import Team, Person, Project
from .repository import EmployeeEventRepository
from .schemas import (
    EventDetailSchema,
    EventListSchema,
    CreateEventSchema,
    UpdateEventSchema,
    CategorySchema,
    CategoryListSchema,
    CreateCategorySchema,
    UpdateCategorySchema,
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
        self.repository = EmployeeEventRepository()
    
    # Employee Event Operations
    
    def create_event(
        self,
        title: str,
        description: str,
        project_id: UUID,
        category_name: Optional[str] = None,
        team_names: Optional[List[str]] = None,
        participant_usernames: Optional[List[str]] = None
    ) -> Union[EventDetailSchema, ErrorResponseSchema]:
        """
        Erstellt ein neues Employee Event.
        
        Args:
            title: Titel des Events
            description: Beschreibung des Events
            project_id: ID des zugehörigen Projekts
            category_name: Optional - Name der Event-Kategorie
            team_names: Optional - Liste der zugeordneten Team-Namen
            participant_usernames: Optional - Liste der Teilnehmer-Benutzernamen
            
        Returns:
            Union[EventDetailSchema, ErrorResponseSchema]: Event oder Fehler
        """
        try:
            # Erstelle CreateEventSchema
            create_data = CreateEventSchema(
                title=title,
                description=description,
                project_id=project_id,
                category_name=category_name,
                team_names=team_names or [],
                participant_usernames=participant_usernames or []
            )
            
            # Event über Repository erstellen
            event = self.repository.create_event(create_data)
            
            return event
            
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Erstellen des Employee Events: {str(e)}",
                details=str(e)
            )
    
    def get_event(self, event_id: UUID) -> Union[EventDetailSchema, ErrorResponseSchema]:
        """
        Holt Details zu einem Employee Event.
        
        Args:
            event_id: ID des Events
            
        Returns:
            Union[EventDetailSchema, ErrorResponseSchema]: Event oder Fehler
        """
        try:
            return self.repository.get_event(event_id)
            
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
    
    def get_all_events(self, project_id: Optional[UUID] = None) -> EventListSchema:
        """
        Holt alle Employee Events, optional gefiltert nach Projekt.
        
        Args:
            project_id: Optional - Nur Events dieses Projekts
            
        Returns:
            EventListSchema: Liste aller Events
        """
        try:
            events = self.repository.get_all_events(project_id)
            return EventListSchema(
                events=events,
                total_count=len(events)
            )
            
        except Exception as e:
            return EventListSchema(events=[], total_count=0)
    
    def get_events_by_team_name(
        self, 
        team_name: str, 
        project_id: UUID
    ) -> Union[EventListSchema, ErrorResponseSchema]:
        """
        Holt alle Employee Events eines Teams anhand des Team-Namens.
        
        Args:
            team_name: Name des Teams
            project_id: ID des Projekts
            
        Returns:
            Union[EventListSchema, ErrorResponseSchema]: Events oder Fehler
        """
        try:
            # Team-ID ermitteln
            team_id = self._get_team_id_by_name(team_name, project_id)
            if not team_id:
                return ErrorResponseSchema(
                    error="TeamNotFound",
                    message=f"Team '{team_name}' nicht gefunden"
                )
            
            events = self.repository.get_events_by_team(team_id)
            return EventListSchema(
                events=events,
                total_count=len(events)
            )
            
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden der Team-Events",
                details=str(e)
            )
    
    def get_events_by_participant_username(
        self, 
        username: str, 
        project_id: UUID
    ) -> Union[EventListSchema, ErrorResponseSchema]:
        """
        Holt alle Employee Events eines Teilnehmers anhand des Benutzernamens.
        
        Args:
            username: Benutzername der Person
            project_id: ID des Projekts
            
        Returns:
            Union[EventListSchema, ErrorResponseSchema]: Events oder Fehler
        """
        try:
            # Person-ID ermitteln
            person_id = self._get_person_id_by_username(username, project_id)
            if not person_id:
                return ErrorResponseSchema(
                    error="ParticipantNotFound",
                    message=f"Teilnehmer '{username}' nicht gefunden"
                )
            
            events = self.repository.get_events_by_participant(person_id)
            return EventListSchema(
                events=events,
                total_count=len(events)
            )
            
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden der Teilnehmer-Events",
                details=str(e)
            )
    
    def update_event(
        self,
        event_id: UUID,
        title: Optional[str] = None,
        description: Optional[str] = None,
        category_name: Optional[str] = None
    ) -> Union[EventDetailSchema, ErrorResponseSchema]:
        """
        Aktualisiert ein Employee Event.
        
        Args:
            event_id: ID des zu aktualisierenden Events
            title: Neuer Titel (optional)
            description: Neue Beschreibung (optional)
            category_name: Name der neuen Kategorie (optional)
            
        Returns:
            Union[EventDetailSchema, ErrorResponseSchema]: Event oder Fehler
        """
        try:
            # Erstelle UpdateEventSchema
            update_data = UpdateEventSchema(
                title=title,
                description=description,
                category_name=category_name
            )
            
            # Event über Repository aktualisieren
            updated_event = self.repository.update_event(event_id, update_data)
            
            return updated_event
            
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
    
    def delete_event(self, event_id: UUID) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Löscht ein Employee Event.
        
        Args:
            event_id: ID des zu löschenden Events
            
        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            # Event-Titel für Meldung holen
            event = self.repository.get_event(event_id)
            title = event.title
            
            success = self.repository.delete_event(event_id)
            
            if success:
                return SuccessResponseSchema(
                    message=f"Employee Event '{title}' erfolgreich gelöscht",
                    data={"event_id": str(event_id), "title": title}
                )
            else:
                return ErrorResponseSchema(
                    error="DeleteFailed",
                    message=f"Fehler beim Löschen des Employee Events '{title}'"
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
    
    # Employee Event Category Operations
    
    def create_category(
        self,
        name: str,
        description: str,
        project_id: UUID
    ) -> Union[CategorySchema, ErrorResponseSchema]:
        """
        Erstellt eine neue Employee Event Category.
        
        Args:
            name: Name der Kategorie
            description: Beschreibung der Kategorie
            project_id: ID des zugehörigen Projekts
            
        Returns:
            Union[CategorySchema, ErrorResponseSchema]: Kategorie oder Fehler
        """
        try:
            # Erstelle CreateCategorySchema
            create_data = CreateCategorySchema(
                name=name,
                description=description,
                project_id=project_id
            )
            
            # Kategorie über Repository erstellen
            category = self.repository.create_category(create_data)
            
            return category
            
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Erstellen der Employee Event Category",
                details=str(e)
            )
    
    def get_all_categories(self, project_id: Optional[UUID] = None) -> CategoryListSchema:
        """
        Holt alle Employee Event Categories, optional gefiltert nach Projekt.
        
        Args:
            project_id: Optional - Nur Kategorien dieses Projekts
            
        Returns:
            CategoryListSchema: Liste aller Kategorien
        """
        try:
            categories = self.repository.get_all_categories(project_id)
            return CategoryListSchema(
                categories=categories,
                total_count=len(categories)
            )
            
        except Exception as e:
            return CategoryListSchema(categories=[], total_count=0)
    
    def update_category(
        self,
        category_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Union[CategorySchema, ErrorResponseSchema]:
        """
        Aktualisiert eine Employee Event Category.
        
        Args:
            category_id: ID der zu aktualisierenden Kategorie
            name: Neuer Name (optional)
            description: Neue Beschreibung (optional)
            
        Returns:
            Union[CategorySchema, ErrorResponseSchema]: Kategorie oder Fehler
        """
        try:
            # Erstelle UpdateCategorySchema
            update_data = UpdateCategorySchema(
                name=name,
                description=description
            )
            
            # Kategorie über Repository aktualisieren
            updated_category = self.repository.update_category(category_id, update_data)
            
            return updated_category
            
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
    
    def delete_category(self, category_id: UUID) -> Union[SuccessResponseSchema, ErrorResponseSchema]:
        """
        Löscht eine Employee Event Category.
        
        Args:
            category_id: ID der zu löschenden Kategorie
            
        Returns:
            Union[SuccessResponseSchema, ErrorResponseSchema]: Erfolg oder Fehler
        """
        try:
            # Kategorie-Name für Meldung holen
            category = self.repository.get_category(category_id)
            name = category.name
            
            success = self.repository.delete_category(category_id)
            
            if success:
                return SuccessResponseSchema(
                    message=f"Employee Event Category '{name}' erfolgreich gelöscht",
                    data={"category_id": str(category_id), "name": name}
                )
            else:
                return ErrorResponseSchema(
                    error="DeleteFailed",
                    message=f"Fehler beim Löschen der Employee Event Category '{name}'"
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
    
    # Statistiken und Reports
    
    def get_statistics(self, project_id: UUID) -> Union[StatisticsSchema, ErrorResponseSchema]:
        """
        Holt Statistiken zu Employee Events eines Projekts.
        
        Args:
            project_id: ID des Projekts
            
        Returns:
            Union[StatisticsSchema, ErrorResponseSchema]: Statistiken oder Fehler
        """
        try:
            return self.repository.get_statistics(project_id)
            
        except Exception as e:
            return ErrorResponseSchema(
                error=type(e).__name__,
                message=f"Fehler beim Laden der Statistiken",
                details=str(e)
            )
    
    # Private Helper Methods
    
    @db_session
    def _get_team_id_by_name(self, name: str, project_id: UUID) -> Optional[UUID]:
        """Ermittelt Team-ID anhand des Namens."""
        team = Team.get(name=name, project=project_id)
        return team.id if team else None
    
    @db_session
    def _get_person_id_by_username(self, username: str, project_id: UUID) -> Optional[UUID]:
        """Ermittelt Person-ID anhand des Benutzernamens."""
        person = Person.get(username=username, project=project_id)
        return person.id if person else None
