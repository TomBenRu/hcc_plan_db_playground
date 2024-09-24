from datetime import datetime
import pytz

class GoogleCalendarEvent:
    def __init__(self, summary, location, description, start_time, end_time, time_zone='Europe/Berlin', attendees=None):
        self.summary = summary
        self.location = location
        self.description = description
        self.start_time = start_time  # datetime-Objekt
        self.end_time = end_time  # datetime-Objekt
        self.time_zone = pytz.timezone(time_zone)  # Zeitzone als pytz-Zeitzonenobjekt
        self.attendees = attendees or []

    def to_google_event(self):
        """Wandelt das Event in das JSON-Format um, das Google erwartet."""
        # Zeitzonenanpassung der Start- und Endzeiten
        start_time_str = self.start_time.astimezone(self.time_zone).isoformat()
        end_time_str = self.end_time.astimezone(self.time_zone).isoformat()

        event = {
            'summary': self.summary,
            'location': self.location,
            'description': self.description,
            'start': {
                'dateTime': start_time_str,
                'timeZone': str(self.time_zone),
            },
            'end': {
                'dateTime': end_time_str,
                'timeZone': str(self.time_zone),
            },
        }

        if self.attendees:
            event['attendees'] = [{'email': email} for email in self.attendees]

        return event
