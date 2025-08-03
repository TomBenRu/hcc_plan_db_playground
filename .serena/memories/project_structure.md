# Projektstruktur hcc_plan_db_playground

## Hauptverzeichnisse

### `/gui/` - GUI Layer (PySide6)
- **`main_window.py`** - Hauptfenster der Anwendung
- **`frm_*.py`** - Formulare für spezifische Funktionen
- **`app.py`** - Anwendungsinitialisierung
- **`data_processing.py`** - GUI-Datenverarbeitung
- **`translations/`** - Mehrsprachige Unterstützung
- **`custom_widgets/`** - Benutzerdefinierte GUI-Komponenten
- **`resources/`** - GUI-Ressourcen (Icons, Styles, etc.)

### `/database/` - Datenebene
- **`models.py`** - Pony ORM Entitätsdefinitionen
- **`db_services.py`** - Datenbankoperationen und Services
- **`schemas.py`** - Pydantic-Schemas für Validierung
- **`database.sqlite`** - SQLite-Hauptdatenbank
- **`authentication.py`** - Benutzerauthentifizierung

### `/commands/` - Business Logic (Command Pattern)
- **`command_base_classes.py`** - Basis-Command-Implementierung
- **`database_commands/`** - Datenbankbezogene Commands
- **Undo/Redo-Funktionalität** über Command Pattern

### `/configuration/` - Konfigurationsmanagement
- **`config_handler.py`** - Zentrale Konfigurationsverwaltung
- **`project_paths.py`** - Pfadkonfiguration
- **`general_settings.py`** - Allgemeine Einstellungen
- **`google_calenders.py`** - Google Calendar Integration

### `/sat_solver/` - Optimierungsalgorithmen
- **OR-Tools Integration** für Constraint-basierte Planung
- **Komplexe Einsatzplanung** mit vielen Nebenbedingungen

### `/employee_event/` - Employee Event Management
- **Service Layer** für Event-Management
- **Repository Pattern** mit Pydantic-Integration
- **GUI-Module** für Event-Verwaltung

### `/employment_statistics/` - Statistik und Analytics
- **Dashboard-Komponenten** mit Chart.js/D3.js
- **Excel-Export-Funktionen**
- **Template-basierte Reports**

## Weitere wichtige Module

### `/google_calendar_api/` - Kalender-Integration
- Google Calendar API-Wrapper
- Terminverwaltung und Synchronisation

### `/export_to_file/` - Export-Funktionen
- Excel-Export für verschiedene Datentypen
- Template-basierte Export-Systeme

### `/tools/` - Hilfswerkzeuge
- Utility-Funktionen
- Helper-Module

### `/email_to_users/` - E-Mail-System
- SMTP-Integration mit Keyring
- Template-basierte E-Mails

## Entry Points
- **`main.py`** - Haupteinstiegspunkt
- **`gui/app.py`** - GUI-Anwendungsstart