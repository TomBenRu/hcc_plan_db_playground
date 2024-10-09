import os
from uuid import UUID

import toml
from pydantic import BaseModel, EmailStr, ConfigDict, Field
from toml.decoder import TomlDecodeError


class GoogleCalendar(BaseModel):
    summary: str | None
    description: str | None
    id: str = Field(alias="id")
    access_control: list[EmailStr]
    person_name: str | None = None
    person_id: UUID | None = None
    team_id: UUID | None = None  # Wenn vorhanden, handelt es sich um einen Team-Kalender
    # (Zugriff von allen Team-Mitgliedern.


class CalendarsHandlerToml:
    def __init__(self):
        self.toml_dir = 'google_calendars'
        self._calender_file_path = os.path.join(os.path.dirname(__file__), self.toml_dir, 'google_calendars.toml')
        self._calenders: list[GoogleCalendar] | None = None
        self._check_toml_dir()

    def _check_toml_dir(self):
        if not os.path.exists(os.path.dirname(__file__)):
            os.mkdir(os.path.dirname(__file__))
        if not os.path.exists(os.path.join(os.path.dirname(__file__), self.toml_dir)):
            os.mkdir(os.path.join(os.path.dirname(__file__), self.toml_dir))

    def _load_calenders_from_file(self) -> dict[str, GoogleCalendar]:
        try:
            with open(self._calender_file_path, 'r') as f:
                return {name: GoogleCalendar.model_validate(c) for name, c in toml.load(f).items()}
        except FileNotFoundError:
            return {}
        except TomlDecodeError:
            return {}

    def save_calenders_to_file(self, calenders: list[GoogleCalendar]):
        self._calenders = {c.summary: c for c in calenders}
        with open(self._calender_file_path, 'w') as f:
            toml.dump({c.summary: c.model_dump(mode='json') for c in calenders}, f)

    def save_calendars_json_to_file(self, calendars: list[dict]):
        calendar_objects = [GoogleCalendar.model_validate(c) for c in calendars]
        self.save_calenders_to_file(calendar_objects)

    def save_calendar_json_to_file(self, calendar: dict):
        calendar_object = GoogleCalendar.model_validate(calendar)
        calendar_objects = list(self.get_calenders().values())
        calendar_objects += [calendar_object]
        self.save_calenders_to_file(calendar_objects)

    def get_calenders(self) -> dict[str, GoogleCalendar]:
        if self._calenders is None:
            self._calenders = self._load_calenders_from_file()
        return self._calenders


curr_calendars_handler = CalendarsHandlerToml()
