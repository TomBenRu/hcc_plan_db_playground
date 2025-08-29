"""
Google Calendar Integration für Employee Events.

Synchronisiert Employee Events aus der Datenbank mit Google Calendar.
Nutzt die bestehende Google Calendar API-Integration.
"""

import datetime
import json
import logging
from typing import Dict, List, Tuple
from uuid import UUID, uuid4

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from PySide6.QtCore import QCoreApplication

from configuration.google_calenders import curr_calendars_handler
from employee_event import ErrorResponseSchema
from employee_event.db_commands import event_commands
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

    categories_text = ("Categories: " + ", ".join(cat.name for cat in employee_event.employee_event_categories) + "\n\n"
                       if employee_event.employee_event_categories else '')
    description_text = QCoreApplication.translate('GoogleCalendarApi',
                                                  '{categories}Description: \n{description}').format(
            categories=categories_text,
            description=employee_event.description
        )
    
    # Google Calendar Event erstellen
    google_event = {
        'summary': employee_event.title,
        'description': description_text,
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



def find_event_by_icaluid(calendar_id: str, ical_uid: str) -> dict | None:
    """
    Findet ein Event anhand seiner iCalUID.
    
    Args:
        calendar_id: Google Calendar ID
        ical_uid: iCalendar UID des Events
        
    Returns:
        dict | None: Google Calendar Event oder None wenn nicht gefunden
    """
    try:
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)
        events_result = service.events().list(
            calendarId=calendar_id,
            iCalUID=ical_uid
        ).execute()
        events = events_result.get('items', [])
        return events[0] if events else None
    except Exception as e:
        logger.error(f"Fehler beim Suchen des Events mit iCalUID {ical_uid}: {e}")
        return None


def update_event_in_calendar(calendar_id: str, event_id: str, event_data: dict) -> bool:
    """
    Aktualisiert ein bestehendes Event in Google Calendar.
    
    Args:
        calendar_id: Google Calendar ID
        event_id: Google Calendar Event ID
        event_data: Aktualisierte Event-Daten
        
    Returns:
        bool: True bei Erfolg, False bei Fehler
    """
    try:
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)
        service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event_data
        ).execute()
        return True
    except HttpError as e:
        logger.error(f"Google Calendar API Fehler beim Event-Update: {e}")
        return False
    except Exception as e:
        logger.error(f"Unbekannter Fehler beim Event-Update: {e}")
        return False



def delete_event_from_calendar(calendar_id: str, ical_uid: str) -> bool:
    """
    Löscht ein Event aus Google Calendar anhand seiner iCalUID.
    
    Args:
        calendar_id: Google Calendar ID
        ical_uid: iCalendar UID des zu löschenden Events
        
    Returns:
        bool: True bei Erfolg (auch wenn Event nicht existiert), False bei Fehler
    """
    try:
        # Erst Event finden
        existing_event = find_event_by_icaluid(calendar_id, ical_uid)
        if not existing_event:
            # Event existiert nicht - das ist ok für Delete-Operation
            logger.info(f"Event mit iCalUID {ical_uid} bereits gelöscht oder existiert nicht")
            return True
        
        # Event löschen
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)
        service.events().delete(
            calendarId=calendar_id,
            eventId=existing_event['id']
        ).execute()
        logger.info(f"Event mit iCalUID {ical_uid} erfolgreich gelöscht")
        return True
        
    except HttpError as e:
        if e.resp.status == 410:  # Event bereits gelöscht
            logger.info(f"Event mit iCalUID {ical_uid} bereits gelöscht (410 Gone)")
            return True
        logger.error(f"Google Calendar API Fehler beim Event-Löschen: {e}")
        return False
    except Exception as e:
        logger.error(f"Unbekannter Fehler beim Event-Löschen: {e}")
        return False

