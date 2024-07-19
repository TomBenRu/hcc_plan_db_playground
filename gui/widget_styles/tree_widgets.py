
from PySide6.QtGui import QLinearGradient, QColor, QBrush
from PySide6.QtWidgets import QStyledItemDelegate

group_bg_color_rgba = (0, 255, 255, 100)
description_fg_color_rgba = (136, 0, 227, 255)
date_fg_color_rgba = (0, 90, 255, 255)
time_of_day_fg_color_rgba = (220, 0, 139, 255)


class ChildZebraDelegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        item = self.parent().itemFromIndex(index)
        if item.date_object:  # Prüfen, ob es sich um ein Child-Item handelt
            rect = option.rect
            gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())

            # Farbverlauf
            gradient.setColorAt(0, QColor(200, 200, 255, 20))
            gradient.setColorAt(1, QColor(200, 200, 255, 5))

            painter.fillRect(rect, QBrush(gradient))
        super().paint(painter, option, index)

