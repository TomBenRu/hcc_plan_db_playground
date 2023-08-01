import datetime
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout, QAbstractItemView, QHeaderView, QTableWidgetItem, QPushButton, QMessageBox

from database import schemas, db_services
from database.special_schema_requests import get_curr_assignment_of_location
from gui import side_menu
from gui.commands import command_base_classes
from gui.observer import signal_handling


class FrmTabLocationPlanPeriods(QWidget):
    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.location_plan_periods = self.plan_period.location_plan_periods
        self.location_id__location_pp = {str(loc_pp.location_of_work.id): loc_pp
                                         for loc_pp in self.plan_period.location_plan_periods}
        self.location_id: UUID | None = None
        self.location: schemas.PersonShow | None = None
        self.scroll_area_events = QScrollArea()
        self.frame_events: FrmLocationPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_pp.setFixedHeight(180)

        self.lb_notes_location = QLabel('Infos zur Einrichtung:')
        self.lb_notes_location.setFixedHeight(20)
        font_lb_notes = self.lb_notes_location.font()
        font_lb_notes.setBold(True)
        self.lb_notes_location.setFont(font_lb_notes)
        self.te_notes_location = QTextEdit()
        self.te_notes_location.textChanged.connect(self.save_info_location)
        self.te_notes_location.setFixedHeight(180)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lb_title_name = QLabel('Einrichtungstermine')
        self.lb_title_name.setContentsMargins(10, 10, 10, 10)

        self.lb_title_name_font = self.lb_title_name.font()
        self.lb_title_name_font.setPointSize(16)
        self.lb_title_name_font.setBold(True)
        self.lb_title_name.setFont(self.lb_title_name_font)
        self.layout.addWidget(self.lb_title_name)

        self.splitter_events = QSplitter()
        self.layout.addWidget(self.splitter_events)

        self.table_select_location = QTableWidget()
        self.splitter_events.addWidget(self.table_select_location)
        self.setup_selector_table()
        self.widget_events = QWidget()
        self.layout_events = QGridLayout()
        self.layout_events.setContentsMargins(0, 0, 0, 0)
        self.widget_events.setLayout(self.layout_events)
        self.splitter_events.addWidget(self.widget_events)
        self.set_splitter_sizes()


        self.layout_controllers = QHBoxLayout()
        self.layout_notes = QHBoxLayout()
        self.layout_notes_location = QVBoxLayout()
        self.layout_notes_location_pp = QVBoxLayout()

        self.layout_events.addWidget(self.scroll_area_events, 0, 0)
        self.layout_events.addLayout(self.layout_controllers, 1, 0)
        self.layout_events.addLayout(self.layout_notes, 2, 0)
        self.layout_notes.addLayout(self.layout_notes_location_pp)
        self.layout_notes.addLayout(self.layout_notes_location)
        self.layout_notes_location_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_location_pp.addWidget(self.te_notes_pp)
        self.layout_notes_location.addWidget(self.lb_notes_location)
        self.layout_notes_location.addWidget(self.te_notes_location)

        self.side_menu = side_menu.WidgetSideMenu(self, 250, 10, 'right')

    def setup_selector_table(self):
        self.table_select_location.setSortingEnabled(True)
        self.table_select_location.setAlternatingRowColors(True)
        self.table_select_location.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_select_location.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_select_location.verticalHeader().setVisible(False)
        self.table_select_location.horizontalHeader().setHighlightSections(False)
        self.table_select_location.cellClicked.connect(self.data_setup)
        self.table_select_location.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_location.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        headers = ['id', 'Name', 'Ort']
        self.table_select_location.setColumnCount(len(headers))
        self.table_select_location.setRowCount(len(self.location_id__location_pp))
        self.table_select_location.setHorizontalHeaderLabels(headers)
        for row, location_pp in enumerate(sorted(self.location_id__location_pp.values(),
                                                 key=lambda x: x.location_of_work.name)):
            self.table_select_location.setItem(row, 0, QTableWidgetItem(str(location_pp.location_of_work.id)))
            self.table_select_location.setItem(row, 1, QTableWidgetItem(location_pp.location_of_work.name))
            self.table_select_location.setItem(row, 2, QTableWidgetItem(location_pp.location_of_work.address.city))
        self.table_select_location.hideColumn(0)

    def set_splitter_sizes(self):
        self.splitter_events.setStretchFactor(0, 0)
        self.splitter_events.setStretchFactor(1, 1)
        header_width = sum(self.table_select_location.horizontalHeader().sectionSize(i)
                           for i in range(self.table_select_location.columnCount()))
        header_width += 3

        self.splitter_events.setSizes([header_width, 10_000])
        self.table_select_location.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def data_setup(self, r, c):
        self.location_id = UUID(self.table_select_location.item(r, 0).text())
        self.location = db_services.LocationOfWork.get(self.location_id)
        location_plan_period = self.location_id__location_pp[str(self.location_id)]
        location_plan_period_show = db_services.LocationPlanPeriod.get(location_plan_period.id)
        self.lb_title_name.setText(f'Termine: {location_plan_period_show.location_of_work.name} '
                                   f'{location_plan_period_show.location_of_work.address.city}')

        if self.frame_events:
            self.disconnect_event_button_signals()
            self.delete_location_plan_period_widgets()
        self.frame_events = FrmLocationPlanPeriod(self, location_plan_period_show, self.side_menu)
        self.scroll_area_events.setWidget(self.frame_events)

        self.info_text_setup()

    def disconnect_event_button_signals(self):
        try:
            signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.disconnect()
            signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.disconnect()
        except Exception as e:
            print(f'Fehler: {e}')

    def delete_location_plan_period_widgets(self):
        self.frame_events.deleteLater()
        for widget in (self.layout_controllers.itemAt(i).widget() for i in range(self.layout_controllers.count())):
            widget.deleteLater()

    def info_text_setup(self):
        self.te_notes_pp.textChanged.disconnect()
        self.te_notes_pp.clear()
        self.te_notes_pp.setText(self.location_id__location_pp[str(self.location_id)].notes)
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_location.textChanged.disconnect()
        self.te_notes_location.clear()
        self.te_notes_location.setText(self.location.notes)
        self.te_notes_location.textChanged.connect(self.save_info_location)

    def save_info_location_pp(self):
        updated_location_plan_period = db_services.LocationPlanPeriod.update_notes(
            self.location_id__location_pp[str(self.location_id)].id, self.te_notes_pp.toPlainText())
        self.location_id__location_pp[str(self.location_id)] = updated_location_plan_period

    def save_info_location(self):
        self.location.notes = self.te_notes_location.toPlainText()
        updated_location = db_services.LocationOfWork.update_notes(
            self.location_id, self.te_notes_location.toPlainText())


class FrmLocationPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabLocationPlanPeriods, location_plan_period: schemas.LocationPlanPeriodShow,
                 side_menu: side_menu.WidgetSideMenu):
        super().__init__(parent)

        self.layout_controllers = parent.layout_controllers

        signal_handling.handler_location_plan_period.signal_reload_location_pp__frm_location_plan_period.connect(
            self.reload_location_plan_period)

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu
        self.setup_side_menu()

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.location_plan_period = location_plan_period
        self.t_o_d_standards: list[schemas.TimeOfDay] = []
        self.t_o_d_enums: list[schemas.TimeOfDayEnum] = []
        self.days: list[datetime.date] = []
        self.set_instance_variables()

        self.weekdays = {0: 'Mo', 1: 'Di', 2: 'Mi', 3: 'Do', 4: 'Fr', 5: 'Sa', 6: 'So'}
        self.months = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
                       9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}

        self.set_headers_months()
        self.set_chk_field()
        self.bt_toggle__avd_group_mode: QPushButton | None = None
        self.setup_controllers()
        self.get_avail_days()

    def setup_side_menu(self):
        self.side_menu.delete_all_buttons()
        bt_time_of_days = QPushButton('Tageszeiten...', clicked=self.edit_time_of_days)
        self.side_menu.add_button(bt_time_of_days)
        bt_reset_all_avail_t_o_ds = QPushButton('Eingabefeld Tagesz. Reset', clicked=self.reset_all_avail_t_o_ds)
        self.side_menu.add_button(bt_reset_all_avail_t_o_ds)
        bt_fixed_cast = QPushButton('Feste Besetzung', clicked=self.edit_fixed_cast)
        self.side_menu.add_button(bt_fixed_cast)

    def reload_location_plan_period(self, event=None):
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        self.set_instance_variables()

    def set_instance_variables(self):
        self.t_o_d_standards = sorted([t_o_d for t_o_d in self.location_plan_period.time_of_day_standards
                                       if not t_o_d.prep_delete], key=lambda x: x.time_of_day_enum.time_index)
        self.t_o_d_enums = [t_o_d.time_of_day_enum for t_o_d in self.t_o_d_standards]
        self.days = [
            self.location_plan_period.plan_period.start + datetime.timedelta(delta) for delta in
            range((self.location_plan_period.plan_period.end - self.location_plan_period.plan_period.start).days + 1)]

    def set_headers_months(self):
        month_year = [(d.month, d.year) for d in self.days]
        header_items_months = {
            m_y: month_year.count(m_y)
            for m_y in sorted(set(month_year), key=lambda x: f'{x[1]}{x[0]:02}')
        }
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
        location_of_work = db_services.LocationOfWork.get(self.location_plan_period.location_of_work.id)

        # Tageszeiten Reihen-Bezeichner:
        for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
            self.layout.addWidget(QLabel(time_of_day.time_of_day_enum.name), row, 0)

        # Tages-Configs Reihenbezeichner / Buttons:
        bt_fixed_cast = QPushButton('Besetzung -> Reset', clicked=self.reset_all_fixed_cast)
        bt_fixed_cast.setStatusTip('Festgelegte Besetzung für alle Verfügbarkeiten in diesem Zeitraum '
                                   'auf die Standartwerte des Planungszeitraums zurücksetzen.')
        self.layout.addWidget(bt_fixed_cast, row + 2, 0)
        lb_notes = QLabel('Notizen')
        self.layout.addWidget(lb_notes, row + 3, 0)
        lb_flags = QLabel('Besondere Eigensch.')
        self.layout.addWidget(lb_flags, row + 4, 0)

        #
        for col, d in enumerate(self.days, start=1):
            disable_buttons = get_curr_assignment_of_location(location_of_work, d).team.id != self.actor_plan_period.team.id
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            if not self.t_o_d_standards:
                QMessageBox.critical(self, 'Verfügbarkeiten',
                                     f'Für diesen Planungszeitraum von {self.actor_plan_period.person.f_name} '
                                     f'{self.actor_plan_period.person.l_name} sind noch keine '
                                     f'Tageszeiten-Standartwerte definiert.')
                return
            for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
                button_event = self.create_event_button(d, time_of_day)
                button_avail_day.setDisabled(disable_buttons)
                self.layout.addWidget(button_avail_day, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet('background-color: #ffdc99')
            self.layout.addWidget(lb_weekday, row + 1, col)
            bt_comb_loc_poss = ButtonCombLocPossible(self, d, 24, self.actor_plan_period)
            bt_comb_loc_poss.setDisabled(disable_buttons)
            self.layout.addWidget(bt_comb_loc_poss, row + 2, col)
            bt_loc_prefs = ButtonActorLocationPref(self, d, 24, self.actor_plan_period)
            bt_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_loc_prefs, row + 3, col)
            bt_partner_loc_prefs = ButtonActorPartnerLocationPref(self, d, 24, self.actor_plan_period)
            bt_partner_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_partner_loc_prefs, row + 4, col)

    def reset_chk_field(self):
        for widget in self.findChildren(QWidget):
            widget.deleteLater()
        self.set_instance_variables()
        self.set_headers_months()
        self.set_chk_field()
        QTimer.singleShot(50, lambda: self.setFixedHeight(self.layout.sizeHint().height()))
        QTimer.singleShot(50, lambda: self.get_avail_days())

    def create_time_of_day_button(self, day: datetime.date, time_of_day: schemas.TimeOfDay) -> ButtonAvailDay:
        # sourcery skip: inline-immediately-returned-variable
        button = ButtonAvailDay(self, day, time_of_day, 24, self.actor_plan_period, self.save_avail_day)
        return button

    def setup_controllers(self):
        self.bt_toggle__avd_group_mode = QPushButton('zum Gruppenmodus', clicked=self.change_mode__avd_group)
        self.layout_controllers.addWidget(self.bt_toggle__avd_group_mode)

    def save_avail_day(self, bt: ButtonAvailDay):
        date = bt.day
        t_o_d = bt.time_of_day
        if bt.isChecked():
            existing_avds_on_day = [avd for avd in self.actor_plan_period.avail_days
                                    if avd.day == date and not avd.prep_delete]
            avail_day_new = schemas.AvailDayCreate(day=date, actor_plan_period=self.actor_plan_period,
                                                   time_of_day=t_o_d)
            save_command = avail_day_commands.Create(avail_day_new)
            self.controller_avail_days.execute(save_command)

            '''Falls es an diesem Tage schon einen oder mehrere AvailDays gibt,
            werden die combination_locations_possibles vom ersten gefundenen AvailDay übernommen, weil, davon ausgegangen
            wird, dass schon evt. geänderte combinations für alle AvailDays an diesem Tag gelten.'''
            created_avail_day = save_command.created_avail_day
            if existing_avds_on_day:
                for comb in created_avail_day.combination_locations_possibles:
                    self.controller_avail_days.execute(
                        avail_day_commands.RemoveCombLocPossible(created_avail_day.id, comb.id))
                for comb_existing in existing_avds_on_day[0].combination_locations_possibles:
                    self.controller_avail_days.execute(
                        avail_day_commands.PutInCombLocPossible(created_avail_day.id, comb_existing.id))
                for loc_pref in created_avail_day.actor_location_prefs_defaults:
                    self.controller_avail_days.execute(
                        avail_day_commands.RemoveActorLocationPref(created_avail_day.id, loc_pref.id))
                for loc_pref_existing in existing_avds_on_day[0].actor_location_prefs_defaults:
                    if loc_pref_existing.prep_delete:
                        continue
                    self.controller_avail_days.execute(
                        avail_day_commands.PutInActorLocationPref(created_avail_day.id, loc_pref_existing.id))
                for partner_loc_pref in created_avail_day.actor_partner_location_prefs_defaults:
                    self.controller_avail_days.execute(
                        avail_day_commands.RemoveActorPartnerLocationPref(created_avail_day.id, partner_loc_pref.id)
                    )
                for partner_loc_pref_existing in existing_avds_on_day[0].actor_partner_location_prefs_defaults:
                    if partner_loc_pref_existing.prep_delete:
                        continue
                    self.controller_avail_days.execute(
                        avail_day_commands.PutInActorPartnerLocationPref(created_avail_day.id,
                                                                         partner_loc_pref_existing.id)
                    )

        else:
            avail_day = db_services.AvailDay.get_from__pp_date_tod(self.actor_plan_period.id, date, t_o_d.id)
            del_command = avail_day_commands.Delete(avail_day.id)
            self.controller_avail_days.execute(del_command)

        self.reload_actor_plan_period()
        bt.reload_actor_plan_period()
        # events.ReloadActorPlanPeriod(self.actor_plan_period, date).fire()
        signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
            signal_handling.DataActorPPWithDate(self.actor_plan_period, date))

    def change_mode__avd_group(self):

        dlg = frm_group_mode.DlgGroupMode(self, self.actor_plan_period)
        if dlg.exec():
            QMessageBox.information(self, 'Gruppenmodus', 'Alle Änderungen wurden vorgenommen.')
            self.reload_actor_plan_period()
            signal_handling.handler_actor_plan_period.reload_actor_pp__avail_days(
                signal_handling.DataActorPPWithDate(self.actor_plan_period))
        else:
            QMessageBox.information(self, 'Gruppenmodus', 'Keine Änderungen wurden vorgenommen.')

        signal_handling.handler_actor_plan_period.change_actor_plan_period_group_mode(
            signal_handling.DataGroupMode(False))

    def get_avail_days(self):
        avail_days = (ad for ad in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id)
                      if not ad.prep_delete)
        for ad in avail_days:
            button: ButtonAvailDay = self.findChild(ButtonAvailDay, f'{ad.day}-{ad.time_of_day.time_of_day_enum.name}')
            if not button:
                QMessageBox.critical(self, 'Fehlende Standards',
                                     f'Fehler:\n'
                                     f'Kann die verfügbaren Zeiten nicht anzeigen.\nEventuell haben Sie nachträglich '
                                     f'"{ad.time_of_day.time_of_day_enum.name}" aus den Standards gelöscht.')
                return
            button.setChecked(True)
            button.time_of_day = ad.time_of_day
            button.create_actions()
            button.reset_context_menu(self.actor_plan_period)
            button.set_tooltip()

    def edit_time_of_days(self):
        dlg = TimeOfDaysActorPlanPeriodEditList(self, self.actor_plan_period)
        if dlg.exec():
            self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
            buttons_avail_day: list[ButtonAvailDay] = self.findChildren(ButtonAvailDay)
            for bt in buttons_avail_day:
                bt.reset_context_menu(self.actor_plan_period)
            self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
            self.reset_chk_field()

    def reset_all_avail_t_o_ds(self):
        avail_days = [ad for ad in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id)
                      if not ad.prep_delete]
        for avail_day in avail_days:
            self.controller_avail_days.execute(
                avail_day_commands.UpdateTimeOfDays(avail_day.id, self.actor_plan_period.time_of_days))
        db_services.TimeOfDay.delete_unused(self.actor_plan_period.project.id)
        db_services.TimeOfDay.delete_prep_deletes(self.actor_plan_period.project.id)

        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.reset_chk_field()

    def edit_comb_loc_possibles(self):
        person = db_services.Person.get(self.actor_plan_period.person.id)

        '''Workaround: für die Dialogklasse wird eine funktion gebraucht'''
        parent_model_factory = lambda date: person
        team_at_date_factory = lambda date: self.actor_plan_period.team
        '''----------------------------------------------------------------------------------------------------'''

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(self, self.actor_plan_period, parent_model_factory,
                                                               team_at_date_factory)
        dlg.de_date.setDate(self.actor_plan_period.plan_period.start)
        dlg.de_date.setDisabled(True)

        if dlg.exec():
            self.reload_actor_plan_period()
            # events.ReloadActorPlanPeriod(self.actor_plan_period).fire()
            signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
                signal_handling.DataActorPPWithDate(self.actor_plan_period))

    def reset_all_avail_combs(self):
        """Setzt combination_locations_possibles aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        reply = QMessageBox.question(self, 'Zurücksetzten der Einrichtungskombinationen',
                                     'Sollen die Einrichtungskombinationen aller Verfügbarkeiten auf die Standardwerte '
                                     'der Planungsperiode zurückgesetzt werden?')
        if reply != QMessageBox.StandardButton.Yes:
            return

        all_avail_dates = {avd.day for avd in self.actor_plan_period.avail_days if not avd.prep_delete}

        if not all_avail_dates:
            QMessageBox.critical(self, 'Einrichtungskombinationen',
                                 f'In dieser Planungsperiode von '
                                 f'{self.actor_plan_period.person.f_name} {self.actor_plan_period.person.l_name} '
                                 f'gibt es noch keine Verfügbarkeiten.')
            return

        button_comb_loc_possibles: list[ButtonCombLocPossible] = self.findChildren(ButtonCombLocPossible)

        for button_comb_loc_possible in button_comb_loc_possibles:
            if button_comb_loc_possible.day in all_avail_dates:
                button_comb_loc_possible.reset_combs_of_day()
                button_comb_loc_possible.reload_actor_plan_period()
                button_comb_loc_possible.set_stylesheet()
        self.reload_actor_plan_period()

    def edit_location_prefs(self):

        person = db_services.Person.get(self.actor_plan_period.person.id)
        team_at_date_factory = lambda date: self.actor_plan_period.team

        locations_at_date = get_locations_of_team_at_date(self.actor_plan_period.team.id,
                                                          self.actor_plan_period.plan_period.start)

        dlg = frm_actor_loc_prefs.DlgActorLocPref(self, self.actor_plan_period, person, team_at_date_factory)
        dlg.de_date.setDate(self.actor_plan_period.plan_period.start)
        dlg.de_date.setDisabled(True)
        if not dlg.exec():
            return
        for loc_id, score in dlg.loc_id__results.items():
            if loc_id in dlg.loc_id__prefs:
                if dlg.loc_id__prefs[loc_id].score == score:
                    continue
                curr_loc_pref: schemas.ActorLocationPref = dlg.loc_id__prefs[loc_id]
                curr_loc_pref.score = score
                self.controller_actor_loc_prefs.execute(
                    actor_plan_period_commands.RemoveActorLocationPref(self.actor_plan_period.id, curr_loc_pref.id))
                if score != 1:
                    new_pref = schemas.ActorLocationPrefCreate(**curr_loc_pref.dict())
                    create_command = actor_loc_pref_commands.Create(new_pref)
                    self.controller_actor_loc_prefs.execute(create_command)
                    created_pref_id = create_command.get_created_actor_loc_pref()

                    self.controller_actor_loc_prefs.execute(
                        actor_plan_period_commands.PutInActorLocationPref(self.actor_plan_period.id, created_pref_id))
            else:
                if score == 1:
                    continue
                location = dlg.location_id__location[loc_id]
                new_loc_pref = schemas.ActorLocationPrefCreate(score=score, person=person, location_of_work=location)
                create_command = actor_loc_pref_commands.Create(new_loc_pref)
                self.controller_actor_loc_prefs.execute(create_command)
                created_pref_id = create_command.get_created_actor_loc_pref()
                self.controller_actor_loc_prefs.execute(
                    actor_plan_period_commands.PutInActorLocationPref(self.actor_plan_period.id, created_pref_id))

        self.controller_actor_loc_prefs.execute(actor_loc_pref_commands.DeleteUnused(person.project.id))
        self.reload_actor_plan_period()
        # events.ReloadActorPlanPeriod(self.actor_plan_period).fire()
        signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
            signal_handling.DataActorPPWithDate(self.actor_plan_period))

    @profile
    def reset_all_loc_prefs(self, e=None):
        """Setzt actor_location_prefs aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        reply = QMessageBox.question(self, 'Zurücksetzten der Einrichtungspräferenzen',
                                     'Sollen die Einrichtungspräferenzen aller Verfügbarkeiten auf die Standardwerte '
                                     'der Planungsperiode zurückgesetzt werden?')
        if reply != QMessageBox.StandardButton.Yes:
            return

        all_avail_dates = {avd.day for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
        if not all_avail_dates:
            QMessageBox.critical(self, 'Einrichtungspräferenzen',
                                 f'In dieser Planungsperiode von '
                                 f'{self.actor_plan_period.person.f_name} {self.actor_plan_period.person.l_name} '
                                 f'gibt es noch keine Verfügbarkeiten.')
            return

        button_actor_location_prefs: list[ButtonActorLocationPref] = self.findChildren(ButtonActorLocationPref)

        for button_actor_location_pref in button_actor_location_prefs:
            if button_actor_location_pref.day in all_avail_dates:
                button_actor_location_pref.reset_prefs_of_day()
                button_actor_location_pref.reload_actor_plan_period()
                button_actor_location_pref.set_stylesheet()
        self.reload_actor_plan_period()

    def edit_partner_loc_prefs(self):
        person = db_services.Person.get(self.actor_plan_period.person.id)
        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_partner_location_prefs.DlgPartnerLocationPrefs(
            self, person, self.actor_plan_period, person, team_at_date_factory)
        dlg.de_date.setDate(self.actor_plan_period.plan_period.start)
        dlg.de_date.setDisabled(True)
        if dlg.exec():
            self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
            signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
                signal_handling.DataActorPPWithDate(self.actor_plan_period))

    def reset_all_partner_loc_prefs(self, e):
        """Setzt actor_partner_location_prefs aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        reply = QMessageBox.question(self, 'Zurücksetzten der Partnerpräferenzen',
                                     'Sollen die Partnerpräferenzen aller Verfügbarkeiten auf die Standardwerte '
                                     'der Planungsperiode zurückgesetzt werden?')
        if reply != QMessageBox.StandardButton.Yes:
            return

        all_avail_dates = {avd.day for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
        if not all_avail_dates:
            QMessageBox.critical(self, 'Partnerpräferenzen',
                                 f'In dieser Planungsperiode von '
                                 f'{self.actor_plan_period.person.f_name} {self.actor_plan_period.person.l_name} '
                                 f'gibt es noch keine Verfügbarkeiten.')
            return

        button_partner_location_prefs: list[ButtonActorPartnerLocationPref] = self.findChildren(
            ButtonActorPartnerLocationPref)

        for button_partner_location_pref in button_partner_location_prefs:  # todo: Kann mit einem Signal an die buttons evt. schneller gemacht werden
            if button_partner_location_pref.day in all_avail_dates:
                button_partner_location_pref.reset_prefs_of_day()
                button_partner_location_pref.reload_actor_plan_period()
                button_partner_location_pref.set_stylesheet()
        self.reload_actor_plan_period()
