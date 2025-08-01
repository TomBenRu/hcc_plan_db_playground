"""
Pydantic-Schemas für Employee Event Management.

Enthält alle Datenstrukturen für typsichere API-Kommunikation
zwischen Repository, Service und GUI-Layer.
"""

from .employee_event_schemas import (
    Event,
    EventCreate,
    EventUpdate,
    EventDetail,
    Category,
    CategoryCreate,
    CategoryUpdate,
    CategoryDetail
)

from .common_schemas import (
    SuccessResponseSchema,
    ErrorResponseSchema,
    StatisticsSchema
)

__all__ = [
    # Event Schemas
    "Event",
    "EventCreate",
    "EventUpdate",
    "EventDetail",
    
    # Category Schemas
    "Category",
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryDetail",
    
    # Common Schemas
    "SuccessResponseSchema",
    "ErrorResponseSchema",
    "StatisticsSchema"
]
