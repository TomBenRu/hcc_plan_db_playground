from datetime import datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from google_calendar_api.authenticate import authenticate_google


def delete_events_in_range(calendar_id: str, start_time: datetime, end_time: datetime,
                           service: Resource | None = None,
                           private_extended_property: str | None = None):
    """
    Diese Funktion löscht alle Events aus einem Kalender im angegebenen Zeitraum.

    :param calendar_id: Die Kalender-ID, aus dem die Events gelöscht werden sollen.
    :param start_time: Start des Zeitraums als datetime-Objekt.
    :param end_time: Ende des Zeitraums als datetime-Objekt.
    :param service: Resource Objekt
    :param private_extended_property: Optionaler Filter im Format 'key=value'. Wenn gesetzt,
                                      werden nur Events mit dieser privaten Extended Property gelöscht.
    :return: Die Anzahl der gelöschten Events.
    """

    if service is None:
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)

    try:
        # Konvertiere start_time und end_time in das RFC3339-Format (ISO 8601)
        start_time_str = start_time.isoformat() + 'Z'  # 'Z' für UTC Zeit
        end_time_str = end_time.isoformat() + 'Z'

        list_kwargs = dict(
            calendarId=calendar_id,
            timeMin=start_time_str,
            timeMax=end_time_str,
            singleEvents=True,
            orderBy='startTime'
        )
        if private_extended_property:
            list_kwargs['privateExtendedProperty'] = private_extended_property

        # Rufe alle Events im angegebenen Zeitraum ab
        events_result = service.events().list(**list_kwargs).execute()

        events = events_result.get('items', [])

        if not events:
            print(f"Keine Events im Zeitraum {start_time} bis {end_time} gefunden.")
            return 0

        # Events nacheinander löschen
        deleted_count = 0
        for event in events:
            event_id = event['id']
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            print(f"Event mit ID {event_id} gelöscht.")
            deleted_count += 1

        print(f"Es wurden {deleted_count} Events gelöscht.")
        return deleted_count

    except HttpError as error:
        print(f"Fehler beim Löschen der Events: {error}")
        return 0


def delete_untagged_events_in_range(calendar_id: str, start_time: datetime, end_time: datetime,
                                    service: Resource | None = None) -> int:
    """
    Einmalige Migrationsfunktion: Löscht alle Events im Zeitraum, die KEIN 'hcc_team_id'-Tag
    in den privaten Extended Properties besitzen.

    Hintergrund: Vor Einführung des Team-Taggings wurden Events ohne extendedProperties
    übertragen. Diese Funktion bereinigt den Kalender vor dem ersten Re-Transfer mit dem
    neuen System, um Duplikate zu vermeiden.

    :param calendar_id: Die Kalender-ID, aus dem die ungetaggten Events gelöscht werden sollen.
    :param start_time: Start des Zeitraums als datetime-Objekt.
    :param end_time: Ende des Zeitraums als datetime-Objekt.
    :param service: Resource Objekt
    :return: Die Anzahl der gelöschten Events.
    """
    if service is None:
        creds = authenticate_google()
        service = build('calendar', 'v3', credentials=creds)

    try:
        start_time_str = start_time.isoformat() + 'Z'
        end_time_str = end_time.isoformat() + 'Z'

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=start_time_str,
            timeMax=end_time_str,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        deleted_count = 0
        for event in events:
            has_tag = event.get('extendedProperties', {}).get('private', {}).get('hcc_team_id')
            if not has_tag:
                service.events().delete(calendarId=calendar_id, eventId=event['id']).execute()
                print(f"Ungetaggtes Event '{event.get('summary', event['id'])}' gelöscht.")
                deleted_count += 1

        print(f"Migration: {deleted_count} ungetaggte Events gelöscht.")
        return deleted_count

    except HttpError as error:
        print(f"Fehler beim Löschen ungetaggter Events: {error}")
        return 0
