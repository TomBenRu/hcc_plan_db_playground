# Wichtige Kommandos für hcc_plan_db_playground

## Projekt-Setup und Dependencies
```bash
# Abhängigkeiten installieren (UV Package Manager)
uv sync

# Development-Dependencies installieren
uv sync --dev

# Neue Dependency hinzufügen
uv add <package_name>

# Dev-Dependency hinzufügen
uv add --dev <package_name>
```

## Anwendung starten
```bash
# Hauptanwendung starten
python main.py

# Alternative: GUI direkt starten
python -m gui.main_window

# Mit UV (empfohlen)
uv run python main.py
```

## Testing und Qualität
```bash
# Tests ausführen
pytest

# Tests mit UV
uv run pytest

# MyPy Type-Checking
mypy .

# MyPy mit UV
uv run mypy .
```

## Development Tools
```bash
# Profiling (Line Profiler für PyCharm verfügbar)
# line-profiler-pycharm ist als Dev-Dependency installiert

# Executable erstellen
# auto-py-to-exe ist verfügbar - GUI-Tool für PyInstaller
uv run auto-py-to-exe
```

## Datenbank-Management
```bash
# Datenbankmigrationen (falls nötig) - Pony ORM Auto-Schema
# Läuft automatisch beim ersten Start der Anwendung

# Backup der SQLite-Datenbank
copy "database\\database.sqlite" "database\\database_backup.sqlite"
```

## Qt-Übersetzungen
```bash
# .ts-Dateien aktualisieren (falls pylupdate verfügbar)
# Wird über das GUI-System verwaltet

# Translation-Tools verfügbar in translation_tools.py
python translation_tools.py
```

## Windows-spezifische Kommandos
```bash
# Verzeichnis auflisten
dir

# Datei suchen
dir /s <filename>

# Prozesse anzeigen
tasklist

# Git-Operationen
git status
git add .
git commit -m "message"
git push
```

## PyInstaller / Executable
```bash
# Auto-py-to-exe GUI (empfohlen)
uv run auto-py-to-exe

# Direkter PyInstaller-Aufruf (komplex wegen vieler Dependencies)
# Konfiguration in auto_py_to_exe_conf.json gespeichert
```