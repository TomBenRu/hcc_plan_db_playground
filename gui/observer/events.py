from py_events import Event


class CustomEvent(Event):
    def __init__(self, data: object):
        super().__init__()

        self.data = data
