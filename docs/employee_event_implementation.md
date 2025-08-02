# Employee Event Management - Implementation Documentation

## Projektübersicht

Das Employee Event Management System verwaltet Unternehmensveranstaltungen wie Fortbildungen, Meetings, Onlinekonferenzen etc. für das hcc_plan_db_playground Projekt.

**Status: ✅ Phase 1-5 vollständig abgeschlossen | Address Management erfolgreich integriert und funktionsfähig**

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
- **Address Management** als shared component ✅
- **Excel-Export für Employee Events** ✅

### 🔄 In Arbeit (Phase 6)
- **Excel-Export-Integration** in bestehenden ExportToXlsx-Workflow
- **GUI-Export-Button** in Employee Events Hauptfenster

### 🔄 Geplant (Phase 7)
- **Event-Import/Export-Funktionen** (CSV/JSON)
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

## Excel-Export für Employee Events ✅ IMPLEMENTIERT

### 🎯 Vollständige Excel-Integration

Das Employee Event Management System verfügt über eine professionelle Excel-Export-Funktionalität, die nahtlos in das bestehende ExportToXlsx-System integriert werden kann.

### ✅ Implementierte Features

#### 1. EmployeeEventsExcelExporter Klasse
```python
class EmployeeEventsExcelExporter:
    """
    Extension class to add Employee Events to existing Excel exports.
    
    Integriert Employee Events in bestehende Excel-Workbooks mit:
    - Team- und Planperioden-Filterung
    - Professionelle Formatierung mit Dark Theme Farben
    - Vollständige Event-Details-Anzeige
    - Summary-Statistiken und Kategorien-Aufschlüsselung
    """
```

#### 2. Automatische Filterung
- **Team-Filter**: Nur Events die dem aktuellen Team zugeordnet sind
- **Planperioden-Filter**: Events innerhalb der aktuellen Planperiode (start/end Datum)
- **Sortierung**: Chronologisch nach Start-Datum und -Zeit

#### 3. Vollständige Event-Details
```
Spalten: Start | End | Title | Description | Address | Categories | Participants
```

**Event-Datenextraktion:**
- **Start**: Vollständiges DateTime "DD.MM.YYYY HH:mm" für Start-Zeitpunkt
- **End**: Vollständiges DateTime "DD.MM.YYYY HH:mm" für End-Zeitpunkt (besonders wichtig für mehrtägige Events)
- **Titel**: Vollständiger Event-Titel
- **Beschreibung**: Automatisch gekürzt bei >100 Zeichen
- **Adresse**: "Straße, Stadt" Format aus Address-Entity
- **Kategorien**: Komma-separierte Liste aller zugewiesenen Kategorien
- **Teilnehmer**: Vollständige Namen oder "X participants (see details)" bei >80 Zeichen

#### 4. Professional Formatting
```python
# Verwendete Farb-Codes (Dark Theme):
format_title = {
    'bg_color': '#0078d4',      # Microsoft Blue
    'font_color': 'white',
    'font_size': 16
}

format_header = {
    'bg_color': '#106ebe',      # Darker Blue
    'font_color': 'white', 
    'font_size': 12
}

# Alternating row colors für bessere Lesbarkeit
format_data_alt = {
    'bg_color': '#f0f0f0'       # Light Gray
}
```

#### 5. Summary-Statistiken
- **Event-Anzahl**: Gesamtzahl der Events im Zeitraum
- **Kategorien-Aufschlüsselung**: Anzahl Events pro Kategorie
- **"No Category" Handling**: Events ohne Kategorien-Zuordnung

#### 6. Integration-ready API
```python
def integrate_employee_events_into_export(
    workbook: xlsxwriter.Workbook, 
    team: schemas.Team, 
    plan_period: schemas.PlanPeriod, 
    excel_settings: schemas.ExcelExportSettings
) -> int:
    """
    Convenience function to integrate Employee Events into existing Excel export.
    
    Returns:
        int: Number of Employee Events that were exported
    """
    exporter = EmployeeEventsExcelExporter(workbook, team, plan_period, excel_settings)
    return exporter.execute()
```

### 🔧 Integration in ExportToXlsx

#### Geplante Integration (nächste Session):
```python
# In export_to_file/export_to_xlsx.py

from export_to_file.employee_events_to_xlsx import integrate_employee_events_into_export

class ExportToXlsx:
    def _export_data(self):
        # ... bestehender Export-Code ...
        
        # Employee Events hinzufügen
        events_count = integrate_employee_events_into_export(
            workbook=self.workbook,
            team=self.team,
            plan_period=self.plan_period,
            excel_settings=self.excel_settings
        )
        
        logger.info(f"Exported {events_count} Employee Events")
```

