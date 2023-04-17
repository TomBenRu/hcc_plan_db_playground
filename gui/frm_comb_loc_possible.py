from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget, QAbstractItemView, QHeaderView

from database import schemas
from database.schemas import ModelWithCombLocPossible


class DlgNewCombLocPossible(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)


class DlgCombLocPossibleEditList(QDialog):
    def __init__(self, parent: QWidget, curr_model: ModelWithCombLocPossible,
                 parent_model: ModelWithCombLocPossible | None, team: schemas.Team):
        """Wenn Combinations des Projektes bearbeitet werden, wird der Parameter parent_model auf None gesetzt.

        In den anderen Fällen ist das parent_model eine Instanz der Pydantic-Klasse von der das curr_model automatisch
        die Combinations erbt."""
        super().__init__(parent)

        self.setWindowTitle('Einrichtungskombinationen')

        self.curr_model = curr_model
        self.parent_model = parent_model

        self.layout = QGridLayout(self)

        self.table_combinations = QTableWidget()
        self.layout.addWidget(self.table_combinations, 0, 0, 1, 3)

        self.setup_table_combinations()

        self.bt_create = QPushButton('Neu...', clicked=self.new)
        self.bt_reset = QPushButton('Reset', clicked=self.reset)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.bt_create, 1, 0)
        self.layout.addWidget(self.bt_reset, 1, 1)
        self.layout.addWidget(self.bt_delete, 1, 2)
        self.layout.addWidget(self.button_box, 2, 0, 1, 3)
        self.button_box.setCenterButtons(True)

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

    def new(self):
        dlg = DlgNewCombLocPossible(self)

    def reset(self):
        ...

    def delete(self):
        ...

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        ...
        super().reject()
