from abc import ABC, abstractmethod
from typing import Iterable, Callable
from uuid import UUID

from PySide6.QtWidgets import QWidget, QMessageBox

from database import schemas


class Command(ABC):

    def __init__(self):
        self.on_undo_callback: Callable[[], None] | None = None
        self.on_redo_callback: Callable[[], None] | None = None
        self.appointment: schemas.Appointment | None = None  # notwendig für undo nach automatischer Validierung und für undo/redo Highlighting

    @abstractmethod
    def execute(self):
        ...

    @abstractmethod
    def _undo(self):
        """Interne Undo-Logik - muss von Subklassen implementiert werden."""
        ...

    @abstractmethod
    def _redo(self):
        """Interne Redo-Logik - muss von Subklassen implementiert werden."""
        ...

    def undo(self):
        """Führt Undo aus und ruft anschließend den Callback auf."""
        self._undo()
        if self.on_undo_callback:
            self.on_undo_callback()

    def redo(self):
        """Führt Redo aus und ruft anschließend den Callback auf."""
        self._redo()
        if self.on_redo_callback:
            self.on_redo_callback()


class Invoker(ABC):

    @abstractmethod
    def execute(self, command: Command):
        ...

########################################################################################################################


class ContrExecUndoRedo(Invoker):
    """Ein Invoker für Commands mit Undo und Redo Funktionalität"""
    def __init__(self):
        self.undo_stack: list[Command] = []
        self.redo_stack: list[Command] = []
        self._on_stacks_changed_callback: Callable[[], None] | None = None

    def set_on_stacks_changed_callback(self, callback: Callable[[], None]):
        """Registriert Callback für Stack-Änderungen (z.B. für Tooltip-Updates)."""
        self._on_stacks_changed_callback = callback

    def _notify_stacks_changed(self):
        """Benachrichtigt über Stack-Änderungen."""
        if self._on_stacks_changed_callback:
            self._on_stacks_changed_callback()

    def execute(self, command: Command):
        command.execute()
        self.redo_stack.clear()
        self.undo_stack.append(command)
        self._notify_stacks_changed()

    def undo(self):
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        self._notify_stacks_changed()

    def redo(self):
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)
        self._notify_stacks_changed()

    def undo_all(self):
        for command in reversed(self.undo_stack):
            command.undo()
        self.redo_stack = self.undo_stack[:]
        self.undo_stack.clear()

    def get_undo_stack(self):
        return self.undo_stack

    def add_to_undo_stack(self, value: Iterable[Command] | Command):
        """Fügt bereits ausgeführte Commands zum Undo-Stack hinzu.

        Wichtig: Leert den Redo-Stack, da eine neue Aktion die Redo-Historie invalidiert.
                 Dies ist nötig, da im Deferred Mode die Commands bereits ausgeführt werden,
                 bevor sie zum Controller hinzugefügt werden.
        """
        self.redo_stack.clear()
        if isinstance(value, Iterable):
            self.undo_stack.extend(value)
        else:
            self.undo_stack.append(value)
        self._notify_stacks_changed()

    def get_recent_undo_command(self) -> Command | None:
        return self.undo_stack[-1] if self.undo_stack else None

    def get_recent_redo_command(self) -> Command | None:
        return self.redo_stack[-1] if self.redo_stack else None


class BatchCommand(Command):
    def __init__(self, parent_window: QWidget, commands: list[Command], description: str | None = None):
        super().__init__()
        self.parent_window = parent_window
        self.commands = commands
        self.description = description

    def execute(self):
        completed_commands: list[Command] = []
        try:
            for command in self.commands:
                command.execute()
                completed_commands.append(command)
        except Exception as e:
            for command in reversed(completed_commands):
                command._undo()  # Direkter Aufruf ohne Callback bei Rollback
            QMessageBox.critical(self.parent_window, 'Fehler',
                                 f'Folgender Fehler trat auf:\n{e}\nDie Aktionen konnten nicht ausgeführt werden.')

    def _undo(self):
        for command in reversed(self.commands):
            command._undo()  # Direkter Aufruf - BatchCommand handhabt eigenen Callback

    def _redo(self):
        for command in self.commands:
            command._redo()  # Direkter Aufruf - BatchCommand handhabt eigenen Callback

    def __str__(self) -> str:
        # 1. Explizite Beschreibung nutzen
        if self.description:
            return self.description

        # 2. Bei einem Command: dessen Beschreibung
        if len(self.commands) == 1:
            return str(self.commands[0])

        # 3. Fallback: Liste der ersten 3 Commands
        descriptions = [str(cmd) for cmd in self.commands[:3]]
        result = "\n".join(f"  • {desc}" for desc in descriptions)

        if len(self.commands) > 3:
            remaining = len(self.commands) - 3
            result += f"\n  ... +{remaining} weitere"

        return result