def find_existing_event_across_all_calendars(event_id: UUID, current_google_calendar_event_id: str, 
                                           calendars: dict) -> list[tuple[str, str]]:
    """
    Sucht ein Event mit gegebener event_id und google_calendar_event_id in ALLEN verfügbaren Kalendern.
    
    ✅ MULTI-KALENDER SUPPORT: 
    - Event kann in mehreren Team-Kalendern gleichzeitig existieren
    - Gibt ALLE gefundenen Standorte zurück
    - Ermöglicht DELETE aus ALLEN Kalendern vor CREATE
    
    Löst das Teamwechsel-Problem: Bei Wechsel von Team A → Team B sucht in allen Kalendern,
    findet Event sowohl in A als auch B, löscht aus BEIDEN.
    
    Args:
        event_id: Employee Event ID
        current_google_calendar_event_id: Aktuelle UUID aus DB
        calendars: Dict {team_id: calendar_object} aller verfügbaren Kalender
        
    Returns:
        list[tuple[str, str]]: Liste aller (calendar_id, ical_uid) wo Event gefunden wurde
    """
    logger.info(f"Globale Event-Suche: event_id={event_id}, uuid={current_google_calendar_event_id}")
    
    found_events: list[tuple[str, str]] = []
    
    for team_id, calendar in calendars.items():
        # iCalUID für diesen Kalender zusammenbauen
        if team_id is None:
            potential_ical_uid = f"employee-event-{event_id}-no-team-{current_google_calendar_event_id}@hcc-plan.local"
        else:
            potential_ical_uid = f"employee-event-{event_id}-team-{team_id}-{current_google_calendar_event_id}@hcc-plan.local"
        
        # In diesem Kalender suchen
        existing_event = find_event_by_icaluid(calendar.id, potential_ical_uid)
        if existing_event:
            logger.info(f"Event GEFUNDEN in {'no-team' if team_id is None else f'Team {team_id}'} Kalender")
            found_events.append((calendar.id, potential_ical_uid))
    
    if found_events:
        logger.info(f"Event in {len(found_events)} Kalender(n) gefunden - DELETE aus allen")
    else:
        logger.info("Event in KEINEM Kalender gefunden - CREATE ohne DELETE")
    
    return found_events


def delete_events_from_all_calendars(event_id: UUID, current_google_calendar_event_id: str,
                                    calendars: dict) -> list[str]:
    """
    Löscht ein Event aus ALLEN verfügbaren Kalendern anhand seiner event_id und google_calendar_event_id.

    Args:
        event_id: Employee Event ID
        current_google_calendar_event_id: Aktuelle UUID aus DB
        calendars: Dict aller verfügbaren Kalender

    Returns:
        list[str]: Liste aller Kalender-IDs aus denen das Event gelöscht wurde
    """
    found_events = find_existing_event_across_all_calendars(event_id, current_google_calendar_event_id, calendars)

    deleted_calendars: list[str] = []
    for calendar_id, ical_uid in found_events:
        delete_success = delete_event_from_calendar(calendar_id, ical_uid)
        if delete_success:
            deleted_calendars.append(calendar_id)
    return deleted_calendars


def create_event_with_new_uuid(calendar_id: str, event_data: dict, event_id: UUID,
                               team_id: UUID, current_google_calendar_event_id: str,
                               new_google_calendar_event_id: str) -> tuple[bool, str]:
    """
    Erstellt ein neues Event in Google Calendar mit einer neuen UUID.

    Args:
        calendar_id: Google Calendar ID
        event_data: Event-Daten im Google Calendar Format
        event_id: Employee Event ID
        team_id: Team ID (None für no-team Events)
        current_google_calendar_event_id: Aktuelle UUID aus DB
        new_google_calendar_event_id: Neue UUID für das Event

    Returns:
        tuple[bool, str]: (Success, neue_google_calendar_event_id)
    """

    # Neue iCalUID für Ziel-Kalender zusammenbauen
    if team_id is None:
        new_ical_uid = f"employee-event-{event_id}-no-team-{new_google_calendar_event_id}@hcc-plan.local"
    else:
        new_ical_uid = f"employee-event-{event_id}-team-{team_id}-{new_google_calendar_event_id}@hcc-plan.local"

    # CREATE in Ziel-Kalender mit neuer iCalUID
    event_data['iCalUID'] = new_ical_uid
    create_success = add_event_to_calendar(calendar_id, event_data)

    if create_success:
        return True, new_google_calendar_event_id
    else:
        return False, current_google_calendar_event_id  # Bei Fehler: alte UUID behalten


