import datetime
from typing import Optional, List, Protocol, runtime_checkable, Union, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

from database.enums import Gender


@runtime_checkable
class ModelWithTimeOfDays(Protocol):
    id: UUID
    time_of_days: list[Union['TimeOfDay', 'TimeOfDayShow']]
    time_of_day_standards: list['TimeOfDay']

    def model_copy(self, deep: bool = False) -> Any:
        pass


@runtime_checkable
class ModelWithCombLocPossible(Protocol):
    id: UUID
    project: 'Project'
    combination_locations_possibles: list['CombinationLocationsPossible']
    prep_delete: Optional[datetime.datetime]

    def model_copy(self, deep: bool = False):
        ...


@runtime_checkable
class ModelWithActorLocPrefs(Protocol):
    id: UUID
    actor_location_prefs_defaults: List['ActorLocationPref']
    prep_delete: datetime.datetime

    def model_copy(self, deep: bool = False):
        ...


@runtime_checkable
class ModelWithFlags(Protocol):
    id: UUID
    flags: List['Flag']

    def model_copy(self, deep: bool = False):
        ...


@runtime_checkable
class ModelWithPartnerLocPrefs(Protocol):
    id: UUID
    actor_partner_location_prefs_defaults: list['ActorPartnerLocationPref']
    prep_delete: datetime.datetime

    def model_copy(self, deep: bool = False):
        ...


@runtime_checkable
class ModelWithFixedCast(Protocol):
    id: UUID
    fixed_cast: Optional[str]

    def model_copy(self, deep: bool = False):
        ...


class PersonCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    f_name: str
    l_name: str
    email: EmailStr
    gender: Gender
    phone_nr: str | None
    username: str
    password: str
    address: Optional['AddressCreate']


class Person(PersonCreate):

    id: UUID
    project: 'Project'
    address: 'Address'
    notes: Optional[str] = None
    prep_delete: Optional[datetime.datetime]


class PersonShow(Person):
    requested_assignments: Optional[int]
    team_actor_assigns: List['TeamActorAssign']
    teams_of_dispatcher: list['Team']
    time_of_day_standards: list['TimeOfDay']
    time_of_days: list['TimeOfDay']
    skills: list['Skill']
    combination_locations_possibles: list['CombinationLocationsPossible']
    actor_location_prefs_defaults: list['ActorLocationPref']
    actor_partner_location_prefs_defaults: list['ActorPartnerLocationPref']
    flags: list['Flag']

    @field_validator('teams_of_dispatcher', 'time_of_days', 'time_of_day_standards',
                     'combination_locations_possibles', 'actor_location_prefs_defaults',
                     'actor_partner_location_prefs_defaults', 'team_actor_assigns', 'flags', 'skills')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class ProjectCreate(BaseModel):
    name: str
    active: bool


