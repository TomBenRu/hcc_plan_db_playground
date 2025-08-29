# Employee-Events Google Calendar API Integration - IMPLEMENTIERUNGS-SPEZIFIKATION

## PROJEKT KONTEXT
**Projekt**: `hcc_plan_db_playground` (Python/PySide6)
**Feature**: Employee-Events aus Datenbank per Google Calendar API übertragen
**UI**: Vollständig implementiert in `gui/frm_create_google_calendar.py`

---

## 1. DATABASE SERVICES ERWEITERUNGEN

### 1.1 Neue Service-Klasse: EmployeeEvent
**Datei**: `database/db_services.py`

```python
class EmployeeEvent:
    @classmethod
    @db_session(sql_debug=LOGGING_ENABLED, show_values=LOGGING_ENABLED)
    def get_all_from_project_by_team(cls, project_id: UUID, team_id: UUID | None, 
                                   last_modified: datetime.datetime | None = None) -> list[EventDetail]:
        """
        Holt Employee-Events eines Projekts gefiltert nach Team und letzter Änderung
        
        Args:
            project_id: UUID des Projekts
            team_id: None für "no team" Events, UUID für team-spezifische Events
            last_modified: None für alle Events, sonst nur Events geändert nach diesem Zeitpunkt
            
        Returns:
            Liste von EventDetail Objekten
        """
        
    @classmethod  
    @db_session(sql_debug=LOGGING_ENABLED, show_values=LOGGING_ENABLED)
    def get_all_from_project(cls, project_id: UUID, 
                           last_modified: datetime.datetime | None = None) -> list[EventDetail]:
        """
        Holt alle Employee-Events eines Projekts mit optionalem last_modified Filter
        """
```

### 1.2 Imports hinzufügen
**Datei**: `database/db_services.py`
```python
from employee_event.schemas.employee_event_schemas import EventDetail
```

### 1.3 Filter-Logic
- **"No team"**: `len(employee_event.teams) == 0`
- **Team-spezifisch**: `team_db in employee_event.teams` 
- **Performance**: `last_modified` Filter zuerst, dann Team-Filter

---

## 2. GOOGLE CALENDAR INTEGRATION ERWEITERUNGEN

### 2.1 Neue Funktionen
**Datei**: `configuration/google_calenders.py`

```python
def validate_team_ids_from_existing_calendars() -> set[UUID]:
    """
    Holt alle Team-IDs von bereits erstellten Employee-Events-Kalendern
    Returns: Set der gültigen Team-IDs für Employee-Events-Synchronisation
    """

def create_google_calendar_event_from_employee_event(employee_event: EventDetail, timezone: str) -> dict:
    """
    Konvertiert EmployeeEvent in Google Calendar Event-Format
    
    Args:
        employee_event: EventDetail Objekt aus DB
        timezone: Timezone-String aus Konfiguration (z.B. 'Europe/Berlin')
        
    Returns:
        Google Calendar Event dict
    """

def sync_employee_events_to_calendar(calendar_id: str, project_id: UUID, team_id: UUID | None) -> dict:
    """
    Synchronisiert Employee-Events mit Google Calendar
    
    Args:
        calendar_id: Google Calendar ID
        project_id: Projekt UUID
        team_id: None für "no team", UUID für team-spezifisch
        
    Returns:
        {
            'successful_count': int,
            'failed_events': [(title, error_message), ...],
            'total_count': int
        }
    """

def get_timezone_from_config() -> str:
    """Liest Timezone aus Konfiguration (Default: 'Europe/Berlin')"""

def create_employee_events_calendar_description(team_id: UUID | None) -> str:
    """
    Erstellt Description JSON für Employee-Events Kalender
    
    Returns:
        JSON String: {"description": "Employee events - team/no team", "team_id": "uuid/"}
    """

def determine_team_filter_from_dialog(dlg: CreateGoogleCalendar) -> tuple[UUID | None, str]:
    """
    Bestimmt Team-Filter basierend auf UI-Auswahl
    Returns: (team_id_for_db_query, team_identifier_for_calendar_description)
    """
```

### 2.2 CalendarsHandlerToml Erweiterungen
```python
def get_last_sync_time(self, calendar_id: str) -> datetime | None:
    """Holt letzte Sync-Zeit für Kalender aus TOML"""

def update_last_sync_time(self, calendar_id: str, sync_time: datetime):
    """Aktualisiert letzte Sync-Zeit für Kalender in TOML"""
```

### 2.3 Google Calendar Event Format
```python
{
    'summary': employee_event.title,
    'description': employee_event.description,
    'start': {
        'dateTime': employee_event.start.isoformat(),
        'timeZone': timezone
    },
    'end': {
        'dateTime': employee_event.end.isoformat(), 
        'timeZone': timezone
    },
    'location': employee_event.address.full_address if employee_event.address else None,
    'attendees': [{'email': p.email} for p in employee_event.participants if p.email]
}
```

### 2.4 Imports hinzufügen
```python
from database.db_services import EmployeeEvent
from employee_event.schemas.employee_event_schemas import EventDetail
import json
import logging
```

---

## 3. BACKEND INTEGRATION CHANGES

### 3.1 main_window.py - create_google_calendar() Erweiterung
**Datei**: `gui/main_window.py`

