from datetime import date, time, datetime
from typing import Optional, List, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, EmailStr, validator

from database.enums import Gender


@runtime_checkable
class ModelWithTimeOfDays(Protocol):
    time_of_days: list['TimeOfDay']


@runtime_checkable
class ModelWithFixedCast(Protocol):
    fixed_cast: Optional[str]


class PersonCreate(BaseModel):
    f_name: str
    l_name: str
    email: EmailStr
    gender: Gender
    phone_nr: str | None
    username: str
    password: str
    address: Optional['AddressCreate']

    class Config:
        orm_mode = True


class Person(PersonCreate):
    id: UUID
    address: Optional['Address']

    class Config:
        orm_mode = True


class PersonShow(Person):
    project: 'Project'
    team_of_actor: Optional['Team']

    class Config:
        orm_mode = True


class ProjectCreate(BaseModel):
    name: str
    active: bool


class Project(ProjectCreate):
    id: UUID

    class Config:
        orm_mode = True


class ProjectShow(Project):
    admin: Optional[Person]
    teams: List['TeamShow']
    persons: List['Person']
    time_of_days_default: List['TimeOfDayShow']
    excel_export_settings: Optional['ExcelExportSettings']

    @validator('teams', pre=True, allow_reuse=True)
    def teams_set_to_list(cls, values):
        return [t for t in values]

    @validator('persons', pre=True, allow_reuse=True)
    def persons_set_to_list(cls, values):
        return [p for p in values]

    @validator('time_of_days_default', pre=True, allow_reuse=True)
    def tim_of_days_set_to_list(cls, values):
        return [p for p in values]

    class Config:
        orm_mode = True


class TeamCreate(BaseModel):
    name: str
    dispatcher: Optional[Person]
    project: Project


class Team(TeamCreate):
    id: UUID
    prep_delete: Optional[datetime]

    class Config:
        orm_mode = True


class TeamShow(Team):
    excel_export_settings: Optional['ExcelExportSettings']

    class Config:
        orm_mode = True


class PlanPeriodCreate(BaseModel):
    start: date
    end: date
    deadline: date
    notes: str = ''
    team: Team


class Planperiod(PlanPeriodCreate):
    id: UUID

    class Config:
        orm_mode = True


class PlanPeriodShow(Planperiod):
    fixed_cast: Optional[str]

    class Config:
        orm_mode = True


class ActorPlanPeriodCreate(BaseModel):
    notes: str = ''
    plan_period: Planperiod
    person: Person


