# Employee Event Management - Implementation Documentation

## Projektübersicht

Das Employee Event Management System verwaltet Unternehmensveranstaltungen wie Fortbildungen, Meetings, Onlinekonferenzen etc. für das hcc_plan_db_playground Projekt.

**Status: ✅ Phase 1 abgeschlossen (Kern-Module) | 🔄 Phase 2 in Arbeit (GUI-Module)**

## Commands-Pattern für Undo/Redo-Funktionalität

### ⚠️ Wichtiger Architektur-Hinweis

**Für schreibende Datenbankoperationen müssen Commands verwendet werden!**

Das hcc_plan_db_playground Projekt nutzt ein Command-Pattern im `commands/` Verzeichnis für alle schreibenden DB-Operationen. Dies ermöglicht:
- **Undo/Redo-Funktionalität** 
- **Rollback bei Fehlern**
- **Transaktionale Sicherheit**
- **Audit-Trail für Änderungen**

### 🔧 Aktuelle Service-Integration (Temporär)

```python
# AKTUELL (Phase 1-2): Direkte Service-Calls
result = self.db_service.create_event(title, description, start, end, ...)
result = self.db_service.update_event(event_id, title, description, ...)
result = self.db_service.delete_event(event_id)
```

### 🎯 Zukünftige Commands-Integration (Phase 3)

```python
# ZUKÜNFTIG: Commands für alle schreibenden Operationen
import employee_events_commands

# Event erstellen
command = employee_events_commands.CreateEvent(title, description, start, end, project_id, ...)
result = self.command_manager.execute(command)

# Event aktualisieren  
command = employee_events_commands.UpdateEvent(event_id, title=new_title, description=new_description, ...)
result = self.command_manager.execute(command)

# Event löschen
command = employee_events_commands.DeleteEvent(event_id)
result = self.command_manager.execute(command)

# Undo/Redo verfügbar
self.command_manager.undo()  # Letzte Aktion rückgängig
self.command_manager.redo()  # Aktion wiederholen
```

### 📋 TODO: Commands-Implementierung (Phase 3)

- [ ] **`commands/employee_events_commands.py`** - Command-Klassen für alle CRUD-Operationen
- [ ] **Service-to-Commands Migration** - Ersetzen direkter Service-Calls durch Commands
- [ ] **GUI-Integration** - Undo/Redo-Buttons in Dialogen und Hauptfenster
- [ ] **Command-Manager-Integration** - Einbindung in bestehende Command-Infrastruktur

### 🔄 Migration-Reihenfolge

1. **Phase 1-2 (AKTUELL):** Service-Integration für funktionsfähige GUI
2. **Phase 3:** Commands-Implementation für Production-Ready-System  
3. **Phase 4:** Undo/Redo-UI-Integration

---

## Architektur

### Moderne Schema-driven Pattern (überarbeitet)
```
Pony ORM Entity → Pydantic Schema → Service → Pydantic Schema → GUI
```

**⚠️ Repository Pattern entfernt** - War Over-Engineering bei PonyORM

