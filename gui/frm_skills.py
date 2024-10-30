from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox, QTableWidget, \
    QTableWidgetItem, QFormLayout, QLineEdit, QHeaderView, QCheckBox, QMessageBox
from PySide6.QtCore import Qt

from commands import command_base_classes
from commands.database_commands import skill_commands, person_commands
from database import db_services, schemas



class DlgSkillsOfProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID, exclude_skill_ids: set[UUID] = None):
        super().__init__(parent)
        self.setWindowTitle("Skills of Project")

        self.project_id = project_id
        self.exclude_skill_ids = exclude_skill_ids

        self.selected_skill: schemas.Skill | None = None

        self._setup_data()
        self._setup_ui()

    def _setup_data(self):
        self.skills: list[schemas.Skill] = db_services.Skill.get_all_from__project(self.project_id)
        self.skills = [skill for skill in self.skills
                       if skill.id not in self.exclude_skill_ids and not skill.prep_delete]

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(f"<h3>Skills of Project {self.project_id}</h3>"
                                     "<p>Hier sind alle Fähigkeiten und Kenntnisse für dein Projekt aufgelistet.</p>")
        self.layout_head.addWidget(self.lb_description)
        self.table_skills = self._setup_table()
        self._put_skills_in_table()
        self.layout_body.addWidget(self.table_skills)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_table(self):
        table_skills = QTableWidget()
        table_skills.setColumnCount(2)
        table_skills.setHorizontalHeaderLabels(["Fähigkeit/Kenntnis", "Beschreibung"])
        table_skills.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_skills.setAlternatingRowColors(True)
        table_skills.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_skills.setSortingEnabled(True)
        table_skills.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        return table_skills

    def _put_skills_in_table(self):
        self.table_skills.setRowCount(len(self.skills))
        for row, skill in enumerate(self.skills):
            item_name = QTableWidgetItem(skill.name)
            item_name.setData(Qt.ItemDataRole.UserRole, skill)
            self.table_skills.setItem(row, 0, item_name)
            self.table_skills.setItem(row, 1, QTableWidgetItem(skill.notes))

    def accept(self):
        self.selected_skill = self.table_skills.item(self.table_skills.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        super().accept()


class DlgSkill(QDialog):
    def __init__(self, parent: QWidget, skill_id: UUID = None):
        super().__init__(parent)
        self.setWindowTitle("Skill")
        self.skill_id = skill_id
        self._setup_ui()
        self._setup_data()

    def _setup_data(self):
        if self.skill_id:
            self.skill = db_services.Skill.get(self.skill_id)
            self.le_name.setText(self.skill.name)
            self.le_notes.setText(self.skill.notes)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(f"<h3>{'Edit Skill' if self.skill_id else 'New Skill'}</h3>"
                                     "<p>Setze hier Name und Beschreibung deiner Fähigkeit/Kenntnis ein.</p>")
        self.layout_head.addWidget(self.lb_description)
        self.le_name = QLineEdit()
        self.le_notes = QLineEdit()
        self.layout_body.addRow("Name", self.le_name)
        self.layout_body.addRow("Beschreibung", self.le_notes)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    @property
    def name(self) -> str:
        return self.le_name.text()

    @property
    def notes(self) -> str:
        return self.le_notes.text()


class DlgEditSkills(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)
        self.project_id = project_id
        self.controller = command_base_classes.ContrExecUndoRedo()

        self._setup_data()
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel("<h3>Skills</h3>"
                                     "<p>Hier kannst du deine Fähigkeiten und Kenntnisse für dein Projekt<br>"
                                     "hinzufügen und bearbeiten.</p>")
        self.layout_head.addWidget(self.lb_description)
        self.table_skills = self._setup_table()
        self.chk_show_deleted = QCheckBox("Gelöschte Fähigkeiten anzeigen")
        self.chk_show_deleted.setChecked(False)
        self.chk_show_deleted.stateChanged.connect(self._update_table)
        self._put_skills_in_table()
        self.layout_body.addWidget(self.table_skills)
        self.layout_body.addWidget(self.chk_show_deleted)
        self.btn_add_skill = QPushButton("Add Skill")
        self.btn_add_skill.clicked.connect(self._add_skill)
        self.btn_edit_skill = QPushButton("Edit Skill")
        self.btn_edit_skill.clicked.connect(self._edit_skill)
        self.btn_delete_skill = QPushButton("Delete Skill")
        self.btn_delete_skill.clicked.connect(self._delete_skill)
        self.btn_undelete_skill = QPushButton("Undelete Skill")
        self.btn_undelete_skill.clicked.connect(self._undelete_skill)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.btn_add_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_edit_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_delete_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_undelete_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_data(self):
        self.skills: list[schemas.Skill] = db_services.Skill.get_all_from__project(self.project_id)

    def _setup_table(self):
        table_skills = QTableWidget()
        table_skills.setColumnCount(3)
        table_skills.setHorizontalHeaderLabels(["Fähigkeit/Kenntnis", "Beschreibung", "Entfernt"])
        table_skills.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_skills.setAlternatingRowColors(True)
        table_skills.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_skills.setSortingEnabled(True)
        table_skills.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        return table_skills

    def _put_skills_in_table(self):
        if self.chk_show_deleted.isChecked():
            skills = self.skills
        else:
            skills = [skill for skill in self.skills if not skill.prep_delete]
        self.table_skills.setRowCount(len(skills))
        for row, skill in enumerate(skills):
            item_name = QTableWidgetItem(skill.name)
            item_name.setData(Qt.ItemDataRole.UserRole, skill.id)
            self.table_skills.setItem(row, 0, item_name)
            self.table_skills.setItem(row, 1, QTableWidgetItem(skill.notes))
            self.table_skills.setItem(row, 2,
                                      QTableWidgetItem(skill.prep_delete.strftime("%d.%m.%Y %H:%M:%S")
                                                       if skill.prep_delete else ""))

    def _update_table(self):
        self.table_skills.setRowCount(0)
        self._put_skills_in_table()

    def _add_skill(self):
        dlg = DlgSkill(self)
        if dlg.exec():
            command = skill_commands.Create(
                schemas.SkillCreate(name=dlg.name, notes=dlg.notes, project_id=self.project_id))
            self.controller.execute(command)
            created_skill = command.created_skill
            self.skills.append(created_skill)
            self.table_skills.setRowCount(len(self.skills))
            item_name = QTableWidgetItem(created_skill.name)
            item_name.setData(Qt.ItemDataRole.UserRole, created_skill.id)
            self.table_skills.setItem(len(self.skills) - 1, 0, item_name)
            self.table_skills.setItem(len(self.skills) - 1, 1, QTableWidgetItem(created_skill.notes))
            self.table_skills.setItem(len(self.skills) - 1, 2, QTableWidgetItem(""))


    def _delete_skill(self):
        skill_id = self.table_skills.item(self.table_skills.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        for i, skill in enumerate(self.skills):
            if skill.id == skill_id:
                if skill.prep_delete:
                    if self._skill_is_used(skill_id):
                        QMessageBox.critical(self, "Error", "Skill is used and cannot be deleted")
                        return
                    reply = QMessageBox.question(self, "Warning",
                                        "Skill wird endgültig gelöscht. Möchtest du es wirklich tun?")
                    if reply == QMessageBox.StandardButton.No:
                        return
                    command = skill_commands.Delete(skill_id, self.project_id)
                else:
                    command = skill_commands.PrepDelete(skill_id)
                break
        else:
            QMessageBox.critical(self, "Error", "Skill not found")
            return
        self.controller.execute(command)
        if isinstance(command, skill_commands.PrepDelete):
            skill.prep_delete = command.skill_deleted.prep_delete
            (self.table_skills.item(self.table_skills.currentRow(), 2)
             .setText(skill.prep_delete.strftime("%d.%m.%Y %H:%M:%S")))
        elif isinstance(command, skill_commands.Delete):
            del self.skills[i]
            self.table_skills.removeRow(self.table_skills.currentRow())

    def _undelete_skill(self):
        if not self.table_skills.item(self.table_skills.currentRow(), 2).text():
            QMessageBox.critical(self, "Error", "Skill is not deleted")
            return
        skill_id = self.table_skills.item(self.table_skills.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        command = skill_commands.Undelete(skill_id)
        self.controller.execute(command)
        skill = command.skill_undeleted
        for i, s in enumerate(self.skills):
            if s.id == skill.id:
                self.skills[i] = skill
                self.table_skills.item(self.table_skills.currentRow(), 2).setText("")

    def _edit_skill(self):
        skill_id = self.table_skills.item(self.table_skills.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        dlg = DlgSkill(self, skill_id)
        if dlg.exec():
            command = skill_commands.Update(
                schemas.SkillUpdate(id=skill_id, name=dlg.name, notes=dlg.notes))
            self.controller.execute(command)
            updated_skill = command.updated_skill
            for skill in self.skills:
                if skill.id == skill_id:
                    skill.name = updated_skill.name
                    skill.notes = updated_skill.notes
            self.table_skills.item(self.table_skills.currentRow(), 0).setText(updated_skill.name)
            self.table_skills.item(self.table_skills.currentRow(), 1).setText(updated_skill.notes)

    def _skill_is_used(self, skill_id: UUID) -> bool:
        return db_services.Skill.is_used(skill_id)


class DlgSelectSkills(QDialog):
    def __init__(self, parent: QWidget, person: schemas.PersonShow):
        super().__init__(parent)
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.person = person

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(f"<h3>Skills</h3>"
                                     f"<p>Wähle hier die Fähigkeiten und Kenntnisse aus,<br>"
                                     f"die {self.person.full_name} für seine Arbeit verwendet.</p>")
        self.layout_head.addWidget(self.lb_description)
        self.table_skills = self._setup_table()
        self._put_skills_in_table()
        self.layout_body.addWidget(self.table_skills)
        self.btn_add_skill = QPushButton("Add Skill")
        self.btn_add_skill.clicked.connect(self._add_skill)
        self.btn_delete_skill = QPushButton("Delete Skill")
        self.btn_delete_skill.clicked.connect(self._remove_skill)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.addButton(self.btn_add_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_delete_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.layout_foot.addWidget(self.button_box)

    def _setup_table(self) -> QTableWidget:
        table_skills = QTableWidget()
        table_skills.setColumnCount(2)
        table_skills.setHorizontalHeaderLabels(["Fähigkeit/Kenntnis", "Beschreibung"])
        table_skills.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table_skills.setAlternatingRowColors(True)
        table_skills.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table_skills.setSortingEnabled(True)
        table_skills.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        return table_skills

    def _put_skills_in_table(self):
        skills = self.person.skills
        self.table_skills.setRowCount(len(skills))
        for row, skill in enumerate(skills):
            item_name = QTableWidgetItem(skill.name)
            item_name.setData(Qt.ItemDataRole.UserRole, skill.id)
            self.table_skills.setItem(row, 0, item_name)
            self.table_skills.setItem(row, 1, QTableWidgetItem(skill.notes))

    def _add_skill(self):
        dlg = DlgSkillsOfProject(
            self, self.person.project.id, {skill.id for skill in self.person.skills})
        if dlg.exec():
            command = person_commands.AddSkill(self.person.id, dlg.selected_skill.id)
            self.controller.execute(command)
            self.person = command.updated_person
            self.table_skills.setRowCount(len(self.person.skills))
            item_name = QTableWidgetItem(dlg.selected_skill.name)
            item_name.setData(Qt.ItemDataRole.UserRole, dlg.selected_skill.id)
            self.table_skills.setItem(len(self.person.skills) - 1, 0, item_name)
            self.table_skills.setItem(len(self.person.skills) - 1, 1, QTableWidgetItem(dlg.selected_skill.notes))

    def _remove_skill(self):
        skill_id = self.table_skills.item(self.table_skills.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        command = person_commands.RemoveSkill(self.person.id, skill_id)
        self.person = command.updated_person
        self.controller.execute(command)
        self.table_skills.removeRow(self.table_skills.currentRow())


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = DlgEditSkills(None, UUID('a2468bcf-064f-4a69-bacf-fd00f929671e'))
    w.show()
    sys.exit(app.exec())
