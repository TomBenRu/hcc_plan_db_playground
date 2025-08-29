"""
Google Calendar Integration für Employee Events.

Synchronisiert Employee Events aus der Datenbank mit Google Calendar.
Nutzt die bestehende Google Calendar API-Integration.
"""

import datetime
import json
import logging
from typing import Dict, List, Tuple
from uuid import UUID

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from configuration.google_calenders import curr_calendars_handler
from employee_event.db_service import EmployeeEventService
from employee_event.schemas.employee_event_schemas import EventDetail
from google_calendar_api.authenticate import authenticate_google

logger = logging.getLogger(__name__)


def get_timezone_from_config() -> str:
    """
    Liest Timezone aus Konfiguration.
    
    Returns:
        str: Timezone-String (Default: 'Europe/Berlin')
    """
    # TODO: Aus Konfiguration lesen, wenn verfügbar
    return 'Europe/Berlin'


def create_google_calendar_event_from_employee_event(employee_event: EventDetail, timezone: str) -> dict:
    """
    Konvertiert EmployeeEvent in Google Calendar Event-Format.
    
    Args:
        employee_event: EventDetail Objekt aus DB
        timezone: Timezone-String (z.B. 'Europe/Berlin')
        
    Returns:
        dict: Google Calendar Event dict
    """
    # Teilnehmer-E-Mails sammeln (nur wenn vorhanden)
    attendees = []
    if employee_event.participants:
        attendees = [
            {'email': p.email} for p in employee_event.participants 
            if p.email and '@' in p.email
        ]
    
    # Location aus Address-Objekt generieren (falls vorhanden)
    location = None
    if employee_event.address:
        location = employee_event.address.full_address
    
    # Google Calendar Event erstellen
    google_event = {
        'summary': employee_event.title,
        'description': employee_event.description,
        'start': {
            'dateTime': employee_event.start.isoformat(),
            'timeZone': timezone
        },
        'end': {
            'dateTime': employee_event.end.isoformat(),
            'timeZone': timezone
        }
    }
    
    # Optionale Felder hinzufügen
    if location:
        google_event['location'] = location
    
    if attendees:
        google_event['attendees'] = attendees
    
    return google_event


def add_event_to_calendar(calendar_id: str, event_data: dict) -> bool:
    """
    Fügt ein Event zu einem Google Calendar hinzu.
    
    Args:
        calendar_id: Google Calendar ID
        event_data: Event-Daten im Google Calendar Format
        
    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    try:
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)
        service.events().insert(calendarId=calendar_id, body=event_data).execute()
        return True
    except HttpError as e:
        logger.error(f"Google Calendar API Fehler beim Event-Hinzufügen: {e}")
        return False
    except Exception as e:
        logger.error(f"Unbekannter Fehler beim Event-Hinzufügen: {e}")
        return False


def sync_employee_events_to_calendar(project_id: UUID) -> dict:
    """
    Synchronisiert Employee Events mit Google Calendar.
    
    Args:
        project_id: Projekt UUID
        
    Returns:
        dict: {
            'successful_count': int,
            'failed_events': [(title, error_message), ...],
            'total_count': int
        }
    """
    # Ergebnis-Struktur initialisieren
    sync_results = {
        'successful_count': 0,
        'failed_events': [],
        'total_count': 0
    }

    employee_event_service = EmployeeEventService()
    last_sync = curr_calendars_handler.get_last_sync_time()
    timezone = get_timezone_from_config()
    calendars = {c.team_id: c for c in curr_calendars_handler.get_calenders().values() if c.type == 'employee_events'}
    events = employee_event_service.get_all_events(project_id, last_sync, False)

    try:
        for event in events:
            if event.teams:
                for team in event.teams:
                    if team.id in calendars:
                        calendar_id = calendars[team.id].id
                        google_event = create_google_calendar_event_from_employee_event(event, timezone)
                        sync_results['total_count'] += 1
                        try:
                            if add_event_to_calendar(calendar_id, google_event):
                                sync_results['successful_count'] += 1
                            else:
                                sync_results['failed_events'].append((event.title, "API-Fehler beim Hinzufügen"))
                        except Exception as e:
                            error_msg = str(e)
                            sync_results['failed_events'].append((event.title, error_msg))
                            logger.error(f"Employee-Event sync failed: Event '{event.title}': {error_msg}")
                else:
                    continue
            else:
                # Noch zu implementieren
                pass

        if not sync_results['failed_events']:
            curr_calendars_handler.update_last_sync_time(datetime.datetime.now(datetime.UTC))
            
        return sync_results
        
    except Exception as e:
        logger.error(f"Fehler bei Employee-Events-Synchronisation: {str(e)}")
        sync_results['failed_events'].append(("Synchronisation", str(e)))
        return sync_results
