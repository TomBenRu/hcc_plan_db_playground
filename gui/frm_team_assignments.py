"""Dialog for managing multi-team assignments for a person.

This module allows assigning a person to multiple teams simultaneously.
Unlike the previous single-team assignment, any number of team assignments
with different start and end dates can be managed here.
"""

import datetime
from functools import partial
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QLabel, QDateEdit, QDialogButtonBox, QMessageBox, QAbstractItemView
)

from database import db_services, schemas
from commands import command_base_classes
from commands.database_commands import person_commands
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import date_to_string


class DlgTeamAssignments(QDialog):
    """Dialog for managing all team assignments of a person.

    Shows a table with all past and current team assignments
    and allows adding new and ending existing assignments.
    """

    def __init__(self, parent: QWidget, project_id: UUID, person: schemas.PersonShow):
        super().__init__(parent)

        self.setWindowTitle(self.tr('Team Assignments'))
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)

        self.project_id = project_id
        self.person = person
        self.controller = command_base_classes.ContrExecUndoRedo()

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)

        # Header with person info
        self.layout_header = QHBoxLayout()
        self.layout.addLayout(self.layout_header)

        self.lb_person = QLabel()
        self.lb_person.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.layout_header.addWidget(self.lb_person)
        self.layout_header.addStretch()

        # Table with assignments
        self.table_assignments = QTableWidget()
        self.table_assignments.setColumnCount(4)
        self.table_assignments.setHorizontalHeaderLabels([
            self.tr('Team'), self.tr('Start'), self.tr('End'), self.tr('Action')
        ])
        self.table_assignments.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_assignments.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_assignments.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_assignments.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_assignments.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_assignments.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.layout.addWidget(self.table_assignments)

        # Add button
        self.layout_buttons = QHBoxLayout()
        self.layout.addLayout(self.layout_buttons)

        self.bt_add = QPushButton(self.tr('Add Team...'))
        self.bt_add.clicked.connect(self._add_team_assignment)
        self.layout_buttons.addWidget(self.bt_add)
        self.layout_buttons.addStretch()

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _load_data(self):
        """Loads all team assignments of the person into the table."""
        self.lb_person.setText(f'{self.person.f_name} {self.person.l_name}')

        # Sort assignments: active first, then by start date descending
        assignments = sorted(
            self.person.team_actor_assigns,
            key=lambda x: (x.end is not None, -x.start.toordinal() if hasattr(x.start, 'toordinal') else -x.start.toordinal()),
            reverse=False
        )

        self.table_assignments.setRowCount(len(assignments))

        for row, assignment in enumerate(assignments):
            # Team name
            item_team = QTableWidgetItem(assignment.team.name)
            item_team.setData(Qt.ItemDataRole.UserRole, assignment.id)
            self.table_assignments.setItem(row, 0, item_team)

            # Start date
            start_str = date_to_string(assignment.start)
            self.table_assignments.setItem(row, 1, QTableWidgetItem(start_str))

            # End date
            end_str = date_to_string(assignment.end) if assignment.end else '-'
            item_end = QTableWidgetItem(end_str)
            if assignment.end is None:
                item_end.setForeground(Qt.GlobalColor.darkGreen)
            self.table_assignments.setItem(row, 2, item_end)

            # Action button (only for active assignments)
            if assignment.end is None or assignment.end > datetime.date.today():
                bt_end = QPushButton(self.tr('End...'))
                bt_end.clicked.connect(partial(self._end_assignment, assignment.id, assignment.team.id))
                self.table_assignments.setCellWidget(row, 3, bt_end)

    def _add_team_assignment(self):
        """Opens dialog for adding a new team assignment."""
        dlg = DlgAddTeamAssignment(self, self.project_id, self.person)
        if dlg.exec():
            try:
                command = person_commands.AddToTeam(self.person.id, dlg.selected_team_id, dlg.start_date)
                self.controller.execute(command)
                self.person = db_services.Person.get(self.person.id)
                self._load_data()

                # Ask about creating planning periods
                team = db_services.Team.get(dlg.selected_team_id)
                reply = QMessageBox.question(
                    self,
                    self.tr('Planning Periods'),
                    self.tr('Do you want to create planning periods for {} in team "{}"?').format(
                        f'{self.person.f_name} {self.person.l_name}', team.name)
                )
                if reply == QMessageBox.StandardButton.Yes:
                    plan_periods = [pp for pp in db_services.PlanPeriod.get_all_from__team(dlg.selected_team_id)
                                    if pp.end > datetime.date.today()]
                    created_count = 0
                    for plan_period in plan_periods:
                        # Check if ActorPlanPeriod already exists for this person
                        existing_apps = db_services.ActorPlanPeriod.get_all_from__plan_period(plan_period.id)
                        already_exists = any(app.person.id == self.person.id for app in existing_apps)
                        if not already_exists:
                            new_actor_plan_period = db_services.ActorPlanPeriod.create(plan_period.id, self.person.id)
                            db_services.AvailDayGroup.create(actor_plan_period_id=new_actor_plan_period.id)
                            created_count += 1

                    if created_count > 0:
                        QMessageBox.information(
                            self,
                            self.tr('Planning Periods Created'),
                            self.tr('{} planning period(s) have been created.').format(created_count)
                        )
                    else:
                        QMessageBox.information(
                            self,
                            self.tr('No New Planning Periods'),
                            self.tr('No new planning periods were created (already exist or no active periods in team).')
                        )
                    # Reload person data
                    self.person = db_services.Person.get(self.person.id)

            except ValueError as e:
                QMessageBox.warning(self, self.tr('Error'), str(e))

    def _end_assignment(self, assignment_id: UUID, team_id: UUID):
        """Opens dialog to end a team assignment."""
        dlg = DlgEndTeamAssignment(self, team_id)
        if dlg.exec():
            try:
                command = person_commands.RemoveFromTeam(self.person.id, team_id, dlg.end_date)
                self.controller.execute(command)
                self.person = db_services.Person.get(self.person.id)
                self._load_data()
            except ValueError as e:
                QMessageBox.warning(self, self.tr('Error'), str(e))

    def reject(self):
        """Undo all changes on cancel."""
        self.controller.undo_all()
        super().reject()


