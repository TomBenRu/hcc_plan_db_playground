import datetime
import json
from collections import defaultdict
from uuid import UUID

from PySide6.QtWidgets import QWidget
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest

from configuration.google_calenders import curr_calendars_handler
from database import schemas, db_services
from google_calendar_api.appointments_from_plan import GoogleCalendarEvent
from google_calendar_api.authenticate import authenticate_google
from google_calendar_api.del_calendar_events import delete_events_in_range
from gui.observer import signal_handling


# todo: implement batch requests for better performance


def callback(request_id, response, exception):
    if exception is not None:
        print(f"Request {request_id} failed: {exception}")
        raise exception
    elif isinstance(response, dict):
        print(f"Request {request_id} succeeded: {response['status']=}")
    else:
        print(f"Request {request_id} succeeded: {response=}")


def transfer_appointments_with_batch_requests(plan: schemas.PlanShow):

    start_time = datetime.datetime.combine(plan.plan_period.start, datetime.datetime.min.time())
    end_time = datetime.datetime.combine(plan.plan_period.end, datetime.datetime.max.time())

    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    calendars = curr_calendars_handler.get_calenders()

    google_events = []
    user_cal_id__google_events: defaultdict[tuple[str, str], list[dict]] = defaultdict(list)
    for appointment in plan.appointments:
        google_event = create_google_event(appointment)
        google_events.append(google_event)
        user_calendars = (c for c in calendars.values()
                          if c.person_id in {avd.actor_plan_period.person.id for avd in appointment.avail_days})
        for user_calendar in user_calendars:
            user_cal_id__google_events[(user_calendar.id, user_calendar.person_name)].append(google_event)

    team_calendar = next((c for c in calendars.values() if c.team_id == plan.plan_period.team.id), None)
    text_time_span = f'{plan.plan_period.start:%d.%m.%y}-{plan.plan_period.end:%d.%m.%y}'

    if team_calendar:
        signal_handling.handler_google_cal_api.transfer_appointments_progress(
            f'Google-Kalender von: Team {plan.plan_period.team.name}\n'
            f'Planungszeitraum: {text_time_span}\n'
            f'Aktion: Termine übertragen.'
        )
        # Batch-Request erstellen
        batch = BatchHttpRequest(callback=callback, batch_uri='https://www.googleapis.com/batch/calendar/v3')

        # Alle Events innerhalb des Zeitrahmens des Team-Kalenders mit id user_cal_id abrufen
        events_result = service.events().list(
            calendarId=team_calendar.id,
            timeMin=f'{start_time.isoformat()}Z',
            timeMax=f'{end_time.isoformat()}Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        # Alle Events innerhalb des Zeitrahmens des Team-Kalenders mit id user_cal_id löschen
        for event in events_result.get('items', []):
            batch.add(service.events().delete(calendarId=team_calendar.id, eventId=event['id']),
                      request_id=f'delete_event_{event["id"]}')

        # Anfrage hinzufügen: Alle Termine in google_events in den Google-Kalender des Teams übertragen
        for google_event in google_events:
            batch.add(service.events().insert(calendarId=team_calendar.id, body=google_event),
                      request_id=f'insert_event_to_team_calendar_{google_event["start"]["dateTime"]}-'
                                 f'{google_event["end"]["dateTime"]}_{google_event["summary"]}')
        # Batch-Request ausführen
        batch.execute()

    # Anfrage hinzufügen: Alle Termine von start_time bis end_time aus den Google-Kalendern der Teilnehmer löschen und
    # Anfrage hinzufügen: Alle Termine in user_cal_id__google_events in den Google-Kalendern der Teilnehmer übertragen
    for (user_cal_id, user_name), g_events in user_cal_id__google_events.items():
        signal_handling.handler_google_cal_api.transfer_appointments_progress(
            f'Google-Kalender von: {user_name}\n'
            f'Planungszeitraum: {text_time_span}\n'
            f'Aktion: Termine übertragen.'
        )

        # Batch-Request erstellen
        batch = BatchHttpRequest(callback=callback, batch_uri='https://www.googleapis.com/batch/calendar/v3')

        # Alle Events innerhalb des Zeitrahmens des Kalenders mit id user_cal_id abrufen
        events_result = service.events().list(
            calendarId=user_cal_id,
            timeMin=f'{start_time.isoformat()}Z',
            timeMax=f'{end_time.isoformat()}Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        # Alle Events innerhalb des Zeitrahmens des Kalenders mit id user_cal_id löschen
        for event in events_result.get('items', []):
            batch.add(service.events().delete(calendarId=user_cal_id, eventId=event['id']),
                      request_id=f'delete_event_{event["id"]}')
        for g_event in g_events:
            batch.add(service.events().insert(calendarId=user_cal_id, body=g_event),
                      request_id=f'insert_event_to_user_calendar_{user_name}_{g_event["start"]["dateTime"]}-'
                                 f'{g_event["end"]["dateTime"]}_{g_event["summary"]}')
        # Batch-Request ausführen
        batch.execute()


def add_event_to_calendar(calendar_id, event, service: Resource | None = None):
    if service is None:
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


def create_google_event(appointment: schemas.Appointment):
    names_of_employees = [avd.actor_plan_period.person.full_name for avd in appointment.avail_days] + appointment.guests
    event_obj = GoogleCalendarEvent(
        summary=appointment.event.location_plan_period.location_of_work.name_an_city,
        location=appointment.event.location_plan_period.location_of_work.name_an_city,
        description=', '.join(names_of_employees) + (f'\nInfo: {appointment.notes}' if appointment.notes else ''),
        start_time=datetime.datetime(appointment.event.date.year, appointment.event.date.month,
                                     appointment.event.date.day, appointment.event.time_of_day.start.hour,
                                     appointment.event.time_of_day.start.minute),
        end_time=datetime.datetime(appointment.event.date.year, appointment.event.date.month,
                                   appointment.event.date.day, appointment.event.time_of_day.end.hour,
                                   appointment.event.time_of_day.end.minute)
    )
    if appointment.event.time_of_day.end < appointment.event.time_of_day.start:
        event_obj.end_time += datetime.timedelta(days=1)
    return event_obj.to_google_event()


def transfer_plan_appointments(plan: schemas.PlanShow):
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    calendars = curr_calendars_handler.get_calenders()
    google_events = []
    user_cal_id__google_events: defaultdict[tuple[str, str], list[dict]] = defaultdict(list)
    for appointment in plan.appointments:
        google_event = create_google_event(appointment)
        google_events.append(google_event)
        user_calendars = (c for c in calendars.values()
                          if c.person_id in {avd.actor_plan_period.person.id for avd in appointment.avail_days})
        for user_calendar in user_calendars:
            user_cal_id__google_events[(user_calendar.id, user_calendar.person_name)].append(google_event)

    team_calendar = next((c for c in calendars.values() if c.team_id == plan.plan_period.team.id), None)
    text_time_span = f'{plan.plan_period.start:%d.%m.%y}-{plan.plan_period.end:%d.%m.%y}'

    if team_calendar:
        signal_handling.handler_google_cal_api.transfer_appointments_progress(
            f'Google-Kalender von: Team {plan.plan_period.team.name}\n'
            f'Planungszeitraum: {text_time_span}\n'
            f'Aktion: Vorhandene Termine werden gelöscht.'
        )
        delete_events_in_range(team_calendar.id,
                               datetime.datetime.combine(plan.plan_period.start, datetime.datetime.min.time()),
                               datetime.datetime.combine(plan.plan_period.end, datetime.datetime.max.time()),
                               service)
        signal_handling.handler_google_cal_api.transfer_appointments_progress(
            f'Google-Kalender von: Team {plan.plan_period.team.name}\n'
            f'Planungszeitraum: {text_time_span}\n'
            f'Aktion: Aktuelle Termine werden übertragen.'
        )
        for google_event in google_events:
            add_event_to_calendar(team_calendar.id, google_event, service)

    for (user_cal_id, user_name), g_events in user_cal_id__google_events.items():
        signal_handling.handler_google_cal_api.transfer_appointments_progress(
            f'Google-Kalender von: {user_name}\n'
            f'Planungszeitraum: {text_time_span}\n'
            f'Aktion: Vorhandene Termine werden gelöscht.'
        )
        delete_events_in_range(user_cal_id,
                               datetime.datetime.combine(plan.plan_period.start, datetime.datetime.min.time()),
                               datetime.datetime.combine(plan.plan_period.end, datetime.datetime.max.time()),
                               service)
        signal_handling.handler_google_cal_api.transfer_appointments_progress(
            f'Google-Kalender von: {user_name}\n'
            f'Planungszeitraum: {text_time_span}\n'
            f'Aktion: Aktuelle Termine werden übertragen.'
        )
        for g_event in g_events:
            add_event_to_calendar(user_cal_id, g_event, service)
