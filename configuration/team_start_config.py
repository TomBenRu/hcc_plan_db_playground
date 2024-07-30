import os
from uuid import UUID

import toml
from pydantic import BaseModel
from toml.decoder import TomlDecodeError


class StartConfigTeam(BaseModel):
    team_id: UUID = None
    tabs_planungsmasken: list[UUID] = []
    tabs_plans: list[UUID] = []


class StartConfig(BaseModel):
    default_team_id: UUID = None
    teams: list[StartConfigTeam] = []


class ConfigHandlerToml:
    _config_file_path = os.path.join(os.path.dirname(__file__), 'team_start_config.toml')
    _start_config: StartConfig | None = None

    @staticmethod
    def load_config_from_file() -> StartConfig:
        try:
            with open(ConfigHandlerToml._config_file_path, 'r') as f:
                return StartConfig.model_validate(toml.load(f))
        except FileNotFoundError:
            return StartConfig()
        except TomlDecodeError:
            return StartConfig()

    @staticmethod
    def save_config_to_file(config: StartConfig):
        ConfigHandlerToml._start_config = config
        with open(ConfigHandlerToml._config_file_path, 'w') as f:
            toml.dump(config.model_dump(mode='json'), f)

    @staticmethod
    def get_start_config() -> StartConfig:
        if ConfigHandlerToml._start_config is None:
            ConfigHandlerToml._start_config = ConfigHandlerToml.load_config_from_file()
        return ConfigHandlerToml._start_config

    @staticmethod
    def get_start_config_for_team(team_id: UUID) -> StartConfigTeam:
        start_config = ConfigHandlerToml.get_start_config()
        for team in start_config.teams:
            if team.team_id == team_id:
                return team
        return StartConfigTeam()

    @staticmethod
    def save_config_for_team(team_id: UUID, config: StartConfigTeam):
        start_config = ConfigHandlerToml.get_start_config()
        for i, team in enumerate(start_config.teams):
            if team.team_id == team_id:
                start_config.teams[i] = config
                break
        else:
            start_config.teams.append(config)
        start_config.default_team_id = team_id
        ConfigHandlerToml.save_config_to_file(start_config)


curr_start_config_handler = ConfigHandlerToml
