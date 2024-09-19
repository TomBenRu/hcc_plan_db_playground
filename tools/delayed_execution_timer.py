from typing import Callable

from PySide6.QtCore import QObject, QTimer


class DelayedTimerSingleShot(QObject):
    def __init__(self, delay: int, function: Callable[..., None], *args, **kwargs):
        super().__init__()

        self._timer = QTimer()
        self._timer.setInterval(delay)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._execute)
        self._function = function
        self._args = args
        self._kwargs = kwargs

    def start_timer(self):
        self._timer.start()

    def _execute(self):
        self._function(*self._args, **self._kwargs)

