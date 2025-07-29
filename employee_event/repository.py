"""
Repository-Layer für Employee Events.

Stellt typsichere Datenbankzugriffe bereit und gibt direkt
Pydantic-Schemas zurück statt rohe ORM-Entities.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pony.orm import db_session, select, count

from database.models import EmployeeEvent, EmployeeEventCategory, Person, Team, Project, utcnow_naive
from .schemas import (
    EventSchema,
    EventDetailSchema, 
    CreateEventSchema,
    UpdateEventSchema,
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
    StatisticsSchema
)
from .exceptions import (
    EmployeeEventNotFoundError,
    EmployeeEventCategoryError,
    EmployeeEventValidationError,
    EmployeeEventParticipantError,
    EmployeeEventTeamError
)


class EmployeeEventRepository:
    """
    Repository-Klasse für Employee Events.
    
    Stellt alle CRUD-Operationen bereit und gibt typsichere
    Pydantic-Schemas zurück.
    """
    
    # Employee Event Operations
    
    @staticmethod
    @db_session
    def create_event(create_data: CreateEventSchema) -> EventDetailSchema:
        """
        Erstellt ein neues Employee Event.
        
        Args:
            create_data: Pydantic-Schema mit Event-Daten
            
        Returns:
            EventDetailSchema: Das erstellte Event
            
        Raises:
            EmployeeEventValidationError: Bei Validierungsfehlern
        """
        # Projekt prüfen
        project = Project.get(id=create_data.project_id)
        if not project:
            raise EmployeeEventValidationError(
                "project_id", 
                str(create_data.project_id), 
                "Projekt nicht gefunden"
            )
        
        # Event erstellen
        now = utcnow_naive()
        event = EmployeeEvent(
            title=create_data.title,
            description=create_data.description,
            start=create_data.start,
            end=create_data.end,
            project=project,
            created_at=now,
            last_modified=now
        )
        
        # Kategorie zuordnen falls angegeben
        if create_data.category_name:
            category = EmployeeEventCategory.get(
                name=create_data.category_name, 
                project=project
            )
            if category:
                event.employee_event_categories.add(category)
        
        # Teams zuordnen
        if create_data.team_names:
            for team_name in create_data.team_names:
                team = Team.get(name=team_name, project=project)
                if team:
                    event.teams.add(team)
        
        # Teilnehmer zuordnen
        if create_data.participant_usernames:
            for username in create_data.participant_usernames:
                person = Person.get(username=username, project=project)
                if person:
                    event.participants.add(person)
        
        return EmployeeEventRepository._event_to_detail_schema(event)
    
    @staticmethod
    @db_session
    def get_event(event_id: UUID) -> EventDetailSchema:
        """
        Holt ein Employee Event anhand der ID.
        
        Args:
            event_id: ID des Events
            
        Returns:
            EventDetailSchema: Das gefundene Event
            
        Raises:
            EmployeeEventNotFoundError: Wenn Event nicht gefunden
        """
        event = EmployeeEvent.get(id=event_id)
        if not event or event.prep_delete:
            raise EmployeeEventNotFoundError(event_id=str(event_id))
        
        return EmployeeEventRepository._event_to_detail_schema(event)
    
    @staticmethod
    @db_session
    def get_all_events(project_id: Optional[UUID] = None) -> List[EventDetailSchema]:
        """
        Holt alle Employee Events, optional gefiltert nach Projekt.
        
        Args:
            project_id: Optional - Nur Events dieses Projekts
            
        Returns:
            List[EventDetailSchema]: Liste aller Events
        """
        if project_id:
            events = select(e for e in EmployeeEvent 
                          if e.project.id == project_id and e.prep_delete is None)[:]
        else:
            events = select(e for e in EmployeeEvent 
                          if e.prep_delete is None)[:]
        
        return [EmployeeEventRepository._event_to_detail_schema(event) for event in events]
    
    @staticmethod
    @db_session
    def get_events_by_team(team_id: UUID) -> List[EventDetailSchema]:
        """
        Holt alle Employee Events eines Teams.
        
        Args:
            team_id: ID des Teams
            
        Returns:
            List[EventDetailSchema]: Events des Teams
            
        Raises:
            EmployeeEventTeamError: Wenn Team nicht gefunden
        """
        team = Team.get(id=team_id)
        if not team:
            raise EmployeeEventTeamError(message=f"Team mit ID {team_id} nicht gefunden")
        
        events = select(e for e in EmployeeEvent 
                       if team in e.teams and e.prep_delete is None)[:]
        
        return [EmployeeEventRepository._event_to_detail_schema(event) for event in events]
    
    @staticmethod
    @db_session
    def get_events_by_participant(person_id: UUID) -> List[EventDetailSchema]:
        """
        Holt alle Employee Events eines Teilnehmers.
        
        Args:
            person_id: ID der Person
            
        Returns:
            List[EventDetailSchema]: Events der Person
            
        Raises:
            EmployeeEventParticipantError: Wenn Person nicht gefunden
        """
        person = Person.get(id=person_id)
        if not person:
            raise EmployeeEventParticipantError(
                message=f"Person mit ID {person_id} nicht gefunden"
            )
        
        events = select(e for e in EmployeeEvent 
                       if person in e.participants and e.prep_delete is None)[:]
        
        return [EmployeeEventRepository._event_to_detail_schema(event) for event in events]
    
    @staticmethod
    @db_session
    def update_event(event_id: UUID, update_data: UpdateEventSchema) -> EventDetailSchema:
        """
        Aktualisiert ein Employee Event.
        
        Args:
            event_id: ID des zu aktualisierenden Events
            update_data: Pydantic-Schema mit Update-Daten
            
        Returns:
            EventDetailSchema: Das aktualisierte Event
            
        Raises:
            EmployeeEventNotFoundError: Wenn Event nicht gefunden
        """
        event = EmployeeEvent.get(id=event_id)
        if not event or event.prep_delete:
            raise EmployeeEventNotFoundError(event_id=str(event_id))
        
        # Updates anwenden
        if update_data.title is not None:
            event.title = update_data.title
        
        if update_data.description is not None:
            event.description = update_data.description
        
        if update_data.start is not None:
            event.start = update_data.start
        
        if update_data.end is not None:
            event.end = update_data.end
        
        if update_data.category_name is not None:
            # Alte Kategorien entfernen
            event.employee_event_categories.clear()
            # Neue Kategorie hinzufügen
            category = EmployeeEventCategory.get(
                name=update_data.category_name,
                project=event.project
            )
            if category:
                event.employee_event_categories.add(category)
        
        event.last_modified = utcnow_naive()
        
        return EmployeeEventRepository._event_to_detail_schema(event)
    
    @staticmethod
    @db_session
    def delete_event(event_id: UUID) -> bool:
        """
        Löscht ein Employee Event (soft delete via prep_delete).
        
        Args:
            event_id: ID des zu löschenden Events
            
        Returns:
            bool: True wenn erfolgreich
            
        Raises:
            EmployeeEventNotFoundError: Wenn Event nicht gefunden
        """
        event = EmployeeEvent.get(id=event_id)
        if not event or event.prep_delete:
            raise EmployeeEventNotFoundError(event_id=str(event_id))
        
        event.prep_delete = utcnow_naive()
        return True
    
    # Employee Event Category Operations
    
    @staticmethod
    @db_session
    def create_category(create_data: CreateCategorySchema) -> CategorySchema:
        """
        Erstellt eine neue Employee Event Category.
        
        Args:
            create_data: Pydantic-Schema mit Kategorie-Daten
            
        Returns:
            CategorySchema: Die erstellte Kategorie
            
        Raises:
            EmployeeEventValidationError: Bei Validierungsfehlern
        """
        # Projekt prüfen
        project = Project.get(id=create_data.project_id)
        if not project:
            raise EmployeeEventValidationError(
                "project_id", 
                str(create_data.project_id), 
                "Projekt nicht gefunden"
            )
        
        # Kategorie erstellen
        now = utcnow_naive()
        category = EmployeeEventCategory(
            name=create_data.name,
            description=create_data.description or "",
            project=project,
            created_at=now,
            last_modified=now
        )
        
        return EmployeeEventRepository._category_to_schema(category)
    
    @staticmethod
    @db_session
    def get_category(category_id: UUID) -> CategorySchema:
        """
        Holt eine Employee Event Category anhand der ID.
        
        Args:
            category_id: ID der Kategorie
            
        Returns:
            CategorySchema: Die gefundene Kategorie
            
        Raises:
            EmployeeEventCategoryError: Wenn Kategorie nicht gefunden
        """
        category = EmployeeEventCategory.get(id=category_id)
        if not category or category.prep_delete:
            raise EmployeeEventCategoryError(
                message=f"Kategorie mit ID {category_id} nicht gefunden"
            )
        
        return EmployeeEventRepository._category_to_schema(category)
    
    @staticmethod
    @db_session
    def get_all_categories(project_id: Optional[UUID] = None) -> List[CategorySchema]:
        """
        Holt alle Employee Event Categories, optional gefiltert nach Projekt.
        
        Args:
            project_id: Optional - Nur Kategorien dieses Projekts
            
        Returns:
            List[CategorySchema]: Liste aller Kategorien
        """
        if project_id:
            categories = select(c for c in EmployeeEventCategory 
                              if c.project.id == project_id and c.prep_delete is None)[:]
        else:
            categories = select(c for c in EmployeeEventCategory 
                              if c.prep_delete is None)[:]
        
        return [EmployeeEventRepository._category_to_schema(category) for category in categories]
    
    @staticmethod
    @db_session
    def update_category(category_id: UUID, update_data: UpdateCategorySchema) -> CategorySchema:
        """
        Aktualisiert eine Employee Event Category.
        
        Args:
            category_id: ID der zu aktualisierenden Kategorie
            update_data: Pydantic-Schema mit Update-Daten
            
        Returns:
            CategorySchema: Die aktualisierte Kategorie
            
        Raises:
            EmployeeEventCategoryError: Wenn Kategorie nicht gefunden
        """
        category = EmployeeEventCategory.get(id=category_id)
        if not category or category.prep_delete:
            raise EmployeeEventCategoryError(
                message=f"Kategorie mit ID {category_id} nicht gefunden"
            )
        
        # Updates anwenden
        if update_data.name is not None:
            category.name = update_data.name
        
        if update_data.description is not None:
            category.description = update_data.description
        
        category.last_modified = utcnow_naive()
        
        return EmployeeEventRepository._category_to_schema(category)
    
    @staticmethod
    @db_session
    def delete_category(category_id: UUID) -> bool:
        """
        Löscht eine Employee Event Category (soft delete via prep_delete).
        
        Args:
            category_id: ID der zu löschenden Kategorie
            
        Returns:
            bool: True wenn erfolgreich
            
        Raises:
            EmployeeEventCategoryError: Wenn Kategorie nicht gefunden
        """
        category = EmployeeEventCategory.get(id=category_id)
        if not category or category.prep_delete:
            raise EmployeeEventCategoryError(
                message=f"Kategorie mit ID {category_id} nicht gefunden"
            )
        
        category.prep_delete = utcnow_naive()
        return True
    
    # Statistiken
    
    @staticmethod
    @db_session
    def get_statistics(project_id: UUID) -> StatisticsSchema:
        """
        Holt Statistiken zu Employee Events eines Projekts.
        
        Args:
            project_id: ID des Projekts
            
        Returns:
            StatisticsSchema: Umfassende Statistiken
        """
        project = Project.get(id=project_id)
        if not project:
            return StatisticsSchema()
        
        # Basis-Statistiken
        total_events = count(e for e in EmployeeEvent 
                           if e.project == project and e.prep_delete is None)
        total_categories = count(c for c in EmployeeEventCategory 
                               if c.project == project and c.prep_delete is None)
        events_with_categories = count(e for e in EmployeeEvent 
                                     if e.project == project and e.prep_delete is None and e.employee_event_categories)
        events_without_categories = total_events - events_with_categories
        
        # Erweiterte Statistiken
        events = select(e for e in EmployeeEvent 
                       if e.project == project and e.prep_delete is None)[:]
        
        # Team-Statistiken
        team_event_counts = {}
        participant_event_counts = {}
        total_participants = 0
        
        for event in events:
            # Team-Zählungen
            for team in event.teams:
                team_event_counts[team.name] = team_event_counts.get(team.name, 0) + 1
            
            # Teilnehmer-Zählungen
            for participant in event.participants:
                participant_event_counts[participant.username] = participant_event_counts.get(participant.username, 0) + 1
            
            total_participants += len(event.participants)
        
        # Most active ermitteln
        most_active_team = max(team_event_counts.items(), key=lambda x: x[1]) if team_event_counts else None
        most_active_participant = max(participant_event_counts.items(), key=lambda x: x[1]) if participant_event_counts else None
        
        # Kategorie-Verteilung
        categories = select(c for c in EmployeeEventCategory 
                          if c.project == project and c.prep_delete is None)[:]
        category_distribution = {}
        for category in categories:
            category_distribution[category.name] = len([e for e in events if category in e.employee_event_categories])
        
        return StatisticsSchema(
            total_events=total_events,
            total_categories=total_categories,
            events_with_categories=events_with_categories,
            events_without_categories=events_without_categories,
            most_active_team=most_active_team,
            most_active_participant=most_active_participant,
            average_participants_per_event=total_participants / total_events if total_events > 0 else 0.0,
            category_distribution=category_distribution,
            project_name=project.name
        )
    
    # Private Helper Methods
    
    @staticmethod
    def _event_to_detail_schema(event: EmployeeEvent) -> EventDetailSchema:
        """Konvertiert EmployeeEvent zu EventDetailSchema mit model_validate."""
        # Dauer berechnen
        duration_hours = (event.end - event.start).total_seconds() / 3600
        
        # Erweitere das Event-Objekt um die benötigten Felder
        event_data = {
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'start': event.start,
            'end': event.end,
            'created_at': event.created_at,
            'last_modified': event.last_modified,
            'project_id': event.project.id,
            'project_name': event.project.name,
            'categories': [cat.name for cat in event.employee_event_categories],
            'teams': [team.name for team in event.teams],
            'participants': [person.username for person in event.participants],
            'participant_count': len(event.participants),
            'team_count': len(event.teams),
            'duration_hours': round(duration_hours, 2),
            'start_date': event.start.strftime('%d.%m.%Y'),
            'start_time': event.start.strftime('%H:%M'),
            'end_date': event.end.strftime('%d.%m.%Y'),
            'end_time': event.end.strftime('%H:%M')
        }
        return EventDetailSchema.model_validate(event_data)
    
    @staticmethod
    def _category_to_schema(category: EmployeeEventCategory) -> CategorySchema:
        """Konvertiert EmployeeEventCategory zu CategorySchema mit model_validate."""
        category_data = {
            'id': category.id,
            'name': category.name,
            'description': category.description,
            'created_at': category.created_at,
            'last_modified': category.last_modified,
            'project_id': category.project.id,
            'project_name': category.project.name,
            'event_count': len(category.employee_events)
        }
        return CategorySchema.model_validate(category_data)
