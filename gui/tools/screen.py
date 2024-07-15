from PySide6.QtWidgets import QApplication


class Screen:
    _screen_width: int | None = None
    _screen_height: int | None = None

    @classmethod
    @property
    def screen_width(cls) -> int:
        return cls._screen_width

    @classmethod
    @property
    def screen_height(cls) -> int:
        return cls._screen_height

    @classmethod
    def set_screen_size(cls):
        cls._screen_width, cls._screen_height = QApplication.primaryScreen().size().toTuple()