class DlgAddTeamAssignment(QDialog):
    """Dialog for adding a person to another team."""

    def __init__(self, parent: QWidget, project_id: UUID, person: schemas.PersonShow):
        super().__init__(parent)

        self.setWindowTitle(self.tr('Add Team'))

        self.project_id = project_id
        self.person = person
        self.selected_team_id: UUID | None = None
        self.start_date: datetime.date | None = None

        self._setup_ui()
        self._load_teams()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)

        # Form
        self.layout_form = QFormLayout()
        self.layout.addLayout(self.layout_form)

        self.cb_team = QComboBoxToFindData()
        self.layout_form.addRow(self.tr('Team:'), self.cb_team)

        self.de_start = QDateEdit()
        self.de_start.setCalendarPopup(True)
        self.de_start.setDate(datetime.date.today())
        self.layout_form.addRow(self.tr('Start:'), self.de_start)

        # Info label
        self.lb_info = QLabel()
        self.lb_info.setWordWrap(True)
        self.lb_info.setStyleSheet("color: gray; font-style: italic;")
        self.layout.addWidget(self.lb_info)

        # Dialog buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def _load_teams(self):
        """Load available teams (excluding already actively assigned ones)."""
        # Determine current team IDs of the person
        current_team_ids = {
            a.team.id for a in self.person.team_actor_assigns
            if a.end is None or a.end > datetime.date.today()
        }

        # Load all teams of the project
        all_teams = db_services.Team.get_all_from__project(self.project_id)
        available_teams = [t for t in all_teams if t.id not in current_team_ids and not t.prep_delete]

        if not available_teams:
            self.lb_info.setText(self.tr('This person is already assigned to all available teams.'))
            self.cb_team.setEnabled(False)
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        else:
            self.lb_info.setText(self.tr('Select a team to which the person should be additionally assigned.'))
            for team in sorted(available_teams, key=lambda t: t.name):
                self.cb_team.addItem(team.name, team.id)

    def accept(self):
        self.selected_team_id = self.cb_team.currentData()
        self.start_date = self.de_start.date().toPython()

        if not self.selected_team_id:
            QMessageBox.warning(self, self.tr('Error'), self.tr('Please select a team.'))
            return

        super().accept()


class DlgEndTeamAssignment(QDialog):
    """Dialog for ending a team assignment."""

    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)

        self.setWindowTitle(self.tr('End Team Assignment'))

        self.team_id = team_id
        self.team = db_services.Team.get(team_id)
        self.end_date: datetime.date | None = None

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(15)

        # Info-Label
        self.lb_info = QLabel(
            self.tr('End assignment to team "{}":').format(self.team.name)
        )
        self.layout.addWidget(self.lb_info)

        # Form
        self.layout_form = QFormLayout()
        self.layout.addLayout(self.layout_form)

        self.de_end = QDateEdit()
        self.de_end.setCalendarPopup(True)
        self.de_end.setDate(datetime.date.today())
        self.layout_form.addRow(self.tr('End from:'), self.de_end)

        # Dialog-Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def accept(self):
        self.end_date = self.de_end.date().toPython()
        super().accept()
