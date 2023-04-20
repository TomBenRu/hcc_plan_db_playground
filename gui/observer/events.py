from py_events import Event


class CustomEvent(Event):
    def __init__(self, data: object | None = None):
        super().__init__()

        self.data = data
