"""
Pydantic-Schemas für Employee Event Management.

Enthält alle Datenstrukturen für typsichere API-Kommunikation
zwischen Repository, Service und GUI-Layer.
"""

from .event_schemas import (
    EventSchema,
    CreateEventSchema,
    UpdateEventSchema,
    EventListSchema,
    EventDetailSchema
)

from .category_schemas import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
    CategoryListSchema
)

from .common_schemas import (
    SuccessResponseSchema,
    ErrorResponseSchema,
    StatisticsSchema
)

__all__ = [
    # Event Schemas
    "EventSchema",
    "CreateEventSchema", 
    "UpdateEventSchema",
    "EventListSchema",
    "EventDetailSchema",
    
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
