import datetime
import functools
from datetime import timedelta
from typing import Callable
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import QTimer, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QGridLayout, QMessageBox, QScrollArea, QTextEdit, \
    QMenu

from line_profiler_pycharm import profile

from database import schemas, db_services
from database.special_schema_requests import get_locations_of_team_at_date, get_persons_of_team_at_date, \
    get_curr_team_of_person_at_date, get_curr_assignment_of_person
from gui import side_menu, frm_comb_loc_possible, frm_actor_loc_prefs, frm_partner_location_prefs, frm_group_mode
from gui.actions import Action
from gui.commands import command_base_classes, avail_day_commands, actor_plan_period_commands, actor_loc_pref_commands
from gui.frm_time_of_day import TimeOfDaysActorPlanPeriodEditList
from gui.observer import events, signal_handling
from gui.tools import clear_layout


class ButtonAvailDay(QPushButton):
    def __init__(self, parent: QWidget, day: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodShow, slot__avail_day_toggled: Callable):
        super().__init__(parent)
        self.setObjectName(f'{day}-{time_of_day.time_of_day_enum.name}')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCheckable(True)
        self.clicked.connect(lambda: slot__avail_day_toggled(self))
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        signal_handling.handler.signal_change_actor_plan_period_group_mode.connect(
            lambda group_mode: self.set_group_mode(group_mode))
        signal_handling.handler.signal_reload_actor_pp__avail_days.connect(
            lambda data: self.reload_actor_plan_period(data.actor_plan_period)
        )

        self.group_mode = False

        if time_of_day.time_of_day_enum.time_index == 1:
            self.setStyleSheet("QPushButton {background-color: #cae4f4}"
                               "QPushButton::checked { background-color: #002aaa; border: none;}"
                               "QPushButton::disabled { background-color: #6a7585;}")
        elif time_of_day.time_of_day_enum.time_index == 2:
            self.setStyleSheet("QPushButton {background-color: #fff4d6}"
                               "QPushButton::checked { background-color: #ff4600; border: none;}"
                               "QPushButton::disabled { background-color: #7f7f7f;}")
        elif time_of_day.time_of_day_enum.time_index == 3:
            self.setStyleSheet("QPushButton {background-color: #daa4c9}"
                               "QPushButton::checked { background-color: #84033c; border: none;}"
                               "QPushButton::disabled { background-color: #674b56;}")
        '#999999'
        self.actor_plan_period = actor_plan_period
        self.slot__avail_day_toggled = slot__avail_day_toggled
        self.day = day
        self.time_of_day = time_of_day
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        self.context_menu = QMenu()

        self.actions = []
        self.create_actions()
        self.context_menu.addActions(self.actions)
        self.set_tooltip()

    def set_group_mode(self, group_mode: bool):
        self.group_mode = group_mode
        if self.isChecked():
            if group_mode:
                avail_day = [avd for avd in self.actor_plan_period.avail_days
                             if (avd.day, avd.time_of_day.name)==(self.day, self.time_of_day.name)][0]
                if avail_day.avail_day_group.avail_day_group.actor_plan_period:
                    self.setText('')
                else:
                    self.setText('g')
            else:
                self.setText(None)
        elif group_mode:
            self.setDisabled(True)
        else:
            self.setEnabled(True)



    def get_t_o_d_for_selection(self) -> list[schemas.TimeOfDay]:
        actor_plan_period_time_of_days = sorted(
            [t_o_d for t_o_d in self.actor_plan_period.time_of_days if not t_o_d.prep_delete], key=lambda x: x.start)
        return [t_o_d for t_o_d in actor_plan_period_time_of_days
                if t_o_d.time_of_day_enum.time_index == self.time_of_day.time_of_day_enum.time_index]

    def contextMenuEvent(self, pos):
        self.context_menu.exec(pos.globalPos())

    def reset_context_menu(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        self.actor_plan_period = actor_plan_period
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        for action in self.context_menu.actions():
            self.context_menu.removeAction(action)
        self.create_actions()
        self.context_menu.addActions(self.actions)

    def set_new_time_of_day(self, new_time_of_day: schemas.TimeOfDay):
        if self.isChecked():
            '''Es wird simuliert: Löschen des aktuellen AvailDay, Erzeugen eines neuen AvailDay mit neuer Tageszeit.'''
            self.setChecked(False)
            self.slot__avail_day_toggled(self)
            self.time_of_day = new_time_of_day
            self.setChecked(True)
            self.slot__avail_day_toggled(self)
        else:
            self.time_of_day = new_time_of_day
        self.reload_actor_plan_period()
        self.create_actions()
        self.reset_context_menu(self.actor_plan_period)
        self.set_tooltip()
    def create_actions(self):
        self.actions = [
            Action(self, QIcon('resources/toolbar_icons/icons/clock-select.png') if t.name == self.time_of_day.name else None,
                   f'{t.name}: {t.start.strftime("%H:%M")}-{t.end.strftime("%H:%M")}', None,
                   functools.partial(self.set_new_time_of_day, t))
            for t in self.t_o_d_for_selection]

    def set_tooltip(self):
        self.setToolTip(f'Rechtsklick:\n'
                        f'Zeitspanne für die Tageszeit "{self.time_of_day.time_of_day_enum.name}" '
                        f'am {self.day} wechseln.\nAktuell: {self.time_of_day.name} '
                        f'({self.time_of_day.start.strftime("%H:%M")}-{self.time_of_day.end.strftime("%H:%M")})')

    def reload_actor_plan_period(self, actor_plan_period: schemas.ActorPlanPeriodShow = None):
        if actor_plan_period:
            self.actor_plan_period = actor_plan_period
        else:
            self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)


