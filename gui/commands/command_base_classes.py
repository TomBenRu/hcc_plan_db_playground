from abc import ABC, abstractmethod

from PySide6.QtWidgets import QWidget, QMessageBox


class Command(ABC):

    @abstractmethod
    def execute(self):
        ...

    @abstractmethod
    def undo(self):
        ...

    @abstractmethod
    def redo(self):
        ...


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

    def execute(self, command: Command):
        command.execute()
        self.redo_stack.clear()
        self.undo_stack.append(command)

    def undo(self):
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)

    def redo(self):
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        command.redo()
        self.undo_stack.append(command)

    def undo_all(self):
        for command in reversed(self.undo_stack):
            command.undo()
        self.redo_stack = self.undo_stack[:]
        self.undo_stack.clear()

    def show_stacks(self):
        return f'Undo-Stack: {self.undo_stack}\nRedo-Stack: {self.redo_stack}'


class BatchCommand(Command):
    def __init__(self, parent_window: QWidget, commands: list[Command]):
        self.parent_window = parent_window
        self.commands = commands

    def execute(self):
        completed_commands: list[Command] = []
        try:
            for command in self.commands:
                command.execute()
                completed_commands.append(command)
        except Exception as e:
            for command in reversed(completed_commands):
                command.undo()
            QMessageBox.critical(self.parent_window, 'Fehler',
                                 f'Folgender Fehler trat auf:\n{e}\nDie Aktionen konnten nicht ausgeführt werden.')

    def undo(self):
        for command in reversed(self.commands):
            command.undo()

    def redo(self):
        for command in self.commands:
            command.redo()
