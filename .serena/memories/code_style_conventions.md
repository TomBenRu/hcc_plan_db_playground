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

## Qt/PySide6 Naming Conventions ⚠️
**KRITISCH: Namenskollisionen mit Qt-Methoden vermeiden**

- **NIEMALS Attributnamen verwenden, die Qt-Methodennamen entsprechen**
- **Besonders problematisch:** `event`, `show`, `close`, `update`, `resize`, `move`, `hide`
- **Grund:** Help-System und Reflection-basierte Tools interpretieren diese als Methoden
- **Lösung:** Beschreibende, eindeutige Namen verwenden

**Beispiele:**
```python
# ❌ SCHLECHT - Kollidiert mit QWidget-Methoden
class MyWidget(QWidget):
    def __init__(self):
        self.event = event_data        # Kollidiert mit QWidget.event()
        self.show = visibility_state   # Kollidiert mit QWidget.show()
        self.update = update_data      # Kollidiert mit QWidget.update()

# ✅ GUT - Eindeutige, beschreibende Namen
class MyWidget(QWidget):
    def __init__(self):
        self.event_of_day = event_data      # Klar und eindeutig
        self.show_details = visibility_state # Klar und eindeutig
        self.update_data = update_data      # Klar und eindeutig
```

**Häufige Qt-Methodennamen die zu vermeiden sind:**
- `event`, `show`, `hide`, `close`, `update`, `resize`, `move`
- `focus`, `paint`, `size`, `pos`, `rect`, `width`, `height`
- `parent`, `child`, `children`, `find`, `grab`

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