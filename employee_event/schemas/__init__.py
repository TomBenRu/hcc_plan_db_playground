"""
Pydantic-Schemas für Employee Event Management.

Enthält alle Datenstrukturen für typsichere API-Kommunikation
zwischen Repository, Service und GUI-Layer.
"""

from .event_and_category_schemas import (
    EventSchema,
    EventCreateSchema,
    EventUpdateSchema,
    EventDetailSchema,
    CategorySchema,
    CategoryCreateSchema,
    CategoryUpdateSchema,
    CategoryDetailSchema
)

from .common_schemas import (
    SuccessResponseSchema,
    ErrorResponseSchema,
    StatisticsSchema
)

__all__ = [
    # Event Schemas
    "EventSchema",
    "EventCreateSchema",
    "EventUpdateSchema",
    "EventDetailSchema",
    
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
