# Employee Event Management - Implementation Documentation

## Projektübersicht

Das Employee Event Management System verwaltet Unternehmensveranstaltungen wie Fortbildungen, Meetings, Onlinekonferenzen etc. für das hcc_plan_db_playground Projekt.

**Status: ✅ Phase 1 abgeschlossen (Kern-Module) | 🔄 Phase 2 in Arbeit (GUI-Module)**

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
    start = Required(datetime)        # NEU: Start-Zeitpunkt
    end = Required(datetime)          # NEU: End-Zeitpunkt  
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
- `create_event(title, description, start, end, project_id, ...) → EventDetailSchema | ErrorResponseSchema`
- `get_event(UUID) → EventDetailSchema | ErrorResponseSchema`
- `get_all_events(project_id?) → EventListSchema`
- `update_event(event_id, title?, description?, start?, end?, ...) → EventDetailSchema | ErrorResponseSchema`
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
- **Zeitfelder-Integration** (start/end datetime mit Validierung)
- **GUI-Hauptfenster** mit Listen- und Kalenderansicht ✅

### 🔄 In Arbeit (Phase 2)
- **Event-Detail-Dialog** (frm_employee_event_details.py)
- **Kategorie-Verwaltung** (dlg_employee_event_categories.py)
- **Teilnehmer-Auswahl** (dlg_participant_selection.py)
- **Tab-Integration** in main_window.py

### 🔄 Geplant (Phase 3-4)
- **Plan-Ansicht Integration** (Extra Spalten für Events)
- **Excel-Export Integration**
- **Google Kalender Synchronisation**

## GUI-Module (Phase 2)

### Hauptfenster (frm_employee_event_main.py) ✅
```python
class FrmEmployeeEventMain(QWidget):
    """
    Hauptfenster für Employee Event Management.
    
    Features:
    - Toggle zwischen Listen- und Kalenderansicht
    - Filter für Teams, Kategorien, Freitextsuche
    - CRUD-Operationen für Events
    - Config-abhängige Datums/Zeit-Formatierung
    """
```

#### Zwei Darstellungsmodi:
- **📋 Listenansicht**: Tabelle mit Spalten `Datum | Zeitspanne | Name | Kategorie | Teams | Teilnehmer`
- **📅 Kalenderansicht**: QCalendarWidget + Event-Panel für ausgewähltes Datum

#### Filter-System:
- **Team-Filter**: Dropdown mit allen verfügbaren Teams  
- **Kategorie-Filter**: Multi-Select für Event-Kategorien
- **Freitextsuche**: In Titel und Beschreibung (300ms Verzögerung)
- **Filter zurücksetzen** + Live-Status-Anzeige

#### Config-Integration:
```python
# Formatierung respektiert User-Einstellungen
formatted_date = date_to_string(event.start.date())
formatted_time = time_to_string(event.start.time())
```

### Implementiert:
- ~~`dlg_employee_event_details.py` - Event erstellen/bearbeiten Dialog~~ **✅ FERTIG (30.07.2025)**
  - ✅ **Widget-Höhen-Korrektur**: Alle Date-Time-Widgets einheitlich 25px hoch (setFixedHeight)
  - ✅ **Layout-Optimierungen**: Kompakteres Design mit 0px Padding und größerem Dialog
  - ✅ **Code-Cleanup**: Entfernung überflüssiger Validierungs-Logik
- ~~`dlg_employee_event_categories.py` - Kategorie-Verwaltung Dialog~~ **✅ FERTIG (30.07.2025)**
  - ✅ **CRUD-Operationen**: Vollständige Kategorie-Verwaltung mit Create/Read/Update/Delete
  - ✅ **Usage-Tracking**: Anzeige wie viele Events jede Kategorie verwendet
  - ✅ **Auto-Save-System**: Verzögerte Speicherung bei Eingaben (1s Timer)
  - ✅ **Dialog-Integration**: Nahtlose Verbindung mit Event-Details-Dialog
  - ✅ **Dark Theme**: Konsistentes Design mit anderen Projektdialogen

### Noch zu implementieren:
- `dlg_participant_selection.py` - Teilnehmer-Auswahl Dialog

## Test Möglichkeiten

```python
from datetime import datetime
from employee_event import create_service, CreateEventSchema
from uuid import uuid4

service = create_service()
result = service.create_event(
    title="Test Event",
    description="Test Description",
    start=datetime(2025, 8, 1, 9, 0),   # 1. August 2025, 9:00
    end=datetime(2025, 8, 1, 17, 0),    # 1. August 2025, 17:00
    project_id=uuid4()  # Ihre Projekt-ID
)
# result ist EventDetailSchema oder ErrorResponseSchema!
```

## Version History

- **v1.0.0** - Ursprüngliche Implementierung
- **v2.0.0** - Pydantic v2 Refactoring + Repository Pattern
- **v2.0.1** - Feldnamen-Korrekturen (participants, employee_event_categories)  
- **v2.1.0** - **Zeitfelder-Integration**: start/end datetime Felder hinzugefügt (29.07.2025)
- **v2.2.0** - **GUI-Hauptfenster**: frm_employee_event_main.py implementiert (29.07.2025)
- **v2.3.0** - **Event-Details-Dialog**: dlg_employee_event_details.py komplett implementiert (30.07.2025)
- **v2.3.1** - **Widget-Höhen-Korrektur**: Alle Date-Time-Widgets einheitlich 35px hoch (30.07.2025)
- **v2.4.0** - **Kategorie-Management-Dialog**: dlg_employee_event_categories.py komplett implementiert (30.07.2025)

## Nächste Schritte

1. **Phase 2 abschließen** - Verbleibende Dialoge implementieren:
   - `dlg_employee_event_categories.py` - Kategorie-Verwaltung Dialog
   - `dlg_participant_selection.py` - Teilnehmer-Auswahl Dialog
2. **Integration testen** - Event-Details-Dialog mit Hauptfenster testen
3. **Phase 3 starten** - Plan-Ansicht Integration für Event-Anzeige

---
**Entwickelt von:** Thomas & Claude  
**Letzte Aktualisierung:** 30.07.2025  
**Status:** Event-Details-Dialog komplett fertig inkl. Widget-Höhen-Korrekturen
