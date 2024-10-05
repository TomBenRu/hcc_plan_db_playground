import os

import toml
from pydantic import BaseModel
from toml.decoder import TomlDecodeError


class PendingRequestData(BaseModel):
    function: str
    parameters: dict[str, str]


class PendingApiHandlerToml:
    def __init__(self):
        self.toml_dir = 'pending_requests'
        self._toml_file_path = os.path.join(os.path.dirname(__file__), self.toml_dir, 'pending.toml')
        self._pending_operations: list[PendingRequestData] | None = None
        self._check_toml_dir()

    def _check_toml_dir(self):
        if not os.path.exists(os.path.join(os.path.dirname(__file__), self.toml_dir)):
            os.mkdir(os.path.join(os.path.dirname(__file__), self.toml_dir))

    def _load_pending_operations_from_file(self) -> list[PendingRequestData]:
        if self._pending_operations is not None:
            return self._pending_operations
        try:
            with open(self._toml_file_path, 'r') as f:
                self._pending_operations = [PendingRequestData.model_validate(r) for r in toml.load(f)['queue']]
                return self._pending_operations
        except FileNotFoundError or TomlDecodeError:
            self._pending_operations = []
            return []

    def _save_pending_operations_to_file(self):
        with open(self._toml_file_path, 'w') as f:
            toml.dump(
                {'queue': [p.model_dump() for p in self._pending_operations]}, f
            )

    def save_operation_to_file(self, operation: str, parameters: dict[str, str]):
        if self._pending_operations is None:
            self._load_pending_operations_from_file()
        self._pending_operations.append(PendingRequestData(function=operation, parameters=parameters))
        self._save_pending_operations_to_file()

    def get_pending_operations(self) -> list[PendingRequestData]:
        return self._load_pending_operations_from_file()

    def delete_pending_operation(self, operation: str, parameters: dict[str, str]):
        for i, o in enumerate(self._pending_operations):
            if (operation == o.function and len(parameters) == len(o.parameters)
                    and all(o.parameters.get(k) == p for k, p in parameters.items())):
                self._pending_operations.pop(i)
                break
        self._save_pending_operations_to_file()


pending_api_handler_toml = PendingApiHandlerToml()


# not_sure: Implementieren?
