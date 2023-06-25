import datetime
import sys
from typing import Callable, Any
from uuid import UUID

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QFormLayout, QComboBox, QSpinBox, QTableWidget, QAbstractItemView, QHeaderView, \
    QVBoxLayout, QGroupBox, QTableWidgetItem, QDateEdit

from database import schemas, db_services
from database.schemas import ModelWithCombLocPossible
from database.special_schema_requests import get_locations_of_team_at_date, get_curr_assignment_of_person
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

        self.checks_loc_of_work: dict[UUID, QCheckBox] = {l_o_w.id: QCheckBox(f'{l_o_w.name} ({l_o_w.address.city})')
                                                          for l_o_w in self.locations_of_work}
        for chk in self.checks_loc_of_work.values():
            self.layout_group_checks.addWidget(chk)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def accept(self) -> None:
        self.comb_location_ids = {l_o_w_id for l_o_w_id, chk in self.checks_loc_of_work.items() if chk.isChecked()}
        super().accept()


class DlgCombLocPossibleEditList(QDialog):
    def __init__(self, parent: QWidget, curr_model: ModelWithCombLocPossible,
                 parent_model_factory: Callable[[datetime.date], ModelWithCombLocPossible] | None,
                 team_at_date_factory: Callable[[datetime.date], schemas.Team] | None):
        """Wenn Combinations des Teams bearbeitet werden, wird der Parameter parent_model_factory auf None gesetzt.
        In den anderen Fällen generiert parent_model_factory eine Instanz der Pydantic-Klasse von der das curr_model
        automatisch die Combinations erbt."""
        super().__init__(parent)

        self.setWindowTitle('Einrichtungskombinationen')

        self.curr_model = curr_model.copy(deep=True)
        self.parent_model_factory = parent_model_factory
        self.team_at_date_factory = team_at_date_factory

        self.curr_team: schemas.Team | None = None
        self.parent_model: ModelWithCombLocPossible | None = None
        self.locations_of_work: list[schemas.LocationOfWork] | None = None

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QGridLayout(self)

        self.table_combinations = QTableWidget()
        self.layout.addWidget(self.table_combinations, 2, 0, 1, 3)

        self.setup_table_combinations()

        self.lb_info = QLabel()
        self.layout.addWidget(self.lb_info, 0, 0, 1, 3)

        self.lb_date = QLabel('Datum')
        self.de_date = QDateEdit()
        self.de_date.dateChanged.connect(self.set_new__locations__parent_model)
        self.de_date.setMinimumDate(datetime.date.today())
        self.layout.addWidget(self.lb_date, 1, 0)
        self.layout.addWidget(self.de_date, 1, 1)

        self.bt_create = QPushButton('Neu...', clicked=self.new)
        self.bt_reset = QPushButton('Reset', clicked=self.reset)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.bt_create, 3, 0)
        self.layout.addWidget(self.bt_reset, 3, 1)
        self.layout.addWidget(self.bt_delete, 3, 2)
        self.layout.addWidget(self.button_box, 4, 0, 1, 3)
        self.button_box.setCenterButtons(True)

    def set_new__locations__parent_model(self):
        date = self.de_date.date().toPython()
        self.curr_team = self.team_at_date_factory(date) if self.team_at_date_factory else self.curr_model
        self.locations_of_work = get_locations_of_team_at_date(self.curr_team.id, date)
        self.parent_model = self.parent_model_factory(date) if self.parent_model_factory else None
        self.fill_table_combinations()

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

        if isinstance(self.curr_model, schemas.ActorPlanPeriod):
            self.union_locations_of_work()

        comb_loc_poss = self.valid_combs_at_date()

        self.table_combinations.setRowCount(len(comb_loc_poss))
        for row, c in enumerate(comb_loc_poss):
            self.table_combinations.setItem(row, 0, QTableWidgetItem(c[0]))
            self.table_combinations.setItem(row, 1, QTableWidgetItem(c[1]))

        self.setMinimumWidth(self.table_combinations.columnWidth(1) + 40)

    def valid_combs_at_date(self) -> list[list[str, str]]:
        curr_location_ids = {l.id for l in self.locations_of_work}
        comb_loc_poss = [[str(c.id), [f'{l.name} ({l.address.city})'
                                      for l in c.locations_of_work if l.id in curr_location_ids]]
                         for c in self.curr_model.combination_locations_possibles]
        comb_loc_poss = [c for c in comb_loc_poss if len(c[1]) > 1]
        comb_loc_poss = [[c[0], ' + '.join(sorted(c[1]))] for c in comb_loc_poss]

        return sorted(comb_loc_poss, key=lambda x: x[1]) if comb_loc_poss else []

    def union_locations_of_work(self):
        """Vereinigung aus allen möglichen Locations an den Tagen der Planungsperiode werden gebildet"""
        person: schemas.PersonShow = self.parent_model
        days_of_plan_period = [self.curr_model.plan_period.start + datetime.timedelta(delta) for delta in
                               range((self.curr_model.plan_period.end - self.curr_model.plan_period.start).days + 1)]
        valid_days_of_actor = [date for date in days_of_plan_period
                               if get_curr_assignment_of_person(person, date).team.id == self.curr_team.id]

        curr_loc_of_work_ids = {loc.id for loc in get_locations_of_team_at_date(self.curr_team.id, valid_days_of_actor[0])}

        self.lb_info.setText('An allen Tagen des Zeitraums gehören dem Team die gleichen Einrichtungen zu.')
        for date in valid_days_of_actor[1:]:
            location_ids = {loc.id for loc in get_locations_of_team_at_date(self.curr_team.id, date)}
            if location_ids != curr_loc_of_work_ids:
                self.lb_info.setText('Nicht an allen Tagen des Zeitraums gehören dem Team die gleichen Einrichtungen zu.')

            curr_loc_of_work_ids |= location_ids

        self.locations_of_work = [db_services.LocationOfWork.get(loc_id) for loc_id in curr_loc_of_work_ids]


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
            command_to_put_in_combination = self.factory_for_put_in_combs(self.curr_model, created_comb_loc_poss.id)
            self.controller.execute(command_to_put_in_combination)
            self.curr_model.combination_locations_possibles.append(created_comb_loc_poss)

            self.fill_table_combinations()

    def reset(self):
        for c in self.curr_model.combination_locations_possibles:
            remove_command = self.factory_for_remove_combs(self.curr_model, c.id)
            self.controller.execute(remove_command)
        self.curr_model.combination_locations_possibles.clear()
        for c in [comb for comb in self.parent_model.combination_locations_possibles
                  if (not comb.prep_delete) or (comb.prep_delete > self.de_date.date().toPython())]:
            put_in_command = self.factory_for_put_in_combs(self.curr_model, c.id)
            self.controller.execute(put_in_command)
        self.curr_model.combination_locations_possibles.extend(self.parent_model.combination_locations_possibles)

        self.fill_table_combinations()

    def delete(self):
        if self.table_combinations.currentRow() == -1:
            QMessageBox.critical(self, 'Einrichtungskombinationen', 'Sie müssen zuerst eine Zeile auswählen.')
            return
        comb_id_to_remove = UUID(self.table_combinations.item(self.table_combinations.currentRow(), 0).text())
        remove_command = self.factory_for_remove_combs(self.curr_model, comb_id_to_remove)
        self.controller.execute(remove_command)
        self.curr_model.combination_locations_possibles = [c for c in self.curr_model.combination_locations_possibles
                                                           if c.id != comb_id_to_remove]
        self.fill_table_combinations()

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def factory_for_put_in_combs(self, curr_model: ModelWithCombLocPossible,
                                 comb_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__put_in_command = {'TeamShow': team_commands.PutInCombLocPossible,
                                           'PersonShow': person_commands.PutInCombLocPossible,
                                           'ActorPlanPeriodShow': actor_plan_period_commands.PutInCombLocPossible,
                                           'AvailDay': avail_day_commands.PutInCombLocPossible,
                                           'AvailDayShow': avail_day_commands.PutInCombLocPossible}

        try:
            return curr_model_name__put_in_command[curr_model_name](curr_model.id, comb_to_put_i_id)
        except KeyError as e:
            raise KeyError(f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.') from e

    def factory_for_remove_combs(self, curr_model: ModelWithCombLocPossible,
                                 comb_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__remove_command = {'TeamShow': team_commands.RemoveCombLocPossible,
                                           'PersonShow': person_commands.RemoveCombLocPossible,
                                           'ActorPlanPeriodShow': actor_plan_period_commands.RemoveCombLocPossible,
                                           'AvailDay': avail_day_commands.RemoveCombLocPossible,
                                           'AvailDayShow': avail_day_commands.RemoveCombLocPossible}
        try:
            command_to_remove = curr_model_name__remove_command[curr_model_name]
            return command_to_remove(curr_model.id, comb_to_put_i_id)
        except KeyError as e:
            raise KeyError(f'Für die Klasse {curr_model_name} ist noch kein Put-In-Command definiert.') from e

    def disable_reset_bt(self):
        self.bt_reset.setDisabled(True)
