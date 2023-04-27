from uuid import UUID

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget, QAbstractItemView, QHeaderView, \
    QVBoxLayout, QGroupBox, QTableWidgetItem

from database import schemas, db_services
from database.schemas import ModelWithCombLocPossible
from gui.commands import command_base_classes, comb_loc_possible_commands, team_commands, person_commands, \
    actor_plan_period_commands, avail_day_commands


class DlgNewCombLocPossible(QDialog):

    def __init__(self, parent: QWidget, locations_of_work: list[schemas.LocationOfWork]):
        super().__init__(parent)

        self.locations_of_work = sorted([loc for loc in locations_of_work if not loc.prep_delete], key=lambda x: x.name)
        self.comb_location_ids: set[UUID] = set()

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
        self.comb_location_ids = {l_o_w_id for l_o_w_id, chk in self.chks_loc_of_work.items() if chk.isChecked()}
        super().accept()


class DlgCombLocPossibleEditList(QDialog):
    def __init__(self, parent: QWidget, curr_model: ModelWithCombLocPossible,
                 parent_model: ModelWithCombLocPossible | None, locations_of_work: list[schemas.LocationOfWork]):
        """Wenn Combinations des Projektes bearbeitet werden, wird der Parameter parent_model auf None gesetzt.

        In den anderen Fällen ist das parent_model eine Instanz der Pydantic-Klasse von der das curr_model automatisch
        die Combinations erbt."""
        super().__init__(parent)

        self.setWindowTitle('Einrichtungskombinationen')

        self.curr_model = curr_model.copy(deep=True)
        self.parent_model = parent_model.copy(deep=True) if parent_model else None
        self.locations_of_work = locations_of_work

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QGridLayout(self)

        self.table_combinations = QTableWidget()
        self.layout.addWidget(self.table_combinations, 0, 0, 1, 3)

        self.setup_table_combinations()
        self.fill_table_combinations()

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
        header_labels = ['ID', 'Einrichtungskombination']
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

    def fill_table_combinations(self):
        while self.table_combinations.rowCount() < 0:
            self.table_combinations.removeRow(0)
        comb_loc_poss = sorted([
            sorted((str(c.id), ' + '.join(sorted([f'{loc.name} ({loc.address.city})' for loc in c.locations_of_work]))),
                   key=lambda x: x[1]) for c in self.curr_model.combination_locations_possibles if not c.prep_delete],
            key=lambda y: y[1])
        self.table_combinations.setRowCount(len(comb_loc_poss))
        for row, c in enumerate(comb_loc_poss):
            self.table_combinations.setItem(row, 0, QTableWidgetItem(c[0]))
            self.table_combinations.setItem(row, 1, QTableWidgetItem(c[1]))

        self.setMinimumWidth(self.table_combinations.columnWidth(1) + 40)

    def new(self):
        curr_model_c_l_p_ids = [{loc.id for loc in c.locations_of_work if not loc.prep_delete}
                                for c in self.curr_model.combination_locations_possibles if not c.prep_delete]
        dlg = DlgNewCombLocPossible(self, self.locations_of_work)
        if not dlg.exec():
            return
        if len(dlg.comb_location_ids) < 2:
            QMessageBox.critical(self, 'Einrichtungskombinationen', 'Sie müssen mindestens 2 Einrichtungen auswählen.')
            return
        if dlg.comb_location_ids not in curr_model_c_l_p_ids:
            locations_work = [db_services.LocationOfWork.get(loc_id) for loc_id in dlg.comb_location_ids]
            comb_to_create = schemas.CombinationLocationsPossibleCreate(project=self.curr_model.project,
                                                                        locations_of_work=locations_work)
            create_command = comb_loc_possible_commands.Create(comb_to_create)
            self.controller.execute(create_command)
            created_comb_loc_poss = create_command.created_comb_loc_poss
            command_to_put_in_combination = self.factory_for_put_in_combs(self.curr_model, self.curr_model.id,
                                                                          created_comb_loc_poss.id)
            self.controller.execute(command_to_put_in_combination)
            self.curr_model.combination_locations_possibles.append(created_comb_loc_poss)

            self.fill_table_combinations()

    def reset(self):
        for c in self.curr_model.combination_locations_possibles:
            remove_command = self.factory_for_remove_combs(self.curr_model, self.curr_model.id, c.id)
            self.controller.execute(remove_command)
        self.curr_model.combination_locations_possibles.clear()
        for c in [comb for comb in self.parent_model.combination_locations_possibles if not comb.prep_delete]:
            put_in_command = self.factory_for_put_in_combs(self.curr_model, self.curr_model.id, c.id)
            self.controller.execute(put_in_command)
        self.curr_model.combination_locations_possibles.extend(self.parent_model.combination_locations_possibles)

        self.fill_table_combinations()

    def delete(self):
        if self.table_combinations.currentRow() == -1:
            QMessageBox.critical(self, 'Einrichtungskombinationen', 'Sie müssen zuerst eine Zeile auswählen.')
            return
        comb_id_to_remove = UUID(self.table_combinations.item(self.table_combinations.currentRow(), 0).text())
        remove_command = self.factory_for_remove_combs(self.curr_model, self.curr_model.id, comb_id_to_remove)
        self.controller.execute(remove_command)
        self.curr_model.combination_locations_possibles = [c for c in self.curr_model.combination_locations_possibles
                                                           if not c.id == comb_id_to_remove]
        self.fill_table_combinations()

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def factory_for_put_in_combs(self, curr_model: ModelWithCombLocPossible,
                                 curr_model_id: UUID, comb_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__put_in_command = {'TeamShow': team_commands.PutInCombLocPossible,
                                           'PersonShow': person_commands.PutInCombLocPossible,
                                           'ActorPlanPeriodShow': actor_plan_period_commands.PutInCombLocPossible,
                                           'AvailDay': avail_day_commands.PutInCombLocPossible,
                                           'AvailDayShow': avail_day_commands.PutInCombLocPossible}

        try:
            return curr_model_name__put_in_command[curr_model_name](curr_model_id, comb_to_put_i_id)
        except KeyError:
            raise KeyError(f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.')

    def factory_for_remove_combs(self, curr_model: ModelWithCombLocPossible,
                                 curr_model_id: UUID, comb_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__remove_command = {'TeamShow': team_commands.RemoveCombLocPossible,
                                           'PersonShow': person_commands.RemoveCombLocPossible,
                                           'ActorPlanPeriodShow': actor_plan_period_commands.RemoveCombLocPossible,
                                           'AvailDay': avail_day_commands.RemoveCombLocPossible,
                                           'AvailDayShow': avail_day_commands.RemoveCombLocPossible}
        try:
            command_to_remove = curr_model_name__remove_command[curr_model_name]
            return command_to_remove(curr_model_id, comb_to_put_i_id)
        except KeyError:
            raise KeyError(f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.')

    def disable_reset_bt(self):
        self.bt_reset.setDisabled(True)
