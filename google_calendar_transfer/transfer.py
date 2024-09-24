import datetime
import os.path
import pprint

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_calendar_transfer.event_object import GoogleCalendarEvent

# Wenn der Zugriff auf den Kalender nur zum Erstellen/Ändern von Events benötigt wird
SCOPES = ['https://www.googleapis.com/auth/calendar']

def authenticate_google():
    creds = None
    # Wenn Token schon existiert, laden
    if os.path.exists('credentials/token.json'):
        creds = Credentials.from_authorized_user_file('credentials/token.json', SCOPES)
    # Wenn keine (gültigen) Anmeldeinformationen vorhanden, melde Benutzer erneut an
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials/client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Speichere die Anmeldeinformationen für das nächste Mal
        with open('credentials/token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def add_event_to_calendar(calendar_id, event):
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)


    try:
        # Das Event erstellen
        event_result = service.events().insert(calendarId=calendar_id, body=event).execute()

        print(f"Event erstellt: {event_result['htmlLink']}")
    except HttpError as error:
        print(f"Ein Fehler ist aufgetreten: {error}")
        print(f"Statuscode: {error.resp.status}")
        print(f"Fehlerdetails: {error.content}")


if __name__ == '__main__':
    # Beispieltermin
    # Erstellen eines datetime-Objekts für die Start- und Endzeit
    start_time = datetime.datetime(2024, 9, 29, 10, 0, 0)  # 29. Sept. 2024, 10:00 Uhr
    end_time = datetime.datetime(2024, 9, 29, 11, 0, 0)  # 29. Sept. 2024, 11:00 Uhr

    # Erstellen eines Events
    event_obj = GoogleCalendarEvent(
        summary="Team-Meeting",
        location="Büro",
        description="Wöchentliches Team-Meeting zur Projektbesprechung.",
        start_time=start_time,
        end_time=end_time,
        time_zone="Europe/Berlin",  # Dynamische Zeitzone
        attendees=None
    )

    # Konvertiere das Event-Objekt ins Google Event Format
    google_event = event_obj.to_google_event()
    pprint.pprint(google_event)

    # Füge das Event in den Kalender ein
    add_event_to_calendar('01e7ea578547693819a0c97a926a2871c1178c5f129eb35563734c7b106985ea@group.calendar.google.com',
                          google_event)
