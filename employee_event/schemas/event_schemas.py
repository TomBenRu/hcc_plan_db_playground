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
    start: datetime = Field(..., description="Start-Zeitpunkt des Events")
    end: datetime = Field(..., description="End-Zeitpunkt des Events")
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
    duration_hours: float = Field(default=0.0, description="Dauer in Stunden")
    start_date: str = Field(default="", description="Start-Datum formatiert")
    start_time: str = Field(default="", description="Start-Zeit formatiert")
    end_date: str = Field(default="", description="End-Datum formatiert")
    end_time: str = Field(default="", description="End-Zeit formatiert")


class CreateEventSchema(BaseModel):
    """Schema für das Erstellen neuer Employee Events."""
    
    title: str = Field(..., min_length=1, max_length=40, description="Titel des Events")
    description: str = Field(..., description="Beschreibung des Events")
    start: datetime = Field(..., description="Start-Zeitpunkt des Events")
    end: datetime = Field(..., description="End-Zeitpunkt des Events")
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
    
    @field_validator('end')
    def end_after_start(cls, v, info):
        if 'start' in info.data and v <= info.data['start']:
            raise ValueError('End-Zeitpunkt muss nach Start-Zeitpunkt liegen')
        return v


class UpdateEventSchema(BaseModel):
    """Schema für das Aktualisieren von Employee Events."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=40, description="Neuer Titel")
    description: Optional[str] = Field(None, description="Neue Beschreibung")
    start: Optional[datetime] = Field(None, description="Neuer Start-Zeitpunkt")
    end: Optional[datetime] = Field(None, description="Neuer End-Zeitpunkt")
    category_name: Optional[str] = Field(None, max_length=40, description="Name der neuen Kategorie")
    
    @field_validator('title')
    def title_must_not_be_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Titel darf nicht leer sein')
        return v.strip() if v else None
    
    @field_validator('description')
    def description_cleanup(cls, v):
        return v.strip() if v else None
    
    @field_validator('end')
    def end_after_start(cls, v, info):
        if v is not None and 'start' in info.data and info.data['start'] is not None:
            if v <= info.data['start']:
                raise ValueError('End-Zeitpunkt muss nach Start-Zeitpunkt liegen')
        return v


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
