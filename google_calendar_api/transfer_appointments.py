import datetime

from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError

from configuration.google_calenders import curr_calendars_handler
from database import schemas, db_services
from google_calendar_api.appointments_from_plan import GoogleCalendarEvent
from google_calendar_api.authenticate import authenticate_google
from google_calendar_api.del_calendar_events import delete_events_in_range


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
        description=', '.join(names_of_employees),
        start_time=datetime.datetime(appointment.event.date.year, appointment.event.date.month,
                                     appointment.event.date.day, appointment.event.time_of_day.start.hour,
                                     appointment.event.time_of_day.start.minute),
        end_time=datetime.datetime(appointment.event.date.year, appointment.event.date.month,
                                   appointment.event.date.day, appointment.event.time_of_day.end.hour,
                                   appointment.event.time_of_day.end.minute)
    )
    return event_obj.to_google_event()


def transfer_plan_appointments(plan: schemas.PlanShow):
    calendars = curr_calendars_handler.get_calenders()
    person_ids = db_services.TeamActorAssign.get_all_actor_ids_between_dates(plan.plan_period.team.id,
                                                                             plan.plan_period.start,
                                                                             plan.plan_period.end)
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)

    team_user_calendars = (c for c in calendars.values() if c.person_id in person_ids)
    for c in team_user_calendars:
        delete_events_in_range(c.id,
                               datetime.datetime.combine(plan.plan_period.start, datetime.datetime.min.time()),
                               datetime.datetime.combine(plan.plan_period.end, datetime.datetime.max.time()),
                               service)
    team_calendar = next((c for c in calendars.values() if c.team_id == plan.plan_period.team.id), None)
    delete_events_in_range(team_calendar.id,
                           datetime.datetime.combine(plan.plan_period.start, datetime.datetime.min.time()),
                           datetime.datetime.combine(plan.plan_period.end, datetime.datetime.max.time()),
                           service)
    for appointment in plan.appointments:
        user_calendars = (c for c in calendars.values()
                          if c.person_id in {avd.actor_plan_period.person.id for avd in appointment.avail_days})
        google_event = create_google_event(appointment)

        if team_calendar:
            add_event_to_calendar(team_calendar.id, google_event, service)
        for c in user_calendars:
            add_event_to_calendar(c.id, google_event, service)
