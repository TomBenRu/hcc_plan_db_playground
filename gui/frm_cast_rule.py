from uuid import UUID

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QDialogButtonBox,
                               QMessageBox)

from database import schemas
from gui.commands import command_base_classes, cast_rule_commands
from gui.tools.custom_validators import LettersAndSymbolsValidator
from gui.tools.custom_widgets.custom_line_edits import LineEditWithCustomFont


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
        if not (self.le_name.text().strip() and self.le_cast_rule.text()):
            QMessageBox.critical(self, 'Besetzungsregel', 'Felder "Name" und "Besetzungsregel" dürfen nicht leer sein.')
            return
        create_command = cast_rule_commands.Create(
            self.project_id, self.le_name.text().strip(), self.le_cast_rule.text())
        self.controller.execute(create_command)
        self.created_cast_rule = create_command.created_cast_rule

        super().accept()

    def le_cast_rule_changed(self):
        self.le_cast_rule.blockSignals(True)
        self.le_cast_rule.setText(self.le_cast_rule.text().upper())
        self.le_cast_rule.blockSignals(False)
