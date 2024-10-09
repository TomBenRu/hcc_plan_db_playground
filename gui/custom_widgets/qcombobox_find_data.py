from PySide6.QtWidgets import QComboBox


class QComboBoxToFindData(QComboBox):
    def findData(self, data, role=None, *args, **kwargs):
        return next(
            (
                index
                for index in range(self.count())
                if self.itemData(index) == data
            ),
            -1,
        )
