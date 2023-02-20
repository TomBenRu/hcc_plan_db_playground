from datetime import date, timedelta
from typing import Set, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class PersonCreate(BaseModel):
    f_name: str
    l_name: str
    email: EmailStr
    phone_nr: str | None
    username: str
    password: str
    project: 'Project'


class Person(PersonCreate):
    id: UUID
    address: Optional['Address']


class PersonShow(Person):
    pass


class ProjectCreate(BaseModel):
    name: str
    active: bool


class Project(ProjectCreate):
    id: UUID
    pass


class ProjectShow(Project):
    pass


class TeamCreate(BaseModel):
    name: str
    project: Project


class Team(TeamCreate):
    id: UUID


class TeamShow(Team):
    pass


class PlanPeriodCreate(BaseModel):
    start: date
    end: date
    deadline: date
    notes: str = ''
    team: Team


class Planperiod(PlanPeriodCreate):
    id: UUID


class PlanPeriodShow(Planperiod):
    pass


class ActorPlanPeriodCreate(BaseModel):
    notes: str = ''
    plan_period: Planperiod
    person: Person


class ActorPlanPeriod(ActorPlanPeriodCreate):
    id: UUID
    combination_locations_possibles: Optional[Set['CombinationLocationsPossible']] = None
    actor_partner_location_prefs: Optional[Set['ActorPartnerLocationPref']] = None


class ActorPlanPeriodShow(ActorPlanPeriodCreate):
    id: UUID
    avail_days: Set['AvailDay']


class AvailDayCreate(BaseModel):
    day: date
    actor_plan_period: ActorPlanPeriod
    time_of_day: 'TimeOfDay'


class AvailDay(AvailDayCreate):
    id: UUID
    time_of_days: Set['TimeOfDay']
    combination_locations_possibles: Set['CombinationLocationsPossible']


class AvailDayShow(AvailDayCreate):
    id: UUID


class TimeOfDayCreate(BaseModel):
    name: str
    start: timedelta
    end: timedelta
    project: Project


class TimeOfDay(TimeOfDayCreate):
    id: UUID


class TimeOfDayShow(TimeOfDayCreate):
    pass


class LocationOfWorkCreate(BaseModel):
    name: str
    address: Optional['Address']
    team: Team
    nr_actors: int = 2


class LocationOfWork(LocationOfWorkCreate):
    id: UUID


class LocationOfWorkShow(LocationOfWork):
    pass


class AddressCreate(BaseModel):
    street: str
    postal_code: str
    city: str


class Address(AddressCreate):
    id: UUID


class AddressShow(Address):
    pass


class EventCreate(BaseModel):
    name: Optional[str]
    notes: Optional[str]
    location_plan_period: 'LocationPlanPeriod'
    date: date
    time_of_day: TimeOfDay
    nr_actors: Optional[int]
    fixed_cast: Optional[str]
    flags: Set['Flag']
    variation_event_group: Optional['VariationEventGroup']
    variation_weight: Optional[int]


class Event(EventCreate):
    id: UUID


class EventShow(Event):
    pass





PersonCreate.update_forward_refs(**locals())
ActorPlanPeriodCreate.update_forward_refs(**locals())
