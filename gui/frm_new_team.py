from PySide6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel


class FrmNewTeam(QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.setWindowTitle('Neues Team')

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.lb_team_name = QLabel('Wie soll der Name des Teams sein?')

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(self.lb_team_name)
        self.layout.addWidget(self.button_box)



