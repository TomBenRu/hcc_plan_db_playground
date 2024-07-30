from typing import Protocol

from pydantic import BaseModel


class ConfigHandler(Protocol):

    @staticmethod
    def load_config_from_file(self) -> BaseModel:
        ...

    @staticmethod
    def save_config_to_file(self, config: BaseModel):
        ...

    @staticmethod
    def get_solver_config(self) -> BaseModel:
        ...
