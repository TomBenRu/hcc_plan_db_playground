from uuid import UUID

from PySide6.QtWidgets import QWidget, QDialog, QGridLayout, QTableWidget, QPushButton, QDialogButtonBox, \
    QAbstractItemView, QTableWidgetItem, QMessageBox, QFormLayout, QLineEdit, QCheckBox

from database import schemas, db_services
from commands import command_base_classes
from commands.database_commands import project_commands, time_of_day_enum_commands
from gui.tools.custom_widgets.custom_spin_boxes import CustomSpinBoxDisallowedValues


class DlgTimeOfDayEnumEdit(QDialog):
    def __init__(self, parent: QWidget, time_of_day_enum: schemas.TimeOfDayEnum | None, standard: bool,
                 project: schemas.ProjectShow):
        super().__init__(parent)

        self.project = project
        self.curr_enum = time_of_day_enum
        self.new_enum: schemas.TimeOfDayEnumCreate | None = None
        self.standard = standard

        self.layout = QFormLayout(self)

        self.le_name = QLineEdit()
        self.le_abbreviation = QLineEdit()
        self.sp_time_index = CustomSpinBoxDisallowedValues()
        self.sp_time_index.setMinimum(1)
        self.chk_default = QCheckBox()
        self.chk_new_mode = QCheckBox()

        self.bt_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.bt_box.accepted.connect(self.accept)
        self.bt_box.rejected.connect(self.reject)

        self.layout.addRow('Name', self.le_name)
        self.layout.addRow('Kürzel', self.le_abbreviation)
        self.layout.addRow('Tageszeit-Index', self.sp_time_index)
        self.layout.addRow('Als Standard definieren?', self.chk_default)
        self.layout.addRow('Als neue Tageszeit speichern?', self.chk_new_mode)

        self.layout.addRow(self.bt_box)

        self.autofill()

    def autofill(self):
        if self.curr_enum:
            self.le_name.setText(self.curr_enum.name)
            self.le_abbreviation.setText(self.curr_enum.abbreviation)
            self.sp_time_index.setValue(self.curr_enum.time_index)
            all_indexes = [e.time_index for e in self.project.time_of_day_enums
                           if e.time_index != self.curr_enum.time_index]
        else:
            all_indexes = [e.time_index for e in self.project.time_of_day_enums]
            print(f'{all_indexes=}')
            self.chk_new_mode.setChecked(True)
        self.sp_time_index.setDisallowedValues(all_indexes)
        self.chk_default.setChecked(self.standard)
        self.chk_new_mode.setDisabled(True)

    def accept(self):
        if not all([self.le_name.text().strip(), self.le_abbreviation.text().strip()]):
            QMessageBox.information(self, 'Fehler', 'Sie müssen die Felder für Kürzel und Name ausfüllen.')
            return
        if self.curr_enum:
            self.curr_enum.name = self.le_name.text()
            self.curr_enum.abbreviation = self.le_abbreviation.text()
            self.curr_enum.time_index = self.sp_time_index.value()
            self.curr_enum.project_standard = self.chk_new_mode.isChecked()
        else:
            self.new_enum = schemas.TimeOfDayEnumCreate(
                name=self.le_name.text(),
                abbreviation=self.le_abbreviation.text(),
                time_index=self.sp_time_index.value(),
                project_standard=self.project if self.chk_default.isChecked() else None,
                project=self.project
            )
        super().accept()


