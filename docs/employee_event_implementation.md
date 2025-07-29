# Employee Event Management - Implementation Documentation

## Projektübersicht

Das Employee Event Management System verwaltet Unternehmensveranstaltungen wie Fortbildungen, Meetings, Onlinekonferenzen etc. für das hcc_plan_db_playground Projekt.

**Status: ✅ Phase 1 abgeschlossen (Kern-Module)**

## Architektur

### Modern Pydantic v2 Pattern
```
Pony ORM Entity → Repository → Pydantic Schema → Service → Pydantic Schema → GUI
```

### Verzeichnisstruktur
```
employee_event/
├── __init__.py               # Package-Exports
├── exceptions.py             # Custom Exception-Klassen (7 Exceptions)
├── repository.py             # Datenbankzugriff mit Pydantic-Returns
├── service.py               # Business Logic API
└── schemas/                 # Pydantic v2 Schemas
    ├── __init__.py          # Schema-Exports
    ├── event_schemas.py     # Event-spezifische Schemas
    ├── category_schemas.py  # Category-spezifische Schemas
    └── common_schemas.py    # Response/Statistics-Schemas
```

## Datenbank-Entities

### EmployeeEvent
```python
class EmployeeEvent(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    title = Required(str, 40)
    description = Required(str)
    created_at = Required(datetime)
    last_modified = Required(datetime) 
    prep_delete = Optional(datetime)  # Soft Delete
    employee_event_categories = Set('EmployeeEventCategory')  # Many-to-Many
    project = Required(Project)
    teams = Set(Team)
    participants = Set(Person)
```

### EmployeeEventCategory
```python
class EmployeeEventCategory(db.Entity):
    id = PrimaryKey(UUID, auto=True)
    name = Required(str, 40)
    description = Optional(str)
    created_at = Required(datetime)
    last_modified = Required(datetime)
    prep_delete = Optional(datetime)  # Soft Delete
    employee_events = Set(EmployeeEvent)
    project = Required(Project)
```

## API Overview

### Repository Layer (Typsicher)
- `create_event(CreateEventSchema) → EventDetailSchema`
- `get_event(UUID) → EventDetailSchema` 
- `get_all_events(project_id?) → List[EventDetailSchema]`
- `update_event(UUID, UpdateEventSchema) → EventDetailSchema`
- `delete_event(UUID) → bool`
- `create_category(CreateCategorySchema) → CategorySchema`
- `get_statistics(UUID) → StatisticsSchema`

### Service Layer (Business Logic)
- `create_event(...) → EventDetailSchema | ErrorResponseSchema`
- `get_event(UUID) → EventDetailSchema | ErrorResponseSchema`
- `get_all_events(project_id?) → EventListSchema`
- `update_event(...) → EventDetailSchema | ErrorResponseSchema`
- `delete_event(UUID) → SuccessResponseSchema | ErrorResponseSchema`

## Pydantic v2 Standards

### Config Pattern
```python
model_config = ConfigDict(from_attributes=True)
```

### Validator Pattern
```python
@field_validator('title')
def title_must_not_be_empty(cls, v):
    # validation logic
```

### Object Conversion
```python
# Automatische Konvertierung mit model_validate()
event_data = {
    'id': event.id,
    'project_name': event.project.name,
    'categories': [cat.name for cat in event.employee_event_categories]
}
return EventDetailSchema.model_validate(event_data)
```

## Implementierung-Details

### Korrigierte Feldnamen
- ✅ `participants` (nicht `partitipants`)
- ✅ `employee_event_categories` (nicht `employee_event_categorys`)

### Removed Fields
- ❌ `category` String-Feld wurde aus EmployeeEvent Entity entfernt
- ✅ Nur Many-to-Many Beziehung `employee_event_categories` verwendet

### ✅ Korrekte PonyORM Patterns
```python
# Korrekt für PonyORM (Timezone-Kompatibilität):
prep_delete = Optional(datetime.datetime, default=utcnow_naive)

def utcnow_naive():
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
```

## Features

### ✅ Implementiert
- **CRUD-Operationen** für Events und Categories
- **Typsichere APIs** mit Pydantic v2
- **Exception-Handling** mit 7 Custom Exceptions
- **Soft Delete** über `prep_delete`
- **Team- und Teilnehmer-Management**
- **Statistische Auswertungen**
- **Performance-optimierte DB-Zugriffe**

### 🔄 Geplant (Phase 2-4)
- **GUI-Module** (frm_employee_event_management.py etc.)
- **Plan-Ansicht Integration** (Extra Spalten für Events)
- **Excel-Export Integration**
- **Google Kalender Synchronisation**

## Test Möglichkeiten

```python
from employee_event import create_service, CreateEventSchema
from uuid import uuid4

service = create_service()
result = service.create_event(
    title="Test Event",
    description="Test Description",
    project_id=uuid4()  # Ihre Projekt-ID
)
# result ist EventDetailSchema oder ErrorResponseSchema!
```

## Version History

- **v1.0.0** - Ursprüngliche Implementierung
- **v2.0.0** - Pydantic v2 Refactoring + Repository Pattern
- **v2.0.1** - Feldnamen-Korrekturen (participants, employee_event_categories)

## Nächste Schritte

1. **models.py korrigieren** - `prep_delete` Default entfernen
2. **Phase 2 starten** - GUI-Module implementieren
3. **Integration testen** - Mit bestehender hcc_plan Anwendung
4. **Plan-Ansicht erweitern** - Employee Event Spalten hinzufügen

---
**Entwickelt von:** Thomas & Claude  
**Letzte Aktualisierung:** 29.07.2025  
**Status:** Production Ready (Phase 1)
