import datetime
import os
from uuid import UUID

from pydantic import BaseModel, Field
import toml

from configuration.project_paths import curr_user_path_handler


class PlanningRules(BaseModel):
    first_day: datetime.date | None = None
    time_of_day_id: UUID | None = None
    interval: int | None = None
    repeat: int | None = None
    num_events: int | None = None


class EventPlanningRules(BaseModel):
    location_of_work_id: UUID
    planning_rules: list[PlanningRules] = Field(default_factory=list)
    cast_rule_at_same_day_id: UUID | None = None
    same_partial_days_for_all_rules: bool = False


class EventPlanningRulesHandlerToml:
    def __init__(self):
        self._toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'event_planning_rules')
        self._toml_file_path = os.path.join(self._toml_dir, 'event_planning_rules.toml')
        self._event_planning_rules: dict[str, EventPlanningRules] | None = None
        self._check_toml_dir()

    def _check_toml_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def _load_toml_file(self):
        if not os.path.exists(self._toml_file_path):
            self._event_planning_rules = {}
            return
        with open(self._toml_file_path, 'r') as f:
            epr_dict = toml.load(f)
            self._event_planning_rules = {k: EventPlanningRules.model_validate(epr) for k, epr in epr_dict.items()}

    def _save_to_toml_file(self):
        with open(self._toml_file_path, 'w') as f:
            toml.dump({k: epr.model_dump(mode='json') for k, epr in self._event_planning_rules.items()}, f)

    def set_event_planning_rules(self, event_planing_rules: EventPlanningRules):
        if self._event_planning_rules is None:
            self._load_toml_file()
        self._event_planning_rules[str(event_planing_rules.location_of_work_id)] = event_planing_rules
        self._save_to_toml_file()

    def get_event_planning_rules(self, location_of_work_id: UUID) -> EventPlanningRules | None:
        if self._event_planning_rules is None:
            self._load_toml_file()
        return self._event_planning_rules.get(str(location_of_work_id))


current_event_planning_rules_handler = EventPlanningRulesHandlerToml()


