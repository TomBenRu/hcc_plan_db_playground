# Code Style und Konventionen

## Programmiersprache
- **Python 3.12+** mit modernen Features
- **Type Hints** durchgehend verwendet (Pydantic, typing)
- **Deutsch als Kommentarsprache** - Kommentare und Docstrings in deutscher Sprache

## Namenskonventionen
- **snake_case** für Funktionen, Variablen und Module
- **PascalCase** für Klassen
- **Deutsche Methodennamen** - z.B. `frm_calculate_plan.py`, `execute_shell_command`
- **Beschreibende Dateinamen** - z.B. `frm_actor_plan_period.py`, `employee_events_commands.py`

## Architektur-Patterns
- **Command Pattern** - Alle schreibenden Operationen als Commands mit Undo/Redo
- **MVC/MVP Pattern** - Trennung von GUI, Business Logic und Datenebene
- **Service Layer Pattern** - Geschäftslogik in separaten Service-Klassen
- **Repository Pattern** - Für Datenbankzugriff (teilweise)

## GUI-Konventionen
- **PySide6** als GUI-Framework
- **Form-basierte Architektur** - `frm_*.py` für Hauptformulare
- **Custom Widgets** in `gui/custom_widgets/`
- **Modularisierte GUI** - Separate Ordner für verschiedene Funktionsbereiche
- **Qt Translations** für Mehrsprachigkeit mit `.ts`-Dateien

## Datenbank-Patterns
- **Pony ORM** als primäres ORM
- **Pydantic Schemas** für API-Contracts und Validierung
- **db_services.py** für strukturierte Datenbankoperationen
- **models.py** für Entitätsdefinitionen

## Code-Organisation
- **Package-basierte Struktur** mit klar definierten Modulen
- **Separate Ordner** für GUI, Database, Commands, Configuration
- **Business Logic in Commands** - Command Pattern für alle schreibenden Operationen
- **Configuration Management** - Zentrale Konfiguration in `configuration/`