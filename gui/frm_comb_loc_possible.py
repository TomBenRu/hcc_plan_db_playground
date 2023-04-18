from typing import List
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget, QAbstractItemView, QHeaderView, \
    QVBoxLayout, QGroupBox

from database import schemas, db_services
from database.schemas import ModelWithCombLocPossible


class DlgNewCombLocPossible(QDialog):

    def __init__(self, parent: QWidget, locations_of_work: list[schemas.LocationOfWork]):
        super().__init__(parent)

        self.locations_of_work = sorted([loc for loc in locations_of_work if not loc.prep_delete], key=lambda x: x.name)
        self.comb_locations: list[schemas.LocationOfWork] = []

        self.layout = QVBoxLayout(self)
        self.group_checks = QGroupBox('Einrichtungen')
        self.layout.addWidget(self.group_checks)
        self.layout_group_checks = QVBoxLayout(self.group_checks)

        self.chks_loc_of_work: dict[UUID, QCheckBox] = {l_o_w.id: QCheckBox(l_o_w.name) 
                                                        for l_o_w in self.locations_of_work}
        for chk in self.chks_loc_of_work.values():
            self.layout_group_checks.addWidget(chk)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def accept(self) -> None:
        self.comb_locations = [db_services.LocationOfWork.get(l_o_w_id)
                               for l_o_w_id, chk in self.chks_loc_of_work.items() if chk.isChecked()]
        super().accept()


class DlgCombLocPossibleEditList(QDialog):
    def __init__(self, parent: QWidget, curr_model: ModelWithCombLocPossible,
                 parent_model: ModelWithCombLocPossible | None, locations_of_work: list[schemas.LocationOfWork]):
        """Wenn Combinations des Projektes bearbeitet werden, wird der Parameter parent_model auf None gesetzt.

        In den anderen Fällen ist das parent_model eine Instanz der Pydantic-Klasse von der das curr_model automatisch
        die Combinations erbt."""
        super().__init__(parent)

        self.setWindowTitle('Einrichtungskombinationen')

        self.curr_model = curr_model
        self.parent_model = parent_model
        self.locations_of_work = locations_of_work

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
        dlg = DlgNewCombLocPossible(self, self.locations_of_work)
        if dlg.exec():
            comb_locations = dlg.comb_locations
            print(comb_locations)

    def reset(self):
        ...

    def delete(self):
        ...

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        ...
        super().reject()
