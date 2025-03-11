from PySide6.QtWidgets import QComboBox
from PySide6.QtCore import Qt


class QComboBoxToFindData(QComboBox):
    """
    This class extends the QComboBox class to allow finding items by their data comparing by equality,
    if the data is a custom python object.
    """
    def findData(self, data, role=Qt.ItemDataRole.UserRole, *args, **kwargs):
        """
        Find the index of the item with the given data. It compares custom python objects by their equality.

        Args:
            data: The data to search for.
            role: The role of the data.

        Returns:
            The index of the item with the given data, or -1 if not found.
        """
        return next(
            (
                index
                for index in range(self.count())
                if self.itemData(index, role) is not None and self.itemData(index, role) == data
            ),
            -1,
        )

