from datetime import date, time, datetime
from typing import Optional, List, Protocol, runtime_checkable, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, validator

from database.enums import Gender


@runtime_checkable
class ModelWithTimeOfDays(Protocol):
    id: UUID
    time_of_days: list[Union['TimeOfDay', 'TimeOfDayShow']]
    time_of_day_standards: list['TimeOfDay']


@runtime_checkable
class ModelWithCombLocPossible(Protocol):
    id: UUID
    project: 'Project'
    combination_locations_possibles: list['CombinationLocationsPossible']
    prep_delete: Optional[datetime]

    def copy(self, deep: bool):
        ...


@runtime_checkable
class ModelWithActorLocPrefs(Protocol):
    id: UUID
    actor_location_prefs_defaults: List['ActorLocationPref']
    prep_delete: date

    def copy(self, deep=bool):
        ...


@runtime_checkable
class ModelWithPartnerLocPrefs(Protocol):
    id: UUID
    actor_partner_location_prefs_defaults: list['ActorPartnerLocationPref']
    prep_delete: date

    def copy(self, deep=bool):
        ...


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
    project: 'Project'
    address: Optional['Address']
    notes: Optional[str]
    prep_delete: Optional[datetime]

    class Config:
        orm_mode = True


class PersonShow(Person):
    requested_assignments: Optional[int]
    project: 'Project'
    team_actor_assigns: List['TeamActorAssign']
    teams_of_dispatcher: list['Team']
    time_of_day_standards: list['TimeOfDay']
    time_of_days: list['TimeOfDay']
    combination_locations_possibles: list['CombinationLocationsPossible']
    actor_location_prefs_defaults: list['ActorLocationPref']
    actor_partner_location_prefs_defaults: list['ActorPartnerLocationPref']

    @validator('teams_of_dispatcher', 'time_of_days', 'time_of_day_standards', 'combination_locations_possibles',
               'actor_location_prefs_defaults', 'actor_partner_location_prefs_defaults', 'team_actor_assigns',
               pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]

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
    time_of_days: List['TimeOfDay']
    time_of_day_standards: List['TimeOfDay']
    time_of_day_enums: List['TimeOfDayEnum']
    excel_export_settings: Optional['ExcelExportSettings']

    @validator('teams', 'persons', 'time_of_days', 'time_of_day_standards', 'time_of_day_enums',
               pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

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
    team_actor_assigns: List['TeamActorAssign']
    team_location_assigns: List['TeamLocationAssign']
    plan_periods: List['PlanPeriod']
    combination_locations_possibles: List['CombinationLocationsPossible']
    excel_export_settings: Optional['ExcelExportSettings']

    @validator('plan_periods', 'combination_locations_possibles', 'team_actor_assigns', 'team_location_assigns',
               pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]

    class Config:
        orm_mode = True


class PlanPeriodCreate(BaseModel):
    start: date
    end: date
    deadline: date
    notes: Optional[str]
    remainder: bool
    team: Team


class PlanPeriod(PlanPeriodCreate):
    id: UUID
    prep_delete: Optional[date]

    class Config:
        orm_mode = True


class PlanPeriodShow(PlanPeriod):
    team: Team
    fixed_cast: Optional[str]
    actor_plan_periods: List['ActorPlanPeriod']
    project: Project

    @validator('actor_plan_periods', pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]

    class Config:
        orm_mode = True


class ActorPlanPeriodCreate(BaseModel):
    notes: Optional[str]
    plan_period: PlanPeriod
    person: Person


class ActorPlanPeriodUpdate(BaseModel):
    id: UUID
    notes: Optional[str]


class ActorPlanPeriod(ActorPlanPeriodCreate):
    id: UUID
    prep_delete: Optional[datetime]

    class Config:
        orm_mode = True


class ActorPlanPeriodShow(ActorPlanPeriod):
    id: UUID
    person: Person
    time_of_days: List['TimeOfDay']
    time_of_day_standards: List['TimeOfDay']
    avail_days: List['AvailDay']
    combination_locations_possibles: List['CombinationLocationsPossible']
    actor_partner_location_prefs_defaults: List['ActorPartnerLocationPref']
    actor_location_prefs_defaults: List['ActorLocationPref']
    team: Team
    project: Project

    @validator('time_of_days', 'avail_days', 'time_of_day_standards', 'combination_locations_possibles',
               'actor_partner_location_prefs_defaults', 'actor_location_prefs_defaults', pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class AvailDayGroupCreate(BaseModel):
    """AvailDayGroups können entweder genau 1 AvailDay beinhalten, oden 1 oder mehrere AvailDayGroups.
       Jede AvailDayGroup ist entweder genau 1 Eventgroup zugeordnet oder genau einer Location PlanPeriod."""
    actor_plan_period: Optional[ActorPlanPeriod]
    nr_avail_day_groups: Optional[int]
    # Falls alle AvailDayGroup innerhalb der AvailDayGroup stattfinden sollen, entspricht der Wert genau dieser Anzahl
    # (alternativ: None).
    # Optional kann der Wert von nr_avail_day_groups auch geringer sein.
    avail_day_group: Optional['AvailDayGroup']
    variation_weight: int = 1
    # Falls weniger AvailDayGroups in einer AvailDayGroup als nr_avail_day_groups der AvailDayGroup, können den Groups
    # unterschiedliche Gewichtungen verliehen werden.


class AvailDayGroup(AvailDayGroupCreate):
    id: UUID
    created_at: datetime
    last_modified: datetime
    nr_avail_day_groups: Optional[int]

    class Config:
        orm_mode = True


class AvailDayGroupShow(AvailDayGroup):

    class Config:
        orm_mode = True


class AvailDayCreate(BaseModel):
    day: date
    actor_plan_period: ActorPlanPeriod
    time_of_day: 'TimeOfDay'


class AvailDay(AvailDayCreate):
    id: UUID
    prep_delete: Optional[datetime]
    project: Project
    avail_day_group: AvailDayGroup
    time_of_days: List['TimeOfDay']
    combination_locations_possibles: List['CombinationLocationsPossible']
    actor_partner_location_prefs_defaults: List['ActorPartnerLocationPref']
    actor_location_prefs_defaults: List['ActorLocationPref']

    @validator('time_of_days', 'combination_locations_possibles', 'actor_partner_location_prefs_defaults',
               'actor_location_prefs_defaults', pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class AvailDayShow(AvailDay):
    id: UUID
    project: Project

    @validator('time_of_days', 'combination_locations_possibles', 'actor_partner_location_prefs_defaults',
               'actor_location_prefs_defaults', pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class TimeOfDayCreate(BaseModel):
    # id: UUID | None = None
    name: str
    time_of_day_enum: 'TimeOfDayEnum'
    project_standard: Optional[Project]
    start: time
    end: time


class TimeOfDay(TimeOfDayCreate):
    id: UUID
    prep_delete: Optional[datetime]
    project: Project
    project_standard: Optional[Project]

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
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class TimeOfDayEnumCreate(BaseModel):
    name: str
    abbreviation: str
    time_index: int
    project: Project


class TimeOfDayEnum(TimeOfDayEnumCreate):
    id: UUID

    class Config:
        orm_mode = True


class TimeOfDayEnumShow(TimeOfDayEnum):
    time_of_days: List[TimeOfDay]

    @validator('time_of_days', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]

    class Config:
        orm_mode = True


class LocationOfWorkCreate(BaseModel):
    name: str
    address: Optional['AddressCreate']
    nr_actors: int = 2


class LocationOfWork(LocationOfWorkCreate):
    id: UUID
    address: Optional['Address']
    project: Project
    prep_delete: Optional[datetime]

    class Config:
        orm_mode = True


class LocationOfWorkShow(LocationOfWork):
    nr_actors: int
    team_location_assigns: List['TeamLocationAssign']
    fixed_cast: Optional[str]
    time_of_days: List[TimeOfDay]
    time_of_day_standards: list[TimeOfDay]

    @validator('time_of_days', 'time_of_day_standards', 'team_location_assigns', pre=True, allow_reuse=True)
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class TeamActorAssignCreate(BaseModel):
    start: Optional[date]
    end: Optional[date]
    person: Person
    team: Team


class TeamActorAssign(TeamActorAssignCreate):
    id: UUID
    start: date

    class Config:
        orm_mode = True


class TeamActorAssignShow(TeamActorAssign):
    pass

    class Config:
        orm_mode = True


class TeamLocationAssignCreate(BaseModel):
    start: Optional[date]
    end: Optional[date]
    location_of_work: LocationOfWork
    team: Team


class TeamLocationAssign(TeamLocationAssignCreate):
    id: UUID
    start: date

    class Config:
        orm_mode = True


class TeamLocationAssignShow(TeamLocationAssign):
    pass

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
    event_group: 'EventGroup'
    date: date
    time_of_day: TimeOfDay
    nr_actors: Optional[int]
    fixed_cast: Optional[str]
    flags: List['Flag']


class Event(EventCreate):
    id: UUID

    @validator('flags', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class EventShow(Event):

    @validator('flags', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class EventGroupCreate(BaseModel):
    location_plan_period: Optional['LocationPlanPeriod']
    same_day_cast_pref: int
    # Wenn am gleichen Tag mehrere Events der gleichen Location stattfinden bedeuten:
    # 0: beliebige Besetzungen, 1: möglichsts die gleiche Besetzung, 2 unbedingt die gleiche Besetzung.
    same_group_cast_pref: int
    # Gibt an, ob innerhalb einer Eventgroup die gleiche Besetzung präferiert werden soll.
    # Gewichtungen wie same_day_cast_pref
    nr_eventgroups: Optional[int]
    # Falls alle Eventgroups innerhalbEventgroup stattfinden sollen, entspricht der Wert genau dieser Anzahl
    # (alternativ: None).
    # Optional kann der Wert von nr_eventgroups auch geringer sein.
    event_group: Optional['EventGroup']
    event: Optional[Event]
    variation_weight: int = 1


class EventGroup(EventGroupCreate):
    id: UUID

    class Config:
        orm_mode = True


class EventGroupShow(EventGroup):
    ...

    class Config:
        orm_mode = True


class LocationPlanPeriodCreate(BaseModel):
    notes: Optional[str]
    plan_period: PlanPeriod
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
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class AppointmentShow(Appointment):

    @validator('avail_days', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
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
    score: float
    prep_delete: Optional[date]

    class Config:
        orm_mode = True


class ActorPartnerLocationPrefShow(ActorPartnerLocationPref):
    person_default: Optional[Person]
    actor_plan_periods_defaults: list[ActorPlanPeriod]
    avail_days_defaults: list[AvailDay]

    @validator('actor_plan_periods_defaults', 'avail_days_defaults', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]

    class Config:
        orm_mode = True


class ActorLocationPrefCreate(BaseModel):
    score: Optional[float]
    person: Person
    location_of_work: LocationOfWork


class ActorLocationPref(ActorLocationPrefCreate):
    id: UUID
    project: Project
    prep_delete: Optional[datetime]

    class Config:
        orm_mode = True


class ActorLocationPrefShow(ActorLocationPref):
    ...

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


class CombinationLocationsPossibleCreate(BaseModel):
    project: Project
    locations_of_work: List[LocationOfWork]


class CombinationLocationsPossible(CombinationLocationsPossibleCreate):
    id: UUID
    prep_delete: Optional[datetime]

    @validator('locations_of_work', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class CombinationLocationsPossibleShow(CombinationLocationsPossible):

    @validator('locations_of_work', pre=True, allow_reuse=True)
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

    class Config:
        orm_mode = True


class PlanCreate(BaseModel):
    name: str
    notes: str = ''
    plan_period: PlanPeriod


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
PlanPeriod.update_forward_refs(**locals())
PlanPeriodShow.update_forward_refs(**locals())
ActorPlanPeriodCreate.update_forward_refs(**locals())
ActorPlanPeriodShow.update_forward_refs(**locals())
AvailDayGroupCreate.update_forward_refs(**locals())
AvailDayGroup.update_forward_refs(**locals())
AvailDayGroupShow.update_forward_refs(**locals())
AvailDayCreate.update_forward_refs(**locals())
LocationOfWorkCreate.update_forward_refs(**locals())
LocationOfWork.update_forward_refs(**locals())
LocationOfWorkShow.update_forward_refs(**locals())
TeamShow.update_forward_refs(**locals())
EventCreate.update_forward_refs(**locals())
EventGroupCreate.update_forward_refs(**locals())
EventGroup.update_forward_refs(**locals())
EventGroupShow.update_forward_refs(**locals())
TimeOfDayCreate.update_forward_refs()
TimeOfDay.update_forward_refs()
TimeOfDayShow.update_forward_refs(**locals())
AvailDay.update_forward_refs()
AvailDayShow.update_forward_refs()

