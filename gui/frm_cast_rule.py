import string
from uuid import UUID

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QDialogButtonBox,
                               QMessageBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QPushButton)
from PySide6.QtCore import Qt

from database import schemas, db_services
from commands import command_base_classes
from commands.database_commands import cast_rule_commands
from gui.custom_widgets.custom_line_edits import LineEditWithCustomFont
from tools.custom_validators import LettersAndSymbolsValidator


def simplify_cast_rule(cast_rule: str) -> str | None:
    if not cast_rule:  # leerer String
        return None

    string_part = cast_rule
    for i in range(1, len(cast_rule)):
        if len(cast_rule) % i == 0 and cast_rule[:i] * (len(cast_rule) // i) == cast_rule:
            string_part = cast_rule[:i]
            break
    if string_part == '*':
        string_part = None
    if string_part and len(string_part) == 1 and string_part in string.ascii_letters:
        string_part = '~'

    return string_part


class DlgCastRule(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.project_id = project_id
        self.controller = command_base_classes.ContrExecUndoRedo()
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

        self.lb_info = QLabel()
        self.layout_head.addWidget(self.lb_info)

        self.le_name = QLineEdit()
        self.le_cast_rule = LineEditWithCustomFont(parent=None, font=None, bold=True, letter_spacing=4)
        self.le_cast_rule.setValidator(LettersAndSymbolsValidator('*~-', False))
        self.le_cast_rule.textChanged.connect(self.le_cast_rule_changed)

        self.layout_body.addRow('Name', self.le_name)
        self.layout_body.addRow('Besetzungsregel', self.le_cast_rule)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                           QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout_foot.addWidget(self.button_box)

    def _setup_data(self):
        ...

    def le_cast_rule_changed(self):
        self.le_cast_rule.blockSignals(True)
        self.le_cast_rule.setText(self.le_cast_rule.text().upper())
        self.le_cast_rule.blockSignals(False)


class DlgCreateCastRule(DlgCastRule):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent, project_id=project_id)

        self.setWindowTitle('Neue Besetzungsregel')
        self.created_cast_rule: schemas.CastRuleShow | None = None

    def _setup_ui(self):
        super()._setup_ui()

    def _setup_data(self):
        self.lb_info.setText('Hier können Sie eine neue Besetzungsregel erstellen.\n'
                              'Symbole:\n'
                              '        *: beliebige Besetzung\n'
                              '        ~: gleiche Besetzung\n'
                              '        -: andere Besetzung\n'
                              '...in Bezug auf den zeitlich vorangegangenen Termin.\n'
                              'Die Sequenz wird automatisch so lange wiederholt, bis die Terminreihe gefüllt ist.')

    def accept(self) -> None:
        project_cast_rules = [cr for cr in db_services.CastRule.get_all_from__project(self.project_id)
                              if not cr.prep_delete]

        if not (self.le_name.text().strip() and self.le_cast_rule.text()):
            QMessageBox.critical(self, 'Besetzungsregel', 'Felder "Name" und "Besetzungsregel" dürfen nicht leer sein.')
            return
        cast_rule = simplify_cast_rule(self.le_cast_rule.text())
        if cast_rule != self.le_cast_rule.text():
            QMessageBox.information(self, 'Besetzungsregel',
                                    f'Die Besetzungsregel wurde vereinfacht:\n'
                                    f'original: {self.le_cast_rule.text()}\nvereinfacht: {cast_rule}')
            if not cast_rule:
                QMessageBox.critical(self, 'Besetzungsregel',
                                     'Durch Vereinfachung is die Besetzungsregel nun None. '
                                     'Bitte wählen Sie eine Besetzungsregel deren Equivalent nicht None ist.')
                return

        if (name := self.le_name.text().strip()) in {cr.name for cr in project_cast_rules}:
            QMessageBox.critical(self, 'Besetzungsregel',
                                 f'Der Name "{name}" ist schon in den Besetzungsregeln des Projekts vorhanden.')
            return

        if same_cast_rule := next((cr for cr in project_cast_rules if cr.rule == cast_rule), None):
            QMessageBox.critical(self, 'Besetzungsregel',
                                 f'Die Besetzungsregel "{cast_rule}" ist schon in den Besetzungsregeln des Projekts '
                                 f'vorhanden.\nSie ist unter dem Namen "{same_cast_rule.name}" gespeichert.')
            return

        create_command = cast_rule_commands.Create(
            self.project_id, self.le_name.text().strip(), cast_rule)
        self.controller.execute(create_command)
        self.created_cast_rule = create_command.created_cast_rule

        super().accept()

    def le_cast_rule_changed(self):
        super().le_cast_rule_changed()


class DlgEditCastRule(DlgCastRule):
    def __init__(self, parent: QWidget, project_id: UUID, cast_rule_id: UUID):
        self.cast_rule_id = cast_rule_id
        super().__init__(parent=parent, project_id=project_id)
        self.setWindowTitle('Besetzungsregel bearbeiten')
        self.updated_cast_rule: schemas.CastRuleShow | None = None

    def _setup_data(self):
        self.cast_rule = db_services.CastRule.get(self.cast_rule_id)
        self.le_name.setText(self.cast_rule.name)
        self.le_cast_rule.setText(self.cast_rule.rule)
        self.lb_info.setText(
            'Hier können Sie die ausgewählte Besetzungsregel bearbeiten.\n'
            'Symbole:\n'
            '        *: beliebige Besetzung\n'
            '        ~: gleiche Besetzung\n'
            '        -: andere Besetzung\n'
            '...in Bezug auf den zeitlich vorangegangenen Termin.\n'
            'Die Sequenz wird automatisch so lange wiederholt, bis die Terminreihe gefüllt ist.'
        )

    def accept(self) -> None:
        project_cast_rules = [cr for cr in db_services.CastRule.get_all_from__project(self.project_id)
                              if not cr.prep_delete and cr.id != self.cast_rule_id]

        if not (self.le_name.text().strip() and self.le_cast_rule.text()):
            QMessageBox.critical(self, 'Besetzungsregel', 'Felder "Name" und "Besetzungsregel" dürfen nicht leer sein.')
            return
        cast_rule = simplify_cast_rule(self.le_cast_rule.text())
        if cast_rule != self.le_cast_rule.text():
            QMessageBox.information(self, 'Besetzungsregel',
                                    f'Die Besetzungsregel wurde vereinfacht:\n'
                                    f'original: {self.le_cast_rule.text()}\nvereinfacht: {cast_rule}')
            if not cast_rule:
                QMessageBox.critical(self, 'Besetzungsregel',
                                     'Durch Vereinfachung is die Besetzungsregel nun None. '
                                     'Bitte wählen Sie eine Besetzungsregel deren Equivalent nicht None ist.')
                return

        if (name := self.le_name.text().strip()) in {cr.name for cr in project_cast_rules}:
            QMessageBox.critical(self, 'Besetzungsregel',
                                 f'Der Name "{name}" ist schon in den Besetzungsregeln des Projekts vorhanden.')
            return

        if same_cast_rule := next((cr for cr in project_cast_rules if cr.rule == cast_rule), None):
            QMessageBox.critical(self, 'Besetzungsregel',
                                 f'Die Besetzungsregel "{cast_rule}" ist schon in den Besetzungsregeln des Projekts '
                                 f'vorhanden.\nSie ist unter dem Namen "{same_cast_rule.name}" gespeichert.')
            return

        update_command = cast_rule_commands.Update(
            self.cast_rule_id, self.le_name.text().strip(), cast_rule)
        self.controller.execute(update_command)
        self.updated_cast_rule = update_command.updated_cast_rule

        super().accept()


class DlgCastRules(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle('Besetzungsregeln')
        self.project_id = project_id
        self.controller = command_base_classes.ContrExecUndoRedo()

        self._setup_data()
        self._setup_ui()

    def _setup_data(self):
        self.cast_rules = sorted((cr for cr in db_services.CastRule.get_all_from__project(self.project_id)
                                  if not cr.prep_delete), key=lambda cr: cr.name)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_info = QLabel('Hier können Sie die Besetzungsregeln des Projekts bearbeiten.')
        self.layout_head.addWidget(self.lb_info)

        self.table_widget = self._create_table()
        self._fill_in_table_widget()
        self.layout_body.addWidget(self.table_widget)

        self.btn_create_cast_rule = QPushButton('Neue Besetzungsregel')
        self.btn_edit_cast_rule = QPushButton('Besetzungsregel bearbeiten')
        self.btn_delete_cast_rule = QPushButton('Besetzungsregel löschen')
        self.btn_create_cast_rule.clicked.connect(self._create_cast_rule)
        self.btn_edit_cast_rule.clicked.connect(self._edit_cast_rule)
        self.btn_delete_cast_rule.clicked.connect(self._delete_cast_rule)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.btn_create_cast_rule, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_edit_cast_rule, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.btn_delete_cast_rule, QDialogButtonBox.ButtonRole.ActionRole)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _create_table(self) -> QTableWidget:
        table_widget = QTableWidget()
        table_widget.setColumnCount(2)
        table_widget.setHorizontalHeaderLabels(['Name', 'Besetzungsregel'])
        table_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table_widget.cellDoubleClicked.connect(self._edit_cast_rule)
        return table_widget

    def _fill_in_table_widget(self):
        self.table_widget.setRowCount(len(self.cast_rules))
        for i, cr in enumerate(self.cast_rules):
            item = QTableWidgetItem(cr.name)
            item.setData(Qt.ItemDataRole.UserRole, cr.id)
            self.table_widget.setItem(i, 0, item)
            self.table_widget.setItem(i, 1, QTableWidgetItem(cr.rule))
        self.table_widget.resizeColumnsToContents()

    def _refresh_table(self):
        self.table_widget.clear()
        self.table_widget.setRowCount(0)
        self._fill_in_table_widget()

    def _create_cast_rule(self):
        dlg = DlgCreateCastRule(self, self.project_id)
        if dlg.exec():
            self._setup_data()
            self._refresh_table()
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())

        else:
            dlg.controller.undo_all()

    def _edit_cast_rule(self, row: int = None, column: int = None):
        if not row:
            row = self.table_widget.currentRow()
        current_cast_rule_id = self.table_widget.item(row, 0).data(Qt.ItemDataRole.UserRole)
        dlg = DlgEditCastRule(self, self.project_id, current_cast_rule_id)
        if dlg.exec():
            self._setup_data()
            self._refresh_table()
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
        else:
            dlg.controller.undo_all()

    def _delete_cast_rule(self):
        current_cast_rule_id = self.table_widget.item(self.table_widget.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
        delete_command = cast_rule_commands.SetPrepDelete(current_cast_rule_id)
        self.controller.execute(delete_command)
        self._setup_data()
        self._refresh_table()
