import string
from uuid import UUID

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QDialogButtonBox,
                               QMessageBox)

from database import schemas, db_services
from commands import command_base_classes
from commands.database_commands import cast_rule_commands
from gui.custom_widgets.custom_line_edits import LineEditWithCustomFont
from gui.tools.custom_validators import LettersAndSymbolsValidator


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

        self.created_cast_rule: schemas.CastRuleShow | None = None
        self.setWindowTitle('Besetzungsregel')

        self.project_id = project_id
        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_info = QLabel('Hier können Sie eine neue Besetzungsregel erstellen.\n'
                              'Symbole:\n'
                              '        *: beliebige Besetzung\n'
                              '        ~: gleiche Besetzung\n'
                              '        -: andere Besetzung\n'
                              '...in Bezug auf den zeitlich vorangegangenen Termin.\n'
                              'Die Sequenz wird automatisch so lange wiederholt, bis die Terminreihe gefüllt ist.')
        self.layout_head.addWidget(self.lb_info)

        self.le_name = QLineEdit()
        self.le_cast_rule = LineEditWithCustomFont(parent=None, font=None, bold=True, letter_spacing=4)
        self.le_cast_rule.setValidator(LettersAndSymbolsValidator('*~-'))
        self.le_cast_rule.textChanged.connect(self.le_cast_rule_changed)

        self.layout_body.addRow('Name', self.le_name)
        self.layout_body.addRow('Besetzungsregel', self.le_cast_rule)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                           QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout_foot.addWidget(self.button_box)

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
        self.le_cast_rule.blockSignals(True)
        self.le_cast_rule.setText(self.le_cast_rule.text().upper())
        self.le_cast_rule.blockSignals(False)