class ActorPlanPeriod(ActorPlanPeriodCreate):
    id: UUID
    combination_locations_possibles: List['CombinationLocationsPossible']
    actor_partner_location_prefs: List['ActorPartnerLocationPref']

    @validator('combination_locations_possibles', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    @validator('actor_partner_location_prefs', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class ActorPlanPeriodShow(ActorPlanPeriodCreate):
    id: UUID
    avail_days: List['AvailDay']

    @validator('combination_locations_possibles', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    @validator('actor_partner_location_prefs', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    @validator('avail_days', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class AvailDayCreate(BaseModel):
    day: date
    actor_plan_period: ActorPlanPeriod
    time_of_day: 'TimeOfDay'


class AvailDay(AvailDayCreate):
    id: UUID
    time_of_days: List['TimeOfDay']
    combination_locations_possibles: List['CombinationLocationsPossible']

    @validator('time_of_days', pre=True, allow_reuse=True)
    def set_to_list(cls, values):
        return [t for t in values]

    @validator('combination_locations_possibles', pre=True, allow_reuse=True)
    def set_to_list(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class AvailDayShow(AvailDayCreate):
    id: UUID

    class Config:
        orm_mode = True


class TimeOfDayCreate(BaseModel):
    name: str
    start: time
    end: time


class TimeOfDay(TimeOfDayCreate):
    id: UUID
    prep_delete: Optional[datetime]
    project: Project

    class Config:
        orm_mode = True


class TimeOfDayShow(TimeOfDay):
    project_defaults: Optional[Project]
    persons_defaults: List[Person]
    actor_plan_periods_defaults: List[ActorPlanPeriod]
    location_plan_periods_defaults: List['LocationPlanPeriod']
    avail_days_defaults: List[AvailDay]
    locations_of_work_defaults: List['LocationOfWork']
    events_defaults: List['Event']

    @validator('persons_defaults', 'actor_plan_periods_defaults', 'location_plan_periods_defaults',
               'avail_days_defaults', 'locations_of_work_defaults', 'events_defaults', pre=True, allow_reuse=True)
    def set_to_list(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class LocationOfWorkCreate(BaseModel):
    name: str
    address: Optional['AddressCreate']
    team: Optional[Team] = None
    nr_actors: int = 2


class LocationOfWork(LocationOfWorkCreate):
    id: UUID
    address: Optional['Address']
    project: Project

    class Config:
        orm_mode = True


class LocationOfWorkShow(LocationOfWork):
    team: Optional[Team]
    nr_actors: int
    fixed_cast: Optional[str]
    time_of_days: List[TimeOfDayShow]

    @validator('time_of_days', pre=True, allow_reuse=True)
    def set_to_list(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class AddressCreate(BaseModel):
    street: str
    postal_code: str
    city: str


class Address(AddressCreate):
    id: UUID
    project: Project

    class Config:
        orm_mode = True


class AddressShow(Address):

    class Config:
        orm_mode = True


class EventCreate(BaseModel):
    name: Optional[str]
    notes: Optional[str]
    location_plan_period: 'LocationPlanPeriod'
    date: date
    time_of_day: TimeOfDay
    nr_actors: Optional[int]
    fixed_cast: Optional[str]
    flags: List['Flag']
    variation_event_group: Optional['VariationEventGroup']
    variation_weight: Optional[int]


class Event(EventCreate):
    id: UUID

    @validator('flags', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class EventShow(Event):

    @validator('flags', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class LocationPlanPeriodCreate(BaseModel):
    notes: str = ''
    plan_period: Planperiod
    location_of_work: LocationOfWork
    nr_actors: Optional[int]


class LocationPlanPeriod(LocationPlanPeriodCreate):
    id: UUID

    class Config:
        orm_mode = True


class LocationPlanPeriodShow(LocationPlanPeriod):

    class Config:
        orm_mode = True


class AppointmentCreate(BaseModel):
    notes: str = ''
    avail_days: List[AvailDay]
    event: Event


class Appointment(AppointmentCreate):
    id: UUID

    @validator('avail_days', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class AppointmentShow(Appointment):

    @validator('avail_days', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class ActorPartnerLocationPrefCreate(BaseModel):
    score: float
    person: Person
    partner: Person
    location_of_work: LocationOfWork


class ActorPartnerLocationPref(ActorPartnerLocationPrefCreate):
    id: UUID

    class Config:
        orm_mode = True


class ActorPartnerLocationPrefShow(ActorPartnerLocationPref):

    class Config:
        orm_mode = True


class FlagCreate(BaseModel):
    category: Optional[str]
    name: str


class Flag(FlagCreate):
    id: UUID

    class Config:
        orm_mode = True


class FlagShow(Flag):

    class Config:
        orm_mode = True


class VariationEventGroupCreate(BaseModel):
    events: List[Event]


class VariationEventGroup(VariationEventGroupCreate):
    id: UUID

    @validator('events', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class VariationEventGroupShow(VariationEventGroup):

    @validator('events', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class CombinationLocationsPossibleCreate(BaseModel):
    locations_of_work: List[LocationOfWork]


class CombinationLocationsPossible(CombinationLocationsPossibleCreate):
    id: UUID

    @validator('locations_of_work', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class CombinationLocationsPossibleShow(CombinationLocationsPossible):

    @validator('locations_of_work', pre=True, allow_reuse=True)
    def set_to_set(cls, values):
        return [t for t in values]

    class Config:
        orm_mode = True


class PlanCreate(BaseModel):
    name: str
    notes: str = ''
    plan_period: Planperiod


class Plan(PlanCreate):
    id: UUID

    class Config:
        orm_mode = True


class PlanShow(Plan):

    class Config:
        orm_mode = True


class ExcelExportSettingsCreate(BaseModel):
    color_head_weekdays_1: str = "#FFFFFF"
    color_head_weekdays_2: str = "#FFFFFF"
    color_head_locations_1: str = "#FFFFFF"
    color_head_locations_2: str = "#FFFFFF"
    color_day_nrs_1: str = "#FFFFFF"
    color_day_nrs_2: str = "#FFFFFF"
    color_column_kw_1: str = "#FFFFFF"
    color_column_kw_2: str = "#FFFFFF"


class ExcelExportSettings(ExcelExportSettingsCreate):
    id: UUID

    class Config:
        orm_mode = True


class ExcelExportSettingsShow(ExcelExportSettings):

    class Config:
        orm_mode = True


PersonCreate.update_forward_refs(**locals())
Person.update_forward_refs(**locals())
PersonShow.update_forward_refs(**locals())
ProjectShow.update_forward_refs(**locals())
ActorPlanPeriodCreate.update_forward_refs(**locals())
AvailDayCreate.update_forward_refs(**locals())
LocationOfWorkCreate.update_forward_refs(**locals())
LocationOfWork.update_forward_refs(**locals())
LocationOfWorkShow.update_forward_refs(**locals())
TeamShow.update_forward_refs(**locals())
EventCreate.update_forward_refs(**locals())
TimeOfDayShow.update_forward_refs(**locals())

