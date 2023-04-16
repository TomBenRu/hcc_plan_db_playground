import datetime
import functools
import time
from datetime import timedelta
from typing import Callable
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QIcon, QShortcut, QKeySequence, QCloseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QSpacerItem, QGridLayout, QMessageBox, QScrollArea, QTextEdit, \
    QMenu, QDialog, QDialogButtonBox

from database import schemas, db_services
from gui import side_menu, frm_time_of_day
from gui.actions import Action
from gui.commands import command_base_classes, avail_day_commands, time_of_day_commands, actor_plan_period_commands


class ButtonAvailDay(QPushButton):
    def __init__(self, day: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 t_o_d_for_selection: list[schemas.TimeOfDay], slot__save_avail_day: Callable):
        super().__init__()
        self.setObjectName(f'{day}-{time_of_day.time_of_day_enum.name}')
        self.setCheckable(True)
        self.released.connect(lambda: slot__save_avail_day(self))
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        if time_of_day.time_of_day_enum.time_index == 1:
            self.setStyleSheet("QPushButton {background-color: #cae4f4}"
                               "QPushButton::checked { background-color: #002aaa; border: none;}")
        elif time_of_day.time_of_day_enum.time_index == 2:
            self.setStyleSheet("QPushButton {background-color: #fff4d6}"
                               "QPushButton::checked { background-color: #ff4600; border: none;}")
        elif time_of_day.time_of_day_enum.time_index == 3:
            self.setStyleSheet("QPushButton {background-color: #daa4c9}"
                               "QPushButton::checked { background-color: #84033c; border: none;}")

        self.slot__save_avail_day = slot__save_avail_day
        self.day = day
        self.time_of_day = time_of_day
        self.t_o_d_for_selection = t_o_d_for_selection

        self.actions = []
        self.create_actions()
        self.set_tooltip()

    def contextMenuEvent(self, pos):
        context_menu = QMenu()
        context_menu.addActions(self.actions)
        context_menu.exec(pos.globalPos())

    def set_new_time_of_day(self, new_time_of_day: schemas.TimeOfDay):
        if self.isChecked():
            '''Es wird simuliert: Löschen des aktuellen AvailDay, Erzeugen eines neuen AvailDay mit neuer Tageszeit.'''
            self.setChecked(False)
            self.slot__save_avail_day(self)
            self.time_of_day = new_time_of_day
            self.setChecked(True)
            self.slot__save_avail_day(self)
        else:
            self.time_of_day = new_time_of_day
        self.create_actions()
        self.set_tooltip()

    def create_actions(self):
        self.actions = [
            Action(self, QIcon('resources/toolbar_icons/icons/clock-select.png') if t == self.time_of_day else None,
                   f'{t.name}: {t.start.strftime("%H:%M")}-{t.end.strftime("%H:%M")}', None,
                   functools.partial(self.set_new_time_of_day, t))
            for t in self.t_o_d_for_selection]

    def set_tooltip(self):
        self.setToolTip(f'Rechtsklick:\n'
                        f'Zeitspanne für die Tageszeit "{self.time_of_day.time_of_day_enum.name}" '
                        f'am {self.day} wechseln.\nAktuell: {self.time_of_day.name} '
                        f'({self.time_of_day.start.strftime("%H:%M")}-{self.time_of_day.end.strftime("%H:%M")})')