class ButtonCombLocPossible(QPushButton):
    def __init__(self, parent, day: datetime.date, width_height: int, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        signal_handling.handler.signal_reload_actor_pp__avail_configs.connect(
            lambda data: self.reload_actor_plan_period(data))

        self.setObjectName(f'comb_loc_poss: {day}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.actor_plan_period = actor_plan_period
        self.person = db_services.Person.get(self.actor_plan_period.person.id)
        self.day = day

        self.setToolTip(f'Einrichtungskombinationen am {day.strftime("%d.%m.%Y")}')

        self.set_stylesheet()  # sollte beschleunigt werden!

    def check_comb_of_day__eq__comb_of_actor_pp(self):
        avail_days = self.actor_plan_period.avail_days
        avail_days_at_date = [avd for avd in avail_days if avd.day == self.day]
        if not avail_days_at_date:
            return
        comb_of_idx0 = {comb.id for comb in avail_days_at_date[0].combination_locations_possibles}
        if len(avail_days_at_date) > 1:
            for avd in avail_days_at_date[1:]:
                if {comb.id for comb in avd.combination_locations_possibles} != comb_of_idx0:
                    self.reset_combs_of_day(avail_days_at_date)
                    return True

        return {comb_locs.id for comb_locs in self.actor_plan_period.combination_locations_possibles} == comb_of_idx0

    def reset_combs_of_day(self, avail_days_at_date: list[schemas.AvailDay] | None = None):
        if not avail_days_at_date:
            avail_days = self.actor_plan_period.avail_days
            avail_days_at_date = [avd for avd in avail_days if avd.day == self.day]

        for avd in avail_days_at_date:
            for comb_avd in avd.combination_locations_possibles:
                db_services.AvailDay.remove_comb_loc_possible(avd.id, comb_avd.id)
            for comb_app in self.actor_plan_period.combination_locations_possibles:
                db_services.AvailDay.put_in_comb_loc_possible(avd.id, comb_app.id)

    def set_stylesheet(self):
        check_comb_of_day__eq__comb_of_actor_pp = self.check_comb_of_day__eq__comb_of_actor_pp()
        if check_comb_of_day__eq__comb_of_actor_pp is None:
            self.setStyleSheet(f"ButtonCombLocPossible {{background-color: #fff4d6}}"
                               f"ButtonCombLocPossible::disabled {{ background-color: #6e6e6e; }}")
        elif check_comb_of_day__eq__comb_of_actor_pp:
            self.setStyleSheet(f"ButtonCombLocPossible {{background-color: #acf49f}}"
                               f"ButtonCombLocPossible::disabled {{ background-color: #6e6e6e; }}")
        else:
            self.setStyleSheet(f"ButtonCombLocPossible {{background-color: #f4b2a5}}"
                               f"ButtonCombLocPossible::disabled {{ background-color: #6e6e6e; }}")
        'acf49f'

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        return [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete and avd.day == self.day]

    def mouseReleaseEvent(self, e) -> None:
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, 'Einrichtungskombinationen',
                                 'Es können keine Einrichtungskombinationen eingerichtet werden, '
                                 'da an diesen Tag noch keine Verfügbarkeit gewählt wurde.')
            return

        parent_model_factory = lambda date: self.actor_plan_period
        team_at_date_factory = functools.partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(self, avail_days_at_date[0], parent_model_factory,
                                                               team_at_date_factory)
        dlg.de_date.setDate(self.day)
        dlg.de_date.setDisabled(True)
        if dlg.exec():
            '''avail_days_at_date[0].combination_locations_possibles wurden geändert.
            nun werden die combination_locations_possibles der übrigen avail_days an diesem Tag angepasst'''
            avail_days_at_date[0] = db_services.AvailDay.get(avail_days_at_date[0].id)
            for avd in avail_days_at_date[1:]:
                for comb in avd.combination_locations_possibles:
                    db_services.AvailDay.remove_comb_loc_possible(avd.id, comb.id)
                for comb_new in avail_days_at_date[0].combination_locations_possibles:
                    db_services.AvailDay.put_in_comb_loc_possible(avd.id, comb_new.id)

            self.reload_actor_plan_period()
            # events.ReloadActorPlanPeriodInActorFrmPlanPeriod().fire()
            signal_handling.handler.reload_actor_pp__frm_actor_plan_period()

    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if self.avail_days_at_date() or data.date:
            if data is None or data.date is None or data.date == self.day:
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet()


class ButtonActorLocationPref(QPushButton):
    def __init__(self, parent, day: datetime.date, width_height: int, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        signal_handling.handler.signal_reload_actor_pp__avail_configs.connect(
            lambda data: self.reload_actor_plan_period(data))

        self.setObjectName(f'act_loc_pref: {day}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.actor_plan_period = actor_plan_period
        self.day = day

        self.setToolTip(f'Einrichtungspräferenzen am {day.strftime("%d.%m.%Y")}')

        self.set_stylesheet()  # sollte beschleunigt werden!

    def check_loc_pref_of_day__eq__loc_pref_of_actor_pp(self):
        locations_at_date_ids = {
            loc.id for loc in get_locations_of_team_at_date(self.actor_plan_period.team.id, self.day)
            if not loc.prep_delete or loc.prep_delete > self.day
        }

        avail_days = self.actor_plan_period.avail_days
        avail_days_at_date = [avd for avd in avail_days if avd.day == self.day]
        if not avail_days_at_date:
            return
        prefs_actor_plan_period = {
            (pref.location_of_work.id, pref.score) for pref in self.actor_plan_period.actor_location_prefs_defaults
            if (not pref.prep_delete or pref.prep_delete > self.day)
               and pref.location_of_work.id in locations_at_date_ids
        }
        pref_of_idx0 = {
            (pref.location_of_work.id, pref.score) for pref in avail_days_at_date[0].actor_location_prefs_defaults
            if (not pref.prep_delete or pref.prep_delete > self.day)
               and pref.location_of_work.id in locations_at_date_ids
        }
        if len(avail_days_at_date) > 1:
            for avd in avail_days_at_date[1:]:
                avd_prefs = {
                    (pref.location_of_work.id, pref.score) for pref in avd.actor_location_prefs_defaults
                    if (not pref.prep_delete or pref.prep_delete > self.day)
                       and pref.location_of_work.id in locations_at_date_ids
                }
                if avd_prefs != pref_of_idx0:
                    self.reset_prefs_of_day(avail_days_at_date)
                    QMessageBox.critical(self, 'Einrichtungspräferenzen',
                                         f'Die Einrichtungspräferenzen der Verfügbarkeiten dieses Tages wurden auf die '
                                         f'Standardwerdte des Planungszeitraums von '
                                         f'{self.actor_plan_period.person.f_name} {self.actor_plan_period.person.l_name} '
                                         f'zurückgesetzt.')
                    return True

        return prefs_actor_plan_period == pref_of_idx0

    def reset_prefs_of_day(self, avail_days_at_date: list[schemas.AvailDay] | None = None):
        if not avail_days_at_date:
            avail_days = self.actor_plan_period.avail_days
            avail_days_at_date = [avd for avd in avail_days if avd.day == self.day]

        for avd in avail_days_at_date:
            for pref_avd in avd.actor_location_prefs_defaults:
                db_services.AvailDay.remove_location_pref(avd.id, pref_avd.id)
            for pref_app in self.actor_plan_period.actor_location_prefs_defaults:
                db_services.AvailDay.put_in_location_pref(avd.id, pref_app.id)

    def set_stylesheet(self):
        check_loc_pref__eq__loc_pref_of_actor_pp = self.check_loc_pref_of_day__eq__loc_pref_of_actor_pp()
        if check_loc_pref__eq__loc_pref_of_actor_pp is None:
            self.setStyleSheet(f"ButtonActorLocationPref {{background-color: #fff4d6;}}"
                               f"ButtonActorLocationPref::disabled {{ background-color: #6e6e6e; }}")
        elif check_loc_pref__eq__loc_pref_of_actor_pp:
            self.setStyleSheet(f"ButtonActorLocationPref {{background-color: #acf49f;}}"
                               f"ButtonActorLocationPref::disabled {{ background-color: #6e6e6e; }}")
        else:
            self.setStyleSheet(f"ButtonActorLocationPref {{background-color: #f4b2a5;}}"
                               f"ButtonActorLocationPref::disabled {{ background-color: #6e6e6e; }}")
        '6e6e6e'

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        return [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete and avd.day == self.day]

    def mouseReleaseEvent(self, e) -> None:
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, 'Einrichtungspräferenzen',
                                 'Es können keine Einrichtungspräferenzen eingerichtet werden, '
                                 'da an diesen Tag noch keine Verfügbarkeit gewählt wurde.')
            return

        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_actor_loc_prefs.DlgActorLocPref(self, avail_days_at_date[0], self.actor_plan_period, team_at_date_factory)
        dlg.de_date.setDate(self.day)
        dlg.de_date.setDisabled(True)
        if not dlg.exec():
            return
        for loc_id, score in dlg.loc_id__results.items():
            if loc_id in dlg.loc_id__prefs:
                if dlg.loc_id__prefs[loc_id].score == score:
                    continue
                curr_loc_pref: schemas.ActorLocationPref = dlg.loc_id__prefs[loc_id]
                curr_loc_pref.score = score
                db_services.AvailDay.remove_location_pref(avail_days_at_date[0].id, curr_loc_pref.id)
                if score != 1:
                    new_pref = schemas.ActorLocationPrefCreate(**curr_loc_pref.dict())
                    created_pref = db_services.ActorLocationPref.create(new_pref)
                    db_services.AvailDay.put_in_location_pref(avail_days_at_date[0].id, created_pref.id)
            else:
                if score == 1:
                    continue
                person = self.actor_plan_period.person
                location = dlg.location_id__location[loc_id]
                new_loc_pref = schemas.ActorLocationPrefCreate(score=score, person=person, location_of_work=location)
                created_pref = db_services.ActorLocationPref.create(new_loc_pref)
                db_services.AvailDay.put_in_location_pref(avail_days_at_date[0].id, created_pref.id)


        '''avail_days_at_date[0].actor_location_prefs_defaults wurden geändert.
        nun werden die actor_location_prefs_defaults der übrigen avail_days an diesem Tag angepasst'''
        avail_days_at_date[0] = db_services.AvailDay.get(avail_days_at_date[0].id)
        for avd in avail_days_at_date[1:]:
            for pref in avd.actor_location_prefs_defaults:
                db_services.AvailDay.remove_location_pref(avd.id, pref.id)
            for pref_new in avail_days_at_date[0].actor_location_prefs_defaults:
                if not pref_new.prep_delete:
                    db_services.AvailDay.put_in_location_pref(avd.id, pref_new.id)

        db_services.ActorLocationPref.delete_unused(self.actor_plan_period.project.id)
        self.reload_actor_plan_period()
        # events.ReloadActorPlanPeriodInActorFrmPlanPeriod().fire()
        signal_handling.handler.reload_actor_pp__frm_actor_plan_period()

    @profile
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if self.avail_days_at_date() or data.date:
            if data is None or data.date is None or data.date == self.day:
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet()


class ButtonActorPartnerLocationPref(QPushButton):
    def __init__(self, parent, day: datetime.date, width_height: int, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        signal_handling.handler.signal_reload_actor_pp__avail_configs.connect(
            lambda data: self.reload_actor_plan_period(data))

        self.setObjectName(f'act_partner_loc_pref: {day}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.actor_plan_period = actor_plan_period
        self.day = day

        self.setToolTip(f'Mitarbeiter- / Einrichtungspräferenzen am {day.strftime("%d.%m.%Y")}')

        self.set_stylesheet()  # sollte beschleunigt werden!

    def check_pref_of_day__eq__pref_of_actor_pp(self):
        partner_at_date_ids = {p.id for p in get_persons_of_team_at_date(self.actor_plan_period.team.id, self.day)
                               if (not p.prep_delete or p.prep_delete > self.day)
                           and p.id != self.actor_plan_period.person.id}
        locations_at_date_ids = {loc.id for loc in get_locations_of_team_at_date(self.actor_plan_period.team.id, self.day)
                                if not loc.prep_delete or loc.prep_delete > self.day}

        avail_days = self.actor_plan_period.avail_days
        avail_days_at_date = [avd for avd in avail_days if avd.day == self.day]
        if not avail_days_at_date:
            return
        prefs_actor_plan_period = {
            (pref.location_of_work.id, pref.partner.id, pref.score)
            for pref in self.actor_plan_period.actor_partner_location_prefs_defaults
            if not pref.prep_delete
               and (pref.location_of_work.id in locations_at_date_ids and pref.partner.id in partner_at_date_ids)
        }
        pref_of_idx0 = {
            (pref.location_of_work.id, pref.partner.id, pref.score)
            for pref in avail_days_at_date[0].actor_partner_location_prefs_defaults
            if not pref.prep_delete
               and (pref.location_of_work.id in locations_at_date_ids and pref.partner.id in partner_at_date_ids)
        }
        if len(avail_days_at_date) > 1:
            for avd in avail_days_at_date[1:]:
                avd_prefs = {(pref.location_of_work.id, pref.partner.id, pref.score)
                             for pref in avd.actor_partner_location_prefs_defaults
                             if not pref.prep_delete
                             and (pref.location_of_work.id in locations_at_date_ids and pref.partner.id in partner_at_date_ids)}
                if avd_prefs != pref_of_idx0:
                    self.reset_prefs_of_day(avail_days_at_date)
                    QMessageBox.critical(self, 'Partner- / Einrichtungspräferenzen',
                                         f'Die Partner- / Einrichtungspräferenzen der Verfügbarkeiten dieses Tages '
                                         f'wurden auf die Standardwerdte des Planungszeitraums von '
                                         f'{self.actor_plan_period.person.f_name} {self.actor_plan_period.person.l_name} '
                                         f'zurückgesetzt.')
                    return True

        return prefs_actor_plan_period == pref_of_idx0

    def reset_prefs_of_day(self, avail_days_at_date: list[schemas.AvailDay] | None = None):
        if not avail_days_at_date:
            avail_days = self.actor_plan_period.avail_days
            avail_days_at_date = [avd for avd in avail_days if avd.day == self.day]

        for avd in avail_days_at_date:
            for pref_avd in avd.actor_partner_location_prefs_defaults:
                db_services.AvailDay.remove_partner_location_pref(avd.id, pref_avd.id)
            for pref_app in self.actor_plan_period.actor_partner_location_prefs_defaults:
                db_services.AvailDay.put_in_partner_location_pref(avd.id, pref_app.id)

    def set_stylesheet(self):
        check_loc_pref__eq__loc_pref_of_actor_pp = self.check_pref_of_day__eq__pref_of_actor_pp()
        if check_loc_pref__eq__loc_pref_of_actor_pp is None:
            self.setStyleSheet(f"ButtonActorPartnerLocationPref {{background-color: #fff4d6}}"
                               f"ButtonActorPartnerLocationPref::disabled {{ background-color: #6e6e6e; }}")
        elif check_loc_pref__eq__loc_pref_of_actor_pp:
            self.setStyleSheet(f"ButtonActorPartnerLocationPref {{background-color: #acf49f}}"
                               f"ButtonActorPartnerLocationPref::disabled {{ background-color: #6e6e6e; }}")
        else:
            self.setStyleSheet(f"ButtonActorPartnerLocationPref {{background-color: #f4b2a5}}"
                               f"ButtonActorPartnerLocationPref::disabled {{ background-color: #6e6e6e; }}")
        'acf49f'

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        return [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete and avd.day == self.day]

    def mouseReleaseEvent(self, e) -> None:
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, 'Partner- / Einrichtungspräferenzen',
                                 'Es können keine Partner- / Einrichtungspräferenzen eingerichtet werden, '
                                 'da an diesen Tag noch keine Verfügbarkeit gewählt wurde.')
            return

        person = db_services.Person.get(self.actor_plan_period.person.id)

        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_partner_location_prefs.DlgPartnerLocationPrefs(
            self, person, avail_days_at_date[0], self.actor_plan_period, team_at_date_factory)
        dlg.de_date.setDate(self.day)
        dlg.de_date.setDisabled(True)
        if not dlg.exec():
            return

        '''avail_days_at_date[0].actor_partner_location_prefs_defaults wurden geändert.
        nun werden die actor_partner_location_prefs_defaults der übrigen avail_days an diesem Tag angepasst'''
        avail_days_at_date[0] = db_services.AvailDay.get(avail_days_at_date[0].id)
        for avd in avail_days_at_date[1:]:
            for pref in avd.actor_partner_location_prefs_defaults:
                db_services.AvailDay.remove_partner_location_pref(avd.id, pref.id)
            for pref_new in avail_days_at_date[0].actor_partner_location_prefs_defaults:
                if not pref_new.prep_delete:
                    db_services.AvailDay.put_in_partner_location_pref(avd.id, pref_new.id)

        self.reload_actor_plan_period()
        # events.ReloadActorPlanPeriodInActorFrmPlanPeriod().fire()
        signal_handling.handler.reload_actor_pp__frm_actor_plan_period()

    @profile
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if self.avail_days_at_date() or data.date:
            if data is None or data.date is None or data.date == self.day:
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet()


class FrmTabActorPlanPeriods(QWidget):
    def __init__(self, plan_period: schemas.PlanPeriod):
        super().__init__()

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.actor_plan_periods = list(self.plan_period.actor_plan_periods)
        self.pers_id__actor_pp = {str(a_pp.person.id): a_pp for a_pp in self.plan_period.actor_plan_periods}
        self.person_id: UUID | None = None
        self.person: schemas.PersonShow | None = None
        self.scroll_area_availables = QScrollArea()
        self.frame_availables: FrmActorPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_actor_pp)
        self.te_notes_pp.setFixedHeight(180)

        self.lb_notes_actor = QLabel('Infos zur Person:')
        self.lb_notes_actor.setFixedHeight(20)
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

        self.side_menu = side_menu.WidgetSideMenu(self, 250, 10, 'right')

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
        self.layout_controllers = QHBoxLayout()
        self.layout_notes = QHBoxLayout()
        self.layout_notes_actor = QVBoxLayout()
        self.layout_notes_actor_pp = QVBoxLayout()

        self.layout_availables.addWidget(self.scroll_area_availables, 0, 0)
        self.layout_availables.addLayout(self.layout_controllers, 1, 0)
        self.layout_availables.addLayout(self.layout_notes, 2, 0)
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
        if self.frame_availables:
            self.disconnect_avail_button_signals()
            self.delete_actor_plan_period_widgets()
        self.frame_availables = FrmActorPlanPeriod(self, actor_plan_period_show, self.side_menu)
        self.scroll_area_availables.setWidget(self.frame_availables)

        self.info_text_setup()

    def disconnect_avail_button_signals(self):
        signal_handling.handler.signal_reload_actor_pp__avail_configs.disconnect()
        signal_handling.handler.signal_change_actor_plan_period_group_mode.disconnect()

    def delete_actor_plan_period_widgets(self):
        self.frame_availables.deleteLater()
        for widget in (self.layout_controllers.itemAt(i).widget() for i in range(self.layout_controllers.count())):
            widget.deleteLater()


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
    def __init__(self, parent: FrmTabActorPlanPeriods, actor_plan_period: schemas.ActorPlanPeriodShow,
                 side_menu: side_menu.WidgetSideMenu):
        super().__init__(parent)

        self.layout_controllers = parent.layout_controllers

        signal_handling.handler.signal_reload_actor_pp__frm_actor_plan_period.connect(self.reload_actor_plan_period)

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu
        self.setup_side_menu()

        self.controller_avail_days = command_base_classes.ContrExecUndoRedo()
        self.controller_actor_loc_prefs = command_base_classes.ContrExecUndoRedo()
        self.actor_plan_period = actor_plan_period
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
        bt_comb_loc_possibles = QPushButton('Einrichtungskombinationen', clicked=self.edit_comb_loc_possibles)
        self.side_menu.add_button(bt_comb_loc_possibles)
        bt_actor_loc_prefs = QPushButton('Einrichtunspräferenzen', clicked=self.edit_location_prefs)
        self.side_menu.add_button(bt_actor_loc_prefs)
        bt_actor_partner_loc_prefs = QPushButton('Mitsp.- / Einr.-Präf.', clicked=self.edit_partner_loc_prefs)
        self.side_menu.add_button(bt_actor_partner_loc_prefs)

    def reload_actor_plan_period(self, event=None):
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.set_instance_variables()

    def set_instance_variables(self):
        self.t_o_d_standards = sorted([t_o_d for t_o_d in self.actor_plan_period.time_of_day_standards
                                       if not t_o_d.prep_delete], key=lambda x: x.time_of_day_enum.time_index)
        self.t_o_d_enums = [t_o_d.time_of_day_enum for t_o_d in self.t_o_d_standards]
        self.days = [
            self.actor_plan_period.plan_period.start + timedelta(delta) for delta in
            range((self.actor_plan_period.plan_period.end - self.actor_plan_period.plan_period.start).days + 1)]

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
        person = db_services.Person.get(self.actor_plan_period.person.id)
        for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
            self.layout.addWidget(QLabel(time_of_day.time_of_day_enum.name), row, 0)
        bt_comb_loc_poss_all_avail = QPushButton('Einricht.-Kombin. -> Reset', clicked=self.reset_all_avail_combs)
        bt_comb_loc_poss_all_avail.setStatusTip('Einrichtungskombinationen für alle Verfügbarkeiten in diesem Zeitraum '
                                                'auf die Standartwerte des Planungszeitraums zurücksetzen.')

        self.layout.addWidget(bt_comb_loc_poss_all_avail, row + 2, 0)
        bt_actor_loc_prefs_all_avail = QPushButton('Einr.-Präf. -> Reset', clicked=self.reset_all_loc_prefs)
        bt_actor_loc_prefs_all_avail.setStatusTip('Einrichtungspräferenzen für alle Verfügbarkeiten in diesem Zeitraum '
                                                  'werden auf die Standartwerte des Planungszeitraums zurückgesetzt.')
        self.layout.addWidget(bt_actor_loc_prefs_all_avail, row+3, 0)

        bt_actor_partner_loc_prefs_all_avail = QPushButton('Partn.-/Einr.-Präf. -> Reset', clicked=self.reset_all_partner_loc_prefs)
        bt_actor_partner_loc_prefs_all_avail.setStatusTip(
            'Mitarbeite- / Einrichtungspräferenzen für alle Verfügbarkeiten in diesem Zeitraum  '
            'werden auf die Standartwerte des Planungszeitraums zurückgesetzt.')
        self.layout.addWidget(bt_actor_partner_loc_prefs_all_avail, row+4, 0)

        for col, d in enumerate(self.days, start=1):
            disable_buttons = get_curr_assignment_of_person(person, d).team.id != self.actor_plan_period.team.id
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
                button_avail_day = self.create_time_of_day_button(d, time_of_day)
                button_avail_day.setDisabled(disable_buttons)
                self.layout.addWidget(button_avail_day, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet('background-color: #ffdc99')
            self.layout.addWidget(lb_weekday, row+1, col)
            bt_comb_loc_poss = ButtonCombLocPossible(self, d, 24, self.actor_plan_period)
            bt_comb_loc_poss.setDisabled(disable_buttons)
            self.layout.addWidget(bt_comb_loc_poss, row+2, col)
            bt_loc_prefs = ButtonActorLocationPref(self, d, 24, self.actor_plan_period)
            bt_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_loc_prefs, row+3, col)
            bt_partner_loc_prefs = ButtonActorPartnerLocationPref(self, d, 24, self.actor_plan_period)
            bt_partner_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_partner_loc_prefs, row+4, col)

    def reset_chk_field(self):
        for widget in self.findChildren(QWidget):
            widget.deleteLater()
        self.set_instance_variables()
        self.set_headers_months()
        self.set_chk_field()
        QTimer.singleShot(50, lambda: self.setFixedHeight(self.layout.sizeHint().height()))
        QTimer.singleShot(50, lambda:  self.get_avail_days())

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
            avail_day_new = schemas.AvailDayCreate(day=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d)
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
                        avail_day_commands.PutInActorPartnerLocationPref(created_avail_day.id, partner_loc_pref_existing.id)
                    )

        else:
            avail_day = db_services.AvailDay.get_from__pp_date_tod(self.actor_plan_period.id, date, t_o_d.id)
            del_command = avail_day_commands.Delete(avail_day.id)
            self.controller_avail_days.execute(del_command)

        self.reload_actor_plan_period()
        bt.reload_actor_plan_period()
        #events.ReloadActorPlanPeriod(self.actor_plan_period, date).fire()
        signal_handling.handler.reload_actor_pp__avail_configs(
            signal_handling.DataActorPPWithDate(self.actor_plan_period, date))

    def change_mode__avd_group(self):

        signal_handling.handler.change_actor_plan_period_group_mode(True)

        self.bt_toggle__avd_group_mode.setText('zum Gruppenmodus')
        dlg = frm_group_mode.DlgGroupMode(self, self.actor_plan_period)
        if dlg.exec():
            QMessageBox.information(self, 'Gruppenmodus', 'Alle Änderungen wurden vorgenommen.')
            self.reload_actor_plan_period()
            signal_handling.handler.reload_actor_pp__avail_days(signal_handling.DataActorPPWithDate(self.actor_plan_period))
        else:
            QMessageBox.information(self, 'Gruppenmodus', 'Keine Änderungen wurden vorgenommen.')

        signal_handling.handler.change_actor_plan_period_group_mode(False)

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
            #events.ReloadActorPlanPeriod(self.actor_plan_period).fire()
            signal_handling.handler.reload_actor_pp__avail_configs(
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
        #events.ReloadActorPlanPeriod(self.actor_plan_period).fire()
        signal_handling.handler.reload_actor_pp__avail_configs(
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
            signal_handling.handler.reload_actor_pp__avail_configs(
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

        button_partner_location_prefs: list[ButtonActorPartnerLocationPref] = self.findChildren(ButtonActorPartnerLocationPref)

        for button_partner_location_pref in button_partner_location_prefs:  # todo: Kann mit einem Signal an die buttons evt. schneller gemacht werden
            if button_partner_location_pref.day in all_avail_dates:
                button_partner_location_pref.reset_prefs_of_day()
                button_partner_location_pref.reload_actor_plan_period()
                button_partner_location_pref.set_stylesheet()
        self.reload_actor_plan_period()


# todo: Wenn Tageszeit-Button geklickt wird und vor dem Loslassen weggezogen wird -> Fehlermeldung