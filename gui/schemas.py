import datetime

from pydantic import BaseModel, Field

from database import schemas


class  RulesData(BaseModel):
    first_day: datetime.date | None = None
    time_of_day: schemas.TimeOfDay | None = None
    interval: int | None = None
    repeat: int | None = None
    num_events: int | None = None

    def __repr__(self):
        return f"RulesData(first_day={self.first_day}, time_of_day={self.time_of_day.name}, interval={self.interval}, repeat={self.repeat}, num_events={self.num_events})"


class Rules(BaseModel):
    rules_data: list[RulesData] = Field(default_factory=list)
    cast_rule_at_same_day: schemas.CastRuleShow | None = None
    same_partial_days_for_all_rules: bool = False
