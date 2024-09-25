import datetime

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_calendar_api.appointments_from_plan import GoogleCalendarEvent
from google_calendar_api.authenticate import authenticate_google


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

    # Füge das Event in den Kalender ein
    add_event_to_calendar('01e7ea578547693819a0c97a926a2871c1178c5f129eb35563734c7b106985ea@group.calendar.google.com',
                          google_event)