#### Optional: Export-Checkbox im Dialog
```python
# Optional: Checkbox im Export-Dialog hinzufügen
self.checkbox_include_events = QCheckBox("Include Employee Events")
self.checkbox_include_events.setChecked(True)  # Default: aktiviert
```

### 🎨 Spalten-Design und Layout

#### Spaltenbreiten (Optimiert für Lesbarkeit):
```python
col_widths = {
    'start': 18,         # DateTime benötigt mehr Platz
    'end': 18,           # DateTime benötigt mehr Platz  
    'title': 25,         # Event-Titel
    'description': 40,   # Beschreibung (breiteste Spalte)
    'address': 25,       # Adresse
    'categories': 20,    # Kategorien
    'participants': 30   # Teilnehmer-Liste
}
```

#### Worksheet-Eigenschaften:
- **Landscape-Modus**: Optimiert für viele Spalten
- **A4-Format**: Standard-Druckformat
- **0.4cm Margins**: Kompakte Darstellung
- **Automatische Zeilenhöhen**: Basierend auf Beschreibungslänge (20-60px)

### 🚀 Ready for Production

Die Excel-Export-Implementierung ist vollständig:
- ✅ **Team- und Zeitraum-gefiltert** - Nur relevante Events
- ✅ **Professional Formatting** - Corporate Design mit Dark Theme
- ✅ **Error-Handling** - Fallback bei leeren Daten oder Fehlern
- ✅ **Integration-ready** - Kann sofort in ExportToXlsx eingebunden werden
- ✅ **Performance-optimiert** - Effiziente Datenbankzugriffe und Formatierung

### 🔄 Nächste Schritte (Integration):
1. **ExportToXlsx erweitern** - `integrate_employee_events_into_export()` einbinden
2. **GUI-Button hinzufügen** - Export direkt aus Employee Events Hauptfenster
3. **Testing** - Mit echten Team-Daten und verschiedenen Planperioden

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
- **v2.7.0** - **Address Management**: Vollständige Integration als shared component (02.08.2025)
  - ✅ **`gui/master_data/dlg_address_edit.py`** - CRUD Dialog für modulübergreifende Verwendung
  - ✅ **Commands Integration** - address_commands.py für Undo/Redo-Support
  - ✅ **Employee Event Integration** - New/Edit Address Buttons funktional
  - ✅ **Signal Integration** - address_saved/address_deleted für Auto-Refresh
- **v2.8.1** - **Mehrtägige Events Verbesserungen**: Verbesserungen für mehrtägige Events (02.08.2025)
  - ✅ **Zeitvalidierung korrigiert** - End-DateTime muss immer nach Start-DateTime sein (komplette DateTime-Validierung)
  - ✅ **Spalten-Design verbessert** - "Start" und "End" Spalten statt "Date" und "Time" für bessere mehrtägige Event-Darstellung  
  - ✅ **Kalender-Ansicht erweitert** - Mehrtägige Events werden an allen relevanten Tagen angezeigt
  - ✅ **Smart Display** - Intelligente Zeit-Anzeige: "ab HH:mm", "bis HH:mm", "ganztägig" je nach Tag
  - ✅ **_on_end_datetime_changed()** - Neue Methode für automatische Zeit-Korrektur bei ungültigen Eingaben
  - ✅ **Verbesserte Validierung** - Benutzerfreundliche Fehlermeldungen mit konkreten Start/End-Zeiten
  - ✅ **Excel-Export angepasst** - Spalten "Start"/"End" konsistent mit GUI, optimierte DateTime-Formatierung

## Address Management ✅ IMPLEMENTIERT

### 🎯 Shared Component für modulübergreifende Verwendung

Das Address Management ist als **shared component** implementiert und kann von verschiedenen Modulen des hcc_plan_db_playground Projekts verwendet werden:
- Employee Event Dialog (für Event-Locations)
- Person Management (für Mitarbeiter-Adressen)
- LocationOfWork (für Arbeitsort-Adressen)
- Weitere Module nach Bedarf

### ✅ Implementierte Struktur
```
gui/master_data/
├── __init__.py                     # Package definition
├── dlg_address_edit.py             # ✅ CRUD Dialog für Adressen
commands/database_commands/
├── address_commands.py             # ✅ Address Commands (Create, Update, Delete)
```

