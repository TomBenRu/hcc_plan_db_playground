import datetime
from typing import Callable
from uuid import UUID, uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QTableWidget, QAbstractItemView, QHeaderView, \
    QVBoxLayout, QGroupBox, QTableWidgetItem, QDateEdit, QFormLayout, QSpinBox

from database import schemas
from database.schemas import ModelWithCombLocPossible
from database.special_schema_requests import get_locations_of_team_at_date, get_curr_assignment_of_person
from database.db_services.location_of_work import get_locations_of_team_between_dates
from database.db_services.team_location_assign import get_location_ids_at_date
from commands import command_base_classes
from tools.helper_functions import setup_form_help
from commands.database_commands import team_commands
from commands.database_commands import actor_plan_period_commands, person_commands, avail_day_commands, \
    comb_loc_possible_commands
from gui.custom_widgets.team_selector import TeamSelectorWidget


class DlgNewCombLocPossible(QDialog):

    def __init__(self, parent: QWidget, locations_of_work: list[schemas.LocationOfWork]):
        super().__init__(parent)

        self.locations_of_work = sorted([loc for loc in locations_of_work if not loc.prep_delete], key=lambda x: x.name)
        self.comb_location_ids: set[UUID] = set()
        self.time_span_between: datetime.timedelta | None = None

        self.layout = QVBoxLayout(self)
        self.group_checks = QGroupBox(self.tr('Facilities'))
        self.layout.addWidget(self.group_checks)
        self.layout_group_checks = QVBoxLayout(self.group_checks)

        self.group_time_span_between = QGroupBox(self.tr('Time span between'))
        self.layout.addWidget(self.group_time_span_between)
        self.layout_group_time_span_between = QFormLayout(self.group_time_span_between)
        self.spin_hours = QSpinBox()
        self.spin_hours.setMaximum(12)
        self.spin_hours.setMinimum(0)
        self.spin_minutes = QSpinBox()
        self.spin_minutes.setMaximum(55)
        self.spin_minutes.setMinimum(0)
        self.spin_minutes.setSingleStep(5)
        self.layout_group_time_span_between.addRow(self.tr('Hours'), self.spin_hours)
        self.layout_group_time_span_between.addRow(self.tr('Minutes'), self.spin_minutes)

        self.checks_loc_of_work: dict[UUID, QCheckBox] = {l_o_w.id: QCheckBox(f'{l_o_w.name} ({l_o_w.address.city})')
                                                          for l_o_w in self.locations_of_work}
        for chk in self.checks_loc_of_work.values():
            chk.checkStateChanged.connect(self.check_changed)
        for chk in self.checks_loc_of_work.values():
            self.layout_group_checks.addWidget(chk)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # F1 Help Integration
        setup_form_help(self, "new_comb_loc_possible", add_help_button=True)

    def check_changed(self, state: int):
        if state == Qt.CheckState.Checked:
            if sum(chk.isChecked() for chk in self.checks_loc_of_work.values()) > 1:
                for chk in self.checks_loc_of_work.values():
                    if not chk.isChecked():
                        chk.setDisabled(True)
        else:
            for chk in self.checks_loc_of_work.values():
                chk.setEnabled(True)

    def accept(self) -> None:
        self.comb_location_ids = {l_o_w_id for l_o_w_id, chk in self.checks_loc_of_work.items() if chk.isChecked()}
        self.time_span_between = datetime.timedelta(hours=self.spin_hours.value(), minutes=self.spin_minutes.value())
        super().accept()


