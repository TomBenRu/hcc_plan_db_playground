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


def get_curr_team_of_location_at_date(location: schemas.LocationOfWorkShow,
                                      date: datetime.date = None) -> schemas.Team | None:
    """Gibt das Team zurück, welchem die Location an einem Datum zugeordnet war/ist.
    Falls date = None, wird das aktuelle Datum genommen."""
    date = date or datetime.date.today()
    if not location.team_location_assigns:
        curr_team = None
    else:
        for assignment in location.team_location_assigns:
            if assignment.start <= date and ((assignment.end is None) or (date < assignment.end)):
                curr_team = assignment.team
                break
        else:
            curr_team = None

    return curr_team


def get_curr_team_of_person_at_date(person: schemas.PersonShow, date: datetime.date = None) -> schemas.Team | None:
    """Gibt das Team zurück, welchem die Person an einem Datum zugeordnet war/ist.
    Falls date = None, wird das aktuelle Datum genommen."""
    date = date or datetime.date.today()
    if not person.team_actor_assigns:
        curr_team = None
    else:
        for assignment in person.team_actor_assigns:
            if assignment.start <= date and ((assignment.end is None) or (date < assignment.end)):
                curr_team = assignment.team
                break
        else:
            curr_team = None

    return curr_team


def get_next_assignment_of_location(location: schemas.LocationOfWorkShow,
                                    date: datetime.date) -> tuple[schemas.TeamLocationAssign | None, datetime.date] | None:
    assignments = sorted(location.team_location_assigns, key=lambda x: x.start)

    for assignment in assignments:
        if assignment.start <= date and assignment.end is None:
            return
        if assignment.start <= date < assignment.end and not [a for a in assignments if a.start == assignment.end]:
            return None, assignment.end
        if assignment.start > date:
            return assignment, assignment.start


def get_curr_assignment_of_person(person: schemas.PersonShow, date: datetime.date) -> schemas.TeamActorAssign:
    for assignment in person.team_actor_assigns:
        if assignment.start <= date and (assignment.end is None or assignment.end > date):
            return assignment

def get_next_assignment_of_person(person: schemas.PersonShow, date: datetime.date) -> schemas.TeamActorAssign:
    assignments = sorted(person.team_actor_assigns, key=lambda x: x.start)
    for assignment in assignments:
        if assignment.start >= date:
            return assignment


def get_curr_locations_of_team(team: schemas.TeamShow) -> list[schemas.LocationOfWork]:
    assignments = team.team_location_assigns
    if not assignments:
        locations = []
    else:
        locations = [a.location_of_work for a in assignments if not a.end or a.end <= datetime.date.today()]
    return locations


def get_locations_of_team_at_date(team_id:UUID, date: datetime.date) -> list[schemas.LocationOfWork]:
    # sourcery skip: inline-immediately-returned-variable
    team_loc_assignments_at_date = db_services.TeamLocationAssign.get_all_at__date(date, team_id)
    locations_at_date = sorted([tla.location_of_work for tla in team_loc_assignments_at_date
                                if (not tla.location_of_work.prep_delete or tla.location_of_work.prep_delete > date)],
                               key=lambda x: x.name)
    return locations_at_date


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






