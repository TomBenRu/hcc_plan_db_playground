import pprint

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from google_calendar_api.authenticate import authenticate_google


class CalendarData:
    def __init__(self, summary: str, description: str, location: str = 'Berlin', time_zone: str = 'Europe/Berlin'):
        self.summary = summary
        self.description = description
        self.location = location
        self.time_zone = time_zone

    def to_google_calendar_json(self) -> dict[str, str]:
        return {
            'summary': self.summary,
            'timeZone': self.time_zone,
            'description': self.description,
            'location': self.location
        }


def create_new_google_calendar(calendar_data: dict[str, str]):
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    try:
        # Versuche, den neuen Kalender zu erstellen
        created_calendar = service.calendars().insert(body=calendar_data).execute()
        print(f"Neuer Kalender erstellt: {created_calendar['id']}")
        return created_calendar
    except HttpError as error:
        print(f"Fehler beim Erstellen des Kalenders: {error}")
        return None


def share_calendar(calendar_id: str, email: str, role: str = 'reader'):
    """
    Kalender für eine bestimmte E-Mail freigeben.

    :param calendar_id: Die Kalender-ID des freizugebenden Kalenders.
    :param email: Die E-Mail-Adresse der Person, die Zugriff erhalten soll.
    :param role: Die Zugriffsrolle (default: 'reader'). Mögliche Werte: 'owner', 'writer', 'reader', 'freeBusyReader'.
    :return: Die erstellte ACL-Regel oder None, wenn ein Fehler auftritt.
    """
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    rule = {
        'scope': {
            'type': 'user',  # 'user' für einzelne E-Mail, 'group' für Google-Gruppen
            'value': email
        },
        'role': role  # Die Zugriffsrolle (reader, writer, owner, freeBusyReader)
    }

    try:
        # Füge eine neue ACL-Regel hinzu, um den Kalender freizugeben
        created_rule = service.acl().insert(calendarId=calendar_id, body=rule).execute()
        print(f"Kalender erfolgreich für {email} mit Rolle {role} freigegeben.")
        return created_rule
    except HttpError as error:
        print(f"Fehler beim Freigeben des Kalenders: {error}")
        return None


if __name__ == '__main__':
    calendar = CalendarData('Mitarbeiter_01', 'Visiten von Mitarbeiter 01')
    created_calendar = create_new_google_calendar(calendar.to_google_calendar_json())
    print(created_calendar)

    ##################################################################

    calendar_id = created_calendar['id']  # ID des Kalenders (primary = Hauptkalender)
    email_to_share = 'kollege@example.com'
    role = 'reader'  # Berechtigungsstufe, z.B. 'reader', 'writer', 'owner'

    share_calendar(calendar_id, email_to_share, role)

