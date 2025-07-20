import datetime
import functools
import os.path
from datetime import timedelta
from typing import Callable
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QGridLayout, QMessageBox, QScrollArea, QTextEdit, \
    QMenu, QApplication
from line_profiler_pycharm import profile
from pydantic_core._pydantic_core import ValidationError

from database import schemas, db_services, schemas_plan_api
from database.special_schema_requests import get_locations_of_team_at_date, get_curr_team_of_person_at_date, \
    get_curr_assignment_of_person, get_locations_of_team_at_date_2, \
    get_persons_of_team_at_date_2, get_next_assignment_of_person
from export_to_file import avail_days_to_xlsx
from gui import (frm_comb_loc_possible, frm_actor_loc_prefs, frm_partner_location_prefs, frm_group_mode,
                 frm_time_of_day, widget_styles, frm_requested_assignments, frm_skills)
from gui.custom_widgets import side_menu
from gui.frm_remote_access_plan_api import plan_api_handler
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import actor_plan_period_commands, avail_day_commands, actor_loc_pref_commands
from gui.observer import signal_handling
from tools.helper_functions import date_to_string, time_to_string


class ButtonAvailDay(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodShow, slot__avail_day_toggled: Callable):
        super().__init__(parent)
        self.setObjectName(f'{date}-{time_of_day.time_of_day_enum.name}')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCheckable(True)
        self.clicked.connect(lambda: slot__avail_day_toggled(self))
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        signal_handling.handler_actor_plan_period.signal_change_actor_plan_period_group_mode.connect(
            self.set_group_mode)
        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_days.connect(
            self.reload_actor_plan_period)

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.group_mode = False
        self.actor_plan_period = actor_plan_period
        self.slot__avail_day_toggled = slot__avail_day_toggled
        self.date = date
        self.time_of_day = time_of_day
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()

        self.set_stylesheet()

        self._setup_context_menu()

        # self.actions = []
        # self.create_actions()
        # self.context_menu.addActions(self.actions)
        self.set_tooltip()

    def set_stylesheet(self):
        self.setStyleSheet(widget_styles.buttons.avail_day__event[self.time_of_day.time_of_day_enum.time_index]
                           .replace('<<ObjectName>>', self.objectName()))

    @Slot(signal_handling.DataGroupMode)
    def set_group_mode(self, group_mode: signal_handling.DataGroupMode):
        self.group_mode = group_mode.group_mode
        if self.isChecked():
            if self.group_mode:
                if group_mode.date and (group_mode.date == self.date
                                        and group_mode.time_index == self.time_of_day.time_of_day_enum.time_index
                                        and group_mode.location_pp__actor_pp_id == self.actor_plan_period.id):
                    self.setText(f'{group_mode.group_nr:02}' if group_mode.group_nr else None)
            else:
                self.setText(None)
        elif self.group_mode:
            self.setDisabled(True)
        else:
            self.setEnabled(True)

    def get_t_o_d_for_selection(self) -> list[schemas.TimeOfDay]:
        actor_plan_period_time_of_days = sorted(
            [t_o_d for t_o_d in self.actor_plan_period.time_of_days if not t_o_d.prep_delete], key=lambda x: x.start)
        return [t_o_d for t_o_d in actor_plan_period_time_of_days
                if t_o_d.time_of_day_enum.time_index == self.time_of_day.time_of_day_enum.time_index]

    def _setup_context_menu(self):
        self.context_menu = QMenu()
        self.menu_times_of_day = QMenu(self.tr('Times of Day'))
        self.context_menu.addMenu(self.menu_times_of_day)
        self.actions_times_of_day = [
            MenuToolbarAction(self,
                              QIcon(
                                  os.path.join(
                                      os.path.dirname(__file__), 'resources/toolbar_icons/icons/clock-select.png'
                                               )
                              )
                              if t.name == self.time_of_day.name else None,
                              f'{t.name}: {time_to_string(t.start)}-{time_to_string(t.end)}', None,
                              functools.partial(self.set_new_time_of_day, t))
            for t in self.t_o_d_for_selection
        ]
        for action in self.actions_times_of_day:
            self.menu_times_of_day.addAction(action)
        self.action_skills = MenuToolbarAction(
            self,
            os.path.join(os.path.dirname(__file__), 'resources/toolbar_icons/icons/screwdriver.png'),
            self.tr('Skills'), None, self._set_skills
        )
        self.context_menu.addAction(self.action_skills)

    def contextMenuEvent(self, pos):
        self.context_menu.exec(pos.globalPos())

    def reset_context_menu(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        self.actor_plan_period = actor_plan_period
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        for action in self.context_menu.actions():
            self.context_menu.removeAction(action)
        self._setup_context_menu()

    def set_new_time_of_day(self, new_time_of_day: schemas.TimeOfDay):
        if self.isChecked():
            avail_day = db_services.AvailDay.get_from__actor_pp_date_tod(
                self.actor_plan_period.id, self.date, self.time_of_day.id)
            avail_day_commands.UpdateTimeOfDay(avail_day, new_time_of_day.id).execute()

        self.time_of_day = new_time_of_day
        self.reload_actor_plan_period()
        self.reset_context_menu(self.actor_plan_period)
        self.set_tooltip()
        signal_handling.handler_actor_plan_period.reload_actor_pp__frm_actor_plan_period()

    def _set_skills(self):
        avail_day = db_services.AvailDay.get_from__actor_pp_date_tod(
            self.actor_plan_period.id, self.date, self.time_of_day.id)
        if not avail_day:
            QMessageBox.critical(self, self.tr('Skills'),
                                 self.tr('Skills cannot be selected,\n'
                                         'as no availability has been chosen yet.'))
            return
        dlg = frm_skills.DlgSelectSkills(self, avail_day)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            signal_handling.handler_actor_plan_period.reset_styling_skills_configs(
                signal_handling.DataDate(self.actor_plan_period.plan_period.id, self.date))
        else:
            dlg.controller.undo_all()

    def set_tooltip(self):
        self.setToolTip(
            self.tr('Right click:\nChange time period for time of day "%s" on %s.\nCurrent: %s (%s-%s)') % (
                self.time_of_day.time_of_day_enum.name, date_to_string(self.date), self.time_of_day.name,
                time_to_string(self.time_of_day.start), time_to_string(self.time_of_day.end)))

    @Slot(signal_handling.DataActorPPWithDate)
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        if data is not None:
            self.actor_plan_period = data.actor_plan_period
        else:
            self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)


