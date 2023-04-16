from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget

from database.schemas import ModelWithCombLocPossible


class FrmCombLocPossible(QDialog):
    def __init__(self, curr_model: ModelWithCombLocPossible, parent_model: ModelWithCombLocPossible):
        super().__init__(self)

        self.curr_model = curr_model
        self.parent_model = parent_model

        self.table_combinations = QTableWidget()

        self.setup_table_combinations()

    def setup_table_combinations(self):


