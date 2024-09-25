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


class CalendarsHandlerToml:
    def __init__(self):
        self._calender_file_path = os.path.join(os.path.dirname(__file__), 'google_calendars', 'google_calendars.toml')
        self._calenders: list[GoogleCalendar] | None = None

    def load_calenders_from_file(self) -> dict[str, GoogleCalendar]:
        try:
            with open(self._calender_file_path, 'r') as f:
                return {name: GoogleCalendar.model_validate(c) for name, c in toml.load(f).items()}
        except FileNotFoundError:
            return {}
        except TomlDecodeError:
            return {}

    def save_calenders_to_file(self, calenders: list[GoogleCalendar]):
        # self._calenders = calenders
        with open(self._calender_file_path, 'w') as f:
            toml.dump({c.summary: c.model_dump(mode='json') for c in calenders}, f)

    def save_json_to_file(self, calendars: list[dict]):
        calendar_objects = [GoogleCalendar.model_validate(c) for c in calendars]
        self.save_calenders_to_file(calendar_objects)

    def get_calenders(self) -> list[GoogleCalendar]:
        if self._calenders is None:
            self._calenders = self.load_calenders_from_file()
        return self._calenders


curr_calendars_handler = CalendarsHandlerToml()