class ButtonCombLocPossible(QPushButton):
    def __init__(self, parent, date: datetime.date, width_height: int, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.connect(
            self.reload_actor_plan_period)

        self.setObjectName(f'comb_loc_poss: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.actor_plan_period = actor_plan_period
        self.person: schemas.PersonShow | None = None
        self.date = date

        self.setToolTip(self.tr('Location combinations on %s') % date_to_string(self.date))

        self.set_stylesheet()  # sollte beschleunigt werden!

    # def deleteLater(self):
    #     # Trenne die Signale explizit, bevor das Widget gelöscht wird
    #     signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.disconnect(
    #         self.reload_actor_plan_period)
    #     super().deleteLater()

    def check_comb_of_day__eq__comb_of_actor_pp(self):
        avail_days = self.actor_plan_period.avail_days
        avail_days_at_date = [avd for avd in avail_days if avd.date == self.date]
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
            avail_days_at_date = [avd for avd in avail_days if avd.date == self.date]

        for avd in avail_days_at_date:
            for comb_avd in avd.combination_locations_possibles:
                db_services.AvailDay.remove_comb_loc_possible(avd.id, comb_avd.id)
            for comb_app in self.actor_plan_period.combination_locations_possibles:
                db_services.AvailDay.put_in_comb_loc_possible(avd.id, comb_app.id)

    def set_stylesheet(self):
        check_comb_of_day__eq__comb_of_actor_pp = self.check_comb_of_day__eq__comb_of_actor_pp()
        if check_comb_of_day__eq__comb_of_actor_pp is None:
            self.setStyleSheet(
                f"ButtonCombLocPossible {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonCombLocPossible::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif check_comb_of_day__eq__comb_of_actor_pp:
            self.setStyleSheet(
                f"ButtonCombLocPossible {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonCombLocPossible::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonCombLocPossible {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonCombLocPossible::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        return [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete and avd.date == self.date]

    def get_person(self) -> schemas.PersonShow:
        if self.person is None:
            self.person = db_services.Person.get(self.actor_plan_period.person.id)
        return self.person

    def mouseReleaseEvent(self, e) -> None:
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, self.tr('Location Combinations'),
                                 self.tr('No location combinations can be set up, '
                                         'as no availability has been selected for this day.'))
            return

        parent_model_factory = lambda date: self.actor_plan_period
        team_at_date_factory = functools.partial(get_curr_team_of_person_at_date, self.get_person())

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(
            self, avail_days_at_date[0], parent_model_factory, team_at_date_factory)
        dlg.de_date.setDate(self.date)
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
            signal_handling.handler_actor_plan_period.reload_actor_pp__frm_actor_plan_period()

    @Slot(signal_handling.DataActorPPWithDate)
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if self.avail_days_at_date() or data.date:
            if data is None or data.date is None or data.date == self.date:
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet()


class ButtonActorLocationPref(QPushButton):
    def __init__(self, parent, date: datetime.date, width_height: int, actor_plan_period: schemas.ActorPlanPeriodShow,
                 team: schemas.TeamShow):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.connect(
            self.reload_actor_plan_period)

        self.setObjectName(f'act_loc_pref: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.actor_plan_period = actor_plan_period
        self.team = team
        self.date = date

        self.setToolTip(self.tr('Location preferences on %s') % date_to_string(date))

        self.set_stylesheet()  # sollte beschleunigt werden!

    def check_loc_pref_of_day__eq__loc_pref_of_actor_pp(self):
        locations_at_date_ids = get_locations_of_team_at_date_2(self.team, self.date)
        avail_days = self.actor_plan_period.avail_days
        avail_days_at_date = [avd for avd in avail_days if avd.date == self.date]
        if not avail_days_at_date:
            return
        prefs_actor_plan_period = {
            (pref.location_of_work.id, pref.score) for pref in self.actor_plan_period.actor_location_prefs_defaults
            if (not pref.prep_delete or pref.prep_delete > self.date)
               and pref.location_of_work.id in locations_at_date_ids
        }
        pref_of_idx0 = {
            (pref.location_of_work.id, pref.score) for pref in avail_days_at_date[0].actor_location_prefs_defaults
            if (not pref.prep_delete or pref.prep_delete > self.date)
               and pref.location_of_work.id in locations_at_date_ids
        }
        if len(avail_days_at_date) > 1:
            for avd in avail_days_at_date[1:]:
                avd_prefs = {
                    (pref.location_of_work.id, pref.score) for pref in avd.actor_location_prefs_defaults
                    if (not pref.prep_delete or pref.prep_delete > self.date)
                       and pref.location_of_work.id in locations_at_date_ids
                }
                if avd_prefs != pref_of_idx0:
                    self.reset_prefs_of_day(avail_days_at_date)
                    QMessageBox.critical(
                        self, self.tr('Location Preferences'),
                        self.tr('The location preferences of the availabilities for this day have been reset to '
                                'the default values of the planning period of '
                                '%s %s.') % (self.actor_plan_period.person.f_name,
                                             self.actor_plan_period.person.l_name)
                    )
                    return True

        return prefs_actor_plan_period == pref_of_idx0

    def reset_prefs_of_day(self, avail_days_at_date: list[schemas.AvailDay] | None = None):
        if not avail_days_at_date:
            avail_days = self.actor_plan_period.avail_days
            avail_days_at_date = [avd for avd in avail_days if avd.date == self.date]

        for avd in avail_days_at_date:
            for pref_avd in avd.actor_location_prefs_defaults:
                db_services.AvailDay.remove_location_pref(avd.id, pref_avd.id)
            for pref_app in self.actor_plan_period.actor_location_prefs_defaults:
                db_services.AvailDay.put_in_location_pref(avd.id, pref_app.id)

    def set_stylesheet(self):
        check_loc_pref__eq__loc_pref_of_actor_pp = self.check_loc_pref_of_day__eq__loc_pref_of_actor_pp()
        if check_loc_pref__eq__loc_pref_of_actor_pp is None:
            self.setStyleSheet(
                f"ButtonActorLocationPref {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors};}}"
                f"ButtonActorLocationPref::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif check_loc_pref__eq__loc_pref_of_actor_pp:
            self.setStyleSheet(
                f"ButtonActorLocationPref {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default};}}"
                f"ButtonActorLocationPref::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonActorLocationPref {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different};}}"
                f"ButtonActorLocationPref::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        return [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete and avd.date == self.date]

    def mouseReleaseEvent(self, e) -> None:
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, self.tr('Location Preferences'),
                                 self.tr('No location preferences can be set up, '
                                         'as no availability has been selected for this day.'))
            return

        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_actor_loc_prefs.DlgActorLocPref(self, avail_days_at_date[0], self.actor_plan_period, team_at_date_factory)
        dlg.de_date.setDate(self.date)
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
                    new_pref = schemas.ActorLocationPrefCreate(**curr_loc_pref.model_dump())
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
        signal_handling.handler_actor_plan_period.reload_actor_pp__frm_actor_plan_period()

    @Slot(signal_handling.DataActorPPWithDate)
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if self.avail_days_at_date() or data.date:
            if data is None or data.date is None or data.date == self.date:
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet()


class ButtonActorPartnerLocationPref(QPushButton):
    def __init__(self, parent, date: datetime.date, width_height: int, actor_plan_period: schemas.ActorPlanPeriodShow,
                 team: schemas.TeamShow):
        super().__init__(parent)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.connect(
            self.reload_actor_plan_period)

        self.setObjectName(f'act_partner_loc_pref: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.actor_plan_period = actor_plan_period
        self.team = team
        self.date = date

        self.setToolTip('Employee / Location Preferences on %s' % date_to_string(date))

        self.set_stylesheet()  # sollte beschleunigt werden!

    # def deleteLater(self):
    #     # Trenne die Signale explizit, bevor das Widget gelöscht wird
    #     signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.disconnect(
    #         self.reload_actor_plan_period)
    #     super().deleteLater()

    def check_pref_of_day__eq__pref_of_actor_pp(self):
        partner_at_date_ids = get_persons_of_team_at_date_2(self.team, self.date)
        locations_at_date_ids = get_locations_of_team_at_date_2(self.team, self.date)

        avail_days = self.actor_plan_period.avail_days
        avail_days_at_date = [avd for avd in avail_days if avd.date == self.date]
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
                    QMessageBox.critical(
                        self, self.tr('Employee / Location Preferences'),
                        self.tr('The employee / location preferences of the availabilities for this day '
                                'have been reset to the default values of the planning period of '
                                '%s %s.') % (
                            self.actor_plan_period.person.f_name, self.actor_plan_period.person.l_name)
                    )
                    return True

        return prefs_actor_plan_period == pref_of_idx0

    def reset_prefs_of_day(self, avail_days_at_date: list[schemas.AvailDay] | None = None):
        if not avail_days_at_date:
            avail_days = self.actor_plan_period.avail_days
            avail_days_at_date = [avd for avd in avail_days if avd.date == self.date]

        for avd in avail_days_at_date:
            for pref_avd in avd.actor_partner_location_prefs_defaults:
                db_services.AvailDay.remove_partner_location_pref(avd.id, pref_avd.id)
            for pref_app in self.actor_plan_period.actor_partner_location_prefs_defaults:
                db_services.AvailDay.put_in_partner_location_pref(avd.id, pref_app.id)

    def set_stylesheet(self):
        check_loc_pref__eq__loc_pref_of_actor_pp = self.check_pref_of_day__eq__pref_of_actor_pp()
        if check_loc_pref__eq__loc_pref_of_actor_pp is None:
            self.setStyleSheet(
                f"ButtonActorPartnerLocationPref {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonActorPartnerLocationPref::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif check_loc_pref__eq__loc_pref_of_actor_pp:
            self.setStyleSheet(
                f"ButtonActorPartnerLocationPref {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonActorPartnerLocationPref::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonActorPartnerLocationPref {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonActorPartnerLocationPref::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        return [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete and avd.date == self.date]

    def mouseReleaseEvent(self, e) -> None:
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, self.tr('Employee / Location Preferences'),
                                 self.tr('No employee / location preferences can be set up, '
                                         'as no availability has been selected for this day.'))
            return

        person = db_services.Person.get(self.actor_plan_period.person.id)

        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_partner_location_prefs.DlgPartnerLocationPrefs(
            self, person, avail_days_at_date[0], self.actor_plan_period, team_at_date_factory)
        dlg.de_date.setDate(self.date)
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
        signal_handling.handler_actor_plan_period.reload_actor_pp__frm_actor_plan_period()

    @Slot(signal_handling.DataActorPPWithDate)
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if self.avail_days_at_date() or data.date:
            if data is None or data.date is None or data.date == self.date:
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet()


class ButtonSkills(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__(parent=parent)

        self.setObjectName(f'skill_groups: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        signal_handling.handler_actor_plan_period.signal_reset_styling_skills_configs.connect(
            self.reset_stylesheet_and_tooltip)
        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.connect(
            self.reload_actor_plan_period)

        self.clicked.connect(self.edit_skills_of_day)

        self.date = date
        self.actor_plan_period = actor_plan_period
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.set_stylesheet_and_tooltip()


    def set_stylesheet_and_tooltip(self):
        self._set_avail_days_at_day()
        self._set_stylesheet()
        self._set_tooltip()

    @Slot(object)
    def reset_stylesheet_and_tooltip(self, data: signal_handling.DataDate):
        if data.plan_period_id == self.actor_plan_period.plan_period.id and data.date == self.date:
            self.set_stylesheet_and_tooltip()

    def _set_avail_days_at_day(self):
        self.avail_days_at_day = db_services.AvailDay.get_from__actor_pp_date(self.actor_plan_period.id, self.date)

    def _check_skills_all_equal(self) -> bool | None:
        if not self.avail_days_at_day:
            return
        if len({len(ad.skills) for ad in self.avail_days_at_day}) > 1:
            return False
        return all(sorted(ad.skills, key=lambda x: x.id)
                   == sorted(self.avail_days_at_day[0].skills, key=lambda x: x.id)
                   for ad in self.avail_days_at_day)

    def _check_skills_all_equal_to_person_skills(self) -> bool | None:
        if not self.avail_days_at_day:
            return
        if len({len(ad.skills) for ad in self.avail_days_at_day}) > 1:
            return False
        person_skills = db_services.Skill.get_all_from__person(self.actor_plan_period.person.id)
        return all(sorted(ad.skills, key=lambda x: x.id)
                   == sorted(person_skills, key=lambda x: x.id)
                   for ad in self.avail_days_at_day)

    def _set_stylesheet(self):
        if (all_equal := self._check_skills_all_equal()) is None:
            self.setStyleSheet(
                f"ButtonSkills {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonSkills::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif all_equal and self._check_skills_all_equal_to_person_skills():
            self.setStyleSheet(
                f"ButtonSkills {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonSkills::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonSkills {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonSkills::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def _set_tooltip(self):
        if not self.avail_days_at_day:
            additional_txt = ''
        elif self._check_skills_all_equal():
            if not self.avail_days_at_day[0].skills:
                additional_txt = (
                    self.tr('\nNo skills selected.\n'
                            'This is the default setting for this employee.')
                    if self._check_skills_all_equal_to_person_skills()
                    else self.tr('\nNo skills selected.\n'
                                'This differs from the employee\'s skills.')
                )
            elif self._check_skills_all_equal_to_person_skills():
                additional_txt = self.tr('\nSkills for availabilities on this day\n'
                                       'are identical to the employee\'s skills.')
            else:
                additional_txt = self.tr('\nSkills for availabilities on this day\n'
                                       'are equal but different from the employee\'s skills.')
        else:
            additional_txt = self.tr('\nSkills for availabilities on this day are different.')
        self.setToolTip(
            self.tr('Click here to edit the skills for availabilities on %s.%s') % (
                date_to_string(self.date), additional_txt)
        )

    def edit_skills_of_day(self):
        if not self.avail_days_at_day:
            QMessageBox.information(
                self, self.tr('Skills for the day'),
                self.tr('No availabilities exist for %s') % date_to_string(self.date))
            return
        avail_day = next((ad for ad in self.avail_days_at_day if ad.skills), self.avail_days_at_day[0])
        dlg = frm_skills.DlgSelectSkills(self, avail_day)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            for avail_day in self.avail_days_at_day:
                for skill in avail_day.skills:
                    command_remove = avail_day_commands.RemoveSkill(avail_day.id, skill.id)
                    self.controller.execute(command_remove)
                for skill in dlg.object_with_skills.skills:
                    command_add = avail_day_commands.AddSkill(avail_day.id, skill.id)
                    self.controller.execute(command_add)
            self.set_stylesheet_and_tooltip()
            QMessageBox.information(
                self, self.tr('Skills for the day'),
                self.tr('The skills for day %s have been modified.') % date_to_string(self.date))
        else:
            dlg.controller.undo_all()

    @Slot(signal_handling.DataActorPPWithDate)
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate = None):
        """Entweder das Signal kommt ohne Datumsangabe oder mit Datumsangabe von ButtonAvailDay"""
        if data and (data.actor_plan_period.id == self.actor_plan_period.id) and (data.date == self.date):
            self._set_avail_days_at_day()
        if self.avail_days_at_day or data.date:
            if (data is None) or (data.date is None) or (data.date == self.date):
                if data is not None:
                    self.actor_plan_period = data.actor_plan_period
                else:
                    self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
                self.set_stylesheet_and_tooltip()


class FrmTabActorPlanPeriods(QWidget):
    resize_signal = Signal()

    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        self.setObjectName('tab_actor_plan_periods')

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.actor_plan_periods = self.plan_period.actor_plan_periods
        self.pers_id__actor_pp = {
            str(a_pp.person.id): a_pp for a_pp in self.plan_period.actor_plan_periods
            if db_services.TeamActorAssign.get_all_between_dates(a_pp.person.id, plan_period.team.id,
                                                                 plan_period.start, plan_period.end)}
        self.person_id: UUID | None = None
        self.person: schemas.PersonShow | None = None

        self.frame_availables: FrmActorPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum der Person:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_actor_pp)
        self.te_notes_pp.setFixedHeight(180)
        self.te_notes_pp.setDisabled(True)

        self.lb_notes_actor = QLabel('Infos zur Person:')
        self.lb_notes_actor.setFixedHeight(20)
        font_lb_notes = self.lb_notes_actor.font()
        font_lb_notes.setBold(True)
        self.lb_notes_actor.setFont(font_lb_notes)
        self.te_notes_actor = QTextEdit()
        self.te_notes_actor.textChanged.connect(self.save_info_person)
        self.te_notes_actor.setFixedHeight(180)
        self.te_notes_actor.setDisabled(True)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lb_title_name = QLabel('Verfügbarkeiten')
        self.lb_title_name.setContentsMargins(10, 10, 10, 10)

        self.lb_title_name_font = self.lb_title_name.font()
        self.lb_title_name_font.setPointSize(16)
        self.lb_title_name_font.setBold(True)
        self.lb_title_name.setFont(self.lb_title_name_font)
        self.layout.addWidget(self.lb_title_name)

        self.splitter_availables = QSplitter()
        self.layout.addWidget(self.splitter_availables)

        self.table_select_actor = QTableWidget()
        self.splitter_availables.addWidget(self.table_select_actor)
        self.setup_selector_table()

        self.widget_availables = QWidget()
        self.layout_availables = QVBoxLayout(self.widget_availables)
        self.layout_availables.setContentsMargins(0, 0, 0, 0)
        self.splitter_availables.addWidget(self.widget_availables)

        self.set_splitter_sizes()

        self.scroll_area_availables = QScrollArea()

        self.layout_controllers = QHBoxLayout()
        self.layout_notes = QHBoxLayout()
        self.layout_notes_actor = QVBoxLayout()
        self.layout_notes_actor_pp = QVBoxLayout()

        self.layout_availables.addWidget(self.scroll_area_availables)
        self.layout_availables.addLayout(self.layout_controllers)
        self.layout_availables.addLayout(self.layout_notes)
        self.layout_notes.addLayout(self.layout_notes_actor_pp)
        self.layout_notes.addLayout(self.layout_notes_actor)
        self.layout_notes_actor_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_actor_pp.addWidget(self.te_notes_pp)
        self.layout_notes_actor.addWidget(self.lb_notes_actor)
        self.layout_notes_actor.addWidget(self.te_notes_actor)

        self.side_menu = side_menu.SlideInMenu(self, 250, 10, 'right')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_signal.emit()

    def setup_selector_table(self):
        self.table_select_actor.setSortingEnabled(True)
        self.table_select_actor.setAlternatingRowColors(True)
        self.table_select_actor.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_select_actor.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_select_actor.verticalHeader().setVisible(False)
        self.table_select_actor.horizontalHeader().setHighlightSections(False)
        self.table_select_actor.cellClicked.connect(self.data_setup)
        self.table_select_actor.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_actor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        headers = ['id', 'Vorname', 'Nachname']
        self.table_select_actor.setColumnCount(len(headers))
        self.table_select_actor.setRowCount(len(self.pers_id__actor_pp))
        self.table_select_actor.setHorizontalHeaderLabels(headers)
        for row, actor_pp in enumerate(sorted(self.pers_id__actor_pp.values(), key=lambda x: x.person.f_name)):
            self.table_select_actor.setItem(row, 0, QTableWidgetItem(str(actor_pp.person.id)))
            self.table_select_actor.setItem(row, 1, QTableWidgetItem(actor_pp.person.f_name))
            self.table_select_actor.setItem(row, 2, QTableWidgetItem(actor_pp.person.l_name))
        self.table_select_actor.hideColumn(0)

    def set_splitter_sizes(self):
        self.splitter_availables.setStretchFactor(0, 0)
        self.splitter_availables.setStretchFactor(1, 1)
        header_width = sum(self.table_select_actor.horizontalHeader().sectionSize(i)
                           for i in range(self.table_select_actor.columnCount()))
        header_width += 3

        self.splitter_availables.setSizes([header_width, 10_000])
        self.table_select_actor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def data_setup(self, row: int = None, col: int = None, person_id: UUID = None):
        if person_id is None:
            self.person_id = UUID(self.table_select_actor.item(row, 0).text())
        else:
            self.person_id = person_id
        self.te_notes_actor.setEnabled(True)
        self.te_notes_pp.setEnabled(True)
        try:
            self.person = db_services.Person.get(self.person_id)
        except ValidationError as e:
            QMessageBox.critical(self, 'Planungsmaske',
                                 f'Planungsmaske der Person konnte nicht geladen werden.\n\n{e}')
            return
        actor_plan_period = self.pers_id__actor_pp[str(self.person_id)]
        actor_plan_period_show = db_services.ActorPlanPeriod.get(actor_plan_period.id)
        self.lb_title_name.setText(
            f'Verfügbarkeiten: {actor_plan_period.person.f_name} {actor_plan_period.person.l_name}')
        if self.frame_availables:
            self.delete_actor_plan_period_widgets()
        self.frame_availables = FrmActorPlanPeriod(self, actor_plan_period_show, self.side_menu)
        self.scroll_area_availables.setWidget(self.frame_availables)
        self.scroll_area_availables.setMinimumHeight(10000)  # brauche ich seltsamerweise, damit die Scrollarea expandieren kann.
        self.scroll_area_availables.setMinimumHeight(0)

        self.info_text_setup()

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
                 side_menu: side_menu.SlideInMenu):
        super().__init__(parent)

        self.setContentsMargins(0, 0, 0, 10)

        self.parent = parent
        self.layout_controllers = parent.layout_controllers

        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__frm_actor_plan_period.connect(self.reload_actor_plan_period)

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.controller_avail_days = command_base_classes.ContrExecUndoRedo()
        self.controller_actor_loc_prefs = command_base_classes.ContrExecUndoRedo()
        self.actor_plan_period = actor_plan_period
        self.t_o_d_standards: list[schemas.TimeOfDay] = []
        self.t_o_d_enums: list[schemas.TimeOfDayEnum] = []
        self.days: list[datetime.date] = []
        self.set_instance_variables()

        self.weekdays = {0: self.tr("Mon"),
                         1: self.tr("Tue"),
                         2: self.tr("Wed"),
                         3: self.tr("Thu"),
                         4: self.tr("Fri"),
                         5: self.tr("Sat"),
                         6: self.tr("Sun")}
        self.months = {1: self.tr("January"),
                       2: self.tr("February"),
                       3: self.tr("March"),
                       4: self.tr("April"),
                       5: self.tr("May"),
                       6: self.tr("June"),
                       7: self.tr("July"),
                       8: self.tr("August"),
                       9: self.tr("September"),
                       10: self.tr("October"),
                       11: self.tr("November"),
                       12: self.tr("December")}

        self.set_headers_months()
        self.set_chk_field()
        self.bt_toggle__avd_group_mode: QPushButton | None = None
        self.setup_controllers()
        self.get_avail_days()
        self._setup_side_menu()

    def _setup_side_menu(self):
        self.side_menu.delete_all_buttons()
        self.bt_requested_assignments = QPushButton(clicked=self.set_requested_assignments)
        self.set_text_bt_requested_assignments()
        self.side_menu.add_button(self.bt_requested_assignments)
        self.bt_time_of_days = QPushButton(self.tr('Times of Day...'), clicked=self.edit_time_of_days)
        self.side_menu.add_button(self.bt_time_of_days)
        self.bt_reset_all_avail_t_o_ds = QPushButton(self.tr('Reset Time Input Field'), clicked=self.reset_all_avail_t_o_ds)
        self.side_menu.add_button(self.bt_reset_all_avail_t_o_ds)
        self.bt_comb_loc_possibles = QPushButton(self.tr('Location Combinations'), clicked=self.edit_comb_loc_possibles)
        self.side_menu.add_button(self.bt_comb_loc_possibles)
        self.bt_actor_loc_prefs = QPushButton(self.tr('Location Preferences'), clicked=self.edit_location_prefs)
        self.side_menu.add_button(self.bt_actor_loc_prefs)
        self.bt_actor_partner_loc_prefs = QPushButton(self.tr('Partner/Location Prefs'), clicked=self.edit_partner_loc_prefs)
        self.side_menu.add_button(self.bt_actor_partner_loc_prefs)
        self.bt_fetch_avail_days_from_api = QPushButton(self.tr('Fetch Availabilities from API'), clicked=self.fetch_avail_days_from_api)
        self.side_menu.add_button(self.bt_fetch_avail_days_from_api)

    def reload_actor_plan_period(self, event=None):
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
        self.set_instance_variables()
        signal_handling.handler_plan_tabs.reload_all_plan_period_plans_from_db(self.actor_plan_period.plan_period.id)
        signal_handling.handler_plan_tabs.refresh_all_plan_period_plans_from_db(self.actor_plan_period.plan_period.id)

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
            label.setStyleSheet(widget_styles.labels.month_header_label_stylesheet)
            label_font = label.font()
            label_font.setPointSize(12)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setContentsMargins(5, 5, 5, 5)
            self.layout.addWidget(label, 0, col, 1, count)
            col += count

    def set_chk_field(self):  # todo: Config-Zeile Anzahl der Termine am Tag. Umsetzung automatisch über Group-Mode.
        person = db_services.Person.get(self.actor_plan_period.person.id)
        team = db_services.Team.get(self.actor_plan_period.team.id)
        for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
            self.layout.addWidget(QLabel(time_of_day.time_of_day_enum.name), row, 0)

        bt_comb_loc_poss_all_avail = QPushButton(self.tr('Location Combinations -> Reset'),
                                                 clicked=self.reset_all_avail_combs)
        bt_comb_loc_poss_all_avail.setStatusTip(
            self.tr('Reset location combinations for all availabilities in this period to the default values'))
        self.layout.addWidget(bt_comb_loc_poss_all_avail, row + 2, 0)

        bt_actor_loc_prefs_all_avail = QPushButton(self.tr('Location Prefs -> Reset'), clicked=self.reset_all_loc_prefs)
        bt_actor_loc_prefs_all_avail.setStatusTip(
            self.tr('Reset location preferences for all availabilities in this period to the default values'))
        self.layout.addWidget(bt_actor_loc_prefs_all_avail, row + 3, 0)

        bt_actor_partner_loc_prefs_all_avail = QPushButton(
            self.tr('Partner/Location Prefs -> Reset'),
            clicked=self.reset_all_partner_loc_prefs)
        bt_actor_partner_loc_prefs_all_avail.setStatusTip(
            self.tr('Reset partner/location preferences for all availabilities in this period to the default values'))
        self.layout.addWidget(bt_actor_partner_loc_prefs_all_avail, row + 4, 0)

        bt_skills_reset_all = QPushButton(self.tr('Skills'))
        bt_skills_reset_all.setStatusTip(self.tr('Edit skills for all availabilities in this period'))
        self.menu_bt_skills_reset_all = QMenu()
        bt_skills_reset_all.setMenu(self.menu_bt_skills_reset_all)

        actions_menu_bt_skills = [
            MenuToolbarAction(
                self,
                os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons',
                             'screwdriver--minus.png'),
                self.tr('Remove Skill'),
                self.tr('Remove all skills from availabilities in this period'),
                self.remove_skills_from_every_avail_day,
            ),
            MenuToolbarAction(
                self,
                os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons', 'screwdriver.png'),
                self.tr('Reset Skills'),
                self.tr('Reset all skills from availabilities in this period to person defaults'),
                self.reset_skills_of_every_avail_day,
            )
        ]
        for action in actions_menu_bt_skills:
            self.menu_bt_skills_reset_all.addAction(action)
        self.layout.addWidget(bt_skills_reset_all, row + 5, 0)

        for col, d in enumerate(self.days, start=1):
            assignment_of_person = get_curr_assignment_of_person(person, d)
            disable_buttons = ((assignment_of_person is None)
                               or (assignment_of_person.team.id != self.actor_plan_period.team.id))
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            if not self.t_o_d_standards:
                QMessageBox.critical(
                    self,
                    self.tr('Availabilities'),
                    self.tr(
                        'No default time-of-day values are defined for this planning period of {first} {last}').format(
                        first=self.actor_plan_period.person.f_name,
                        last=self.actor_plan_period.person.l_name
                    )
                )
                return
            for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
                button_avail_day = self.create_time_of_day_button(d, time_of_day)
                button_avail_day.setDisabled(disable_buttons)
                self.layout.addWidget(button_avail_day, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet(
                    f'background-color: rgba{widget_styles.labels.check_field_weekend_color_rgba_string};')
            self.layout.addWidget(lb_weekday, row + 1, col)
            bt_comb_loc_poss = ButtonCombLocPossible(self, d, 24, self.actor_plan_period)
            bt_comb_loc_poss.setDisabled(disable_buttons)
            self.layout.addWidget(bt_comb_loc_poss, row + 2, col)
            bt_loc_prefs = ButtonActorLocationPref(self, d, 24, self.actor_plan_period, team)
            bt_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_loc_prefs, row + 3, col)
            bt_partner_loc_prefs = ButtonActorPartnerLocationPref(self, d, 24, self.actor_plan_period, team)
            bt_partner_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_partner_loc_prefs, row + 4, col)
            bt_skills = ButtonSkills(self, d, 24, self.actor_plan_period)
            bt_skills.setDisabled(disable_buttons)
            self.layout.addWidget(bt_skills, row + 5, col)

    def reset_chk_field(self):
        self.parent.data_setup(person_id=self.actor_plan_period.person.id)
        return

    def create_time_of_day_button(self, date: datetime.date, time_of_day: schemas.TimeOfDay) -> ButtonAvailDay:
        # sourcery skip: inline-immediately-returned-variable
        button = ButtonAvailDay(self, date, time_of_day, 24, self.actor_plan_period, self.save_avail_day)
        return button

    def setup_controllers(self):
        self.bt_toggle__avd_group_mode = QPushButton(self.tr('Switch to Group Mode'),
                                                     clicked=self.change_mode__avd_group)
        self.layout_controllers.addWidget(self.bt_toggle__avd_group_mode)

    def save_avail_day(self, bt: ButtonAvailDay):
        date = bt.date
        t_o_d = bt.time_of_day
        if bt.isChecked():
            existing_avds_on_day = [avd for avd in self.actor_plan_period.avail_days
                                    if avd.date == date and not avd.prep_delete]
            avail_day_new = schemas.AvailDayCreate(date=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d)
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

            self.reload_actor_plan_period()

        else:
            avail_day = db_services.AvailDay.get_from__actor_pp_date_tod(self.actor_plan_period.id, date, t_o_d.id)
            del_command = avail_day_commands.Delete(avail_day.id)
            self.controller_avail_days.execute(del_command)
            self.reload_actor_plan_period()
            if not (master_group := del_command.avail_day_to_delete.avail_day_group.avail_day_group).actor_plan_period:
                if len(childs := db_services.AvailDayGroup.get_child_groups_from__parent_group(master_group.id)) < 2:
                    solo_avail_day = db_services.AvailDay.get_from__avail_day_group(childs[0].id)
                    QMessageBox.critical(
                        self,
                        self.tr('Availability Groups'),
                        self.tr(
                            'Deleting this appointment left a group with only one date: {date}\n'
                            'Please correct this in the following dialog.').format(
                            date=date_to_string(solo_avail_day.date)
                        )
                    )
                    self.change_mode__avd_group()

        bt.reload_actor_plan_period()

        signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
            signal_handling.DataActorPPWithDate(self.actor_plan_period, date))

    def change_mode__avd_group(self):
        dlg = frm_group_mode.DlgGroupModeBuilderActorPlanPeriod(self, self.actor_plan_period).build()
        if dlg.exec():
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('All changes have been applied.'))
            self.reload_actor_plan_period()
            signal_handling.handler_actor_plan_period.reload_actor_pp__avail_days(
                signal_handling.DataActorPPWithDate(self.actor_plan_period))
        else:
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('No changes were made.'))

        signal_handling.handler_actor_plan_period.change_actor_plan_period_group_mode(
            signal_handling.DataGroupMode(False))

    def set_button_avail_day_to_checked_and_configure(
            self, date: datetime.date, time_of_day: schemas.TimeOfDay, uncheck=False) -> ButtonAvailDay | None:
        button: ButtonAvailDay = self.findChild(ButtonAvailDay, f'{date}-{time_of_day.time_of_day_enum.name}')
        if not button:
            QMessageBox.critical(
                self,
                self.tr('Missing Standards'),
                self.tr('Error:\nCannot display available times.\nYou may have subsequently deleted "{time_of_day_name}" from the standards.').format(
                    time_of_day_name=time_of_day.time_of_day_enum.name
                )
            )
            return
        button.setChecked(not uncheck)
        button.time_of_day = time_of_day
        button.reset_context_menu(self.actor_plan_period)
        button.set_tooltip()

        return button

    def get_avail_days(self):
        avail_days = (ad for ad in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id)
                      if not ad.prep_delete)
        for ad in avail_days:
            self.set_button_avail_day_to_checked_and_configure(ad.date, ad.time_of_day)

    def set_text_bt_requested_assignments(self):
        self.bt_requested_assignments.setText(
            self.tr('Requested assignm. (curr.: {count}{required})').format(
                count=self.actor_plan_period.requested_assignments,
                required=self.tr(', required') if self.actor_plan_period.required_assignments else ''
            )
        )

    def set_requested_assignments(self):
        dlg = frm_requested_assignments.DlgRequestedAssignments(self, self.actor_plan_period.id)
        if dlg.exec():
            self.reload_actor_plan_period()
            self.set_text_bt_requested_assignments()

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderActorPlanPeriod(self, self.actor_plan_period).build()
        if dlg.exec():
            self.reload_actor_plan_period()
            self.reset_chk_field()

    def reset_all_avail_t_o_ds(self):
        """übernimmt bei allen avail_days die time_of_days der Planperiode."""
        avail_days = [ad for ad in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id)
                      if not ad.prep_delete]
        for avail_day in avail_days:
            self.controller_avail_days.execute(
                avail_day_commands.UpdateTimeOfDays(avail_day.id, self.actor_plan_period.time_of_days))
            time_of_day = next(t_o_d for t_o_d in self.actor_plan_period.time_of_day_standards
                               if t_o_d.time_of_day_enum.time_index == avail_day.time_of_day.time_of_day_enum.time_index)

            self.controller_avail_days.execute(
                avail_day_commands.UpdateTimeOfDay(
                    avail_day,
                    time_of_day.id)
            )
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
            signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
                signal_handling.DataActorPPWithDate(self.actor_plan_period))

    def reset_all_avail_combs(self):
        """Setzt combination_locations_possibles aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        reply = QMessageBox.question(
            self,
            self.tr('Reset Location Combinations'),
            self.tr('Do you want to reset all location combinations of availabilities '
                    'to the default values of the planning period?')
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        all_avail_dates = {avd.date for avd in self.actor_plan_period.avail_days if not avd.prep_delete}

        if not all_avail_dates:
            QMessageBox.critical(
                self,
                self.tr('Location Combinations'),
                self.tr('No availabilities exist in this planning period for {name}.').format(
                    name=self.actor_plan_period.person.full_name
                )
            )
            return

        button_comb_loc_possibles: list[ButtonCombLocPossible] = self.findChildren(ButtonCombLocPossible)

        for button_comb_loc_possible in button_comb_loc_possibles:
            if button_comb_loc_possible.date in all_avail_dates:
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
                    new_pref = schemas.ActorLocationPrefCreate(**curr_loc_pref.model_dump())
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
        signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
            signal_handling.DataActorPPWithDate(self.actor_plan_period))

    def reset_all_loc_prefs(self, e=None):
        """Setzt actor_location_prefs aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        reply = QMessageBox.question(
            self,
            self.tr('Reset Location Preferences'),
            self.tr('Do you want to reset all location preferences of availabilities '
                    'to the default values of the planning period?')
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        all_avail_dates = {avd.date for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
        if not all_avail_dates:
            QMessageBox.critical(
                self,
                self.tr('Location Preferences'),
                self.tr('No availabilities exist in this planning period for {name}.').format(
                    name=self.actor_plan_period.person.full_name
                )
            )
            return

        button_actor_location_prefs: list[ButtonActorLocationPref] = self.findChildren(ButtonActorLocationPref)

        for button_actor_location_pref in button_actor_location_prefs:
            if button_actor_location_pref.date in all_avail_dates:
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

        reply = QMessageBox.question(
            self,
            self.tr('Reset Partner Preferences'),
            self.tr('Do you want to reset all partner preferences of availabilities '
                    'to the default values of the planning period?')
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        all_avail_dates = {avd.date for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
        if not all_avail_dates:
            QMessageBox.critical(
                self,
                self.tr('Partner Preferences'),
                self.tr('No availabilities exist in this planning period for {name}.').format(
                    name=self.actor_plan_period.person.full_name
                )
            )
            return

        button_partner_location_prefs: list[ButtonActorPartnerLocationPref] = self.findChildren(ButtonActorPartnerLocationPref)

        for button_partner_location_pref in button_partner_location_prefs:  # todo: Kann mit einem Signal an die buttons evt. schneller gemacht werden
            if button_partner_location_pref.date in all_avail_dates:
                button_partner_location_pref.reset_prefs_of_day()
                button_partner_location_pref.reload_actor_plan_period()
                button_partner_location_pref.set_stylesheet()
        self.reload_actor_plan_period()

    def fetch_avail_days_from_api(self, *args, **kwargs):
        try:
            avail_days_on_server = plan_api_handler.fetch_avail_days(
                self.actor_plan_period.plan_period.id, self.actor_plan_period.person.id)
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr('Available Days'),
                self.tr('The following error occurred while downloading available days:\n{error}').format(error=e)
            )
            return
        if not avail_days_on_server:
            reply = QMessageBox.question(
                self,
                self.tr('Available Days'),
                self.tr('No available days found on server for {name} in the period {start} - {end}.\n'
                       'Do you want to delete all available days from the planning mask?').format(
                    name=self.actor_plan_period.person.full_name,
                    start=date_to_string(self.actor_plan_period.plan_period.start),
                    end=date_to_string(self.actor_plan_period.plan_period.end)
                )
            )
            if reply == QMessageBox.StandardButton.Yes:
                for avail_day in self.actor_plan_period.avail_days:
                    db_services.AvailDay.delete(avail_day.id)
                    # todo: besser... send AvailDayButton Signal to uncheck:
                    self.set_button_avail_day_to_checked_and_configure(avail_day.date, avail_day.time_of_day, True)
            return

        avail_days = [avd for avd in self.actor_plan_period.avail_days if not avd.prep_delete]
        if avail_days:
            reply = QMessageBox.question(
                self,
                self.tr('Available Days'),
                self.tr('Available days already exist in the planning mask for {name} in the period {start} - {end}.\n'
                       'Do you want to delete these available days from the planning mask?').format(
                    name=self.actor_plan_period.person.full_name,
                    start=date_to_string(self.actor_plan_period.plan_period.start),
                    end=date_to_string(self.actor_plan_period.plan_period.end)
                )
            )
            if reply == QMessageBox.StandardButton.No:
                return

        for avail_day in self.actor_plan_period.avail_days:
            db_services.AvailDay.delete(avail_day.id)
            # todo: besser... send AvailDayButton Signal to uncheck:
            self.set_button_avail_day_to_checked_and_configure(avail_day.date, avail_day.time_of_day, True)

        # fixme: Dies ist ein Workaround.
        #  Wenn die API auf die Tageszeiten dieses Projektes angepasst wird, kann dieser Workaround gelöscht werden
        abbreviation_dict = {'v': ('m',), 'n': ('n',), 'g': ('m', 'n')}
        for avail_day in avail_days_on_server:
            for abbreviation in abbreviation_dict[avail_day.time_of_day.value]:
                date = avail_day.day
                t_o_d = next(t for t in self.actor_plan_period.time_of_day_standards
                             if t.time_of_day_enum.abbreviation == abbreviation)
                button_avail_day = self.set_button_avail_day_to_checked_and_configure(date, t_o_d)
                save_command = avail_day_commands.Create(
                    schemas.AvailDayCreate(date=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d)
                )
                self.controller_avail_days.execute(save_command)

        self.reload_actor_plan_period()
        signal_handling.handler_actor_plan_period.reload_actor_pp__avail_configs(
            signal_handling.DataActorPPWithDate(self.actor_plan_period))

        QMessageBox.information(
            self,
            self.tr('Available Days'),
            self.tr('Available days were successfully downloaded.')
        )

    def remove_skills_from_every_avail_day(self):
        reply = QMessageBox.question(
            self,
            self.tr('Remove Skills'),
            self.tr('Do you want to remove skills from all availabilities in this planning period?')
        )
        if reply == QMessageBox.StandardButton.No:
            return

        for avail_day in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id):
            if not avail_day.prep_delete:
                for skill in avail_day.skills:
                    command = avail_day_commands.RemoveSkill(avail_day.id, skill.id)
                    self.controller.execute(command)

            signal_handling.handler_actor_plan_period.reset_styling_skills_configs(
                signal_handling.DataDate(self.actor_plan_period.plan_period.id, avail_day.date)
            )
        QMessageBox.information(
            self,
            self.tr('Remove Skills'),
            self.tr('All skills have been successfully removed from all availabilities in this planning period.')
        )

    def reset_skills_of_every_avail_day(self):
        reply = QMessageBox.question(
            self,
            self.tr('Reset Skills'),
            self.tr('Do you want to reset all skills of availabilities in this planning period '
                    'to the employee\'s default values?')
        )
        if reply == QMessageBox.StandardButton.No:
            return

        for avail_day in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id):
            if not avail_day.prep_delete:
                for skill in avail_day.skills:
                    command_remove = avail_day_commands.RemoveSkill(avail_day.id, skill.id)
                    self.controller.execute(command_remove)
                person = db_services.Person.get(self.actor_plan_period.person.id)
                for skill in person.skills:
                    command_add = avail_day_commands.AddSkill(avail_day.id, skill.id)
                    self.controller.execute(command_add)

            signal_handling.handler_actor_plan_period.reset_styling_skills_configs(
                signal_handling.DataDate(self.actor_plan_period.plan_period.id, avail_day.date)
            )
        QMessageBox.information(
            self,
            self.tr('Reset Skills'),
            self.tr('All skills have been successfully reset to default values '
                    'for all availabilities in this planning period.')
        )

if __name__ == '__main__':
    app = QApplication()
    plan_periods = [pp for pp in db_services.PlanPeriod.get_all_from__project(UUID('116C83375CA842E79DF97B0D2C7DBDE0'))
                    if not pp.prep_delete]
    window = FrmTabActorPlanPeriods(None, plan_periods[0])
    window.show()
    app.exec()


# todo: Wenn Tageszeit-Button geklickt wird und vor dem Loslassen weggezogen wird -> Fehlermeldung
# todo: Reset-Buttons in avail-day-frame sollten Signale senden