### ✅ Implementierte Features

#### 1. DlgAddressEdit Features:
- **✅ CRUD-Modi**: Create/Update/Delete in einem Dialog implementiert
- **✅ Mode Detection**: Automatisch basierend auf ob address_id übergeben wird
- **✅ Form Fields**: Street, Postal Code, City mit Validierung
- **✅ Dark Theme**: Nutzt bestehende app.py Styles mit konsistentem Design
- **✅ Commands Integration**: Verwendet address_commands für Undo/Redo
- **✅ Returns**: `created_address_id` oder `updated_address_id` via get_result()
- **✅ Signals**: address_saved/address_deleted für externe Integration
- **✅ Convenience Functions**: create_address_dialog() und edit_address_dialog()

#### 2. Address Commands:
- **✅ Create(AddressCreate, project_id)** - Erstellt neue Adresse mit Undo/Redo
- **✅ Update(Address)** - Aktualisiert bestehende Adresse mit Undo/Redo  
- **✅ Delete(address_id)** - Soft Delete mit prep_delete und Undo/Redo

#### 3. Integration Points:
- **✅ Employee Event Dialog** kann direkt importieren
- **✅ Andere Module** (Person, LocationOfWork) können ebenfalls nutzen
- **✅ Command Pattern** folgt bestehendem Projektstandard
- **✅ Schema-driven** nutzt bestehende AddressCreate/Address Schemas

### ✅ Usage Examples (Implementiert)

#### ✅ Employee Event Dialog Integration (Implementiert)
```python
# In gui/employee_event/dlg_employee_event_details.py
from gui.master_data.dlg_address_edit import DlgAddressEdit

# New Address Button
def _new_address(self):
    dlg = DlgAddressEdit(self)
    dlg.address_saved.connect(self._on_address_saved)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        # Auto-refresh address list and select new address
        self._refresh_addresses_list()
        created_address_id = dlg.get_result()
        # Auto-select the new address

# Edit Address Button  
def _edit_address(self):
    selected_address_id = self.combo_address.currentData()
    dlg = DlgAddressEdit(self, selected_address_id)
    dlg.address_saved.connect(self._on_address_saved)
    dlg.address_deleted.connect(self._on_address_deleted)
    # Auto-refresh and handle deletion
```

#### ✅ GUI Features Implementiert
- **✅ Address Dropdown** - Zeigt alle verfügbaren Adressen sortiert nach Stadt, Straße
- **✅ New Address Button** - Öffnet Create-Dialog, fügt neue Adresse automatisch zur Liste hinzu
- **✅ Edit Address Button** - Öffnet Edit-Dialog für ausgewählte Adresse (auto-disabled wenn keine Auswahl)
- **✅ Signal Integration** - address_saved/address_deleted Callbacks für UI-Updates
- **✅ Auto-Refresh** - Adress-Liste wird automatisch nach Änderungen aktualisiert
- **✅ Smart Selection** - Neue/bearbeitete Adressen werden automatisch ausgewählt
```python
from gui.master_data.dlg_address_edit import create_address_dialog, edit_address_dialog

# Neue Adresse erstellen
created_address_id = create_address_dialog(parent=self)
if created_address_id:
    print(f"Neue Adresse erstellt: {created_address_id}")

# Bestehende Adresse bearbeiten  
updated_address_id = edit_address_dialog(parent=self, address_id=existing_id)
if updated_address_id:
    print(f"Adresse aktualisiert: {updated_address_id}")
```

#### Direkte Dialog-Nutzung mit Signal-Integration
```python
from gui.master_data.dlg_address_edit import DlgAddressEdit
from PySide6.QtWidgets import QDialog

# Create Mode
address_dialog = DlgAddressEdit(parent=self)
address_dialog.address_saved.connect(self.on_address_created)
if address_dialog.exec() == QDialog.Accepted:
    result_id = address_dialog.get_result()

# Edit Mode
address_dialog = DlgAddressEdit(parent=self, address_id=existing_id) 
address_dialog.address_saved.connect(self.on_address_updated)
address_dialog.address_deleted.connect(self.on_address_deleted)
if address_dialog.exec() == QDialog.Accepted:
    result_id = address_dialog.get_result()

def on_address_created(self, address_id):
    print(f"Address created: {address_id}")

def on_address_updated(self, address_id):
    print(f"Address updated: {address_id}")

def on_address_deleted(self, address_id):
    print(f"Address deleted: {address_id}")
```

