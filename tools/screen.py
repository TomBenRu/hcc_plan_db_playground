from PySide6.QtWidgets import QApplication


class Screen:
    screen_width: int | None = None
    screen_height: int | None = None

    @classmethod
    def set_screen_size(cls):
        cls.screen_width, cls.screen_height = QApplication.primaryScreen().size().toTuple()