def sync_employee_events_to_calendar(project_id: UUID) -> dict:
    """
    Synchronisiert Employee Events mit Google Calendar.
    Behandelt auch gelöschte Events (prep_delete).
    
    Args:
        project_id: Projekt UUID
        
    Returns:
        dict: {
            'successful_count': int,
            'failed_events': [(title, error_message), ...],
            'total_count': int,
            'deleted_count': int
        }
    """
    # Ergebnis-Struktur initialisieren
    sync_results = {
        'successful_count': 0,
        'failed_events': [],
        'total_count': 0,
        'deleted_count': 0,

    }

    employee_event_service = EmployeeEventService()
    last_sync = curr_calendars_handler.get_last_sync_time()
    timezone = get_timezone_from_config()
    calendars = {c.team_id: c for c in curr_calendars_handler.get_calenders().values() if c.type == 'employee_events'}
    
    # Alle Events inklusive gelöschte holen
    events = employee_event_service.get_all_events(project_id, last_sync, include_prep_delete=True)

    try:
        for event in events:
            if event.prep_delete:
                logger.info(f"Sync: Event {event.id} mit prep_delete gefunden")
                sync_results['total_count'] += 1
                calendars_with_event = delete_events_from_all_calendars(event.id, event.google_calendar_event_id, calendars)
                if calendars_with_event:
                    sync_results['deleted_count'] += len(calendars_with_event)
                    sync_results['successful_count'] += len(calendars_with_event)
            elif event.teams:
                calendars_with_event = delete_events_from_all_calendars(
                    event.id, event.google_calendar_event_id, calendars)
                if calendars_with_event:
                    sync_results['deleted_count'] += len(calendars_with_event)
                    sync_results['successful_count'] += len(calendars_with_event)
                # Neue UUID generieren
                new_uuid = str(uuid4())
                for team in event.teams:
                    if team.id in calendars:
                        calendar_id = calendars[team.id].id
                        sync_results['total_count'] += 1
                        
                        try:
                            logger.info(f"Sync: CREATE für Event {event.id} in Team {team.id}")
                            google_event = create_google_calendar_event_from_employee_event(event, timezone)
                            success, new_uuid = create_event_with_new_uuid(
                                calendar_id, google_event, event.id,
                                team.id, event.google_calendar_event_id, new_uuid
                            )
                            if success:
                                sync_results['successful_count'] += 1
                                update_employee_event_with_new_ical_uid(event.id, new_uuid)
                            else:
                                sync_results['failed_events'].append((event.title, "API-Fehler beim DELETE+CREATE"))
                        
                        except Exception as e:
                            error_msg = str(e)
                            sync_results['failed_events'].append((event.title, error_msg))
                            logger.error(f"Employee-Event sync failed: Event '{event.title}': {error_msg}")

            else:
                # Events ohne Team-Zuordnung - synchronisiert mit "no team" Kalender
                calendars_with_event = delete_events_from_all_calendars(
                    event.id, event.google_calendar_event_id, calendars)
                if calendars_with_event:
                    sync_results['deleted_count'] += len(calendars_with_event)
                    sync_results['successful_count'] += len(calendars_with_event)
                no_team_calendar = calendars.get(None)
                # Neue UUID generieren
                new_uuid = str(uuid4())
                if no_team_calendar:
                    calendar_id = no_team_calendar.id
                    sync_results['total_count'] += 1
                    
                    try:
                        logger.info(f"Sync: DELETE+CREATE für no-team Event {event.id}")
                        google_event = create_google_calendar_event_from_employee_event(event, timezone)
                        success, new_uuid = create_event_with_new_uuid(
                            calendar_id, google_event, event.id, None,
                            event.google_calendar_event_id, new_uuid
                        )
                        if success:
                            sync_results['successful_count'] += 1
                            update_employee_event_with_new_ical_uid(event.id, new_uuid)
                        else:
                            sync_results['failed_events'].append((event.title, "API-Fehler beim DELETE+CREATE (no team)"))
                    
                    except Exception as e:
                        error_msg = str(e)
                        sync_results['failed_events'].append((event.title, f"{error_msg} (no team)"))
                        logger.error(f"Employee-Event sync failed (no team): Event '{event.title}': {error_msg}")
                else:
                    # Kein "no team" Kalender verfügbar - Event wird übersprungen
                    logger.info(f"Event '{event.title}' ohne Team-Zuordnung übersprungen - kein 'no team' Kalender vorhanden")

        if not sync_results['failed_events']:
            curr_calendars_handler.update_last_sync_time(
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=1))
            
        return sync_results
        
    except Exception as e:
        logger.error(f"Fehler bei Employee-Events-Synchronisation: {str(e)}")
        sync_results['failed_events'].append(("Synchronisation", str(e)))
        return sync_results


def update_employee_event_with_new_ical_uid(event_id: UUID, new_ical_uid: str) -> bool:
    """
    Aktualisiert das iCalUID eines Employee Events in der Datenbank.

    Args:
        event_id: UUID des Events
        new_ical_uid: Neuer iCalUID

    Returns:
        bool: True, wenn erfolgreich, False sonst
    """
    command = event_commands.UpdateGoogleCalendarEventId(event_id, new_ical_uid)
    command.execute()
    if isinstance(command.result, ErrorResponseSchema):
        logger.error(f"DB Update fehlgeschlagen: {command.result.message}")