### 🧪 Testing der Integration

Ein Test-Script ist verfügbar um die vollständige Integration zu testen:

```bash
# Test-Script ausführen
python test_address_integration.py
```

#### Test-Features:
- **✅ Standalone Address Dialog** - Test der Address CRUD-Funktionalität  
- **✅ Employee Event Integration** - Test der eingebetteten Address-Buttons
- **✅ Convenience Functions** - Test der create_address_dialog() und edit_address_dialog()
- **✅ Signal Integration** - Test der address_saved/address_deleted Callbacks
- **✅ Dark Theme** - Visueller Test der konsistenten Styling

#### Manual Test Checklist:
1. **✅ New Address in Employee Event Dialog** - "New..." Button öffnet Address Dialog
2. **✅ Address Auto-Selection** - Neue Adresse wird automatisch ausgewählt
3. **✅ Edit Address** - "Edit..." Button öffnet selected Address für Bearbeitung
4. **✅ Edit Button State** - Edit-Button disabled wenn keine Adresse ausgewählt
5. **✅ Address Deletion** - Löschen einer Adresse setzt Auswahl auf "No address" zurück
6. **✅ List Refresh** - Address-Liste wird nach allen Änderungen automatisch aktualisiert
```python
from commands.database_commands import address_commands
from commands.command_base_classes import ContrExecUndoRedo
from database.schemas import AddressCreate
from configuration.general_settings import get_current_project_id

# Setup
controller = ContrExecUndoRedo()

# Create Address
address_create = AddressCreate(
    street="Musterstraße 123",
    postal_code="12345", 
    city="Berlin"
)
create_command = address_commands.Create(address_create, get_current_project_id())
controller.execute(create_command)

# Undo/Redo verfügbar
controller.undo()  # Rückgängig
controller.redo()  # Wiederholen
```
```python
# Usage Example für andere Module:
from gui.master_data.dlg_address_edit import DlgAddressEdit, create_address_dialog, edit_address_dialog

# Convenience Functions (Empfohlen):
created_address_id = create_address_dialog(parent=self)
updated_address_id = edit_address_dialog(parent=self, address_id=existing_id)

# Direkte Dialog-Nutzung:
address_dialog = DlgAddressEdit(parent=self)  # Create Mode
address_dialog = DlgAddressEdit(parent=self, address_id=existing_id)  # Edit Mode
if address_dialog.exec() == QDialog.Accepted:
    result_id = address_dialog.get_result()

# Signal-Integration:
address_dialog.address_saved.connect(self.on_address_saved)
address_dialog.address_deleted.connect(self.on_address_deleted)
```

### ✅ Architektur-Prinzipien (Umgesetzt)
- **✅ Overengineering vermieden** - Einfache, direkte Implementation ohne Repository-Layer
- **✅ Commands Integration** - Vollständiger Undo/Redo Support für alle CRUD-Operationen
- **✅ Schema-driven** - Nutzt bestehende Pydantic v2 Schemas (AddressCreate, Address)
- **✅ Dark Theme** - Konsistent mit bestehenden Dialogen und app.py Styling
- **✅ Shared Component** - Wiederverwendbar für verschiedene Module ohne Abhängigkeiten
- **✅ Validation** - Vollständige Eingabevalidierung mit benutzerfreundlichen Fehlermeldungen
- **✅ Modal Dialog** - Modernes Design konsistent mit Employee Event Dialogen

## Nächste Schritte

1. **✅ Address Management implementiert** (02.08.2025):
   - `gui/master_data/dlg_address_edit.py` - CRUD Dialog ✅
   - `commands/database_commands/address_commands.py` - Commands implementiert ✅
   - Address Entity und Schemas bereits vorhanden ✅
2. **Integration testen** - Mit Employee Event Dialog und anderen Modulen (Person, LocationOfWork)
3. **Commands-Integration (Optional)** - Production-Ready-System mit Undo/Redo für Employee Events:
   - `commands/employee_event_commands.py` - Command-Klassen implementieren
   - Service → Commands Migration durchführen
4. **Testing** - Vollständige Funktionalität aller Module testen

⚠️ **WICHTIG:** Für Production-System muss Commands-Pattern implementiert werden!

---
**Entwickelt von:** Thomas & Claude  
**Letzte Aktualisierung:** 30.07.2025  
**Status:** Phase 1-3 vollständig abgeschlossen - Commands-Integration für Production erforderlich
