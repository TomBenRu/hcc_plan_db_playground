from PySide6.QtGui import Qt
from PySide6.QtWidgets import QSlider


class SliderWithPressEvent(QSlider):
    """only works for horizontal orientation"""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            e.accept()
            x = e.position().x()
            value = (self.maximum() - self.minimum()) * x / self.width() + self.minimum()
            value = round(value)
            if value == self.value():
                super().mousePressEvent(e)
            self.setValue(value)
        else:
            return super().mousePressEvent(e)
