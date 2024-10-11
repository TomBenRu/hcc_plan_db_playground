import json
import pprint
from json import JSONDecodeError
from uuid import UUID

from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from configuration.google_calenders import curr_calendars_handler
from database import db_services
from google_calendar_api.authenticate import authenticate_google


def add_data_from_description_field(calendar: dict) -> dict:
    try:
        description: dict = json.loads(calendar['description'])
        team_id = description.get('team_id')
        person_id = description.get('person_id')
        person_name = db_services.Person.get_full_name_of_person(person_id) if person_id else None
        calendar['team_id'] = UUID(team_id) if team_id else None
        calendar['person_id'] = UUID(person_id) if person_id else None
        calendar['person_name'] = person_name
    except JSONDecodeError as e:
        print(f'Fehler: description field does not contain valid json string: {e}')

    return calendar


def list_calendar_acl(calendar_id: str, service: Resource = None):
    """
    Diese Funktion ruft alle Freigaben (ACL) für einen bestimmten Kalender ab.
    :param calendar_id: Die ID des Kalenders.
    :param service: Das Google API-Objekt, das für die Authentifizierung und Abfrage des Kalenders verwendet wird.
    :return: Eine Liste von ACL-Einträgen oder None bei einem Fehler.
    """
    if service is None:
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)

    try:
        acl_result = service.acl().list(calendarId=calendar_id).execute()
        acl_entries = acl_result.get('items', [])

        if not acl_entries:
            # print(f"Keine Freigaben für Kalender-ID: {calendar_id}")
            return None

        # for acl in acl_entries:
            # print(f"Role: {acl['role']}, Scope: {acl['scope']['type']}, Email: {acl['scope'].get('value', 'N/A')}")

        return acl_entries
    except HttpError as error:
        print(f"Fehler beim Abrufen der ACLs für Kalender-ID {calendar_id}: {error}")
        return None


def list_all_calendars_with_acl():
    """
    Diese Funktion ruft alle vorhandenen Kalender und deren Freigaben ab.
    :return: Eine Liste von Kalenderobjekten und deren ACLs oder None bei einem Fehler.
    """
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    try:
        # Kalenderliste abrufen
        calendars_result = service.calendarList().list().execute()
        calendars = calendars_result.get('items', [])

        if not calendars:
            print("Keine Kalender gefunden.")
            return None

        for calendar in calendars:
            # Freigaben (ACLs) für den aktuellen Kalender abrufen
            acl_entries = list_calendar_acl(calendar['id'], service)
            calendar['access_control'] = [a['scope'].get('value') for a in acl_entries] if acl_entries else []

        return [c for c in calendars if c.get('accessRole') == 'owner' and not c.get('primary')]
    except HttpError as error:
        print(f"Fehler beim Abrufen der Kalender: {error}")
        return None


def get_calendar_by_id(calendar_id: str):
    """
    Diese Funktion ruft die Daten eines Google-Kalenders anhand seiner Kalender-ID ab.

    :param calendar_id: Die Kalender-ID, deren Daten abgerufen werden sollen.
    :return: Die Kalenderdaten als Dictionary oder None bei einem Fehler.
    """
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    try:
        # Kalenderdaten abrufen
        calendar = service.calendars().get(calendarId=calendar_id).execute()
        acl_entries = list_calendar_acl(calendar_id, service)
        calendar['access_control'] = [a['scope'].get('value') for a in acl_entries] if acl_entries else []
        try:
            calendar = add_data_from_description_field(calendar)
        except JSONDecodeError as e:
            print(f'Fehler: description field does not contain valid json string: {e}')
        return calendar
    except HttpError as error:
        print(f"Fehler beim Abrufen des Kalenders mit ID {calendar_id}: {error}")
        return None


def synchronize_local_calendars():
    calendars = list_all_calendars_with_acl()
    for c in calendars:
        try:
            add_data_from_description_field(c)
        except JSONDecodeError as e:
            print(f'Fehler: description field does not contain valid json string: {e}')

    curr_calendars_handler.save_calendars_json_to_file(calendars)