class DlgTimeOfDayEnumsEditList(QDialog):
    def __init__(self, parent: QWidget, project: schemas.ProjectShow):
        super().__init__(parent)

        self.resize(450, 350)

        self.project = project.model_copy()

        self.setWindowTitle('Tageszeiten Enums')

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QGridLayout(self)

        self.table_enums: QTableWidget | None = None
        self.setup_table_enums()

        self.bt_new = QPushButton('Neu...', clicked=self.new_enum)
        self.bt_edit = QPushButton('Bearbeiten...', clicked=self.edit_enum)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete_time_of_day_enum)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout.addWidget(self.bt_new, 1, 0)
        self.layout.addWidget(self.bt_edit, 1, 1)
        self.layout.addWidget(self.bt_delete, 1, 2)
        self.layout.addWidget(self.button_box, 3, 0, 1, 3)

    def setup_table_enums(self):
        if self.table_enums:
            self.table_enums.setParent(None)
            self.table_enums.deleteLater()
        self.table_enums = QTableWidget()
        self.layout.addWidget(self.table_enums, 0, 0, 1, 3)
        enums = sorted((t_o_d_enum for t_o_d_enum in self.project.time_of_day_enums
                        if not t_o_d_enum.prep_delete),  key=lambda x: x.time_index)
        enum_standards = [t_o_d_enum for t_o_d_enum in self.project.time_of_day_enum_standards
                          if not t_o_d_enum.prep_delete]
        header_labels = ['id', 'Name', 'Index', 'Standard']
        self.table_enums.setRowCount(len(enums))
        self.table_enums.setColumnCount(len(header_labels))
        self.table_enums.setHorizontalHeaderLabels(header_labels)
        self.table_enums.setSortingEnabled(True)
        self.table_enums.setAlternatingRowColors(True)
        self.table_enums.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_enums.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_enums.horizontalHeader().setHighlightSections(False)
        self.table_enums.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.table_enums.hideColumn(0)

        for row, t_o_d_enum in enumerate(enums):
            self.table_enums.setItem(row, 0, QTableWidgetItem(str(t_o_d_enum.id)))
            self.table_enums.setItem(row, 1, QTableWidgetItem(t_o_d_enum.name))
            self.table_enums.setItem(row, 2, QTableWidgetItem(str(t_o_d_enum.time_index)))
            if t_o_d_enum.id in [t.id for t in enum_standards]:
                text_standard = 'ja'
            else:
                text_standard = 'nein'
            self.table_enums.setItem(row, 3, QTableWidgetItem(text_standard))

    def accept(self) -> None:
        super().accept()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def new_enum(self):
        dlg = DlgTimeOfDayEnumEdit(self, None, False, self.project)

        if not dlg.exec():
            return
        self.create_enum(dlg.new_enum, dlg.chk_default.isChecked())
        self.reload_project()
        self.setup_table_enums()

    def edit_enum(self):
        curr_row = self.table_enums.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, 'Tageszeiten Enums', 'Sie müssen zuerst eine Zeile zur Bearbeitung auswählen.')
            return
        curr_enum_id = UUID(self.table_enums.item(curr_row, 0).text())
        curr_enum = db_services.TimeOfDayEnum.get(curr_enum_id)

        standard = curr_enum_id in [t.id for t in self.project.time_of_day_standards if not t.prep_delete]
        dlg = DlgTimeOfDayEnumEdit(self, curr_enum, standard, self.project)

        if not dlg.exec():
            return

        self.controller.execute(time_of_day_enum_commands.Update(dlg.curr_enum))
        if not standard and dlg.chk_default.isChecked():
            self.controller.execute(project_commands.NewTimeOfDayEnumStandard(curr_enum_id))
        if standard and not dlg.chk_default.isChecked():
            self.controller.execute(project_commands.RemoveTimeOfDayEnumStandard(curr_enum_id))

        self.reload_project()
        self.setup_table_enums()

    def create_enum(self, time_of_day_enum: schemas.TimeOfDayEnumCreate, standard: bool):
        if time_of_day_enum.name in [t.name for t in self.project.time_of_day_enums if not t.prep_delete]:
            '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
            QMessageBox.critical(self, 'Fehler', f'Das Tageszeit-Enum "{time_of_day_enum.name}" ist schon vorhanden.')
            return
        create_command = time_of_day_enum_commands.Create(time_of_day_enum)
        self.controller.execute(create_command)
        if standard:
            created_t_o_d_enum_id = create_command.get_created_time_of_day_enum_id()
            self.controller.execute(project_commands.NewTimeOfDayEnumStandard(created_t_o_d_enum_id))
        # todo: consolidate enum-indexes wth button or with accept

    def delete_time_of_day_enum(self):
        curr_row = self.table_enums.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, 'Tageszeiten Enums', 'Sie müssen zuerst eine Zeile zur Bearbeitung auswählen.')
            return

        curr_enum_id = UUID(self.table_enums.item(curr_row, 0).text())
        self.controller.execute(time_of_day_enum_commands.PrepDelete(curr_enum_id))

        curr_enum = db_services.TimeOfDayEnum.get(curr_enum_id)
        QMessageBox.information(self, 'Tageszeit Enum Löschen', f'Das Tageszeit Enum wurde gelöscht:\n{curr_enum.name}')

    def reload_project(self):
        self.project = db_services.Project.get(self.project.id)