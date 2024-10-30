from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QPushButton, QDialogButtonBox, QTableWidget, \
    QTableWidgetItem, QFormLayout, QLineEdit, QHeaderView, QCheckBox
from PySide6.QtCore import Qt

from commands import command_base_classes
from commands.database_commands import skill_commands
from database import db_services, schemas


class DlgSkill(QDialog):
    def __init__(self, parent: QWidget, skill_id: UUID = None):
        super().__init__(parent)
        self.setWindowTitle("Skill")
        self.skill_id = skill_id
        self._setup_ui()
        self._setup_data()

    def _setup_data(self):
        if self.skill_id:
            self.skill = db_services.Skills.get(self.skill_id)
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

        self.lb_description = QLabel("<h3>Skill</h3>"
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
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.btn_add_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_edit_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_delete_skill, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_data(self):
        self.skills: list[schemas.Skill] = db_services.Skills.get_all_from__project(self.project_id)

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


    def _delete_skill(self):
        skill_id = self.table_skills.item(self.table_skills.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        command = skill_commands.Delete(skill_id)
        self.controller.execute(command)
        for skill in self.skills:
            if skill.id == skill_id:
                skill.prep_delete = command.skill_deleted.prep_delete

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


class DlgSelectSkills(QDialog):
    def __init__(self, parent: QWidget, *args, **kwargs):
        super().__init__(parent)
        self.controller = command_base_classes.ContrExecUndoRedo()


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = DlgEditSkills(None, UUID('a2468bcf-064f-4a69-bacf-fd00f929671e'))
    w.show()
    sys.exit(app.exec())
