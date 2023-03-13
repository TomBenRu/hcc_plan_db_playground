from PySide6.QtWidgets import QComboBox


class QComboBoxToFindData(QComboBox):
    def findData(self, data):
        for index in range(self.count()):
            if self.itemData(index) == data:
                return index
        return -1