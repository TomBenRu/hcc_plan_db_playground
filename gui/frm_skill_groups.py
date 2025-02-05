from uuid import UUID

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QWidget, QLabel, QDialogButtonBox, QFormLayout,
                               QComboBox, QSpinBox, QMessageBox)
from PySide6.QtCore import Qt

from commands import command_base_classes
from commands.database_commands import skill_group_commands, location_of_work_commands, event_commands
from database import schemas, db_services
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData


class DlgSkillGroup(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID, exclude_skill_ids: set[UUID] = None,
                 skill_group: schemas.SkillGroup = None):
        super().__init__(parent)
        self.setWindowTitle("Fertigkeitsgruppe")

        self.skills_of_project: list[schemas.Skill] = db_services.Skill.get_all_from__project(project_id)

        self.exclude_skill_ids = exclude_skill_ids
        self.skill_group = skill_group

        self._setup_ui()
        self._setup_data()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel("<h3>Fertigkeitsgruppe</h3>")
        self.layout_head.addWidget(self.lb_description)

        self.combo_skill = self._setup_combo_skill()
        self.spin_person_count = self._setup_spin_person_count()
        self.layout_body.addRow("Fähigkeit/Kenntnis", self.combo_skill)
        self.layout_body.addRow("Anzahl Personen", self.spin_person_count)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_combo_skill(self) -> QComboBoxToFindData:
        combo_skill = QComboBoxToFindData()
        if self.skill_group:
            combo_skill.addItem(
                f'{self.skill_group.skill.name} ({self.skill_group.skill.notes})', self.skill_group.skill.id)
        for skill in [s for s in self.skills_of_project if s.id not in self.exclude_skill_ids]:
            combo_skill.addItem(f'{skill.name} ({skill.notes})', skill.id)
        return combo_skill

    def _setup_spin_person_count(self) -> QSpinBox:
        spin_person_count = QSpinBox()
        spin_person_count.setMinimum(1)
        spin_person_count.setMaximum(100)
        return spin_person_count

    def _setup_data(self):
        if self.skill_group:
            self.combo_skill.setCurrentIndex(self.combo_skill.findData(self.skill_group.skill.id))
            self.spin_person_count.setValue(self.skill_group.nr_actors)

    @property
    def skill_id(self) -> UUID:
        return self.combo_skill.currentData()

    @property
    def nr_actors(self) -> int:
        return self.spin_person_count.value()


