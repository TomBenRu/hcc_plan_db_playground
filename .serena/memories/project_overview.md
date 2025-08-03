# hcc_plan_db_playground - Projekt Übersicht

## Projektpurpose
**Automatisierte Einsatzplanung für freiberufliche Mitarbeiter** - Eine umfassende Planungssoftware für mittelständische Unternehmen zur optimalen Zuordnung von Mitarbeitern zu Arbeitseinsätzen an verschiedenen Standorten.

## Hauptfunktionen
- **Automatische Einsatzplanung** mit OR-Tools Constraint-Optimierung
- **GUI-basierte Anwendung** mit PySide6
- **Komplexe Datenbank-Architektur** mit Pony ORM
- **Google Calendar Integration** für Terminverwaltung
- **Excel Export/Import** für Pläne und Verfügbarkeiten
- **Benutzerauthentifizierung** mit JWT und bcrypt
- **Mehrsprachige Unterstützung** (Deutsch/Englisch) mit Qt Translator
- **Command Pattern** für Undo/Redo-Funktionalität

## Tech Stack
- **Python 3.12+** als Hauptsprache
- **PySide6** - GUI Framework (Qt-basiert)
- **Pony ORM** - Datenbankzugriff und O/R-Mapping
- **OR-Tools** - Google's Optimierungsalgorithmen für Constraint-Solving
- **Google APIs** - Kalenderintegration
- **Pandas** - Datenverarbeitung und -analyse
- **Pydantic** - Datenvalidierung und Schema-Definition
- **Jinja2** - Template-Engine für Reports
- **XlsxWriter/OpenPyXL** - Excel-Integration

## Zielgruppe
Mittelständische Unternehmen mit freiberuflichen Mitarbeitern, die komplexe Einsatzplanung mit vielen Constraints (Verfügbarkeiten, Qualifikationen, Standort-Präferenzen, etc.) benötigen.