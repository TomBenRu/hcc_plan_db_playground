# HANDOVER: Google Calendar API Integration für Employee-Events - Nächste Session

## AKTUELLER PROJEKTSTAND ✅
**Projekt**: `hcc_plan_db_playground` (Python/PySide6)
**Hauptdatei**: `gui/frm_create_google_calendar.py`
**Feature**: Google Calendar-Erstellung mit drei Tab-System

### VOLLSTÄNDIG ABGESCHLOSSEN:
✅ **Employee-Events Calendar Tab UI** ist vollständig implementiert und funktionsfähig
✅ **Team-spezifische vs. "No team" Logic** implementiert  
✅ **Person-Filter und E-Mail-Bearbeitung** funktioniert
✅ **Qt ItemDataRole-Bug** behoben
✅ **Automatische Kalender-Namensgebung** implementiert

## NÄCHSTE AUFGABE 🎯
**Google Calendar API Integration für Employee-Events-Kalender**

### ZIEL:
Employee-Events aus der Datenbank per Google Calendar API in die erstellten Employee-Events-Kalender übertragen.

### DESIGN-SPEZIFIKATION:
1. **Team-spezifische Kalender**: Employee-Events die bestimmten Teams zugeordnet sind
2. **"No team" Kalender**: Employee-Events ohne Team-Zuordnung (teams = empty set)

### TECHNISCHE ANFORDERUNGEN:

#### 1. Employee-Events Datenbank-Services
- **Models bereits vorhanden**: `EmployeeEvent`, `EmployeeEventCategory` in `database/models.py`
- **Benötigt**: Service-Klassen in `database/db_services.py` erweitern
- **Filter-Logic**: 
  - Team-spezifisch: `employee_event.teams.contains(team_id)`
  - "No team": `employee_event.teams.is_empty()`

#### 2. Google Calendar API Integration
- **Bestehende Integration**: `configuration/google_calenders.py` bereits vorhanden
- **Benötigt**: Employee-Events API calls parallel zu bestehenden Team/Person-Kalender calls
- **Event-Format**: Google Calendar Event-Objects für Employee-Events

#### 3. Backend-Integration  
- **Datei**: `gui/main_window.py` - Dialog-Integration erweitern
- **Bestehende Logic**: Team-Kalender und Person-Kalender bereits implementiert
- **Benötigt**: Employee-Events-Kalender case hinzufügen

### WICHTIGE DATEIEN FÜR NÄCHSTE SESSION:

#### Hauptdateien:
- `gui/frm_create_google_calendar.py` - UI bereits fertig ✅
- `gui/main_window.py` - Backend-Integration erweitern 
- `database/db_services.py` - Employee-Events Services hinzufügen
- `configuration/google_calenders.py` - API-Integration erweitern

#### Memory-Dateien zu lesen:
- `employee_events_calendar_ui_implementation_complete_august_2025` - Vollständige UI-Details
- `team_calendar_email_input_complete_august_2025` - Referenz-Implementation
- `code_style_conventions` - Projekt-Konventionen
- `string_formatierung_hinweis_wichtig` - Wichtiger String-Handling Hinweis

### KALENDER-DESCRIPTION FORMAT:
```json
// Team-spezifisch:
{"description": "Employee events - team", "team_id": "uuid"}

// Ohne Team:  
{"description": "Employee events - no team", "team_id": ""}
```

### EMPFOHLENER ANSATZ:
1. **Analysiere bestehende Team-Kalender API-Integration** als Referenz
2. **Erweitere db_services.py** um Employee-Events Services
3. **Implementiere Google Calendar API calls** für Employee-Events
4. **Integriere in main_window.py** Backend-Verbindung
5. **Teste End-to-End** Funktionalität

### ARCHITEKTUR-VORSICHT ⚠️
- **Keine eigenständigen Änderungen** an grundlegenden Komponenten ohne Absprache
- **Strukturelle Änderungen** vorher besprechen  
- **Schrittweise Implementation** bevorzugen
- **Serena für Coding-Aufgaben nutzen**

### USER-PRÄFERENZEN:
- Nutze **sequential-thinking** bei komplexeren Aufgaben
- Halte Rücksprache bei grundlegenden Änderungen
- Zerlege umfangreiche Aufgaben in kleinere Teilschritte

## STATUS: BEREIT FÜR GOOGLE CALENDAR API INTEGRATION
Das UI ist vollständig funktionsfähig. Der nächste Schritt ist die Backend-Integration für Employee-Events-Übertragung.

**WICHTIG**: Employee-Events Models und UI sind bereits vorhanden - fokussiere auf die API-Integration und Backend-Verbindung.
