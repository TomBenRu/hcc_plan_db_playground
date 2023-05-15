import datetime
from uuid import UUID

from database import schemas, db_services


def get_curr_team_of_location(location: schemas.LocationOfWorkShow) -> schemas.Team | None:
    if location.team_location_assigns:
        latest_assignment = max(location.team_location_assigns, key=lambda x: x.start)
        if latest_assignment.end and latest_assignment.end <= datetime.date.today():
            curr_team = None
        else:
            curr_team = latest_assignment.team
    else:
        curr_team = None
    return curr_team


def get_curr_team_of_person(person: schemas.PersonShow) -> schemas.Team | None:
    if person.team_actor_assigns:
        latest_assignment = max(person.team_actor_assigns, key=lambda x: x.start)
        if latest_assignment.end and latest_assignment.end <= datetime.date.today():
            curr_team = None
        else:
            curr_team = latest_assignment.team
    else:
        curr_team = None
    return curr_team


def get_curr_locations_of_team(team: schemas.TeamShow) -> list[schemas.LocationOfWork]:
    assignments = team.team_location_assigns
    if not assignments:
        locations = []
    else:
        locations = [a.location_of_work for a in assignments if not a.end or a.end <= datetime.date.today()]
    return locations


def get_curr_persons_of_team(team: schemas.TeamShow) -> list[schemas.Person]:
    assignments = team.team_actor_assigns
    if not assignments:
        persons = []
    else:
        persons = [a.person for a in assignments if not a.end or a.end <= datetime.date.today()]
    return persons


def get_persons_of_team_at_date(team_id: UUID, date: datetime.date) -> list[schemas.Person]:
    team_actor_assignments_at_date = db_services.TeamActorAssign.get_all_at__date(date, team_id)
    persons_at_date = sorted([taa.person for taa in team_actor_assignments_at_date
                              if (not taa.person.prep_delete or taa.person.prep_delete > date)],
                             key=lambda x: x.f_name)
    return persons_at_date


def get_locations_of_team_at_date(team_id:UUID, date: datetime.date) -> list[schemas.LocationOfWork]:
    team_loc_assignments_at_date = db_services.TeamLocationAssign.get_all_at__date(date, team_id)
    locations_at_date = sorted([tla.location_of_work for tla in team_loc_assignments_at_date
                                if (not tla.location_of_work.prep_delete or tla.location_of_work.prep_delete > date)],
                               key=lambda x: x.name)
    return locations_at_date






