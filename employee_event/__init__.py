"""
Employee Event Management Package

Dieses Package verwaltet Unternehmensveranstaltungen wie Fortbildungen, 
Meetings, Onlinekonferenzen etc. für das hcc_plan_db_playground Projekt.

Hauptkomponenten:
- repository.py: Typsichere Datenbankzugriffe mit Pydantic-Schemas
- service.py: Business Logic API 
- schemas/: Pydantic-Models für alle Datenstrukturen
- exceptions.py: Custom Exception-Klassen

Architektur:
Pony ORM Entity → Repository → Pydantic Schema → Service → Pydantic Schema → GUI
"""

from .db_service import EmployeeEventService
from .exceptions import (
    EmployeeEventError,
    EmployeeEventNotFoundError,
    EmployeeEventValidationError,
    EmployeeEventCategoryError,
    EmployeeEventParticipantError,
    EmployeeEventTeamError,
    EmployeeEventDateError
)

# Import wichtiger Schemas für externe Nutzung
from .schemas import (
    # Event Schemas
    EventSchema,
    EventDetailSchema,
    EventCreateSchema,
    EventUpdateSchema,
    
    # Category Schemas
    CategorySchema,
    CategoryCreateSchema,
    CategoryUpdateSchema,
    CategoryDetailSchema,
    
    # Common Schemas
    SuccessResponseSchema,
    ErrorResponseSchema,
    StatisticsSchema
)

__version__ = "2.0.0"
__author__ = "Thomas"

__all__ = [
    # Core Classes
    "EmployeeEventService",
    
    # Exceptions
    "EmployeeEventError",
    "EmployeeEventNotFoundError",
    "EmployeeEventValidationError",
    "EmployeeEventCategoryError",
    "EmployeeEventParticipantError",
    "EmployeeEventTeamError",
    "EmployeeEventDateError",
    
    # Event Schemas
    "EventSchema",
    "EventDetailSchema",
    "EventCreateSchema",
    "EventUpdateSchema",
    
    # Category Schemas
    "CategorySchema",
    "CategoryCreateSchema",
    "CategoryUpdateSchema",
    "CategoryDetailSchema",
    
    # Common Schemas
    "SuccessResponseSchema",
    "ErrorResponseSchema",
    "StatisticsSchema"
]
