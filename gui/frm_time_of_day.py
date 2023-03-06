from PySide6.QtWidgets import QDialog, QWidget


class TimeOfDay(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle('Tageszeit')

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.lb_start = QLabel('Zeitpunkt Start')
        self.te_start = QTimeEdit()
        self.lb_end = QLabel('Zeitpunkt Ende')
        self.te_end = QTimeEdit()
        self.bt_save = QPushButton('Tageszeit speichern')
        self.bt_save.clicked.connect(self.save_time_of_day)

        self.layout_group_time_of_day_data.addWidget(self.lb_tod_name, 0, 0)
        self.layout_group_time_of_day_data.addWidget(self.le_tod_name, 0, 1)
        self.layout_group_time_of_day_data.addWidget(self.lb_tod_start, 1, 0)
        self.layout_group_time_of_day_data.addWidget(self.te_tod_start, 1, 1)
        self.layout_group_time_of_day_data.addWidget(self.lb_tod_end, 2, 0)
        self.layout_group_time_of_day_data.addWidget(self.te_tod_end, 2, 1)
        self.layout_group_time_of_day_data.addWidget(self.bt_tod_save, 3, 1)

    def set_time_of_day_values(self):
        tod_name = self.cb_time_of_days.currentText()
        for tod in self.project.time_of_days:
            if tod.name == tod_name and not tod.prep_delete:
                self.le_tod_name.setText(tod.name)
                self.te_tod_start.setTime(tod.start)
                self.te_tod_end.setTime(tod.end)
                break

    def save_time_of_day(self):
        name = self.le_tod_name.text()
        if not name:
            QMessageBox.information(self, 'Fehler', 'Sie müsser einen Namen für diese Tageszeit angeben.')
            return
        start = datetime.time(self.te_tod_start.time().hour(), self.te_tod_start.time().minute())
        end = datetime.time(self.te_tod_end.time().hour(), self.te_tod_end.time().minute())

        if tods := [tod for tod in self.project.time_of_days if tod.name == name and not tod.prep_delete]:
            db_services.delete_time_of_day(tods[0].id)
            self.project.time_of_days.remove(tods[0])
        new_time_of_day = schemas.TimeOfDayCreate(name=name, start=start, end=end)
        created_time_of_day = db_services.create_time_of_day(new_time_of_day, self.project.id)
        self.project.time_of_days.append(created_time_of_day)
        self.project.name = self.le_name.text()
        project_updated = db_services.update_project(self.project)
        self.project = project_updated
        QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit {created_time_of_day.name} wurde upgedatet bzw. dem '
                                                   f'Projekt {self.project.name} hinzugefügt.')
        self.autofill()
        self.cb_time_of_days.setCurrentText(created_time_of_day.name)
