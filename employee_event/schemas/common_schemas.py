"""
Gemeinsame Pydantic-Schemas für Employee Event Management.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class SuccessResponseSchema(BaseModel):
    """Schema für erfolgreiche API-Antworten."""
    
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(True, description="Erfolgs-Flag")
    message: str = Field(..., description="Erfolgs-Nachricht")
    data: Optional[Dict[str, Any]] = Field(None, description="Zusätzliche Daten")
    timestamp: datetime = Field(default_factory=datetime.now, description="Zeitstempel der Antwort")


class ErrorResponseSchema(BaseModel):
    """Schema für Fehler-Antworten."""
    
    model_config = ConfigDict(from_attributes=True)
    
    success: bool = Field(False, description="Erfolgs-Flag")
    error: str = Field(..., description="Fehler-Beschreibung")
    message: str = Field(..., description="Benutzerfreundliche Fehler-Nachricht")
    details: Optional[str] = Field(None, description="Detaillierte Fehler-Informationen")
    timestamp: datetime = Field(default_factory=datetime.now, description="Zeitstempel des Fehlers")


class StatisticsSchema(BaseModel):
    """Schema für Employee Event Statistiken."""
    
    model_config = ConfigDict(from_attributes=True)
    
    total_events: int = Field(default=0, description="Gesamtanzahl Events")
    total_categories: int = Field(default=0, description="Gesamtanzahl Kategorien")
    events_with_categories: int = Field(default=0, description="Events mit zugeordneten Kategorien")
    events_without_categories: int = Field(default=0, description="Events ohne Kategorien")
    most_active_team: Optional[Tuple[str, int]] = Field(None, description="Team mit den meisten Events")
    most_active_participant: Optional[Tuple[str, int]] = Field(None, description="Teilnehmer mit den meisten Events")
    average_participants_per_event: float = Field(default=0.0, description="Durchschnittliche Teilnehmer pro Event")
    category_distribution: Dict[str, int] = Field(default_factory=dict, description="Verteilung der Events nach Kategorien")
    project_name: Optional[str] = Field(None, description="Name des Projekts")
    generated_at: datetime = Field(default_factory=datetime.now, description="Zeitstempel der Statistik-Generierung")


class PaginationSchema(BaseModel):
    """Schema für Paginierung."""
    
    model_config = ConfigDict(from_attributes=True)
    
    page: int = Field(1, ge=1, description="Aktuelle Seite")
    page_size: int = Field(50, ge=1, le=1000, description="Anzahl Elemente pro Seite")
    total_items: int = Field(default=0, description="Gesamtanzahl Elemente")
    total_pages: int = Field(default=0, description="Gesamtanzahl Seiten")
    has_next: bool = Field(default=False, description="Weitere Seiten verfügbar")
    has_previous: bool = Field(default=False, description="Vorherige Seiten verfügbar")


class FilterSchema(BaseModel):
    """Schema für Filter-Optionen."""
    
    model_config = ConfigDict(from_attributes=True)
    
    project_id: Optional[UUID] = Field(None, description="Filter nach Projekt-ID")
    category_name: Optional[str] = Field(None, description="Filter nach Kategorie-Name")
    team_name: Optional[str] = Field(None, description="Filter nach Team-Name")
    participant_username: Optional[str] = Field(None, description="Filter nach Teilnehmer-Username")
    date_from: Optional[datetime] = Field(None, description="Filter ab Datum")
    date_to: Optional[datetime] = Field(None, description="Filter bis Datum")


class BulkOperationSchema(BaseModel):
    """Schema für Bulk-Operationen."""
    
    model_config = ConfigDict(from_attributes=True)
    
    operation: str = Field(..., description="Art der Operation (create, update, delete)")
    item_ids: List[UUID] = Field(..., description="Liste der betroffenen IDs")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Zusätzliche Parameter")


class BulkResultSchema(BaseModel):
    """Schema für Ergebnisse von Bulk-Operationen."""
    
    model_config = ConfigDict(from_attributes=True)
    
    operation: str = Field(..., description="Art der Operation")
    total_items: int = Field(..., description="Gesamtanzahl bearbeiteter Elemente")
    successful_items: int = Field(..., description="Anzahl erfolgreich bearbeiteter Elemente")
    failed_items: int = Field(..., description="Anzahl fehlgeschlagener Elemente")
    errors: List[str] = Field(default_factory=list, description="Liste der aufgetretenen Fehler")
    processed_at: datetime = Field(default_factory=datetime.now, description="Zeitstempel der Verarbeitung")