class FrmTabActorPlanPeriods(QWidget):
    def __init__(self, plan_period: schemas.PlanPeriodShow):
        super().__init__()

        self.plan_period = plan_period
        self.actor_plan_periods = [a_pp for a_pp in plan_period.actor_plan_periods]
        self.pers_id__actor_pp = {str(a_pp.person.id): a_pp for a_pp in plan_period.actor_plan_periods}
        self.person_id: UUID | None = None
        self.person: schemas.PersonShow | None = None
        self.scroll_area_availables = QScrollArea()
        self.frame_availables: FrmActorPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum:')
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_actor_pp)
        self.te_notes_pp.setFixedHeight(180)

        self.lb_notes_actor = QLabel('Infos zur Person:')
        font_lb_notes = self.lb_notes_actor.font()
        font_lb_notes.setBold(True)
        self.lb_notes_actor.setFont(font_lb_notes)
        self.te_notes_actor = QTextEdit()
        self.te_notes_actor.textChanged.connect(self.save_info_person)
        self.te_notes_actor.setFixedHeight(180)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.lb_title_name = QLabel('Verfügbarkeiten')
        self.lb_title_name.setContentsMargins(10, 10, 10, 10)

        self.lb_title_name_font = self.lb_title_name.font()
        self.lb_title_name_font.setPointSize(16)
        self.lb_title_name_font.setBold(True)
        self.lb_title_name.setFont(self.lb_title_name_font)
        self.layout.addWidget(self.lb_title_name)

        self.splitter_availables = QSplitter()
        self.layout.addWidget(self.splitter_availables)

        self.side_menu = side_menu.WidgetSideMenu(self, 200, 10, 'right')

        self.table_select_actor = QTableWidget()
        self.splitter_availables.addWidget(self.table_select_actor)
        self.widget_availables = QWidget()
        self.layout_availables = QGridLayout()
        self.layout_availables.setContentsMargins(0, 0, 0, 0)
        self.widget_availables.setLayout(self.layout_availables)
        self.splitter_availables.addWidget(self.widget_availables)
        self.setup_selector_table()
        self.splitter_availables.setSizes([175, 10000])
        self.layout.setStretch(0, 2)
        self.layout.setStretch(1, 99)
        self.layout_notes = QHBoxLayout()
        self.layout_notes_actor = QVBoxLayout()
        self.layout_notes_actor_pp = QVBoxLayout()

        self.layout_availables.addWidget(self.scroll_area_availables, 0, 0)
        self.layout_availables.addLayout(self.layout_notes, 1, 0)
        self.layout_notes.addLayout(self.layout_notes_actor_pp)
        self.layout_notes.addLayout(self.layout_notes_actor)
        self.layout_notes_actor_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_actor_pp.addWidget(self.te_notes_pp)
        self.layout_notes_actor.addWidget(self.lb_notes_actor)
        self.layout_notes_actor.addWidget(self.te_notes_actor)

    def setup_selector_table(self):
        self.table_select_actor.setMaximumWidth(175)
        self.table_select_actor.setMinimumWidth(150)
        self.table_select_actor.setSortingEnabled(True)
        self.table_select_actor.setAlternatingRowColors(True)
        self.table_select_actor.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_select_actor.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_select_actor.verticalHeader().setVisible(False)
        self.table_select_actor.horizontalHeader().setHighlightSections(False)
        self.table_select_actor.cellClicked.connect(self.data_setup)
        self.table_select_actor.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_actor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        headers = ['id', 'Vorname', 'Nachname']
        self.table_select_actor.setColumnCount(len(headers))
        self.table_select_actor.setRowCount(len(self.pers_id__actor_pp))
        self.table_select_actor.setHorizontalHeaderLabels(headers)
        for row, actor_pp in enumerate(sorted(self.pers_id__actor_pp.values(), key=lambda x: x.person.f_name)):
            self.table_select_actor.setItem(row, 0, QTableWidgetItem(str(actor_pp.person.id)))
            self.table_select_actor.setItem(row, 1, QTableWidgetItem(actor_pp.person.f_name))
            self.table_select_actor.setItem(row, 2, QTableWidgetItem(actor_pp.person.l_name))
        self.table_select_actor.hideColumn(0)

    def data_setup(self, r, c):
        self.table_select_actor.setMaximumWidth(10000)
        self.person_id = UUID(self.table_select_actor.item(r, 0).text())
        self.person = db_services.Person.get(self.person_id)
        actor_plan_period = self.pers_id__actor_pp[str(self.person_id)]
        actor_plan_period_show = db_services.ActorPlanPeriod.get(actor_plan_period.id)
        self.lb_title_name.setText(
            f'Verfügbarkeiten: {f"{actor_plan_period.person.f_name} {actor_plan_period.person.l_name}"}')
        self.layout_availables.addWidget(self.scroll_area_availables, 0, 0)
        self.frame_availables = FrmActorPlanPeriod(actor_plan_period_show, self.side_menu)
        self.scroll_area_availables.setWidget(self.frame_availables)

        self.info_text_setup()

    def info_text_setup(self):
        self.te_notes_pp.textChanged.disconnect()
        self.te_notes_pp.clear()
        self.te_notes_pp.setText(self.pers_id__actor_pp[str(self.person_id)].notes)
        self.te_notes_pp.textChanged.connect(self.save_info_actor_pp)
        self.te_notes_actor.textChanged.disconnect()
        self.te_notes_actor.clear()
        self.te_notes_actor.setText(self.person.notes)
        self.te_notes_actor.textChanged.connect(self.save_info_person)

    def save_info_actor_pp(self):
        updated_actor_plan_period = db_services.ActorPlanPeriod.update_notes(
            schemas.ActorPlanPeriodUpdate(id=self.pers_id__actor_pp[str(self.person_id)].id,
                                          notes=self.te_notes_pp.toPlainText()))
        self.pers_id__actor_pp[str(updated_actor_plan_period.person.id)] = updated_actor_plan_period

    def save_info_person(self):
        self.person.notes = self.te_notes_actor.toPlainText()
        updated_actor = db_services.Person.update(self.person)


