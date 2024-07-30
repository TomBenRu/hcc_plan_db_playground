import pickle
from datetime import date, datetime, timedelta
from typing import Optional, Any, List, Union
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from .enums import TimeOfDay


class ProjectCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    # admin: Optional['Person']
    active: bool


class Project(ProjectCreate):
    id: UUID


class ProjectShow(Project):
    pass


class PersonCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    f_name: str
    l_name: str
    artist_name: Optional[str] = None
    email: EmailStr
    username: str
    password: Optional[str] = None
    project: Optional[Project] = None


class Person(PersonCreate):
    id: UUID
    project: Project


class PersonShow(Person):
    project_of_admin: Optional[Project] = None
    teams_of_dispatcher: List['Team']
    team_of_actor: Optional['Team'] = None

    @field_validator('teams_of_dispatcher')
    def pony_set_to_list(cls, values):
        return [v for v in values]


class TeamCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    dispatcher: Optional[Person] = None


class Team(TeamCreate):
    id: UUID
    dispatcher: Person


class TeamShow(Team):
    pass


class AvailablesCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person: Person
    notes: str


class Availables(AvailablesCreate):
    id: UUID


class AvailablesShow(Availables):
    plan_period: 'PlanPeriod'
    avail_days: List['AvailDay']

    @field_validator('avail_days')
    def pony_set_to_list(cls, values):
        return [v for v in values]


class PlanPeriodCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: date
    end: date
    deadline: date
    notes: Optional[str] = None
    team: Team


class PlanPeriod(PlanPeriodCreate):
    id: UUID
    closed: bool


class PlanPeriodShow(PlanPeriod):
    availabless: List[AvailablesShow]

    def avail_days(self, actor_id: UUID) -> dict[date, Any]:
        av_days = {}
        for available in self.availabless:
            if available.person.id != actor_id:
                continue
            for av_d in available.avail_days:
                av_days[av_d.day] = av_d.time_of_day.value
        return av_days

    def notes_of_availables(self, actor_id: UUID) -> str:
        for avail in self.availabless:
            if avail.person.id == actor_id:
                return avail.notes
        return ''

    @property
    def all_days(self):
        delta: timedelta = self.end - self.start
        all_days: List[datetime.date] = []
        for i in range(delta.days + 1):
            day = self.start + timedelta(days=i)
            all_days.append(day)
        return all_days

    @property
    def calender_week_days(self):
        kw__day_wd = {d.isocalendar()[1]: [] for d in self.all_days}
        for day in self.all_days:
            kw__day_wd[day.isocalendar()[1]].append((day, date.weekday(day)))
        return kw__day_wd

    @field_validator('availabless')
    def pony_set_to_list(cls, values):
        return [v for v in values]


class PlanPerEtFilledIn(BaseModel):
    plan_period: PlanPeriodShow
    filled_in: bool


class AvailDayCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day: date
    time_of_day: TimeOfDay


class AvailDay(AvailDayCreate):
    id: UUID
    created_at: date
    last_modified: datetime
    time_of_day: TimeOfDay
    # availables: Availables


class AvailDayShow(AvailDay):
    pass




ProjectCreate.model_rebuild()
Project.model_rebuild()
PersonShow.model_rebuild()
PersonCreate.model_rebuild()
AvailablesShow.model_rebuild()
TeamShow.model_rebuild()