class DlgSkillGroups(QDialog):
    def __init__(self, parent: QWidget, object_with_skill_groups: schemas.LocationOfWorkShow | schemas.EventShow):
        super().__init__(parent)
        self.setWindowTitle("Skill Groups")

        self.object_with_skill_groups = object_with_skill_groups
        self.controller = command_base_classes.ContrExecUndoRedo()

        self._setup_ui()
        self._setup_data()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
            text_description = (f"<h3>Fertigkeitsgruppen</h3>"
                                f"<p>Hier können Sie die Fertigkeitsgruppen für"
                                f" {self.object_with_skill_groups.name_an_city} festlegen.</p>")
        elif isinstance(self.object_with_skill_groups, schemas.EventShow):
            text_description = (
                f"<h3>Fertigkeitsgruppen</h3>"
                f"<p>Hier können Sie die Fertigkeitsgruppen für die Einsätze am<br>"
                f"{self.object_with_skill_groups.date:%d.%m.%Y} "
                f"({self.object_with_skill_groups.time_of_day.name}) - "
                f"{self.object_with_skill_groups.location_plan_period.location_of_work.name_an_city}<br>"
                f"festlegen.</p>")
        else:
            raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")
        self.lb_description = QLabel(text_description)
        self.layout_head.addWidget(self.lb_description)

        self.table_skill_groups = self._setup_table_skill_groups()
        self.layout_body.addWidget(self.table_skill_groups)

        self.btn_add_skill_group = QPushButton("Neue Fertigkeitsgruppe")
        self.btn_add_skill_group.clicked.connect(self.add_skill_group)
        self.btn_remove_skill_group = QPushButton("Fertigkeitsgruppe entfernen")
        self.btn_remove_skill_group.clicked.connect(self.remove_skill_group)
        self.btn_edit_skill_group = QPushButton("Fertigkeitsgruppe bearbeiten")
        self.btn_edit_skill_group.clicked.connect(self.edit_skill_group)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.btn_add_skill_group, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_remove_skill_group, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_edit_skill_group, QDialogButtonBox.ButtonRole.ActionRole)
        if isinstance(self.object_with_skill_groups, schemas.EventShow):
            self.btn_reset = QPushButton("Zurücksetzen")
            self.btn_reset.clicked.connect(self.reset_skill_groups)
            self.button_box.addButton(self.btn_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_table_skill_groups(self) -> QTableWidget:
        table_skills_groups = QTableWidget()
        table_skills_groups.setColumnCount(3)
        table_skills_groups.setHorizontalHeaderLabels(["Fähigkeit/Kenntnis", "Beschreibung", "Anzahl Personen"])
        table_skills_groups.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_skills_groups.setAlternatingRowColors(True)
        table_skills_groups.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_skills_groups.setSortingEnabled(True)
        table_skills_groups.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        return table_skills_groups

    def _setup_data(self):
        if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
            skill_groups = db_services.SkillGroup.get_all_from__location_of_work(self.object_with_skill_groups.id)
        elif isinstance(self.object_with_skill_groups, schemas.EventShow):
            skill_groups = db_services.SkillGroup.get_all_from__event(self.object_with_skill_groups.id)
        else:
            raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")
        self.table_skill_groups.setRowCount(len(skill_groups))
        for i, skill_group in enumerate(skill_groups):
            skill = skill_group.skill
            item_skill_name = QTableWidgetItem(skill.name)
            item_skill_name.setData(Qt.ItemDataRole.UserRole, skill_group.id)
            self.table_skill_groups.setItem(i, 0, item_skill_name)
            self.table_skill_groups.setItem(i, 1, QTableWidgetItem(skill.notes))
            self.table_skill_groups.setItem(i, 2, QTableWidgetItem(str(skill_group.nr_actors)))

    def _reload_object_with_skill_groups(self):
        if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
            self.object_with_skill_groups = db_services.LocationOfWork.get(self.object_with_skill_groups.id)
        elif isinstance(self.object_with_skill_groups, schemas.EventShow):
            self.object_with_skill_groups = db_services.Event.get(self.object_with_skill_groups.id)
        else:
            raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")

    def add_skill_group(self):
        if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
            project_id = self.object_with_skill_groups.project.id
        elif isinstance(self.object_with_skill_groups, schemas.EventShow):
            project_id = self.object_with_skill_groups.location_plan_period.location_of_work.project.id
        else:
            raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")
        already_used_skill_ids = {sg.skill.id for sg in self.object_with_skill_groups.skill_groups}
        if not [s for s in db_services.Skill.get_all_from__project(project_id) if s.id not in already_used_skill_ids]:
            QMessageBox.warning(self, "Fehler", "Es sind keine weiteren Fähigkeiten/Kenntnisse verfügbar.")
            return
        dlg = DlgSkillGroup(self, project_id, already_used_skill_ids)
        if dlg.exec():
            command_create = skill_group_commands.Create(
                schemas.SkillGroupCreate(skill_id=dlg.skill_id, nr_persons=dlg.nr_actors))
            self.controller.execute(command_create)
            if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
                command_add = location_of_work_commands.AddSkillGroup(
                    self.object_with_skill_groups.id, command_create.created_skill_group.id)
            elif isinstance(self.object_with_skill_groups, schemas.EventShow):
                command_add = event_commands.AddSkillGroup(
                    self.object_with_skill_groups.id, command_create.created_skill_group.id)
            else:
                raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")
            self.controller.execute(command_add)

            self.table_skill_groups.setRowCount(self.table_skill_groups.rowCount() + 1)
            item_skill_name = QTableWidgetItem(command_create.created_skill_group.skill.name)
            item_skill_name.setData(Qt.ItemDataRole.UserRole, command_create.created_skill_group.id)
            self.table_skill_groups.setItem(self.table_skill_groups.rowCount() - 1, 0, item_skill_name)
            self.table_skill_groups.setItem(self.table_skill_groups.rowCount() - 1, 1,
                                            QTableWidgetItem(command_create.created_skill_group.skill.notes))
            self.table_skill_groups.setItem(self.table_skill_groups.rowCount() - 1, 2,
                                            QTableWidgetItem(str(command_create.created_skill_group.nr_actors)))
            self._reload_object_with_skill_groups()

    def remove_skill_group(self):
        current_row = self.table_skill_groups.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Fehler", "Keine Fertigkeitsgruppe ausgewählt.")
            return
        skill_group_id = self.table_skill_groups.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
            command_remove = location_of_work_commands.RemoveSkillGroup(self.object_with_skill_groups.id, skill_group_id)
        elif isinstance(self.object_with_skill_groups, schemas.EventShow):
            command_remove = event_commands.RemoveSkillGroup(self.object_with_skill_groups.id, skill_group_id)
        else:
            raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")
        self.controller.execute(command_remove)
        self.table_skill_groups.removeRow(current_row)
        self._reload_object_with_skill_groups()

    def edit_skill_group(self):
        if isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
            project_id = self.object_with_skill_groups.project.id
        elif isinstance(self.object_with_skill_groups, schemas.EventShow):
            project_id = self.object_with_skill_groups.location_plan_period.location_of_work.project.id
        else:
            raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")
        current_row = self.table_skill_groups.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Fehler", "Keine Fertigkeitsgruppe ausgewählt.")
            return
        curr_skill_group_id = self.table_skill_groups.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        curr_skill_group = db_services.SkillGroup.get(curr_skill_group_id)
        already_used_skill_ids = {sg.skill.id for sg in self.object_with_skill_groups.skill_groups}
        dlg = DlgSkillGroup(self, project_id, already_used_skill_ids,
                            curr_skill_group)
        if dlg.exec():
            if isinstance(self.object_with_skill_groups, schemas.EventShow):
                command_remove = event_commands.RemoveSkillGroup(self.object_with_skill_groups.id, curr_skill_group_id)
                self.controller.execute(command_remove)
                command_create = skill_group_commands.Create(
                    schemas.SkillGroupCreate(skill_id=dlg.skill_id, nr_persons=dlg.nr_actors))
                self.controller.execute(command_create)
                command_add = event_commands.AddSkillGroup(self.object_with_skill_groups.id, command_create.created_skill_group.id)
                self.controller.execute(command_add)
                self.table_skill_groups.item(current_row, 0).setText(command_create.created_skill_group.skill.name)
                self.table_skill_groups.item(current_row, 0).setData(Qt.ItemDataRole.UserRole, command_create.created_skill_group.id)
                self.table_skill_groups.item(current_row, 1).setText(command_create.created_skill_group.skill.notes)
                self.table_skill_groups.item(current_row, 2).setText(str(command_create.created_skill_group.nr_actors))
                self._reload_object_with_skill_groups()
            elif isinstance(self.object_with_skill_groups, schemas.LocationOfWorkShow):
                command_update = skill_group_commands.Update(
                    schemas.SkillGroupUpdate(id=curr_skill_group_id, skill_id=dlg.skill_id,
                                             nr_persons=dlg.nr_actors))
                self.controller.execute(command_update)
                self.table_skill_groups.item(current_row, 0).setText(command_update.updated_skill_group.skill.name)
                self.table_skill_groups.item(current_row, 1).setText(command_update.updated_skill_group.skill.notes)
                self.table_skill_groups.item(current_row, 2).setText(str(command_update.updated_skill_group.nr_actors))
                self._reload_object_with_skill_groups()
            else:
                raise NotImplementedError(f"Unsupported object type: {type(self.object_with_skill_groups)}")

    def reset_skill_groups(self):
        if isinstance(self.object_with_skill_groups, schemas.EventShow):
            skill_groups_of_location_of_work = db_services.SkillGroup.get_all_from__location_of_work(
                self.object_with_skill_groups.location_plan_period.location_of_work.id)
            for skill_group in self.object_with_skill_groups.skill_groups:
                command_remove = event_commands.RemoveSkillGroup(self.object_with_skill_groups.id, skill_group.id)
                self.controller.execute(command_remove)
            for skill_group in skill_groups_of_location_of_work:
                command_add = event_commands.AddSkillGroup(self.object_with_skill_groups.id, skill_group.id)
                self.controller.execute(command_add)
            self._reload_object_with_skill_groups()
            self.table_skill_groups.setRowCount(0)
            self._setup_data()



