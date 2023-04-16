from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget, QAbstractItemView, QHeaderView

from database.schemas import ModelWithCombLocPossible


class FrmCombLocPossibleEditList(QDialog):
    def __init__(self, parent: QWidget, curr_model: ModelWithCombLocPossible, parent_model: ModelWithCombLocPossible | None):
        super().__init__(parent)

        self.setWindowTitle('Einrichtungskombinationen')

        self.curr_model = curr_model
        self.parent_model = parent_model

        self.layout = QGridLayout(self)

        self.table_combinations = QTableWidget()
        self.layout.addWidget(self.table_combinations, 0, 0, 1, 3)

        self.setup_table_combinations()

    def setup_table_combinations(self):
        comb_loc_poss = [
            sorted((str(c.id), ' + '.join(sorted([f'{loc.name} ({loc.address.city})' for loc in c.locations_of_work]))),
                   key=lambda x: x[1]) for c in self.curr_model.combination_locations_possibles]
        print(comb_loc_poss)
        header_labels = ['ID', 'Einrichtungskombination']
        self.table_combinations.setRowCount(len(comb_loc_poss))
        self.table_combinations.setColumnCount(len(header_labels))
        self.table_combinations.setHorizontalHeaderLabels(header_labels)
        self.table_combinations.setSortingEnabled(True)
        self.table_combinations.setAlternatingRowColors(True)
        self.table_combinations.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_combinations.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_combinations.horizontalHeader().setHighlightSections(False)
        self.table_combinations.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.table_combinations.hideColumn(0)
        self.table_combinations.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