#### 3.1.1 create() Funktion erweitern:
```python
# NEU: Employee-Events Zugriffskontrolle
elif dlg.calendar_type == 'employee_events' and dlg.selected_ee_person_emails:
    for email in dlg.selected_ee_person_emails:
        share_calendar(created_calendar['id'], email, 'reader')

# NEU: Employee-Events synchronisieren
if dlg.calendar_type == 'employee_events':
    team_id = dlg.selected_ee_team_id if dlg.selected_ee_team_id != 'no_team' else None
    sync_results = sync_employee_events_to_calendar(
        created_calendar['id'], 
        self.project_id, 
        team_id
    )
    return {'success': True, 'sync_results': sync_results}
```

#### 3.1.2 finished() Slot erweitern:
```python
# NEU: Employee-Events Success-Message
elif dlg.calendar_type == 'employee_events':
    team_text = dlg.combo_ee_teams.currentText()
    calendar_name = f"Employee-Events ({team_text})"
    
    # Access Control Text
    if dlg.selected_ee_person_emails:
        emails_text = '\n'.join(dlg.selected_ee_person_emails)
        text_access_control = f'\nZugriff für folgende Personen:\n{emails_text}'
    else:
        text_access_control = '\nKein Personenzugriff konfiguriert.'
    
    # Sync Results Text
    if sync_results := result.get('sync_results'):
        sync_text = (f'\n\nEvents synchronisiert: {sync_results["successful_count"]}'
                   f'/{sync_results["total_count"]}')
        if sync_results['failed_events']:
            failed_titles = [title for title, _ in sync_results['failed_events'][:3]]
            sync_text += f'\nFehler bei: {", ".join(failed_titles)}'
            if len(sync_results['failed_events']) > 3:
                sync_text += f' (+{len(sync_results["failed_events"])-3} weitere)'
    else:
        sync_text = ''
    
    text_access_control += sync_text
```

#### 3.1.3 Progress-Text erweitern:
```python
if dlg.calendar_type == 'employee_events':
    team_text = dlg.combo_ee_teams.currentText()
    progress_text = f'Employee-Events Kalender ({team_text}) wird erstellt und synchronisiert...'
```

### 3.2 Imports hinzufügen
```python
from configuration.google_calenders import (
    sync_employee_events_to_calendar,
    determine_team_filter_from_dialog,
    create_employee_events_calendar_description
)
```

---

## 4. ERROR HANDLING & LOGGING

### 4.1 Error-Behandlung
- **API-Fehler**: Einzelne Events überspringen, weiter synchronisieren
- **Logging**: Alle Fehler mit logger.error() protokollieren
- **UI-Feedback**: Max. 3 fehlgeschlagene Event-Titel im Success-Dialog
- **Sync-Time**: Nur bei mind. einem erfolgreichen Event aktualisieren

### 4.2 Logging-Format
```python
logger.error(f"Employee-Event sync failed: Event '{event.title}': {str(e)}")
```

---

## 5. KONFIGURATION

### 5.1 Timezone-Konfiguration
- **Standard**: 'Europe/Berlin'
- **Quelle**: Aus bestehender Anwendungskonfiguration lesen
- **Fallback**: 'Europe/Berlin' wenn nicht konfiguriert

### 5.2 TOML-Erweiterung für Sync-Tracking
```toml
[calendar_sync_times]
"calendar_id_1" = "2025-08-29T15:30:00"
"calendar_id_2" = "2025-08-29T16:45:00"
```

---

## 6. UI INTEGRATION

### 6.1 Dialog Properties (bereits implementiert)
- `dlg.calendar_type == 'employee_events'`
- `dlg.selected_ee_team_id` (UUID oder 'no_team')
- `dlg.selected_ee_person_emails` (List[str])
- `dlg.combo_ee_teams.currentText()` für UI-Anzeige

### 6.2 Calendar Description Format
```json
{"description": "Employee events - team", "team_id": "uuid-string"}
{"description": "Employee events - no team", "team_id": ""}
```

---

## 7. BUSINESS LOGIC RULES

### 7.1 Team-Filter Logic
- **"No team"**: Employee-Events ohne Team-Zuordnung (`len(teams) == 0`)
- **Team-spezifisch**: Employee-Events die diesem Team zugeordnet sind
- **Multi-Team**: Events erscheinen in ALLEN zugeordneten Team-Kalendern
- **Team-ID-Validierung**: Nur Team-IDs von bestehenden Employee-Events-Kalendern

### 7.2 Sync-Performance
- **Inkrementell**: Nur Events mit `last_modified > last_sync_time`
- **Basis-Query**: Projekt-Filter zuerst, dann last_modified, dann Team-Filter

---

## 8. IMPLEMENTIERUNGS-REIHENFOLGE

### Phase 1: Database Services
1. `EmployeeEvent` Service-Klasse in `db_services.py`
2. Imports und Logging

### Phase 2: Google Calendar Integration  
1. Helper-Funktionen in `google_calenders.py`
2. `CalendarsHandlerToml` erweitern
3. Sync-Hauptfunktion

### Phase 3: Backend Integration
1. `main_window.py` erweitern
2. Error-Handling und UI-Feedback
3. Testing und Validierung

---

## STATUS: BEREIT FÜR IMPLEMENTIERUNG
Alle strukturellen Änderungen sind geplant und besprochen. Die UI ist bereits vollständig implementiert und funktionsfähig.
