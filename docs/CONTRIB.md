# Contributing Guide - HCC Plan

Diese Dokumentation beschreibt den Entwicklungs-Workflow für das HCC Plan Projekt.

**Letzte Aktualisierung:** 2026-01-24
**Generiert aus:** requirements.txt, .env.example, Projektstruktur

---

## Inhaltsverzeichnis

1. [Environment Setup](#environment-setup)
2. [Abhängigkeiten](#abhängigkeiten)
3. [Environment-Variablen](#environment-variablen)
4. [Verfügbare Scripts](#verfügbare-scripts)
5. [Entwicklungs-Workflow](#entwicklungs-workflow)
6. [Testing](#testing)
7. [Docker-Entwicklung](#docker-entwicklung)

---

## Environment Setup

### Voraussetzungen

- **Python 3.12+** (empfohlen)
- **uv** oder **pip** für Dependency-Management
- **Docker** (für Multi-User-Setup)
- **Git** für Versionskontrolle

### Installation

```bash
# 1. Repository klonen
git clone <repository-url>
cd hcc_plan_db_playground

# 2. Virtuelle Umgebung mit uv
uv sync

# 3. Oder mit pip
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
pip install -r requirements.txt

# 4. Anwendung starten
python main.py
```

---

## Abhängigkeiten

### Core Dependencies (requirements.txt)

| Package | Version | Beschreibung |
|---------|---------|--------------|
| `pony` | ~=0.7.17 | ORM für Datenbankzugriff |
| `pydantic[email]` | ~=2.9 | Datenvalidierung mit Email-Support |
| `pyside6` | ~=6.8 | GUI Framework (Qt6) |
| `bcrypt` | ~=5.0 | Passwort-Hashing |
| `sympy` | ~=1.12 | Symbolische Mathematik |
| `icecream` | ~=2.1.3 | Debug-Printing |
| `python-dateutil` | ~=2.8 | Erweiterte Datum-Operationen |
| `ortools` | ~=9.12 | Optimierungs-Solver |
| `anytree` | ~=2.10 | Baumstruktur-Datentypen |
| `line-profiler-pycharm` | ~=1.2.0 | Performance-Profiling |
| `toml` | ~=0.10.2 | TOML-Konfigurationsdateien |
| `requests` | ~=2.32.3 | HTTP-Client |
| `PyJWT` | ~=2.10 | JWT-Token-Handling |
| `pydantic_core` | ~=2.21 | Pydantic Core-Bibliothek |
| `future` | ~=1.0.0 | Python 2/3 Kompatibilität |
| `XlsxWriter` | ~=3.2.0 | Excel-Dateien schreiben |
| `pytz` | ~=2025.1 | Zeitzonen-Unterstützung |
| `google-auth` | latest | Google API Authentifizierung |
| `google-auth-oauthlib` | latest | OAuth für Google APIs |
| `google-auth-httplib2` | latest | HTTP-Transport für Google Auth |
| `google-api-python-client` | latest | Google API Client |
| `httplib2` | ~=0.22.0 | HTTP-Client-Bibliothek |
| `urllib3` | ~=2.2 | HTTP-Bibliothek |
| `keyring` | ~=25.5 | Sichere Credential-Speicherung |
| `keyrings.alt` | ~=5.0 | Alternative Keyring-Backends |
| `pandas` | ~=2.2 | Datenanalyse |
| `openpyxl` | ~=3.0 | Excel-Dateien lesen |

---

## Environment-Variablen

### Konfiguration (.env.example)

Kopiere `.env.example` zu `.env` und passe die Werte an:

```bash
cp .env.example .env
```

#### Database Configuration

| Variable | Beispiel | Beschreibung |
|----------|----------|--------------|
| `POSTGRES_DB` | `hcc_plan_db` | Name der PostgreSQL-Datenbank |
| `POSTGRES_USER` | `hcc_user` | Datenbank-Benutzer |
| `POSTGRES_PASSWORD` | `change_this...` | **Ändern!** Sicheres Passwort |
| `POSTGRES_PORT` | `5432` | PostgreSQL-Port |
| `DATABASE_URL` | `postgresql://...` | Vollständige DB-URL |

#### Guacamole Configuration (Multi-User)

| Variable | Beispiel | Beschreibung |
|----------|----------|--------------|
| `GUACAMOLE_SECRET_KEY` | `4c0b569e...` | **Generieren!** `openssl rand -hex 32` |
| `GUACAMOLE_PORT` | `8080` | Web-Interface Port |
| `GUACAMOLE_SESSION_TIMEOUT` | `240` | Session-Timeout in Minuten |

#### Auth Service Configuration

| Variable | Beispiel | Beschreibung |
|----------|----------|--------------|
| `AUTH_SERVICE_PORT` | `8001` | Port des Auth-Services |
| `AUTH_SERVICE_HOST` | `0.0.0.0` | Bind-Adresse |

#### Logging & Debugging

| Variable | Beispiel | Beschreibung |
|----------|----------|--------------|
| `GUACD_LOG_LEVEL` | `info` | Guacamole-Daemon Log Level (debug/info/warn/error) |
| `PYTHON_LOG_LEVEL` | `INFO` | Python-Logging Level |

#### Session Management

| Variable | Beispiel | Beschreibung |
|----------|----------|--------------|
| `MAX_CONCURRENT_SESSIONS` | `3` | Max. gleichzeitige User-Sessions |
| `SESSION_TIMEOUT_HOURS` | `4` | Session-Timeout in Stunden |
| `VNC_BASE_PORT` | `5900` | Basis-Port für VNC |
| `DISPLAY_BASE_NUMBER` | `10` | Basis-Display-Nummer |

#### Development Settings

| Variable | Beispiel | Beschreibung |
|----------|----------|--------------|
| `ENVIRONMENT` | `production` | `development` für erweiterte Logs |
| `ENABLE_SESSION_RECORDING` | `true` | Session-Aufzeichnung aktivieren |
| `ENABLE_BRUTE_FORCE_PROTECTION` | `true` | Brute-Force-Schutz aktivieren |

---

## Verfügbare Scripts

### Windows Batch-Scripts

| Script | Beschreibung |
|--------|--------------|
| `start-hcc-direct-gui.bat` | Startet HCC Plan Direct GUI (optimiert, ohne Desktop) |
| `stop-hcc-direct-gui.bat` | Stoppt Direct GUI Container |
| `status-hcc-direct-gui.bat` | Zeigt Container-Status |
| `start-hcc-dynamic-multi-user.bat` | Startet Multi-User-Setup |
| `stop-hcc-dynamic-multi-user.bat` | Stoppt Multi-User-Setup |
| `start-simple.bat` | Einfacher Start ohne Docker |

### Python-Befehle

```bash
# Anwendung starten
python main.py

# Tests ausführen
pytest

# Tests mit Coverage
pytest --cov=. --cov-report=html

# Profiling (line-profiler)
kernprof -l -v main.py
```

---

## Entwicklungs-Workflow

### Branch-Strategie

- `master` - Stabiler Produktions-Branch
- `feature/*` - Feature-Entwicklung
- `bugfix/*` - Bug-Fixes

### Commit-Konventionen

```bash
# Feature hinzufügen
git commit -m "Add: Neue Funktion XYZ"

# Bug-Fix
git commit -m "Fix: Problem mit ABC behoben"

# Refactoring
git commit -m "Refactor: Code-Struktur verbessert"
```

### Code-Architektur

Das Projekt verwendet ein **Command-Pattern** für schreibende DB-Operationen:

```python
# Beispiel: Command für Undo/Redo
from commands.database_commands import event_commands

command = event_commands.CreateEventCommand(...)
result = command_manager.execute(command)
command_manager.undo()  # Rückgängig
command_manager.redo()  # Wiederholen
```

---

## Testing

### Test-Ausführung

```bash
# Alle Tests
pytest

# Bestimmte Tests
pytest tests/test_solver_integration.py

# Mit Verbose-Output
pytest -v

# Nur fehlgeschlagene Tests
pytest --lf
```

### Test-Struktur

```
tests/
├── conftest.py              # Test-Fixtures
├── test_help_system.py      # Help-System Tests
├── test_qcombobox_find_data.py
├── test_solver_integration.py
└── unit/
    └── test_workload_calculator.py
```

---

## Docker-Entwicklung

### Direct GUI (Empfohlen für Entwicklung)

```bash
# Starten
docker-compose -f docker-compose-DIRECT.yml up --build -d

# Status prüfen
docker-compose -f docker-compose-DIRECT.yml ps

# Logs
docker-compose -f docker-compose-DIRECT.yml logs -f

# Stoppen
docker-compose -f docker-compose-DIRECT.yml down
```

**Zugang:** http://localhost:8081/guacamole/
**Login:** anna / test123

### Performance-Vorteile Direct GUI

| Metrik | Desktop-Version | Direct GUI |
|--------|----------------|------------|
| Memory | ~350MB | ~155MB (**55% Reduktion**) |
| Startup | 30-45s | 10-15s |
| UI | Desktop-Umgebung | Clean GUI |

### Ports-Übersicht

| Port | Service | Beschreibung |
|------|---------|--------------|
| 8080 | Guacamole | Standard Web-Interface |
| 8081 | Guacamole-Direct | Direct GUI Web-Interface |
| 5901 | VNC | Standard VNC-Zugang |
| 5902 | VNC-Direct | Direct GUI VNC-Zugang |

---

## Projektstruktur

```
hcc_plan_db_playground/
├── gui/                     # GUI-Module (PySide6)
│   ├── main_window.py       # Hauptfenster
│   ├── frm_*.py            # Formulare
│   ├── custom_widgets/      # Wiederverwendbare Widgets
│   └── data_models/         # GUI-Datenmodelle
├── database/                # Datenbank-Layer
│   ├── models.py           # Pony ORM Modelle
│   └── db_services.py      # DB-Operationen
├── commands/                # Command-Pattern für Undo/Redo
│   └── database_commands/   # DB-spezifische Commands
├── sat_solver/              # OR-Tools Optimierung
│   └── constraints/         # Constraint-Definitionen
├── configuration/           # Konfiguration
├── google_calendar_api/     # Google Calendar Integration
├── export_to_file/          # Excel-Export
├── help/                    # Integriertes Hilfesystem
├── tools/                   # Utilities
└── tests/                   # Test-Suite
```

---

## Support

- **Issues:** GitHub Issues
- **Lizenz:** EULA (siehe EULA.rtf)
- **Kontakt:** happy code company