### Verzeichnisstruktur
```
employee_event/
├── __init__.py               # Package-Exports
├── exceptions.py             # Custom Exception-Klassen (7 Exceptions)
├── db_service.py            # Service-Layer mit direkter PonyORM-Integration
├── db_commands/             # Commands für Undo/Redo (in Entwicklung)
│   ├── __init__.py
│   └── employee_event_commands.py
└── schemas/                 # Pydantic v2 Schemas
    ├── __init__.py          # Schema-Exports
    ├── event_and_category_schemas.py  # Event & Category Schemas
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

### Service Layer (Direkte PonyORM Integration)
- `create_event(EventCreateSchema) → EventDetailSchema | ErrorResponseSchema`
- `get_event(UUID) → EventDetailSchema | ErrorResponseSchema` 
- `get_all_events(project_id?) → List[EventDetailSchema]`
- `update_event(EventUpdateSchema) → EventDetailSchema | ErrorResponseSchema`
- `delete_event(UUID) → SuccessResponseSchema | ErrorResponseSchema`
- `create_category(CategoryCreateSchema) → CategorySchema | ErrorResponseSchema`
- `get_all_categories_by_project(UUID) → List[CategorySchema]`

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

## Architektur-Entscheidungen

### ✅ Repository Pattern entfernt (v2.6.0)
**Problem:** Over-Engineering - PonyORM ist bereits eine perfekte Abstraktion  
**Lösung:** Direkte Service → PonyORM Integration mit Pydantic Schemas

**Vorher (Over-Engineering):**
```
Database → PonyORM → Repository → Service → GUI
```

**Jetzt (Elegant):**
```
Database → PonyORM → Service → GUI
```

**Vorteile der neuen Architektur:**
- **Weniger Code** = weniger Bugs
- **Bessere Performance** - keine unnötigen Mapping-Ebenen
- **Modernere Patterns** - Schema-driven Design
- **Direkte PonyORM-Integration** - nutzt alle ORM-Features optimal

### ✅ Schema-driven Service API
```python
# Modern: Schema-basierte API
def create_event(self, event_create: EventCreateSchema) -> Union[EventDetailSchema, ErrorResponseSchema]:
    project_db = models.Project.get(id=event_create.project_id)
    event_db = models.EmployeeEvent(
        title=event_create.title,
        description=event_create.description,
        start=event_create.start,
        end=event_create.end,
        project=project_db
    )
    return EventDetailSchema.model_validate(event_db)
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
- ~~`dlg_participant_selection.py` - Teilnehmer-Auswahl Dialog~~ **✅ FERTIG (30.07.2025)**
  - ✅ **Multi-Select-Interface**: Drag & Drop zwischen verfügbaren und ausgewählten Personen
  - ✅ **Team-Filter**: Filter nach Teams für bessere Übersicht
  - ✅ **Freitextsuche**: Suche in Namen mit 300ms Verzögerung
  - ✅ **Transfer-Buttons**: Add/Remove einzeln oder alle auf einmal (➤ ⏩ ◀ ⏪)
  - ✅ **Split-Layout**: Verfügbare | Transfer-Buttons | Ausgewählte (40%-20%-40%)
  - ✅ **Integration**: Vollständige Verbindung mit Event-Details-Dialog

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
- **v2.4.1** - **Hauptfenster-Integration**: "Manage Categories" Button mit Dialog verbunden (30.07.2025)
- **v2.4.2** - **Commands-Pattern Dokumentation**: Wichtige Architektur-Hinweise für Production-System (30.07.2025)
- **v2.5.0** - **Teilnehmer-Auswahl-Dialog**: dlg_participant_selection.py komplett implementiert (30.07.2025)
- **v2.5.1** - **Teilnehmer-Integration**: Automatische Übernahme vorhandener Teilnehmer beim Öffnen des Auswahl-Dialogs (30.07.2025)
- **v2.6.0** - **Architektur-Refactoring**: Repository Pattern entfernt, Schema-driven Service API (01.08.2025)
  - ✅ **Over-Engineering eliminiert** - Direkte Service ↔ PonyORM Integration
  - ✅ **Schema-basierte APIs** - EventCreateSchema, EventUpdateSchema, CategoryCreateSchema
  - ✅ **Performance-Verbesserung** - Weniger Abstraktionsebenen
  - ✅ **Commands-Pattern vorbereitet** - db_commands/ Struktur für Undo/Redo

## Nächste Schritte

1. **Phase 3 abschließen** - Letzten Dialog implementieren:
   - `dlg_participant_selection.py` - Teilnehmer-Auswahl Dialog
2. **Commands-Integration** - Production-Ready-System mit Undo/Redo:
   - `commands/employee_event_commands.py` - Command-Klassen implementieren
   - Service → Commands Migration durchführen
3. **Testing** - Vollständige Funktionalität testen

⚠️ **WICHTIG:** Für Production-System muss Commands-Pattern implementiert werden!

---
**Entwickelt von:** Thomas & Claude  
**Letzte Aktualisierung:** 30.07.2025  
**Status:** Phase 1-3 vollständig abgeschlossen - Commands-Integration für Production erforderlich
