# hcc_plan_db_playground

Planungssoftware, um Freiberufliche Mitarbeiter eines Mittelständigen Unternehmens zu Arbeitseinsätzen an verschiedenen Einsatzorten einzuplanen.
Die Einsatzplanung kann auf Basis von vielen Vorgaben zu Einsatzbereichen und Wünschen und Fähigkeiten der Mitarbeiter automatisch durchgeführt werden.
Ziel ist es, einen Einsatzplan über einen festgelegten Planungszeitraum automatisch zu generieren, der allen zuvor festgelegten Vorgaben gerecht wird.

## Features

- **Automatische Einsatzplanung** mit OR-Tools Optimierung
- **GUI-basierte Anwendung** mit PySide6
- **Datenbankintegration** mit Pony ORM
- **Google Calendar Integration** für Terminverwaltung
- **Excel Export/Import** für Pläne und Verfügbarkeiten
- **Benutzerauthentifizierung** mit JWT und bcrypt
- **Mehrsprachige Unterstützung** (Deutsch/Englisch)
- **Integriertes Hilfe-System** mit F1-Shortcuts und Browser-basierter Hilfe

## Technologien

- **Python 3.12+**
- **PySide6** - GUI Framework
- **Pony ORM** - Datenbankzugriff
- **OR-Tools** - Optimierungsalgorithmen
- **Google APIs** - Kalenderintegration
- **Pandas** - Datenverarbeitung
- **Pydantic** - Datenvalidierung

## Installation

1. Repository klonen:
```bash
git clone <repository-url>
cd hcc_plan_db_playground
```

2. Abhängigkeiten installieren:
```bash
uv sync
```

3. Anwendung starten:
```bash
python -m gui.main_window
```

## Projektstruktur

```
├── gui/                     # GUI-Module mit PySide6
│   ├── main_window.py      # Hauptfenster
│   ├── frm_plan.py         # Planungsformulare
│   └── translations/       # Übersetzungen
├── database/               # Datenbankmodelle und Services
│   ├── db_services.py      # Datenbankoperationen
│   └── schemas.py          # Pony ORM Modelle
├── commands/               # Geschäftslogik-Commands
│   ├── plan_commands.py    # Planungsbefehle
│   └── team_commands.py    # Team-Management
├── google_calendar_api/    # Google Calendar Integration
├── export_to_file/         # Excel Export-Funktionen
├── tools/                  # Hilfswerkzeuge
└── configuration/          # Konfigurationsdateien
```

## Verwendung

1. **Projekt erstellen**: Neues Planungsprojekt über das GUI anlegen
2. **Team konfigurieren**: Mitarbeiter und deren Fähigkeiten definieren
3. **Einsatzorte einrichten**: Standorte und Anforderungen festlegen
4. **Planungszeitraum**: Zeitraum für die automatische Planung bestimmen
5. **Optimierung starten**: Automatische Einsatzplanung durchführen
6. **Export**: Ergebnisse nach Excel oder Google Calendar exportieren

## Entwicklung

Tests ausführen:
```bash
pytest
```

Profiling aktivieren:
```bash
# line-profiler-pycharm ist als Dev-Dependency verfügbar
```

Executable erstellen:
```bash
# auto-py-to-exe ist verfügbar für Standalone-Builds
```

## Lizenz

Diese Software unterliegt einer **Endbenutzer-Lizenzvereinbarung (EULA)** der **happy code company**.

### Wichtige Lizenzbestimmungen:

- **6 Wochen Testversion**: Kostenlose Nutzung für 6 Wochen als Try-Out-Version
- **Jährliche Lizenz erforderlich**: Nach der Testphase ist eine kostenpflichtige Jahreslizenz notwendig
- **Online-Dienst inklusive**: Die Jahreslizenz beinhaltet Zugang zum Online-Planungsdienst
- **Nicht übertragbar**: Die Lizenz ist an das Gerät/den Nutzer gebunden

Die vollständige Lizenzvereinbarung finden Sie in der Datei `EULA.rtf`.

**Kontakt für Lizenzfragen**: happy code company

---

*Hinweis: Mit der Installation und Nutzung der Software stimmen Sie den Bedingungen der EULA zu.*