class DlgCombLocPossibleEditList(QDialog):
    def __init__(self, parent: QWidget, curr_model: ModelWithCombLocPossible,
                 parent_model_factory: Callable[[datetime.date], ModelWithCombLocPossible] | None,
                 team_at_date_factory: Callable[[datetime.date], schemas.Team] | None,
                 curr_date: datetime.date | None = None):
        """Wenn Combinations des Teams bearbeitet werden, wird der Parameter parent_model_factory auf None gesetzt.
        In den anderen Fällen generiert parent_model_factory eine Instanz der Pydantic-Klasse von der das curr_model
        automatisch die Combinations erbt."""
        super().__init__(parent)

        self.setWindowTitle(self.tr('Facility Combinations'))

        self.curr_model = curr_model.model_copy(deep=True)
        self.parent_model_factory = parent_model_factory
        self.team_at_date_factory = team_at_date_factory
        self.curr_date = curr_date

        # Cache-Pattern: alle Änderungen nur im Speicher, DB-Schreiben erst bei accept()
        self._original_ids: set[UUID] = {c.id for c in curr_model.combination_locations_possibles
                                         if not c.prep_delete}
        self._pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]] = []

        self.curr_team: schemas.Team | None = None
        self.parent_model: ModelWithCombLocPossible | None = None
        self.locations_of_work: list[schemas.LocationOfWork] | None = None

        self.layout = QGridLayout(self)

        self.table_combinations = QTableWidget()
        self.layout.addWidget(self.table_combinations, 2, 0, 1, 3)

        self.setup_table_combinations()

        self.lb_info = QLabel()
        self.layout.addWidget(self.lb_info, 0, 0, 1, 3)

        self.lb_date = QLabel(self.tr('Date'))
        self.de_date = QDateEdit()
        self.layout.addWidget(self.lb_date, 1, 0)
        self.layout.addWidget(self.de_date, 1, 1)

        self._setup_date_widget()

        self.bt_create = QPushButton(self.tr('New...'), clicked=self.new)
        self.bt_reset = QPushButton(self.tr('Reset'), clicked=self.reset)
        self.bt_delete = QPushButton(self.tr('Delete'), clicked=self.delete)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.bt_create, 3, 0)
        self.layout.addWidget(self.bt_reset, 3, 1)
        self.layout.addWidget(self.bt_delete, 3, 2)
        self.layout.addWidget(self.button_box, 4, 0, 1, 3)
        self.button_box.setCenterButtons(True)

        # F1 Help Integration
        setup_form_help(self, "comb_loc_possible_edit_list", add_help_button=True)

    def _setup_date_widget(self):
        # Team-Selektor für Multi-Team-Personen (nur bei PersonShow mit team_at_date_factory)
        # WICHTIG: Muss VOR dateChanged-Connect initialisiert werden!
        self.team_selector: TeamSelectorWidget | None = None
        if self.team_at_date_factory and isinstance(self.curr_model, schemas.PersonShow):
            self.team_selector = TeamSelectorWidget(self)
            self.team_selector.teamChanged.connect(self._on_team_changed)
            self.layout.addWidget(self.team_selector, 1, 2)

        if self.curr_date is not None:
            # Datum ist vorgegeben: setDate feuert dateChanged → Tabelle wird befüllt, Widget wird gesperrt
            self.de_date.dateChanged.connect(self._on_date_changed)
            self.de_date.setDate(self.curr_date)
            self.de_date.setDisabled(True)
        else:
            self.de_date.dateChanged.connect(self._on_date_changed)
            self.de_date.setDate(datetime.date.today())
            self.de_date.setMinimumDate(datetime.date.today())


    @property
    def original_ids(self) -> set[UUID]:
        """IDs die beim Öffnen des Dialogs vorhanden waren — für Diff-Berechnung im Caller."""
        return self._original_ids

    @property
    def pending_creates(self) -> list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]]:
        """Neue CombLocPossibles (Temp-UUID, Create-Schema) die noch nicht in der DB existieren."""
        return self._pending_creates

    def _on_date_changed(self):
        """Wird aufgerufen wenn das Datum geändert wird."""
        # Bei Multi-Team: Team-Selektor aktualisieren
        if self.team_selector:
            self.team_selector.update_teams(self.curr_model.id, self.de_date.date().toPython())

        self.set_new__locations__parent_model()

    def _on_team_changed(self, team: schemas.TeamShow | None):
        """Wird aufgerufen wenn der Benutzer ein anderes Team auswählt."""
        self.set_new__locations__parent_model()

    def set_new__locations__parent_model(self):
        date = self.de_date.date().toPython()

        # Team vom Selektor oder von der Factory holen
        if self.team_selector and self.team_selector.get_current_team():
            self.curr_team = self.team_selector.get_current_team()
        elif self.team_at_date_factory:
            self.curr_team = self.team_at_date_factory(date)
        else:
            self.curr_team = self.curr_model

        if not self.curr_team:
            self.lb_info.setText(self.tr('No team is assigned to this person at this date.'))
            return
        self.locations_of_work = get_locations_of_team_at_date(self.curr_team.id, date)
        self.parent_model = self.parent_model_factory(date) if self.parent_model_factory else None
        self.fill_table_combinations()

    def setup_table_combinations(self):
        header_labels = ['ID', self.tr('Facility Combination'), self.tr('Time between assignments')]
        self.table_combinations.setColumnCount(len(header_labels))
        self.table_combinations.setHorizontalHeaderLabels(header_labels)
        self.table_combinations.setSortingEnabled(True)
        self.table_combinations.setAlternatingRowColors(True)
        self.table_combinations.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_combinations.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_combinations.horizontalHeader().setHighlightSections(False)
        self.table_combinations.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.table_combinations.hideColumn(0)
        self.table_combinations.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        # self.table_combinations.resizeColumnsToContents()

    def fill_table_combinations(self):
        while self.table_combinations.rowCount() > 0:
            self.table_combinations.removeRow(0)

        if isinstance(self.curr_model, schemas.ActorPlanPeriod):
            self.union_locations_of_work()

        comb_loc_poss = self.valid_combs_at_date()

        self.table_combinations.setRowCount(len(comb_loc_poss))
        for row, c in enumerate(comb_loc_poss):
            self.table_combinations.setItem(row, 0, QTableWidgetItem(c[0]))
            self.table_combinations.setItem(row, 1, QTableWidgetItem(c[1]))
            self.table_combinations.setItem(row, 2, QTableWidgetItem(c[2]))

        table_width = self.table_combinations.horizontalHeader().length()
        self.resize(table_width + 40, 480)

    def valid_combs_at_date(self) -> list[tuple[str, str, str]]:
        curr_location_ids = {l.id for l in self.locations_of_work}
        comb_loc_poss = [[str(c.id), [f'{l.name} ({l.address.city})'
                                      for l in c.locations_of_work if l.id in curr_location_ids],
                          str(c.time_span_between)]
                         for c in self.curr_model.combination_locations_possibles]
        comb_loc_poss = [c for c in comb_loc_poss if len(c[1]) > 1]
        comb_loc_poss = [(c[0], ' + '.join(sorted(c[1])), c[2]) for c in comb_loc_poss]

        return sorted(comb_loc_poss, key=lambda x: x[1]) if comb_loc_poss else []

    def union_locations_of_work(self):
        """Vereinigung aus allen möglichen Locations an den Tagen der Planungsperiode werden gebildet"""
        person: schemas.PersonForCombLocDialog = self.parent_model
        days_of_plan_period = [self.curr_model.plan_period.start + datetime.timedelta(delta) for delta in
                               range((self.curr_model.plan_period.end - self.curr_model.plan_period.start).days + 1)]
        valid_days_of_actor = [date for date in days_of_plan_period
                               if (assignment := get_curr_assignment_of_person(person, date))
                               and assignment.team.id == self.curr_team.id]

        if not valid_days_of_actor:
            self.locations_of_work = []
            self.lb_info.setText(self.tr('No valid days found for this person in the selected team.'))
            return

        date_start, date_end = valid_days_of_actor[0], valid_days_of_actor[-1]
        self.locations_of_work = get_locations_of_team_between_dates(self.curr_team.id, date_start, date_end)

        locs_at_start = get_location_ids_at_date(self.curr_team.id, date_start)
        all_ids = {loc.id for loc in self.locations_of_work}
        if all_ids == locs_at_start:
            self.lb_info.setText(self.tr('The team has the same facilities on all days of the period.'))
        else:
            self.lb_info.setText(self.tr('The team does not have the same facilities on all days of the period.'))

    def new(self):
        if not self.locations_of_work:
            QMessageBox.critical(self, self.tr('Facility Combinations'),
                                 self.tr('No facilities are assigned to this team at this date.'))
            return
        curr_model_c_l_p_ids = [{loc.id for loc in c.locations_of_work if not loc.prep_delete}
                                for c in self.curr_model.combination_locations_possibles if not c.prep_delete]
        dlg = DlgNewCombLocPossible(self, self.locations_of_work)
        if not dlg.exec():
            return
        if len(dlg.comb_location_ids) < 2:
            QMessageBox.critical(self, self.tr('Facility Combinations'),
                                 self.tr('You must select at least 2 facilities.'))
            return
        if dlg.comb_location_ids not in curr_model_c_l_p_ids:
            # Locations aus self.locations_of_work — kein DB-Call nötig
            locations_work = [loc for loc in self.locations_of_work if loc.id in dlg.comb_location_ids]
            comb_to_create = schemas.CombinationLocationsPossibleCreate(
                project=self.curr_team.project,
                locations_of_work=locations_work,
                time_span_between=dlg.time_span_between)

            # Temp-UUID für In-Memory-Darstellung; echter DB-Write erst bei accept()
            temp_id = uuid4()
            self._pending_creates.append((temp_id, comb_to_create))
            self.curr_model.combination_locations_possibles.append(
                schemas.CombinationLocationsPossible(
                    id=temp_id,
                    project=comb_to_create.project,
                    locations_of_work=comb_to_create.locations_of_work,
                    time_span_between=comb_to_create.time_span_between,
                    prep_delete=None))
            self.fill_table_combinations()

    def reset(self):
        if not self.parent_model:
            return
        self._pending_creates.clear()
        self.curr_model.combination_locations_possibles.clear()
        date = self.de_date.date().toPython()
        valid_parent_combs = [c for c in self.parent_model.combination_locations_possibles
                              if (not c.prep_delete) or (c.prep_delete > date)]
        self.curr_model.combination_locations_possibles.extend(valid_parent_combs)
        self.fill_table_combinations()

    def delete(self):
        if self.table_combinations.currentRow() == -1:
            QMessageBox.critical(self, self.tr('Facility Combinations'),
                                 self.tr('You must first select a row.'))
            return
        comb_id_to_remove = UUID(self.table_combinations.item(self.table_combinations.currentRow(), 0).text())
        self._pending_creates = [(t, c) for t, c in self._pending_creates if t != comb_id_to_remove]
        self.curr_model.combination_locations_possibles = [
            c for c in self.curr_model.combination_locations_possibles if c.id != comb_id_to_remove]
        self.fill_table_combinations()

    def accept(self) -> None:
        # Kein DB-Write hier — Caller führt jeweils den passenden Bulk-Command aus.
        caller_handles_db = (schemas.ActorPlanPeriodForMask, schemas.AvailDayForMask,
                              schemas.PersonShow, schemas.TeamShow)
        if not isinstance(self.curr_model, caller_handles_db):
            controller = command_base_classes.ContrExecUndoRedo()

            # 1. Neue CombLocPossibles anlegen und Temp-IDs auf echte IDs abbilden
            temp_to_real: dict[UUID, UUID] = {}
            for temp_id, comb_to_create in self._pending_creates:
                create_cmd = comb_loc_possible_commands.Create(comb_to_create)
                controller.execute(create_cmd)
                temp_to_real[temp_id] = create_cmd.created_comb_loc_poss.id

            # 2. Finale echte IDs bestimmen
            current_ids = {temp_to_real.get(c.id, c.id)
                           for c in self.curr_model.combination_locations_possibles}

            # 3. Entfernte Assoziationen löschen
            for removed_id in self._original_ids - current_ids:
                controller.execute(self.factory_for_remove_combs(self.curr_model, removed_id))

            # 4. Neue Assoziationen eintragen
            for added_id in current_ids - self._original_ids:
                controller.execute(self.factory_for_put_in_combs(self.curr_model, added_id))

        super().accept()

    def reject(self) -> None:
        super().reject()  # Kein Undo nötig — kein DB-Write während des Dialogs

    def factory_for_put_in_combs(self, curr_model: ModelWithCombLocPossible,
                                 comb_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__put_in_command = {'TeamShow': team_commands.PutInCombLocPossible,
                                           'PersonShow': person_commands.PutInCombLocPossible,
                                           'ActorPlanPeriodForMask': actor_plan_period_commands.PutInCombLocPossible,
                                           'AvailDay': avail_day_commands.PutInCombLocPossible,
                                           'AvailDayShow': avail_day_commands.PutInCombLocPossible,
                                           'AvailDayForMask': avail_day_commands.PutInCombLocPossible}

        try:
            return curr_model_name__put_in_command[curr_model_name](curr_model.id, comb_to_put_i_id)
        except KeyError as e:
            raise KeyError(f'No Put-In-Command defined for class {curr_model_name}.') from e

    def factory_for_remove_combs(self, curr_model: ModelWithCombLocPossible,
                                 comb_to_put_i_id: UUID) -> command_base_classes.Command:
        curr_model_name = curr_model.__class__.__name__
        curr_model_name__remove_command = {'TeamShow': team_commands.RemoveCombLocPossible,
                                           'PersonShow': person_commands.RemoveCombLocPossible,
                                           'ActorPlanPeriodForMask': actor_plan_period_commands.RemoveCombLocPossible,
                                           'AvailDay': avail_day_commands.RemoveCombLocPossible,
                                           'AvailDayShow': avail_day_commands.RemoveCombLocPossible,
                                           'AvailDayForMask': avail_day_commands.RemoveCombLocPossible}
        try:
            command_to_remove = curr_model_name__remove_command[curr_model_name]
            return command_to_remove(curr_model.id, comb_to_put_i_id)
        except KeyError as e:
            raise KeyError(f'No Remove-Command defined for class {curr_model_name}.') from e

    def disable_reset_bt(self):
        self.bt_reset.setDisabled(True)