class FrmActorPlanPeriod(QWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow, side_menu: side_menu.WidgetSideMenu):
        super().__init__()

        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu
        self.setup_side_menu()

        self.controller_avail_days = command_base_classes.ContrExecUndoRedo()
        self.actor_plan_period = actor_plan_period
        self.t_o_d_standards: list[schemas.TimeOfDay] = []
        self.t_o_d_enums: list[schemas.TimeOfDayEnum] = []
        self.actor_plan_period_time_of_days: list[schemas.TimeOfDay] = []
        self.days: list[datetime.date] = []
        self.set_instance_variables()

        self.weekdays = {0: 'Mo', 1: 'Di', 2: 'Mi', 3: 'Do', 4: 'Fr', 5: 'Sa', 6: 'So'}
        self.months = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
                       9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}

        self.set_headers_months()
        self.set_chk_field()
        self.get_avail_days()

    def setup_side_menu(self):
        self.side_menu.delete_all_buttons()
        bt_time_of_days = QPushButton('Tageszeiten...', clicked=self.edit_time_of_days)
        self.side_menu.add_button(bt_time_of_days)

    def set_instance_variables(self):
        self.t_o_d_standards = sorted([t_o_d for t_o_d in self.actor_plan_period.time_of_day_standards
                                       if not t_o_d.prep_delete], key=lambda x: x.time_of_day_enum.time_index)
        self.t_o_d_enums = [t_o_d.time_of_day_enum for t_o_d in self.t_o_d_standards]
        self.actor_plan_period_time_of_days = sorted(
            [t_o_d for t_o_d in self.actor_plan_period.time_of_days if not t_o_d.prep_delete], key=lambda x: x.start)
        self.days = [
            self.actor_plan_period.plan_period.start + timedelta(delta) for delta in
            range((self.actor_plan_period.plan_period.end - self.actor_plan_period.plan_period.start).days + 1)]

    def set_headers_months(self):
        month_year = [(d.month, d.year) for d in self.days]
        header_items_months = {m_y: month_year.count(m_y) for m_y in sorted({my for my in month_year},
                                                                            key=lambda x: f'{x[1]}{x[0]:02}')}
        col = 1
        for (month, year), count in header_items_months.items():
            label = QLabel(f'{self.months[month]} {year}')
            label.setStyleSheet('background: qlineargradient( x1:0 y1:0, x2:1 y2:0, stop:0 #a9ffaa, stop:1 #137100)')
            label_font = label.font()
            label_font.setPointSize(12)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setContentsMargins(5, 5, 5, 5)
            self.layout.addWidget(label, 0, col, 1, count)
            col += count

    def set_chk_field(self):
        for col, d in enumerate(self.days, start=1):
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            if not self.t_o_d_standards:
                QMessageBox.critical(self, 'Verfügbarkeiten',
                                     f'Für diesen Planungszeitraum von {self.actor_plan_period.person.f_name} '
                                     f'{self.actor_plan_period.person.l_name} sind noch keine '
                                     f'Tageszeiten-Standartwerdte definiert.')
                return
            for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
                self.layout.addWidget(QLabel(time_of_day.time_of_day_enum.name), row, 0)
                self.create_time_of_day_button(d, time_of_day, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet('background-color: #ffdc99')
            self.layout.addWidget(lb_weekday, row+1, col)

    def create_time_of_day_button(self, day: datetime.date, time_of_day: schemas.TimeOfDay, row: int, col: int):
        t_o_d_for_selection = [t_o_d for t_o_d in self.actor_plan_period_time_of_days
                               if t_o_d.time_of_day_enum == time_of_day.time_of_day_enum]
        button = ButtonAvailDay(day, time_of_day, 24, t_o_d_for_selection, self.save_avail_day)
        self.layout.addWidget(button, row, col)

    def save_avail_day(self, bt: ButtonAvailDay):
        date = bt.day
        t_o_d = bt.time_of_day
        if bt.isChecked():
            avail_day_new = schemas.AvailDayCreate(day=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d)
            save_command = avail_day_commands.Create(avail_day_new)
            self.controller_avail_days.execute(save_command)
            created_avail_day = save_command.created_avail_day

            '''new_avail_day = db_services.AvailDay.create(
                schemas.AvailDayCreate(day=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d))
            # QMessageBox.information(self, 'new time_of_day', f'{new_avail_day}')'''
        else:
            avail_day = db_services.AvailDay.get_from__pp_date_tod(self.actor_plan_period.id, date, t_o_d.id)
            del_command = avail_day_commands.Delete(avail_day.id)
            self.controller_avail_days.execute(del_command)
            '''deleted_avail_day = db_services.AvailDay.delete(avail_day.id)'''

    def get_avail_days(self):
        avail_days = [ad for ad in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id)
                      if not ad.prep_delete]
        for ad in avail_days:
            button: ButtonAvailDay = self.findChild(QPushButton, f'{ad.day}-{ad.time_of_day.time_of_day_enum.name}')
            if not button:
                QMessageBox.critical(self, 'Fehlende Standards',
                                     f'Fehler:\n'
                                     f'Kann die verfügbaren Zeiten nich anzeigen.\nEventuell haben Sie nachträglich '
                                     f'"{ad.time_of_day.time_of_day_enum.name}" aus den Standards gelöscht.')
                return
            button.setChecked(True)
            button.time_of_day = ad.time_of_day
            button.create_actions()
            button.set_tooltip()

    def edit_time_of_days(self):
        dlg = TimeOfDays(self, self.actor_plan_period)
        dlg.exec()
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)


