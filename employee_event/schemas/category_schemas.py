"""
Pydantic-Schemas für Employee Event Categories.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator, ConfigDict


class CategorySchema(BaseModel):
    """Basis-Schema für Employee Event Categories."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str = Field(..., max_length=40, description="Name der Kategorie")
    description: Optional[str] = Field(None, description="Beschreibung der Kategorie")
    created_at: datetime
    last_modified: datetime
    project_id: UUID
    project_name: str
    event_count: int = Field(default=0, description="Anzahl Events in dieser Kategorie")


class CreateCategorySchema(BaseModel):
    """Schema für das Erstellen neuer Employee Event Categories."""
    
    name: str = Field(..., min_length=1, max_length=40, description="Name der Kategorie")
    description: Optional[str] = Field(None, description="Beschreibung der Kategorie")
    project_id: UUID = Field(..., description="ID des zugehörigen Projekts")
    
    @field_validator('name')
    def name_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Name darf nicht leer sein')
        return v.strip()
    
    @field_validator('description')
    def description_cleanup(cls, v):
        return v.strip() if v else ""


class UpdateCategorySchema(BaseModel):
    """Schema für das Aktualisieren von Employee Event Categories."""
    
    name: Optional[str] = Field(None, min_length=1, max_length=40, description="Neuer Name")
    description: Optional[str] = Field(None, description="Neue Beschreibung")
    
    @field_validator('name')
    def name_must_not_be_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Name darf nicht leer sein')
        return v.strip() if v else None
    
    @field_validator('description')
    def description_cleanup(cls, v):
        return v.strip() if v else None


class CategoryListSchema(BaseModel):
    """Schema für Listen von Employee Event Categories."""
    
    model_config = ConfigDict(from_attributes=True)
    
    categories: List[CategorySchema] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Gesamtanzahl Kategorien")


class CategoryWithEventsSchema(CategorySchema):
    """Erweiterte Kategorie mit zugeordneten Event-Titeln."""
    
    event_titles: List[str] = Field(default_factory=list, description="Titel der Events in dieser Kategorie")
