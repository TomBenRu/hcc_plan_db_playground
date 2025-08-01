"""
Pydantic-Schemas für Employee Events.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict

from database import schemas
from tools.helper_functions import date_to_string


class ProjectMinimal(BaseModel):
    """Minimal-Schema für Projekte."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str

class Event(BaseModel):
    """Basis-Schema für Employee Events."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: str = Field(..., max_length=40, description="Titel des Events")
    description: str = Field(..., description="Beschreibung des Events")
    start: datetime = Field(..., description="Start-Zeitpunkt des Events")
    end: datetime = Field(..., description="End-Zeitpunkt des Events")
    created_at: datetime
    last_modified: datetime
    project: ProjectMinimal


class EventDetail(Event):
    """Detailliertes Schema für Employee Events mit Beziehungen."""
    
    employee_event_categories: List['Category'] = Field(default_factory=list, description="Zugeordnete Kategorien")
    teams: List[schemas.Team] = Field(default_factory=list, description="Zugeordnete Teams")
    participants: List[schemas.Person] = Field(default_factory=list, description="Teilnehmer")

    @property
    def participant_count(self):
        """Anzahl Teilnehmer"""
        return len(self.participants)

    @property
    def team_count(self):
        """Anzahl Teams"""
        return len(self.teams)

    @property
    def start_date(self):
        """Start-Datum formatiert"""
        return date_to_string(self.start.date())

    @property
    def end_date(self):
        """End-Datum formatiert"""
        return date_to_string(self.end.date())

    @property
    def start_time(self):
        """Start-Zeit formatiert"""
        return self.start.strftime('%H:%M')

    @property
    def end_time(self):
        """End-Zeit formatiert"""
        return self.end.strftime('%H:%M')


    @property
    def duration_hours(self):
        """Dauer in Stunden"""
        return (self.end - self.start).total_seconds() / 3600


class EventCreate(BaseModel):
    """Schema für das Erstellen neuer Employee Events."""
    
    title: str = Field(..., min_length=1, max_length=40, description="Titel des Events")
    description: str = Field(..., description="Beschreibung des Events")
    start: datetime = Field(..., description="Start-Zeitpunkt des Events")
    end: datetime = Field(..., description="End-Zeitpunkt des Events")
    project_id: UUID = Field(..., description="ID des zugehörigen Projekts")
    category_ids: list[UUID] = Field(default_factory=list, description="IDs der zugeordneten Kategorien")
    team_ids: list[UUID] = Field(default_factory=list, description="IDs der zugeordneten Teams")
    participant_ids: list[UUID] = Field(default_factory=list, description="IDs der Teilnehmer")
    
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


class EventUpdate(BaseModel):
    """Schema für das Aktualisieren von Employee Events."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    title: Optional[str] = Field(None, min_length=1, max_length=40, description="Neuer Titel")
    description: Optional[str] = Field(None, description="Neue Beschreibung")
    start: Optional[datetime] = Field(None, description="Neuer Start-Zeitpunkt")
    end: Optional[datetime] = Field(None, description="Neuer End-Zeitpunkt")
    category_ids: Optional[list[UUID]] = Field(None, description="IDs der neuen Kategorien")
    team_ids: Optional[list[UUID]] = Field(None, description="IDs der neuen Teams")
    participant_ids: Optional[list[UUID]] = Field(None, description="IDs der neuen Teilnehmer")
    
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

    @field_validator('category_ids', 'team_ids', 'participant_ids')
    def models_to_ids(cls, v):
        if v is not None:
            return [t.id if isinstance(t, BaseModel) else t for t in v]
        return None


class Category(BaseModel):
    """Basis-Schema für Employee Event Categories."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(..., max_length=40, description="Name der Kategorie")
    description: Optional[str] = Field(None, description="Beschreibung der Kategorie")


class CategoryCreate(BaseModel):
    """Schema für das Erstellen neuer Employee Event Categories."""

    name: str = Field(..., min_length=1, max_length=40, description="Name der Kategorie")
    description: Optional[str] = Field(None, description="Beschreibung der Kategorie")
    project_id: UUID = Field(..., description="ID des zugehörigen Projekts")


class CategoryUpdate(BaseModel):
    """Schema für das Aktualisieren von Employee Event Categories."""

    id: UUID
    name: Optional[str] = Field(None, min_length=1, max_length=40, description="Neuer Name")
    description: Optional[str] = Field(None, description="Neue Beschreibung")


class CategoryDetail(Category):
    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    last_modified: datetime
    project: ProjectMinimal
    employee_events: list[Event] = Field(default_factory=list)

    @field_validator('employee_events')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]

    @property
    def event_count(self):
        """Anzahl Events in dieser Kategorie"""
        return len(self.employee_events)