class TimeOfDays(QDialog):
    def __init__(self, parent: QWidget, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.resize(450, 350)
        self.setWindowTitle(f'Tageszeiten des Planungszeitraums, '
                            f'{actor_plan_period.person.f_name} {actor_plan_period.person.l_name}')

        self.actor_plan_period = actor_plan_period

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QGridLayout(self)

        self.table_time_of_days: QTableWidget | None = None
        self.setup_table_time_of_days()

        self.bt_new = QPushButton('Neu...', clicked=self.create_time_of_day)
        self.bt_edit = QPushButton('Berabeiten...', clicked=self.edit_time_of_day)
        self.bt_delete = QPushButton('Löschen', clicked=self.delete_time_of_day)
        self.bt_reset = QPushButton('Reset', clicked=self.reset_time_of_days)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.setCenterButtons(True)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.escape)

        QShortcut(QKeySequence("Esc"), self, self.escape)

        self.layout.addWidget(self.bt_new, 1, 0)
        self.layout.addWidget(self.bt_edit, 1, 1)
        self.layout.addWidget(self.bt_delete, 1, 2)
        self.layout.addWidget(self.bt_reset, 2, 1)
        self.layout.addWidget(self.button_box, 3, 0, 1, 3)

    def setup_table_time_of_days(self):
        if self.table_time_of_days:
            self.table_time_of_days.deleteLater()
        self.table_time_of_days = QTableWidget()
        self.layout.addWidget(self.table_time_of_days, 0, 0, 1, 3)
        time_of_days = sorted(self.actor_plan_period.time_of_days, key=lambda x: x.time_of_day_enum.time_index)
        time_of_day_standards = self.actor_plan_period.time_of_day_standards
        header_labels = ['id', 'Name', 'Zeitspanne', 'Enum', 'Standard']
        self.table_time_of_days.setRowCount(len(time_of_days))
        self.table_time_of_days.setColumnCount(len(header_labels))
        self.table_time_of_days.setHorizontalHeaderLabels(header_labels)
        self.table_time_of_days.setSortingEnabled(True)
        self.table_time_of_days.setAlternatingRowColors(True)
        self.table_time_of_days.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_time_of_days.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_time_of_days.horizontalHeader().setHighlightSections(False)
        self.table_time_of_days.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.table_time_of_days.hideColumn(0)

        for row, t_o_d in enumerate(time_of_days):
            self.table_time_of_days.setItem(row, 0, QTableWidgetItem(str(t_o_d.id)))
            self.table_time_of_days.setItem(row, 1, QTableWidgetItem(t_o_d.name))
            text_times = f'{t_o_d.start.strftime("%H:%M")}-{t_o_d.end.strftime("%H:%M")}'
            self.table_time_of_days.setItem(row, 2, QTableWidgetItem(text_times))
            self.table_time_of_days.setItem(row, 3, QTableWidgetItem(t_o_d.time_of_day_enum.name))
            if t_o_d.id in [t.id for t in time_of_day_standards]:
                text_standard = 'ja'
            else:
                text_standard = 'nein'
            self.table_time_of_days.setItem(row, 4, QTableWidgetItem(text_standard))

    def closeEvent(self, event):
        self.escape()
        super().closeEvent(event)

    def escape(self):
        print('reject')
        self.controller.undo_all()
        self.reject()

    def create_time_of_day(self):
        project = db_services.Project.get(self.actor_plan_period.project.id)
        dlg = frm_time_of_day.FrmTimeOfDay(self, None, project, True)

        if dlg.exec():
            ...

    def edit_time_of_day(self):
        curr_row = self.table_time_of_days.currentRow()
        if curr_row == -1:
            QMessageBox.critical(self, 'Tageszeiten', 'Sie müssen zuerst eine Tageszeit zur Bearbeitung auswählen.')
            return
        curr_t_o_d_id = UUID(self.table_time_of_days.item(curr_row, 0).text())
        curr_t_o_d = db_services.TimeOfDay.get(curr_t_o_d_id)
        _, only_new_time_of_day_cause_parent_model, standard = frm_time_of_day.set_params_for__frm_time_of_day(
            self.actor_plan_period, curr_t_o_d_id, 'persons_defaults')

        project = db_services.Project.get(self.actor_plan_period.project.id)
        dlg = frm_time_of_day.FrmTimeOfDay(self, curr_t_o_d, project, only_new_time_of_day_cause_parent_model, standard)
        dlg.set_delete_disabled()
        dlg.set_new_mode_disabled()

        if not dlg.exec():
            return

        if dlg.chk_new_mode.isChecked():
            if only_new_time_of_day_cause_parent_model:
                '''Die aktuell gewählte Tageszeit ist dem parent-model zugeordnet 
                und wird daher aus time_of_days entfernt.'''
                for t_o_d in self.actor_plan_period.time_of_days:
                    if t_o_d.id == curr_t_o_d_id:
                        self.actor_plan_period.time_of_days.remove(t_o_d)
                        break
            if dlg.new_time_of_day.name in [t.name for t in self.actor_plan_period.time_of_days if not t.prep_delete]:
                '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
                QMessageBox.critical(dlg, 'Fehler', f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                if only_new_time_of_day_cause_parent_model:  # Die zuvor entfernte Tagesz. wird wieder hinzugefügt
                    self.actor_plan_period.time_of_days.append(curr_t_o_d)
            else:
                if only_new_time_of_day_cause_parent_model:
                    '''Die aktuelle Tageszeit wurde aus times_of_days entfernt, weil sie zum Parent-Model gehöhrt.
                     Falls sie sich auch in den Personenstandarts befindet, wird sie auch da entfernt.'''
                    if curr_t_o_d_id in [t.id for t in self.actor_plan_period.time_of_day_standards]:
                        self.controller.execute(
                            actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id,
                                                                               curr_t_o_d_id))

                create_command = time_of_day_commands.Create(dlg.new_time_of_day, self.actor_plan_period.project.id)
                self.controller.execute(create_command)
                created_t_o_d_id = create_command.time_of_day_id
                self.actor_plan_period.time_of_days.append(db_services.TimeOfDay.get(created_t_o_d_id))
                self.controller.execute(actor_plan_period_commands.Update(self.actor_plan_period))

                if dlg.chk_default.isChecked():
                    self.controller.execute(
                        actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id, created_t_o_d_id))
                else:
                    self.controller.execute(
                        actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id, created_t_o_d_id))

        else:
            if dlg.curr_time_of_day.name in [t.name for t in self.actor_plan_period.time_of_days
                                             if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
                QMessageBox.critical(dlg, 'Fehler',
                                     f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
            else:
                curr_t_o_d_id = dlg.curr_time_of_day.id
                self.controller.execute(time_of_day_commands.Update(dlg.curr_time_of_day))

                if dlg.chk_default.isChecked():
                    self.controller.execute(
                        actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id, curr_t_o_d_id))
                else:
                    self.controller.execute(
                        actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id, curr_t_o_d_id))

        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.setup_table_time_of_days()

    def reset_time_of_days(self):
        project = db_services.Project.get(self.actor_plan_period.project.id)
        for t_o_d in self.actor_plan_period.time_of_days:
            '''Alle nicht nur zur Location gehörigen TimeOfDays werden mit dem Controller gelöscht.
            Diese werden dann mit Bestätigen des vorherigen Dialogs entgültig gelöscht.'''
            if not db_services.TimeOfDay.get(t_o_d.id).project_defaults:
                '''Das funktioniert, weil der Eintrag nicht wirklich gelöscht wird, 
                sondern nur das Attribut "prep_delete" gesetzt wird.'''
                self.controller.execute(time_of_day_commands.Delete(t_o_d.id))
        for t_o_d in self.actor_plan_period.time_of_day_standards:
            self.controller.execute(actor_plan_period_commands.RemoveTimeOfDayStandard(self.actor_plan_period.id,
                                                                                       t_o_d.id))
        self.actor_plan_period.time_of_days.clear()  # notendig?
        for t_o_d in [t for t in project.time_of_days if not t.prep_delete]:
            self.actor_plan_period.time_of_days.append(t_o_d)
            if t_o_d.project_standard:
                self.controller.execute(actor_plan_period_commands.NewTimeOfDayStandard(self.actor_plan_period.id,
                                                                                        t_o_d.id))

        self.controller.execute(actor_plan_period_commands.Update(self.actor_plan_period))
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)

        QMessageBox.information(self, 'Tageszeiten reset',
                                f'Die Tageszeiten wurden zurückgesetzt:\n'
                                f'{[(t_o_d.name, t_o_d.start, t_o_d.end) for t_o_d in self.actor_plan_period.time_of_days]}')
        self.setup_table_time_of_days()

    def delete_time_of_day(self):
        ...