class Project(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class ProjectShow(Project):

    admin: Optional[Person]
    teams: List['TeamShow']
    persons: List['Person']
    time_of_days: List['TimeOfDay']
    time_of_day_standards: List['TimeOfDay']
    time_of_day_enums: List['TimeOfDayEnum']
    excel_export_settings: Optional['ExcelExportSettings']
    skills: list['Skill']
    flags: list['Flag']

    @field_validator('teams', 'persons', 'time_of_days', 'time_of_day_standards', 'time_of_day_enums',
                     'skills', 'flags')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class TeamCreate(BaseModel):
    name: str
    dispatcher: Optional[Person]
    project: Project


class Team(TeamCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime]


class TeamShow(Team):

    team_actor_assigns: List['TeamActorAssign']
    team_location_assigns: List['TeamLocationAssign']
    plan_periods: List['PlanPeriod']
    combination_locations_possibles: List['CombinationLocationsPossible']
    excel_export_settings: Optional['ExcelExportSettings']

    @field_validator('plan_periods', 'combination_locations_possibles', 'team_actor_assigns',
                     'team_location_assigns')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class PlanPeriodCreate(BaseModel):
    start: datetime.date
    end: datetime.date
    deadline: datetime.date
    notes: Optional[str]
    remainder: bool
    team: Team


class PlanPeriod(PlanPeriodCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime] = None


class PlanPeriodShow(PlanPeriod):

    team: Team
    fixed_cast: Optional[str] = None
    actor_plan_periods: List['ActorPlanPeriod']
    location_plan_periods: List['LocationPlanPeriod']
    project: Project

    @field_validator('actor_plan_periods', 'location_plan_periods')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class ActorPlanPeriodCreate(BaseModel):
    notes: Optional[str] = None
    plan_period: PlanPeriod
    person: Person


class ActorPlanPeriodUpdate(BaseModel):
    id: UUID
    notes: Optional[str] = None


class ActorPlanPeriod(ActorPlanPeriodCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime] = None


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

    @field_validator('time_of_days', 'avail_days', 'time_of_day_standards',
                     'combination_locations_possibles', 'actor_partner_location_prefs_defaults',
                     'actor_location_prefs_defaults')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime.datetime
    last_modified: datetime.datetime
    nr_avail_day_groups: Optional[int]


class AvailDayGroupShow(AvailDayGroup):
    pass


class AvailDayCreate(BaseModel):
    date: datetime.date
    actor_plan_period: ActorPlanPeriod
    time_of_day: 'TimeOfDay'


class AvailDay(AvailDayCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime]
    project: Project
    avail_day_group: AvailDayGroup
    time_of_days: List['TimeOfDay']
    combination_locations_possibles: List['CombinationLocationsPossible']
    actor_partner_location_prefs_defaults: List['ActorPartnerLocationPref']
    actor_location_prefs_defaults: List['ActorLocationPref']

    @field_validator('time_of_days', 'combination_locations_possibles',
                     'actor_partner_location_prefs_defaults', 'actor_location_prefs_defaults')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class AvailDayShow(AvailDay):

    skills: list['Skill']

    @field_validator('time_of_days', 'combination_locations_possibles',
                     'actor_partner_location_prefs_defaults', 'actor_location_prefs_defaults', 'skills')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class TimeOfDayCreate(BaseModel):
    # id: UUID | None = None
    name: str
    time_of_day_enum: 'TimeOfDayEnum'
    project_standard: Optional[Project] = None
    start: datetime.time
    end: datetime.time


class TimeOfDay(TimeOfDayCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime]
    project: Project
    project_standard: Optional[Project]


class TimeOfDayShow(TimeOfDay):

    project_defaults: Optional[Project]
    persons_defaults: List[Person]
    actor_plan_periods_defaults: List[ActorPlanPeriod]
    location_plan_periods_defaults: List['LocationPlanPeriod']
    avail_days_defaults: List[AvailDay]
    locations_of_work_defaults: List['LocationOfWork']
    events_defaults: List['Event']

    @field_validator('persons_defaults', 'actor_plan_periods_defaults', 'location_plan_periods_defaults',
                     'avail_days_defaults', 'locations_of_work_defaults', 'events_defaults')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class TimeOfDayEnumCreate(BaseModel):
    name: str
    abbreviation: str
    time_index: int
    project: Project


class TimeOfDayEnum(TimeOfDayEnumCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class TimeOfDayEnumShow(TimeOfDayEnum):

    time_of_days: List[TimeOfDay]

    @field_validator('time_of_days')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class LocationOfWorkCreate(BaseModel):
    name: str
    address: Optional['AddressCreate']
    nr_actors: int = 2


class LocationOfWork(LocationOfWorkCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    address: 'Address'
    notes: Optional[str]
    project: Project
    prep_delete: Optional[datetime.datetime]


class LocationOfWorkShow(LocationOfWork):

    team_location_assigns: List['TeamLocationAssign']
    fixed_cast: Optional[str] = None
    time_of_days: List[TimeOfDay]
    time_of_day_standards: list[TimeOfDay]
    skill_groups: list['SkillGroup']

    @field_validator('time_of_days', 'time_of_day_standards', 'team_location_assigns', 'skill_groups')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class TeamActorAssignCreate(BaseModel):
    start: Optional[datetime.date]
    end: Optional[datetime.date]
    person: Person
    team: Team


class TeamActorAssign(TeamActorAssignCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    start: datetime.date


class TeamActorAssignShow(TeamActorAssign):
    pass


class TeamLocationAssignCreate(BaseModel):
    start: Optional[datetime.date]
    end: Optional[datetime.date]
    location_of_work: LocationOfWork
    team: Team


class TeamLocationAssign(TeamLocationAssignCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    start: datetime.date


class TeamLocationAssignShow(TeamLocationAssign):
    pass


class AddressCreate(BaseModel):
    street: str = ''
    postal_code: str = ''
    city: str = ''


class Address(AddressCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project: Project


class AddressShow(Address):
    pass


class EventCreate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    location_plan_period: 'LocationPlanPeriod'
    date: datetime.date
    time_of_day: TimeOfDay
    nr_actors: Optional[int] = 2
    fixed_cast: Optional[str] = None
    flags: List['Flag']


class Event(EventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime]

    @field_validator('flags')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class EventShow(Event):

    event_group: 'EventGroup'
    skill_groups: list['SkillGroup']

    @field_validator('flags', 'skill_groups')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class EventGroupCreate(BaseModel):
    location_plan_period: Optional['LocationPlanPeriod']
    same_day_cast_pref: int
    # Wenn am gleichen Tag mehrere Events der gleichen Location stattfinden bedeuten:
    # 0: beliebige Besetzungen, 1: möglichsts die gleiche Besetzung, 2 unbedingt die gleiche Besetzung.
    same_group_cast_pref: int
    # Gibt an, ob innerhalb einer Eventgroup die gleiche Besetzung präferiert werden soll.
    # Gewichtungen wie same_day_cast_pref
    nr_event_groups: Optional[int] = None
    # Falls alle Eventgroups innerhalbEventgroup stattfinden sollen, entspricht der Wert genau dieser Anzahl
    # (alternativ: None).
    # Optional kann der Wert von nr_eventgroups auch geringer sein.
    event_group: Optional['EventGroup']
    event: Optional[Event]
    variation_weight: int = 1


class EventGroup(EventGroupCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class EventGroupShow(EventGroup):
    pass


class LocationPlanPeriodCreate(BaseModel):
    notes: Optional[str]
    plan_period: PlanPeriod
    location_of_work: LocationOfWork
    nr_actors: Optional[int]


class LocationPlanPeriod(LocationPlanPeriodCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class LocationPlanPeriodShow(LocationPlanPeriod):
    time_of_days: List[TimeOfDay]
    time_of_day_standards: List[TimeOfDay]
    team: Team
    events: List[Event]
    fixed_cast: Optional[str] = None
    project: Project

    @field_validator('time_of_days', 'time_of_day_standards', 'events')
    def set_to_list(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class AppointmentCreate(BaseModel):
    notes: str = ''
    avail_days: List[AvailDay]
    event: Event


class Appointment(AppointmentCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID

    @field_validator('avail_days')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class AppointmentShow(Appointment):
    pass

    @field_validator('avail_days')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class ActorPartnerLocationPrefCreate(BaseModel):
    score: float
    person: Person
    partner: Person
    location_of_work: LocationOfWork


class ActorPartnerLocationPref(ActorPartnerLocationPrefCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    score: float
    prep_delete: Optional[datetime.datetime]


class ActorPartnerLocationPrefShow(ActorPartnerLocationPref):
    person_default: Optional[Person]
    actor_plan_periods_defaults: list[ActorPlanPeriod]
    avail_days_defaults: list[AvailDay]

    @field_validator('actor_plan_periods_defaults', 'avail_days_defaults')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class ActorLocationPrefCreate(BaseModel):
    score: Optional[float]
    person: Person
    location_of_work: LocationOfWork


class ActorLocationPref(ActorLocationPrefCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project: Project
    prep_delete: Optional[datetime.datetime]


class ActorLocationPrefShow(ActorLocationPref):
    pass


class FlagCreate(BaseModel):
    category: Optional[str]
    name: str


class Flag(FlagCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project: Project


class FlagShow(Flag):
    pass


class SkillCreate(BaseModel):
    name: str
    level: int


class Skill(SkillCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime.datetime
    last_modified: datetime.datetime
    prep_delete: datetime.datetime
    project: Project

    def before_update(self):
        self.last_modified = datetime.datetime.utcnow()


class SkillShow(Skill):
    id: UUID
    persons: list[Person]
    avail_days: list[AvailDay]
    skill_groups: list['SkillGroup']

    def before_update(self):
        self.last_modified = datetime.datetime.utcnow()

    @field_validator('persons', 'avail_days', 'skill_groups')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class SkillGroupCreate(BaseModel):
    """Legt fest, wie viele der eingesetzten Personen den Skill beherrschen müssen."""
    skill: Skill


class SkillGroup(SkillGroupCreate):
    """Legt fest, wie viele der eingesetzten Personen den Skill beherrschen müssen."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nr_actors: Optional[int] = None
    location_of_work: Optional[LocationOfWork]
    created_at: datetime.datetime
    last_modified: datetime.datetime
    prep_delete: datetime.datetime


class SkillGroupShow(SkillGroup):
    """Legt fest, wie viele der eingesetzten Personen den Skill beherrschen müssen."""
    events: list[Event]

    @field_validator('events')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [v for v in values]


class CombinationLocationsPossibleCreate(BaseModel):
    project: Project
    locations_of_work: List[LocationOfWork]


class CombinationLocationsPossible(CombinationLocationsPossibleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prep_delete: Optional[datetime.datetime]

    @field_validator('locations_of_work')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]


class CombinationLocationsPossibleShow(CombinationLocationsPossible):
    pass


    @field_validator('locations_of_work')
    def set_to_set(cls, values):  # sourcery skip: identity-comprehension
        return [t for t in values]

class PlanCreate(BaseModel):
    name: str
    notes: str = ''
    plan_period: PlanPeriod


class Plan(PlanCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class PlanShow(Plan):
    pass


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
    model_config = ConfigDict(from_attributes=True)

    id: UUID


class ExcelExportSettingsShow(ExcelExportSettings):
    pass


PersonCreate.model_rebuild()
Person.model_rebuild()
PersonShow.model_rebuild()
ProjectShow.model_rebuild()
PlanPeriod.model_rebuild()
PlanPeriodShow.model_rebuild()
ActorPlanPeriodCreate.model_rebuild()
ActorPlanPeriodShow.model_rebuild()
AvailDayGroupCreate.model_rebuild()
AvailDayGroup.model_rebuild()
AvailDayGroupShow.model_rebuild()
AvailDayCreate.model_rebuild()
LocationOfWorkCreate.model_rebuild()
LocationOfWork.model_rebuild()
LocationOfWorkShow.model_rebuild()
TeamShow.model_rebuild()
Event.model_rebuild()
EventCreate.model_rebuild()
EventShow.model_rebuild()
EventGroupCreate.model_rebuild()
EventGroup.model_rebuild()
EventGroupShow.model_rebuild()
TimeOfDayCreate.model_rebuild()
TimeOfDay.model_rebuild()
TimeOfDayShow.model_rebuild()
AvailDay.model_rebuild()
AvailDayShow.model_rebuild()
