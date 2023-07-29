from PySide6.QtGui import Qt
from PySide6.QtWidgets import QSlider


class SliderWithPressEvent(QSlider):
    """works eventually also for vertical orientation"""

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return super().mousePressEvent(e)
        e.accept()
        if self.orientation() == Qt.Orientation.Horizontal:
            position = e.position().x()
        else:
            position = e.position().y()
        value = (self.maximum() - self.minimum()) * position / self.width() + self.minimum()
        value = round(value)
        if value == self.value():
            super().mousePressEvent(e)
        self.setValue(value)
