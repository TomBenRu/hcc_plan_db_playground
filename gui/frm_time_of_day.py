import datetime

from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox

from database import schemas


class FrmTimeOfDay(QDialog):
    def __init__(self, parent: QWidget, time_of_day: schemas.TimeOfDay, only_new_time_of_day=False):
        super().__init__(parent)
        self.setWindowTitle('Tageszeit')

        self.only_new_time_of_day = only_new_time_of_day

        self.curr_time_of_day = time_of_day.copy() if time_of_day else None
        self.new_time_of_day: schemas.TimeOfDayCreate | None = None
        self.to_delete_status = False
        self.new_mode = False

        self.layout = QGridLayout(self)

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.lb_start = QLabel('Zeitpunkt Start')
        self.te_start = QTimeEdit()
        self.lb_end = QLabel('Zeitpunkt Ende')
        self.te_end = QTimeEdit()
        self.bt_delete = QPushButton('Löschen', clicked=self.delete)
        self.chk_new_mode = QCheckBox('Als neue Tageszeit speichern?')
        self.chk_new_mode.toggled.connect(self.change_new_mode)

        self.layout.addWidget(self.lb_name, 0, 0)
        self.layout.addWidget(self.le_name, 0, 1)
        self.layout.addWidget(self.lb_start, 1, 0)
        self.layout.addWidget(self.te_start, 1, 1)
        self.layout.addWidget(self.lb_end, 2, 0)
        self.layout.addWidget(self.te_end, 2, 1)
        self.layout.addWidget(self.chk_new_mode, self.layout.rowCount(), 0, 1, 2)

        self.bt_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.bt_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.DestructiveRole)
        self.bt_box.accepted.connect(self.save_time_of_day)
        self.bt_box.rejected.connect(self.reject)
        self.layout.addWidget(self.bt_box, 4, 0, 1, 2)

        self.autofill()

    def autofill(self):
        if self.curr_time_of_day:
            self.le_name.setText(self.curr_time_of_day.name)
            self.te_start.setTime(self.curr_time_of_day.start)
            self.te_end.setTime(self.curr_time_of_day.end)
        if not self.curr_time_of_day or self.new_mode or self.only_new_time_of_day:
            self.new_mode = True
            self.chk_new_mode.setChecked(True)
            if not self.new_time_of_day or self.only_new_time_of_day:
                self.chk_new_mode.setDisabled(True)

    def change_new_mode(self):
        if self.chk_new_mode.isChecked():
            print('checked', self.chk_new_mode.isChecked())
            self.bt_delete.setDisabled(True)
        else:
            print('checked', self.chk_new_mode.isChecked())
            self.bt_delete.setEnabled(True)

    def save_time_of_day(self):
        name = self.le_name.text()
        if not name:
            QMessageBox.information(self, 'Fehler', 'Sie müsser einen Namen für diese Tageszeit angeben.')
            return
        start = datetime.time(self.te_start.time().hour(), self.te_start.time().minute())
        end = datetime.time(self.te_end.time().hour(), self.te_end.time().minute())

        if self.chk_new_mode.isChecked():
            self.new_time_of_day = schemas.TimeOfDayCreate(name=name, start=start, end=end)
        else:
            self.curr_time_of_day.name = name
            self.curr_time_of_day.start = start
            self.curr_time_of_day.end = end
        self.accept()

    def delete(self):
        self.to_delete_status = True
        self.accept()
