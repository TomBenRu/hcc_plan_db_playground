"""
Pydantic-Schemas für Employee Events.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EventSchema(BaseModel):
    """Basis-Schema für Employee Events."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str = Field(..., max_length=40, description="Titel des Events")
    description: str = Field(..., description="Beschreibung des Events")
    created_at: datetime
    last_modified: datetime
    project_id: UUID
    project_name: str


class EventDetailSchema(EventSchema):
    """Detailliertes Schema für Employee Events mit Beziehungen."""
    
    categories: List[str] = Field(default_factory=list, description="Namen der zugeordneten Kategorien")
    teams: List[str] = Field(default_factory=list, description="Namen der zugeordneten Teams")
    participants: List[str] = Field(default_factory=list, description="Benutzernamen der Teilnehmer")
    participant_count: int = Field(default=0, description="Anzahl Teilnehmer")
    team_count: int = Field(default=0, description="Anzahl Teams")


class CreateEventSchema(BaseModel):
    """Schema für das Erstellen neuer Employee Events."""
    
    title: str = Field(..., min_length=1, max_length=40, description="Titel des Events")
    description: str = Field(..., description="Beschreibung des Events")
    project_id: UUID = Field(..., description="ID des zugehörigen Projekts")
    category_name: Optional[str] = Field(None, max_length=40, description="Name der Event-Kategorie")
    team_names: Optional[List[str]] = Field(default_factory=list, description="Namen der zugeordneten Teams")
    participant_usernames: Optional[List[str]] = Field(default_factory=list, description="Benutzernamen der Teilnehmer")
    
    @field_validator('title')
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Titel darf nicht leer sein')
        return v.strip()
    
    @field_validator('description')
    def description_cleanup(cls, v):
        return v.strip() if v else ""


class UpdateEventSchema(BaseModel):
    """Schema für das Aktualisieren von Employee Events."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=40, description="Neuer Titel")
    description: Optional[str] = Field(None, description="Neue Beschreibung")
    category_name: Optional[str] = Field(None, max_length=40, description="Name der neuen Kategorie")
    
    @field_validator('title')
    def title_must_not_be_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Titel darf nicht leer sein')
        return v.strip() if v else None
    
    @field_validator('description')
    def description_cleanup(cls, v):
        return v.strip() if v else None


class EventListSchema(BaseModel):
    """Schema für Listen von Employee Events."""
    
    model_config = ConfigDict(from_attributes=True)
    
    events: List[EventDetailSchema] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Gesamtanzahl Events")


class EventParticipantSchema(BaseModel):
    """Schema für Event-Teilnehmer."""
    
    model_config = ConfigDict(from_attributes=True)
    
    event_id: UUID
    username: str = Field(..., description="Benutzername des Teilnehmers")
    person_id: UUID
    f_name: str
    l_name: str


class EventTeamSchema(BaseModel):
    """Schema für Event-Teams."""
    
    model_config = ConfigDict(from_attributes=True)
    
    event_id: UUID
    team_name: str = Field(..., description="Name des Teams")
    team_id: UUID
