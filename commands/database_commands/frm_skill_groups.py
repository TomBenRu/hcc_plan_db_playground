from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QWidget, QLabel, QDialogButtonBox)

from database import schemas


class DlgSkillGroups(QDialog):
    def __init__(self, parent: QWidget, object_with_skill_groups: schemas.LocationOfWorkShow | schemas.EventShow):
        super().__init__(parent)
        self.setWindowTitle("Skill Groups")

        self.object_with_skill_groups = object_with_skill_groups

        self._setup_ui()

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
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def add_skill_group(self):
        pass

    def remove_skill_group(self):
        pass

    def edit_skill_group(self):
        pass



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
