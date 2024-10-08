import os
from uuid import UUID

import toml
from pydantic import BaseModel
from toml.decoder import TomlDecodeError


class StartConfigTeam(BaseModel):
    team_id: UUID | None = None
    current_index_left_tabs: int = 0
    current_index_planungsmasken_tabs: int = 0
    current_index_plans_tabs: int = 0
    tabs_planungsmasken: dict[UUID, dict[str, UUID | int | None]] = {}
    tabs_plans: list[UUID] = []


class StartConfig(BaseModel):
    project_id: UUID | None = None
    default_team_id: UUID | None = None
    teams: list[StartConfigTeam] = []


class ConfigHandlerToml:
    def __init__(self):
        self._config_file_path = os.path.join(os.path.dirname(__file__), 'team_start_config.toml')
        self._start_config: StartConfig | None = None

    def load_config_from_file(self) -> StartConfig:
        try:
            with open(self._config_file_path, 'r') as f:
                return StartConfig.model_validate(toml.load(f))
        except FileNotFoundError:
            return StartConfig()
        except TomlDecodeError:
            return StartConfig()

    def save_config_to_file(self, config: StartConfig):
        self._start_config = config
        with open(self._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    def get_start_config(self) -> StartConfig:
        if self._start_config is None:
            self._start_config = self.load_config_from_file()
        return self._start_config

    def get_start_config_for_team(self, team_id: UUID) -> StartConfigTeam:
        start_config = self.get_start_config()
        for team in start_config.teams:
            if team.team_id == team_id:
                return team
        return StartConfigTeam()

    def save_config_for_team(self, team_id: UUID, config: StartConfigTeam):
        start_config = self.get_start_config()
        for i, team in enumerate(start_config.teams):
            if team.team_id == team_id:
                start_config.teams[i] = config
                break
        else:
            start_config.teams.append(config)
        start_config.default_team_id = team_id
        self.save_config_to_file(start_config)


curr_start_config_handler = ConfigHandlerToml()
