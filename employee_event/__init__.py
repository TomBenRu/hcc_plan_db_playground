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

from .repository import EmployeeEventRepository
from .service import EmployeeEventService
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
    CreateEventSchema,
    UpdateEventSchema,
    EventListSchema,
    
    # Category Schemas
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
    CategoryListSchema,
    
    # Common Schemas
    SuccessResponseSchema,
    ErrorResponseSchema,
    StatisticsSchema
)

__version__ = "2.0.0"
__author__ = "Thomas"

__all__ = [
    # Core Classes
    "EmployeeEventRepository",
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
    "CreateEventSchema",
    "UpdateEventSchema",
    "EventListSchema",
    
    # Category Schemas
    "CategorySchema",
    "CreateCategorySchema",
    "UpdateCategorySchema", 
    "CategoryListSchema",
    
    # Common Schemas
    "SuccessResponseSchema",
    "ErrorResponseSchema",
    "StatisticsSchema"
]

# Convenience imports für einfache Nutzung
def create_service() -> EmployeeEventService:
    """
    Erstellt eine neue EmployeeEventService-Instanz.
    
    Returns:
        EmployeeEventService: Service-Instanz
    """
    return EmployeeEventService()

def create_repository() -> EmployeeEventRepository:
    """
    Erstellt eine neue EmployeeEventRepository-Instanz.
    
    Returns:
        EmployeeEventRepository: Repository-Instanz
    """
    return EmployeeEventRepository()
