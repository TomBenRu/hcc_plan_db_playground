import pprint

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from configuration.google_calenders import curr_calendars_handler
from google_calendar_transfer.authenticate import authenticate_google


def list_calendar_acl(calendar_id: str):
    """
    Diese Funktion ruft alle Freigaben (ACL) für einen bestimmten Kalender ab.
    :param calendar_id: Die ID des Kalenders.
    :return: Eine Liste von ACL-Einträgen oder None bei einem Fehler.
    """
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
            acl_entries = list_calendar_acl(calendar['id'])
            calendar['access_control'] = [a['scope'].get('value') for a in acl_entries] if acl_entries else []

        return [c for c in calendars if c.get('accessRole') == 'owner' and not c.get('primary')]
    except HttpError as error:
        print(f"Fehler beim Abrufen der Kalender: {error}")
        return None


def synchronize_local_calendars():
    calendars = list_all_calendars_with_acl()
    curr_calendars_handler.save_json_to_file(calendars)


if __name__ == '__main__':
    # Rufe alle Kalender mit ihren Freigaben (ACL) ab
    calendars = list_all_calendars_with_acl()
    pprint.pprint(calendars)

    curr_calendars_handler.save_json_to_file(calendars)
    print(curr_calendars_handler.get_calenders())
