import datetime
import functools
import logging
import os.path
import threading
from datetime import timedelta
from typing import Callable
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QGridLayout, QMessageBox, QScrollArea, QTextEdit, \
    QMenu, QApplication
from pydantic_core._pydantic_core import ValidationError

from database import schemas, db_services
from database.special_schema_requests import get_locations_of_team_at_date, get_curr_team_of_person_at_date, \
    get_curr_assignment_of_person, get_location_ids_at_date_from_team, \
    get_person_ids_at_date_from_team, get_next_assignment_of_person
from export_to_file import avail_days_to_xlsx
from gui import (frm_comb_loc_possible, frm_actor_loc_prefs, frm_partner_location_prefs, frm_group_mode,
                 frm_time_of_day, widget_styles, frm_requested_assignments, frm_skills)
from gui.custom_widgets import side_menu, BaseConfigButton
from gui.custom_widgets.custom_text_edits import NotesTextEdit
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import (actor_plan_period_commands, avail_day_commands,
                                        actor_loc_pref_commands, actor_partner_loc_pref_commands,
                                        person_commands, time_of_day_commands)
from gui.observer import signal_handling
from tools.helper_functions import date_to_string, time_to_string, setup_form_help, warn_and_clear_undo_redo_if_plans_open

logger = logging.getLogger(__name__)


class ButtonAvailDay(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodForMask, slot__avail_day_toggled: Callable):
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

        self.setProperty('time_index', str(self.time_of_day.time_of_day_enum.time_index))
        self.set_stylesheet()

        self.context_menu: QMenu | None = None  # Lazy – wird erst beim ersten Rechtsklick aufgebaut

        # self.actions = []
        # self.create_actions()
        # self.context_menu.addActions(self.actions)
        self.set_tooltip()

    def set_stylesheet(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

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
        if self.context_menu is None:
            self._setup_context_menu()
        self.context_menu.exec(pos.globalPos())

    def reset_context_menu(self, actor_plan_period: schemas.ActorPlanPeriodForMask):
        self.actor_plan_period = actor_plan_period
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        if self.context_menu is None:
            return  # Noch nie geöffnet – kein Reset nötig
        for action in self.context_menu.actions():
            self.context_menu.removeAction(action)
        self._setup_context_menu()

    def set_new_time_of_day(self, new_time_of_day: schemas.TimeOfDay):
        if self.isChecked():
            plan_period = self.actor_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end
            ):
                return

            avail_day = db_services.AvailDay.get_from__actor_pp_date_tod(
                self.actor_plan_period.id, self.date, self.time_of_day.id)
            avail_day_commands.UpdateTimeOfDay(avail_day, new_time_of_day.id).execute()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

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
            plan_period = self.actor_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                return

            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            signal_handling.handler_actor_plan_period.reset_styling_skills_configs(
                signal_handling.DataActorPlanPeriodDate(self.actor_plan_period.id, date=self.date))
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)
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
            self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)


class ButtonLocationCombinations(BaseConfigButton):
    """Button für Standort-Kombinationen pro Tag.

    Zeigt an, ob die Standort-Kombinationen am jeweiligen Tag den Defaults
    der ActorPlanPeriod entsprechen.
    """

    def __init__(self, parent, date: datetime.date, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodForMask,
                 controller: command_base_classes.ContrExecUndoRedo):
        # Eigene Attribute vor super().__init__() setzen
        self.person: schemas.PersonShow | None = None
        self.controller = controller

        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'comb_loc_poss: {date}')

        # Klick-Handler für Dialog-Öffnung
        self.clicked.connect(self._open_edit_dialog)

    # === Template Method Implementierungen ===

    def _check_matches_defaults(self) -> bool | None:
        """Prüft ob Standort-Kombinationen den Defaults entsprechen (reine Query)."""
        return self._check_comb_of_day__eq__comb_of_actor_pp()

    def _setup_tooltip(self) -> None:
        self.setToolTip(self.tr('Location combinations on %s') % date_to_string(self.date))

    # === CQS-konforme Methoden ===

    def _ensure_consistency(self) -> None:
        """Prüft auf Inkonsistenzen zwischen AvailDays und resettet bei Bedarf."""
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return

        if self._has_internal_inconsistency(avail_days_at_date):
            self._reset_to_defaults(avail_days_at_date)
            QMessageBox.critical(
                self, self.tr('Location Combinations'),
                self.tr('The location combinations of the availabilities for this day '
                        'have been reset to the default values of the planning period of '
                        '%s %s.') % (self.actor_plan_period.person.f_name,
                                     self.actor_plan_period.person.l_name)
            )

    def _has_internal_inconsistency(self, avail_days_at_date: list[schemas.AvailDay]) -> bool:
        """Prüft ob AvailDays am Tag untereinander inkonsistent sind (reine Query)."""
        if len(avail_days_at_date) <= 1:
            return False
        comb_of_idx0 = {comb.id for comb in avail_days_at_date[0].combination_locations_possibles}
        for avd in avail_days_at_date[1:]:
            if {comb.id for comb in avd.combination_locations_possibles} != comb_of_idx0:
                return True
        return False

    def _check_comb_of_day__eq__comb_of_actor_pp(self) -> bool | None:
        """Prüft ob Standort-Kombinationen am Tag den ActorPlanPeriod-Defaults entsprechen (reine Query)."""
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return None
        comb_of_idx0 = {comb.id for comb in avail_days_at_date[0].combination_locations_possibles}
        return {comb_locs.id for comb_locs in self.actor_plan_period.combination_locations_possibles} == comb_of_idx0

    def _reset_to_defaults(self, avail_days_at_date: list[schemas.AvailDay] | None = None) -> None:
        """Setzt Standort-Kombinationen auf ActorPlanPeriod-Defaults zurück."""
        if not avail_days_at_date:
            avail_days_at_date = self.avail_days_at_date()

        self.controller.execute(
            avail_day_commands.ReplaceAvailDayCombLocPossibles(
                avail_day_ids=[avd.id for avd in avail_days_at_date],
                person_id=self.actor_plan_period.person.id,
                original_ids=set(),
                pending_creates=[],
                current_combs=list(self.actor_plan_period.combination_locations_possibles),
            )
        )


    def get_person(self) -> schemas.PersonShow:
        """Gibt die Person der ActorPlanPeriod zurück (lazy loading)."""
        if self.person is None:
            self.person = db_services.Person.get(self.actor_plan_period.person.id)
        return self.person

    def _open_edit_dialog(self) -> None:
        """Öffnet den Dialog zur Bearbeitung der Standort-Kombinationen."""
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            QMessageBox.critical(self, self.tr('Location Combinations'),
                                 self.tr('No location combinations can be set up, '
                                         'as no availability has been selected for this day.'))
            return

        parent_model_factory = lambda date: self.actor_plan_period
        team_at_date_factory = functools.partial(get_curr_team_of_person_at_date, self.get_person())

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(
            self, avail_days_at_date[0], parent_model_factory, team_at_date_factory,
            curr_date=self.date)
        if dlg.exec():
            plan_period = self.actor_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end
            ):
                return

            self.controller.execute(
                avail_day_commands.ReplaceAvailDayCombLocPossibles(
                    avail_day_ids=[avd.id for avd in avail_days_at_date],
                    person_id=self.actor_plan_period.person.id,
                    original_ids=dlg.original_ids,
                    pending_creates=dlg.pending_creates,
                    current_combs=list(dlg.curr_model.combination_locations_possibles),
                )
            )

            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)
            self.refresh()
            signal_handling.handler_actor_plan_period.reload_actor_pp__frm_actor_plan_period()


class ButtonLocationPreferences(BaseConfigButton):
    """Button für Standort-Präferenzen pro Tag.

    Zeigt an, ob die Standort-Präferenzen am jeweiligen Tag den Defaults
    der ActorPlanPeriod entsprechen.
    """

    def __init__(self, parent, date: datetime.date, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodForMask, team: schemas.TeamShow):
        # Eigenes Attribut vor super().__init__() setzen
        self.team = team

        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'act_loc_pref: {date}')

        # Klick-Handler für Dialog-Öffnung
        self.clicked.connect(self._open_edit_dialog)

    # === Template Method Implementierungen ===

    def _check_matches_defaults(self) -> bool | None:
        """Prüft ob Standort-Präferenzen den Defaults entsprechen (reine Query)."""
        return self._check_loc_pref_of_day__eq__loc_pref_of_actor_pp()

    def _setup_tooltip(self) -> None:
        self.setToolTip(self.tr('Location preferences on %s') % date_to_string(self.date))

    # === CQS-konforme Methoden ===

    def _ensure_consistency(self) -> None:
        """Prüft auf Inkonsistenzen zwischen AvailDays und resettet bei Bedarf."""
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return

        if self._has_internal_inconsistency(avail_days_at_date):
            self._reset_to_defaults(avail_days_at_date)
            QMessageBox.critical(
                self, self.tr('Location Preferences'),
                self.tr('The location preferences of the availabilities for this day have been reset to '
                        'the default values of the planning period of '
                        '%s %s.') % (self.actor_plan_period.person.f_name,
                                     self.actor_plan_period.person.l_name)
            )

    def _has_internal_inconsistency(self, avail_days_at_date: list[schemas.AvailDay]) -> bool:
        """Prüft ob AvailDays am Tag untereinander inkonsistent sind (reine Query)."""
        if len(avail_days_at_date) <= 1:
            return False
        locations_at_date_ids = get_location_ids_at_date_from_team(self.team, self.date)
        pref_of_idx0 = {
            (pref.location_of_work.id, pref.score) for pref in avail_days_at_date[0].actor_location_prefs_defaults
            if (not pref.prep_delete or pref.prep_delete > self.date)
               and pref.location_of_work.id in locations_at_date_ids
        }
        for avd in avail_days_at_date[1:]:
            avd_prefs = {
                (pref.location_of_work.id, pref.score) for pref in avd.actor_location_prefs_defaults
                if (not pref.prep_delete or pref.prep_delete > self.date)
                   and pref.location_of_work.id in locations_at_date_ids
            }
            if avd_prefs != pref_of_idx0:
                return True
        return False

    def _check_loc_pref_of_day__eq__loc_pref_of_actor_pp(self) -> bool | None:
        """Prüft ob Standort-Präferenzen am Tag den ActorPlanPeriod-Defaults entsprechen (reine Query)."""
        locations_at_date_ids = get_location_ids_at_date_from_team(self.team, self.date)
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return None
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
        return prefs_actor_plan_period == pref_of_idx0

    def _reset_to_defaults(self, avail_days_at_date: list[schemas.AvailDay] | None = None) -> None:
        """Setzt Standort-Präferenzen auf ActorPlanPeriod-Defaults zurück."""
        if not avail_days_at_date:
            avail_days_at_date = self.avail_days_at_date()

        location_id_to_score = {
            pref.location_of_work.id: pref.score
            for pref in self.actor_plan_period.actor_location_prefs_defaults
            if not pref.prep_delete
        }
        self.controller.execute(
            avail_day_commands.ReplaceAvailDayLocationPrefs(
                avail_day_ids=[avd.id for avd in avail_days_at_date],
                person_id=self.actor_plan_period.person.id,
                project_id=self.actor_plan_period.project.id,
                location_id_to_score=location_id_to_score,
            )
        )

    def _open_edit_dialog(self) -> None:
        """Öffnet den Dialog zur Bearbeitung der Standort-Präferenzen."""
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

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return  # Dialog wurde bereits geschlossen, Änderungen sind in DB

        self.controller.execute(
            avail_day_commands.ReplaceAvailDayLocationPrefs(
                avail_day_ids=[avd.id for avd in avail_days_at_date],
                person_id=self.actor_plan_period.person.id,
                project_id=self.actor_plan_period.project.id,
                location_id_to_score=dlg.loc_id__results,
            )
        )

        new_actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
        self.refresh(signal_handling.DataActorPPWithDate(new_actor_plan_period, self.date))
        signal_handling.handler_plan_tabs.invalidate_entities_cache(plan_period.id)


class ButtonPartnerPreferences(BaseConfigButton):
    """Button für Mitarbeiter/Standort-Präferenzen pro Tag.

    Zeigt an, ob die Partner/Standort-Präferenzen am jeweiligen Tag den Defaults
    der ActorPlanPeriod entsprechen.
    """

    def __init__(self, parent, date: datetime.date, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodForMask, team: schemas.TeamShow):
        # Eigenes Attribut vor super().__init__() setzen
        self.team = team

        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'act_partner_loc_pref: {date}')

        # Klick-Handler für Dialog-Öffnung
        self.clicked.connect(self._open_edit_dialog)

    # === Template Method Implementierungen ===

    def _check_matches_defaults(self) -> bool | None:
        """Prüft ob Partner/Standort-Präferenzen den Defaults entsprechen (reine Query)."""
        return self._check_pref_of_day__eq__pref_of_actor_pp()

    def _setup_tooltip(self) -> None:
        self.setToolTip(self.tr('Employee / Location Preferences on %s') % date_to_string(self.date))

    # === CQS-konforme Methoden ===

    def _ensure_consistency(self) -> None:
        """Prüft auf Inkonsistenzen zwischen AvailDays und resettet bei Bedarf."""
        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return

        if self._has_internal_inconsistency(avail_days_at_date):
            self._reset_to_defaults(avail_days_at_date)
            QMessageBox.critical(
                self, self.tr('Employee / Location Preferences'),
                self.tr('The employee / location preferences of the availabilities for this day '
                        'have been reset to the default values of the planning period of '
                        '%s %s.') % (
                    self.actor_plan_period.person.f_name, self.actor_plan_period.person.l_name)
            )

    def _has_internal_inconsistency(self, avail_days_at_date: list[schemas.AvailDay]) -> bool:
        """Prüft ob AvailDays am Tag untereinander inkonsistent sind (reine Query)."""
        if len(avail_days_at_date) <= 1:
            return False
        partner_at_date_ids = get_person_ids_at_date_from_team(self.team, self.date)
        locations_at_date_ids = get_location_ids_at_date_from_team(self.team, self.date)
        pref_of_idx0 = {
            (pref.location_of_work.id, pref.partner.id, pref.score)
            for pref in avail_days_at_date[0].actor_partner_location_prefs_defaults
            if not pref.prep_delete
               and (pref.location_of_work.id in locations_at_date_ids and pref.partner.id in partner_at_date_ids)
        }
        for avd in avail_days_at_date[1:]:
            avd_prefs = {(pref.location_of_work.id, pref.partner.id, pref.score)
                         for pref in avd.actor_partner_location_prefs_defaults
                         if not pref.prep_delete
                         and (pref.location_of_work.id in locations_at_date_ids and pref.partner.id in partner_at_date_ids)}
            if avd_prefs != pref_of_idx0:
                return True
        return False

    def _check_pref_of_day__eq__pref_of_actor_pp(self) -> bool | None:
        """Prüft ob Partner/Standort-Präferenzen am Tag den ActorPlanPeriod-Defaults entsprechen (reine Query)."""
        partner_at_date_ids = get_person_ids_at_date_from_team(self.team, self.date)
        locations_at_date_ids = get_location_ids_at_date_from_team(self.team, self.date)

        avail_days_at_date = self.avail_days_at_date()
        if not avail_days_at_date:
            return None
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
        return prefs_actor_plan_period == pref_of_idx0

    def _reset_to_defaults(self, avail_days_at_date: list[schemas.AvailDay] | None = None) -> None:
        """Setzt Partner/Standort-Präferenzen auf ActorPlanPeriod-Defaults zurück."""
        if not avail_days_at_date:
            avail_days_at_date = self.avail_days_at_date()

        for avd in avail_days_at_date:
            remove_command = avail_day_commands.ClearActorPartnerLocationPrefs(avd.id,
                [apl.id for apl in avd.actor_partner_location_prefs_defaults])
            add_command = avail_day_commands.PutInActorPartnerLocationPrefs(avd.id,
                [apl.id for apl in self.actor_plan_period.actor_partner_location_prefs_defaults])
            batch_command = command_base_classes.BatchCommand(self, [remove_command, add_command])
            self.controller.execute(batch_command)

    def _open_edit_dialog(self) -> None:
        """Öffnet den Dialog zur Bearbeitung der Partner/Standort-Präferenzen."""
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

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        self.controller.execute(
            avail_day_commands.ReplacePartnerPrefsForAvailDays(
                avail_day_ids=[avd.id for avd in avail_days_at_date],
                person_id=self.actor_plan_period.person.id,
                new_prefs=dlg.new_prefs,
            )
        )

        new_actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
        self.refresh(signal_handling.DataActorPPWithDate(new_actor_plan_period, self.date))
        signal_handling.handler_plan_tabs.invalidate_entities_cache(plan_period.id)


class ButtonSkills(BaseConfigButton):
    """Button für Skills pro Tag.

    Zeigt an, ob die Skills der AvailDays am jeweiligen Tag den Person-Skills entsprechen.
    Besonderheiten:
    - Verwendet set_stylesheet_and_tooltip() statt nur set_stylesheet()
    - Hat eigenes Signal signal_reset_styling_skills_configs
    - Verwendet clicked-Signal statt mouseReleaseEvent
    """

    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 actor_plan_period: schemas.ActorPlanPeriodForMask,
                 avail_days_show: list[schemas.AvailDayWithSkills] | None = None,
                 person_skills: list | None = None):
        # Eigene Attribute vor super().__init__() setzen
        self._cached_avail_days: list[schemas.AvailDayWithSkills] = []
        self._prefetched_avail_days_show = avail_days_show
        self._prefetched_person_skills = person_skills
        self.controller = command_base_classes.ContrExecUndoRedo()

        super().__init__(parent, date, width_height, actor_plan_period)
        self.setObjectName(f'skill_groups: {date}')

        # Klick-Handler für Dialog-Öffnung
        self.clicked.connect(self.edit_skills_of_day)

    # === Template Method Implementierungen ===

    def _check_matches_defaults(self) -> bool | None:
        """Prüft ob Skills den Person-Skills entsprechen (reine Query).

        Returns:
            None: Keine AvailDays vorhanden
            True: Skills gleich UND entsprechen Person-Skills
            False: Skills unterschiedlich ODER entsprechen nicht Person-Skills
        """
        all_equal = self._check_skills_all_equal()
        if all_equal is None:
            return None
        if all_equal and self._check_skills_all_equal_to_person_skills():
            return True
        return False

    def _connect_signals(self) -> None:
        """Verbindet das zusätzliche Signal für Skill-Styling-Reset."""
        signal_handling.handler_actor_plan_period.signal_reset_styling_skills_configs.connect(
            self._reset_stylesheet_and_tooltip)

    def _on_stylesheet_updated(self) -> None:
        """Aktualisiert den Tooltip nach jedem Stylesheet-Update."""
        self._update_tooltip()

    # === Überschriebene Methoden ===

    def set_stylesheet(self) -> None:
        """Überschrieben um avail_days_at_date vor dem Check zu laden."""
        self._load_avail_days_at_date()
        super().set_stylesheet()

    @Slot(signal_handling.DataActorPPWithDate)
    def refresh(self, data: signal_handling.DataActorPPWithDate | None = None) -> None:
        """Überschrieben um set_stylesheet_and_tooltip() aufzurufen."""
        if data is None:
            self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
            self.set_stylesheet_and_tooltip()
        elif data.actor_plan_period.id == self.actor_plan_period.id:
            if data.date is None or data.date == self.date:
                self.actor_plan_period = data.actor_plan_period
                self.set_stylesheet_and_tooltip()

    # === Klassenspezifische Methoden ===

    def set_stylesheet_and_tooltip(self) -> None:
        """Aktualisiert Stylesheet und Tooltip gemeinsam."""
        self._load_avail_days_at_date()
        super().set_stylesheet()  # Ruft _on_stylesheet_updated() auf, das den Tooltip setzt

    @Slot(signal_handling.DataActorPlanPeriodDate)
    def _reset_stylesheet_and_tooltip(self, data: signal_handling.DataActorPlanPeriodDate) -> None:
        """Handler für signal_reset_styling_skills_configs."""
        # Optimierter Pfad: Prüfe zuerst actor_plan_period_id (schneller)
        if data.actor_plan_period_id is not None:
            if data.actor_plan_period_id != self.actor_plan_period.id:
                return
        # Fallback: Prüfe plan_period_id (für Plan-weite Updates)
        elif data.plan_period_id is not None:
            if data.plan_period_id != self.actor_plan_period.plan_period.id:
                return
        if (data.date and data.date == self.date) or not data.date:
            self._prefetched_avail_days_show = None  # Bei Reload immer frisch aus DB lesen
            self._prefetched_person_skills = None
            self.set_stylesheet_and_tooltip()

    def _load_avail_days_at_date(self) -> None:
        """Lädt und cached die AvailDays am Button-Datum."""
        if self._prefetched_avail_days_show is not None:
            self._cached_avail_days = self._prefetched_avail_days_show
            self._prefetched_avail_days_show = None  # Consume-once: danach immer aus DB laden
        else:
            self._cached_avail_days = db_services.AvailDay.get_with_skills__actor_pp_date(
                self.actor_plan_period.id, self.date)

    def _check_skills_all_equal(self) -> bool | None:
        """Prüft ob alle AvailDays am Tag die gleichen Skills haben."""
        if not self._cached_avail_days:
            return None
        if len({len(ad.skills) for ad in self._cached_avail_days}) > 1:
            return False
        return all(sorted(ad.skills, key=lambda x: x.id)
                   == sorted(self._cached_avail_days[0].skills, key=lambda x: x.id)
                   for ad in self._cached_avail_days)

    def _check_skills_all_equal_to_person_skills(self) -> bool | None:
        """Prüft ob die Skills der AvailDays den Person-Skills entsprechen."""
        if not self._cached_avail_days:
            return None
        if len({len(ad.skills) for ad in self._cached_avail_days}) > 1:
            return False
        person_skills = (self._prefetched_person_skills
                         if self._prefetched_person_skills is not None
                         else db_services.Skill.get_all_from__person(self.actor_plan_period.person.id))
        return all(sorted(ad.skills, key=lambda x: x.id)
                   == sorted(person_skills, key=lambda x: x.id)
                   for ad in self._cached_avail_days)

    def _update_tooltip(self) -> None:
        """Aktualisiert den Tooltip basierend auf dem aktuellen Skill-Status."""
        if not self._cached_avail_days:
            additional_txt = ''
        elif self._check_skills_all_equal():
            if not self._cached_avail_days[0].skills:
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

    def edit_skills_of_day(self) -> None:
        """Öffnet den Dialog zur Bearbeitung der Skills für diesen Tag."""
        if not self._cached_avail_days:
            QMessageBox.information(
                self, self.tr('Skills for the day'),
                self.tr('No availabilities exist for %s') % date_to_string(self.date))
            return
        # Für den Dialog volle AvailDayShow laden (benötigt actor_plan_period.person, time_of_day, project)
        avail_days_show = db_services.AvailDay.get_from__actor_pp_date(self.actor_plan_period.id, self.date)
        dialog_avail_day = next((ad for ad in avail_days_show if ad.skills), avail_days_show[0])
        dlg = frm_skills.DlgSelectSkills(self, dialog_avail_day)
        if dlg.exec():
            plan_period = self.actor_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                return

            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            for avail_day in avail_days_show:
                if avail_day.id == dialog_avail_day.id:
                    continue  # bereits durch den Dialog bearbeitet, Befehle schon im Undo-Stack
                for skill in avail_day.skills:
                    command_remove = avail_day_commands.RemoveSkill(avail_day.id, skill.id)
                    self.controller.execute(command_remove)
                for skill in dlg.object_with_skills.skills:
                    command_add = avail_day_commands.AddSkill(avail_day.id, skill.id)
                    self.controller.execute(command_add)
            self.set_stylesheet_and_tooltip()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)
            QMessageBox.information(
                self, self.tr('Skills for the day'),
                self.tr('The skills for day %s have been modified.') % date_to_string(self.date))
        else:
            dlg.controller.undo_all()


class FrmTabActorPlanPeriods(QWidget):
    resize_signal = Signal()

    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        self.setObjectName('tab_actor_plan_periods')

        signal_handling.handler_actor_plan_period.signal_update_app_in_app_tab_widget.connect(self.update_actor_plan_period)
        signal_handling.handler_actor_plan_period.signal_reload_app_notes_in_app_tab_widget.connect(self.reload_actor_plan_period_notes)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.plan_period = db_services.PlanPeriod.get_for_actor_tab(plan_period.id)
        self.team = self.plan_period.team
        self.actor_plan_periods = self.plan_period.actor_plan_periods
        active_person_ids = {
            taa.person.id for taa in self.plan_period.team.team_actor_assigns
            if taa.start <= plan_period.end and (taa.end is None or taa.end > plan_period.start)
        }
        self.pers_id__actor_pp = {
            str(a_pp.person.id): a_pp for a_pp in self.plan_period.actor_plan_periods
            if a_pp.person.id in active_person_ids}
        # ActorPlanPeriodForMask wird lazy on demand geladen (erstes data_setup) und dann gecacht
        self.pers_id__actor_pp_show: dict[str, schemas.ActorPlanPeriodForMask] = {}
        # Batch-Vorabladen: AvailDay-Skills und Person-Skills für alle aktiven Akteure
        self.app_id__avail_days_with_skills: dict[UUID, list[schemas.AvailDayWithSkills]] = (
            db_services.AvailDay.get_avail_days_skills__plan_period(plan_period.id))
        self.person_id__skills: dict[UUID, list[schemas.Skill]] = (
            db_services.Skill.get_person_skills__plan_period(plan_period.id))
        self.person_id: UUID | None = None
        self.person: schemas.PersonShow | None = None

        self.frame_availables: FrmActorPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum der Person:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = NotesTextEdit()
        self.te_notes_pp.editing_finished.connect(self.save_info_actor_pp)
        self.te_notes_pp.setFixedHeight(180)
        self.te_notes_pp.setDisabled(True)

        self.lb_notes_actor = QLabel('Infos zur Person:')
        self.lb_notes_actor.setFixedHeight(20)
        font_lb_notes = self.lb_notes_actor.font()
        font_lb_notes.setBold(True)
        self.lb_notes_actor.setFont(font_lb_notes)
        self.te_notes_actor = NotesTextEdit()
        self.te_notes_actor.editing_finished.connect(self.save_info_person)
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

        self.side_menu = side_menu.SlideInMenu(self,
                                               250,
                                               10,
                                               'right',
                                               (20, 30, 0, 20),
                                               (130, 205, 203, 100),
                                               True)

        # Help-System Integration
        setup_form_help(self, "actor_plan_period", add_help_button=True)

        # Die Planungsmaske der alphabetisch 1. Person wird als erstes angezeigt
        self.data_setup(None, None,
                        sorted(self.plan_period.actor_plan_periods, key=lambda x: x.person.f_name)[0].person.id)
        # Restliche Akteure im Hintergrund vorladen
        self._start_prefetch_remaining_actors()

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
        """
        Öffnet die Planungsmaske der Person, die entweder über die Tabelle ausgewählt wurde oder über die person_id.

        :param row: Zeile der Tabelle, falls die Person aus der Tabelle ausgewählt wurde.
        :param col: Spalte der Tabelle, falls die Person aus der Tabelle ausgewählt wurde.
        :param person_id: ID der Person, falls die Person direkt über die ID geöffnet werden soll.
        """
        if person_id is None:
            self.person_id = UUID(self.table_select_actor.item(row, 0).text())
        else:
            self.person_id = person_id
        self.te_notes_actor.setEnabled(True)
        self.te_notes_pp.setEnabled(True)
        actor_plan_period = self.pers_id__actor_pp[str(self.person_id)]
        actor_plan_period_show = self.pers_id__actor_pp_show.get(str(self.person_id))
        if actor_plan_period_show is None:
            actor_plan_period_show = db_services.ActorPlanPeriod.get_for_mask(actor_plan_period.id)
            self.pers_id__actor_pp_show[str(self.person_id)] = actor_plan_period_show
        self.person = actor_plan_period_show.person
        self.lb_title_name.setText(
            f'Verfügbarkeiten: {actor_plan_period.person.f_name} {actor_plan_period.person.l_name}')
        if self.frame_availables:
            self.delete_actor_plan_period_widgets()
        self.frame_availables = FrmActorPlanPeriod(self, actor_plan_period_show, self.side_menu, self.team)
        self.scroll_area_availables.setWidget(self.frame_availables)
        self.scroll_area_availables.setMinimumHeight(10000)  # brauche ich seltsamerweise, damit die Scrollarea expandieren kann.
        self.scroll_area_availables.setMinimumHeight(0)

        self.info_text_setup()

    def delete_actor_plan_period_widgets(self):
        self.frame_availables.deleteLater()
        for widget in (self.layout_controllers.itemAt(i).widget() for i in range(self.layout_controllers.count())):
            widget.deleteLater()

    def notes_app_setup(self):
        self.te_notes_pp.clear()
        self.te_notes_pp.setText(self.pers_id__actor_pp[str(self.person_id)].notes)

    def notes_person_setup(self):
        self.te_notes_actor.clear()
        self.te_notes_actor.setText(self.person.notes)

    def info_text_setup(self):
        self.notes_app_setup()
        self.notes_person_setup()

    def save_info_actor_pp(self):
        app_show = self.pers_id__actor_pp[str(self.person_id)]
        new_notes = self.te_notes_pp.toPlainText()
        old_notes = app_show.notes or ''
        if new_notes == old_notes:
            return
        cmd = actor_plan_period_commands.UpdateNotes(
            app_show.id, new_notes, notes_old=old_notes)
        self.controller.execute(cmd)
        # Cache lokal aktualisieren — der Server-Response ist absichtlich
        # ein leichtes ActorPlanPeriod (nicht Show), um die 140-KB-
        # Response-Bloat-Falle zu vermeiden.
        app_show.notes = new_notes

    def save_info_person(self):
        new_notes = self.te_notes_actor.toPlainText()
        old_notes = self.person.notes or ''
        if new_notes == old_notes:
            return
        cmd = person_commands.UpdateNotes(
            self.person.id, new_notes, notes_old=old_notes)
        self.controller.execute(cmd)
        # Cache lokal aktualisieren — Server liefert 204 No Content.
        self.person.notes = new_notes

    @Slot(schemas.ActorPlanPeriod)
    def update_actor_plan_period(self, actor_plan_period: schemas.ActorPlanPeriod):
        if actor_plan_period.plan_period.id == self.plan_period.id:
            person_key = str(actor_plan_period.person.id)
            self.pers_id__actor_pp[person_key] = actor_plan_period
            # Show-Cache und Skills-Caches invalidieren: nächstes data_setup lädt fresh vom DB
            self.pers_id__actor_pp_show.pop(person_key, None)
            self.app_id__avail_days_with_skills.pop(actor_plan_period.id, None)
            self.person_id__skills.pop(actor_plan_period.person.id, None)

    @Slot(UUID, UUID)
    def reload_actor_plan_period_notes(self, plan_period_id: UUID, person_id: UUID):
        if plan_period_id == self.plan_period.id and person_id == self.person_id:
            self.notes_app_setup()

    def _start_prefetch_remaining_actors(self):
        """Startet Hintergrund-Vorladen aller noch nicht gecachten ActorPlanPeriodForMask."""
        thread = threading.Thread(target=self._prefetch_actor_plan_periods, daemon=True)
        thread.start()

    def _prefetch_actor_plan_periods(self):
        """Läuft im Hintergrund-Thread. Lädt alle verbleibenden ActorPlanPeriodForMask per Batch."""
        remaining_ids = [
            a_pp.id for pers_id_str, a_pp in self.pers_id__actor_pp.items()
            if pers_id_str not in self.pers_id__actor_pp_show
        ]
        if not remaining_ids:
            return
        results = db_services.ActorPlanPeriod.get_multiple_for_mask(remaining_ids)
        for app in results:
            pers_id_str = str(app.person.id)
            if pers_id_str not in self.pers_id__actor_pp_show:
                self.pers_id__actor_pp_show[pers_id_str] = app


class FrmActorPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabActorPlanPeriods, actor_plan_period: schemas.ActorPlanPeriodForMask,
                 side_menu: side_menu.SlideInMenu, team: schemas.TeamShow):
        super().__init__(parent)

        self.setContentsMargins(0, 0, 0, 10)

        self.parent = parent
        self.layout_controllers = parent.layout_controllers

        signal_handling.handler_actor_plan_period.signal_reload_actor_pp__frm_actor_plan_period.connect(self.reload_actor_plan_period_and_set_instance_variables)

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.controller_avail_days = command_base_classes.ContrExecUndoRedo()
        self.controller_actor_loc_prefs = command_base_classes.ContrExecUndoRedo()
        self.controller_comb_loc_possibles = command_base_classes.ContrExecUndoRedo()
        self.actor_plan_period = actor_plan_period
        self.team = team
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
        self.setStyleSheet(widget_styles.buttons.avail_day__event_parent_css)
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
        self.bt_reset_all_avail_t_o_ds = QPushButton(self.tr('Reset Time of Day Input Field'), clicked=self.reset_all_avail_t_o_ds)
        self.bt_reset_all_avail_t_o_ds.setToolTip(
            self.tr("Adopts the time of day standards of the employee's planning period\n"
                    "for all of the employee's availabilities between {start} - {end}.").format(
                start=date_to_string(self.actor_plan_period.plan_period.start),
                end=date_to_string(self.actor_plan_period.plan_period.end)
            )
        )
        self.side_menu.add_button(self.bt_reset_all_avail_t_o_ds)
        self.bt_comb_loc_possibles = QPushButton(self.tr('Location Combinations'), clicked=self.edit_comb_loc_possibles)
        self.side_menu.add_button(self.bt_comb_loc_possibles)
        self.bt_actor_loc_prefs = QPushButton(self.tr('Location Preferences'), clicked=self.edit_location_prefs)
        self.side_menu.add_button(self.bt_actor_loc_prefs)
        self.bt_actor_partner_loc_prefs = QPushButton(self.tr('Partner/Location Prefs'), clicked=self.edit_partner_loc_prefs)
        self.side_menu.add_button(self.bt_actor_partner_loc_prefs)

    def reload_actor_plan_period_and_set_instance_variables(self, event=None):
        self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
        # Parent-Cache synchron halten: beim Wechsel zurück auf diesen Mitarbeiter
        # soll der frisch geladene Stand verwendet werden, nicht der veraltete Cache-Eintrag.
        self.parent.pers_id__actor_pp_show[str(self.actor_plan_period.person.id)] = self.actor_plan_period
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
        self.setUpdatesEnabled(False)
        try:
            self._set_chk_field()
        finally:
            self.setUpdatesEnabled(True)

    def _set_chk_field(self):
        person = self.actor_plan_period.person
        team = self.team
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

        # Berechne aktive Tage aus bereits geladenem team.team_actor_assigns (kein DB-Call)
        person_id = person.id
        active_in_team_dates = {
            d for taa in self.team.team_actor_assigns
            if taa.person.id == person_id
            for d in self.days
            if taa.start <= d and (taa.end is None or taa.end > d)
        }
        # Aus Startup-Cache lesen (kein DB-Call), Fallback auf DB wenn Cache invalidiert
        cached_avd_skills = self.parent.app_id__avail_days_with_skills.get(self.actor_plan_period.id)
        if cached_avd_skills is None:
            cached_avd_skills = db_services.AvailDay.get_all_with_skills__actor_plan_period(
                self.actor_plan_period.id)
        avail_days_show_by_date: dict = {}
        for avd in cached_avd_skills:
            avail_days_show_by_date.setdefault(avd.date, []).append(avd)
        cached_person_skills = self.parent.person_id__skills.get(self.actor_plan_period.person.id)
        person_skills = (cached_person_skills if cached_person_skills is not None
                         else db_services.Skill.get_all_from__person(self.actor_plan_period.person.id))
        for col, d in enumerate(self.days, start=1):
            # Multi-Team-kompatibel: Prüfe ob Person an diesem Tag dem Team des ActorPlanPeriods zugeordnet ist
            disable_buttons = d not in active_in_team_dates
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
            bt_comb_loc_poss = ButtonLocationCombinations(self, d, 24, self.actor_plan_period,
                                                           self.controller_comb_loc_possibles)
            bt_comb_loc_poss.setDisabled(disable_buttons)
            self.layout.addWidget(bt_comb_loc_poss, row + 2, col)
            bt_loc_prefs = ButtonLocationPreferences(self, d, 24, self.actor_plan_period, team)
            bt_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_loc_prefs, row + 3, col)
            bt_partner_loc_prefs = ButtonPartnerPreferences(self, d, 24, self.actor_plan_period, team)
            bt_partner_loc_prefs.setDisabled(disable_buttons)
            self.layout.addWidget(bt_partner_loc_prefs, row + 4, col)
            bt_skills = ButtonSkills(self, d, 24, self.actor_plan_period,
                                     avail_days_show=avail_days_show_by_date.get(d, []),
                                     person_skills=person_skills)
            bt_skills.setDisabled(disable_buttons)
            self.layout.addWidget(bt_skills, row + 5, col)

    def reset_chk_field(self):
        self.parent.data_setup(person_id=self.actor_plan_period.person.id)
        return

    def create_time_of_day_button(self, date: datetime.date, time_of_day: schemas.TimeOfDay) -> ButtonAvailDay:
        button = ButtonAvailDay(self, date, time_of_day, 24, self.actor_plan_period, self.save_avail_day)
        return button

    def setup_controllers(self):
        self.bt_toggle__avd_group_mode = QPushButton(self.tr('Switch to Group Mode'),
                                                     clicked=self.change_mode__avd_group)
        self.layout_controllers.addWidget(self.bt_toggle__avd_group_mode)


    def save_avail_day(self, bt: ButtonAvailDay):
        # WARNUNG AM ANFANG - VOR DB-Operation
        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end,
            on_cancel=bt.toggle  # Button-Status zurücksetzen
        ):
            return

        date = bt.date
        t_o_d = bt.time_of_day
        if bt.isChecked():
            existing_avds_on_day = [avd for avd in self.actor_plan_period.avail_days
                                    if avd.date == date and not avd.prep_delete]
            avail_day_new = schemas.AvailDayCreate(date=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d)
            save_command = avail_day_commands.Create(avail_day_new)
            self.controller_avail_days.execute(save_command)

            '''Falls es an diesem Tage schon einen oder mehrere AvailDays gibt, 
            werden die combination_locations_possibles, actor_location_prefs und actor_partner_location_prefs
            vom ersten gefundenen AvailDay übernommen, weil, davon ausgegangen
            wird, dass schon evt. geänderte combinations für alle AvailDays an diesem Tag gelten.'''
            created_avail_day = save_command.created_avail_day
            if existing_avds_on_day:
                self.controller_avail_days.execute(
                    avail_day_commands.ClearCombLocPossibles(created_avail_day.id,
                        [comb.id for comb in created_avail_day.combination_locations_possibles]))
                self.controller_avail_days.execute(
                    avail_day_commands.PutInCombLocPossibles(
                        created_avail_day.id,
                        [comb.id for comb in existing_avds_on_day[0].combination_locations_possibles if not comb.prep_delete]
                    )
                )
                self.controller_avail_days.execute(
                    avail_day_commands.ClearActorLocationPrefs(created_avail_day.id,
                        [alp.id for alp in created_avail_day.actor_location_prefs_defaults]))
                self.controller_avail_days.execute(
                    avail_day_commands.PutInActorLocationPrefs(
                        created_avail_day.id,
                        [alp.id for alp in existing_avds_on_day[0].actor_location_prefs_defaults if not alp.prep_delete]
                    )
                )
                self.controller_avail_days.execute(
                    avail_day_commands.ClearActorPartnerLocationPrefs(created_avail_day.id,
                        [apl.id for apl in created_avail_day.actor_partner_location_prefs_defaults]))
                self.controller.execute(
                    avail_day_commands.PutInActorPartnerLocationPrefs(
                        created_avail_day.id,
                        [apl.id for apl in existing_avds_on_day[0].actor_partner_location_prefs_defaults if not apl.prep_delete]
                    )
                )

            self.reload_actor_plan_period_and_set_instance_variables()

        else:
            avail_day = db_services.AvailDay.get_from__actor_pp_date_tod(self.actor_plan_period.id, date, t_o_d.id)
            del_command = avail_day_commands.Delete(avail_day.id)
            self.controller_avail_days.execute(del_command)
            self.reload_actor_plan_period_and_set_instance_variables()
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
        
        # Entities-Cache invalidieren bei Verfügbarkeitsänderungen
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

    def change_mode__avd_group(self):
        dlg = frm_group_mode.DlgGroupModeBuilderActorPlanPeriod(self, self.actor_plan_period).build()
        if dlg.exec():
            plan_period = self.actor_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                signal_handling.handler_actor_plan_period.change_actor_plan_period_group_mode(
                    signal_handling.DataGroupMode(False))
                return

            QMessageBox.information(self, self.tr('Group Mode'), self.tr('All changes have been applied.'))
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)
            self.reload_actor_plan_period_and_set_instance_variables()
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
        for ad in self.actor_plan_period.avail_days:
            if not ad.prep_delete:
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
            self.reload_actor_plan_period_and_set_instance_variables()
            self.set_text_bt_requested_assignments()

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderActorPlanPeriod(self, self.actor_plan_period).build()
        if dlg.exec():
            self.reload_actor_plan_period_and_set_instance_variables()
            self.reset_chk_field()

    def reset_all_avail_t_o_ds(self):
        """
        übernimmt für alle AvailDays der ActorPlanPeriod die TimeOfDays-Standards der ActorPlanPeriod.
        """
        # Warnung für Undo/Redo VOR den Änderungen
        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

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
        self.controller_avail_days.execute(
            time_of_day_commands.DeleteUnusedInProject(self.actor_plan_period.project.id))
        self.controller_avail_days.execute(
            time_of_day_commands.DeletePrepDeletesInProject(self.actor_plan_period.project.id))

        self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
        self.reset_chk_field()
        
        # Entities-Cache invalidieren bei TimeOfDay-Änderungen
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

    def edit_comb_loc_possibles(self, *args):
        person = db_services.Person.get_for_comb_loc_dialog(self.actor_plan_period.person.id)

        '''Workaround: für die Dialogklasse wird eine funktion gebraucht'''
        parent_model_factory = lambda date: person
        team_at_date_factory = lambda date: self.actor_plan_period.team
        '''----------------------------------------------------------------------------------------------------'''

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(self, self.actor_plan_period,
                                                               parent_model_factory,
                                                               team_at_date_factory,
                                                               self.actor_plan_period.plan_period.start)

        if dlg.exec():
            self.controller_comb_loc_possibles.execute(
                actor_plan_period_commands.ReplaceCombLocPossibles(
                    actor_plan_period_id=self.actor_plan_period.id,
                    person_id=self.actor_plan_period.person.id,
                    original_ids=dlg.original_ids,
                    pending_creates=dlg.pending_creates,
                    current_combs=dlg.curr_model.combination_locations_possibles,
                )
            )
            self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
            self.set_instance_variables()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)
            data = signal_handling.DataActorPPWithDate(self.actor_plan_period)
            for button in self.findChildren(ButtonLocationCombinations):
                button.refresh(data)

    def reset_all_avail_combs(self):
        """Setzt combination_locations_possibles aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        def refresh_ui():
            """Gemeinsamer UI-Refresh für Execute, Undo und Redo."""
            button_comb_loc_possibles: list[ButtonLocationCombinations] = self.findChildren(ButtonLocationCombinations)
            for button_comb_loc_possible in button_comb_loc_possibles:
                if button_comb_loc_possible.date in all_avail_dates:
                    button_comb_loc_possible.refresh(signal_handling.DataActorPPWithDate(
                        self.actor_plan_period))
            self.set_instance_variables()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

        def handle_reset():
            """Callback für Execute und Redo – schnelles In-Place-Patching."""
            defaults = list(self.actor_plan_period.combination_locations_possibles)
            for avail_day in self.actor_plan_period.avail_days:
                if not avail_day.prep_delete:
                    avail_day.combination_locations_possibles = list(defaults)
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        def handle_undo():
            """Callback für Undo – muss aus DB laden (individuelle Original-Werte)."""
            self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        # --- User-Interaktion ---
        reply = QMessageBox.question(
            self,
            self.tr('Reset Location Combinations'),
            self.tr('Do you want to reset all location combinations of availabilities '
                    'to the default values of the planning period?')
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
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

        # --- Ausführung ---
        self._reset_all_avail_days_comb_loc_possibles_to_defaults(
            on_undo_callback=handle_undo, on_redo_callback=handle_reset)
        handle_reset()

    def edit_location_prefs(self):

        person = db_services.Person.get(self.actor_plan_period.person.id)
        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_actor_loc_prefs.DlgActorLocPref(self, self.actor_plan_period, person, team_at_date_factory)
        dlg.de_date.setDate(self.actor_plan_period.plan_period.start)
        dlg.de_date.setDisabled(True)
        if not dlg.exec():
            return

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        self.controller_actor_loc_prefs.execute(
            actor_plan_period_commands.UpdateLocationPrefsBulk(
                self.actor_plan_period.id,
                dlg.loc_id__results,
            )
        )
        self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
        self.set_instance_variables()
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)
        data = signal_handling.DataActorPPWithDate(self.actor_plan_period)
        for button in self.findChildren(ButtonLocationPreferences):
            button.refresh(data)

    def reset_all_loc_prefs(self, e=None):
        """Setzt actor_location_prefs aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        def refresh_ui():
            """Gemeinsamer UI-Refresh für Execute, Undo und Redo."""
            button_actor_location_prefs: list[ButtonLocationPreferences] = self.findChildren(ButtonLocationPreferences)
            for button_actor_location_pref in button_actor_location_prefs:
                if button_actor_location_pref.date in all_avail_dates:
                    button_actor_location_pref.refresh(signal_handling.DataActorPPWithDate(
                        self.actor_plan_period))
            self.set_instance_variables()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

        def handle_reset():
            """Callback für Execute und Redo – schnelles In-Place-Patching."""
            defaults = self.actor_plan_period.actor_location_prefs_defaults
            for avail_day in self.actor_plan_period.avail_days:
                if not avail_day.prep_delete:
                    avail_day.actor_location_prefs_defaults = defaults
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        def handle_undo():
            """Callback für Undo – muss aus DB laden (individuelle Original-Werte)."""
            self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        # --- User-Interaktion ---
        reply = QMessageBox.question(
            self,
            self.tr('Reset Location Preferences'),
            self.tr('Do you want to reset all location preferences of availabilities '
                    'to the default values of the planning period?')
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
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

        # --- Ausführung ---
        self._reset_all_avail_days_location_prefs_to_defaults(
            on_undo_callback=handle_undo, on_redo_callback=handle_reset)
        handle_reset()

    def edit_partner_loc_prefs(self):
        person = db_services.Person.get(self.actor_plan_period.person.id)
        team_at_date_factory = lambda date: self.actor_plan_period.team

        dlg = frm_partner_location_prefs.DlgPartnerLocationPrefs(
            self, person, self.actor_plan_period, person, team_at_date_factory)
        dlg.de_date.setDate(self.actor_plan_period.plan_period.start)
        dlg.de_date.setDisabled(True)
        if not dlg.exec():
            return

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        self.controller_actor_loc_prefs.execute(
            actor_partner_loc_pref_commands.ReplaceAll(
                model_class_name=self.actor_plan_period.__class__.__name__,
                model_id=self.actor_plan_period.id,
                person_id=person.id,
                new_prefs=dlg.new_prefs,
            )
        )
        self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
        signal_handling.handler_plan_tabs.invalidate_entities_cache(plan_period.id)
        data = signal_handling.DataActorPPWithDate(self.actor_plan_period)
        for button in self.findChildren(ButtonPartnerPreferences):
            button.refresh(data)

    def reset_all_partner_loc_prefs(self, e):
        """Setzt actor_partner_location_prefs aller AvailDays in dieser Planperiode auf die Werte der Planperiode zurück."""

        def refresh_ui():
            button_partner_location_prefs: list[ButtonPartnerPreferences] = self.findChildren(ButtonPartnerPreferences)
            for button_partner_location_pref in button_partner_location_prefs:
                if button_partner_location_pref.date in all_avail_dates:
                    button_partner_location_pref.refresh(signal_handling.DataActorPPWithDate(
                        self.actor_plan_period))  # Lädt Daten und aktualisiert Stylesheet
            self.set_instance_variables()
            # Entities-Cache invalidieren bei Partner-Präferenzänderungen
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

        def handle_reset():
            # In-place Patch: bestehende Pydantic-Schemas aktualisieren, statt kompletten Objektgraphen neu aus DB zu laden
            defaults = self.actor_plan_period.actor_partner_location_prefs_defaults
            for avail_day in self.actor_plan_period.avail_days:
                if not avail_day.prep_delete:
                    avail_day.actor_partner_location_prefs_defaults = defaults
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        def handle_undo():
            # Bei Undo müssen die individuellen Original-Werte aus der DB geladen werden
            self.actor_plan_period = db_services.ActorPlanPeriod.get_for_mask(self.actor_plan_period.id)
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        reply = QMessageBox.question(
            self,
            self.tr('Reset Partner Preferences'),
            self.tr('Do you want to reset all partner preferences of availabilities '
                    'to the default values of the planning period?')
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # NEU: Warnung für Undo/Redo VOR den Änderungen
        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
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

        self._reset_all_avail_days_partner_location_prefs_to_defaults(
            on_undo_callback=handle_undo, on_redo_callback=handle_reset)
        handle_reset()

    def _reset_all_avail_days_partner_location_prefs_to_defaults(
            self, on_undo_callback=None, on_redo_callback=None) -> None:
        """Setzt Partner/Standort-Präferenzen für alle AvailDays der ActorPlanPeriod auf Defaults zurück."""
        command = avail_day_commands.ResetAllAvailDaysActorPartnerLocationPrefsToDefaults(self.actor_plan_period.id)
        self.controller.execute(command)
        command.on_undo_callback = on_undo_callback
        command.on_redo_callback = on_redo_callback

    def _reset_all_avail_days_location_prefs_to_defaults(
            self, on_undo_callback=None, on_redo_callback=None) -> None:
        """Setzt Standort-Präferenzen für alle AvailDays der ActorPlanPeriod auf Defaults zurück."""
        command = avail_day_commands.ResetAllAvailDaysActorLocationPrefsToDefaults(self.actor_plan_period.id)
        self.controller.execute(command)
        command.on_undo_callback = on_undo_callback
        command.on_redo_callback = on_redo_callback

    def _reset_all_avail_days_comb_loc_possibles_to_defaults(
            self, on_undo_callback=None, on_redo_callback=None) -> None:
        """Setzt Standort-Kombinationen für alle AvailDays der ActorPlanPeriod auf Defaults zurück."""
        command = avail_day_commands.ResetAllAvailDaysCombLocPossiblesToDefaults(self.actor_plan_period.id)
        self.controller.execute(command)
        command.on_undo_callback = on_undo_callback
        command.on_redo_callback = on_redo_callback

    def _remove_all_skills_from_all_avail_days(
            self, on_undo_callback=None, on_redo_callback=None) -> None:
        """Entfernt alle Skills von allen AvailDays der ActorPlanPeriod."""
        command = avail_day_commands.RemoveAllSkillsFromAllAvailDays(self.actor_plan_period.id)
        self.controller.execute(command)
        command.on_undo_callback = on_undo_callback
        command.on_redo_callback = on_redo_callback

    def _reset_all_skills_of_all_avail_days_to_person_defaults(
            self, on_undo_callback=None, on_redo_callback=None) -> None:
        """Setzt Skills aller AvailDays der ActorPlanPeriod auf Person-Defaults zurück."""
        command = avail_day_commands.ResetAllSkillsOfAllAvailDaysToPersonDefaults(self.actor_plan_period.id)
        self.controller.execute(command)
        command.on_undo_callback = on_undo_callback
        command.on_redo_callback = on_redo_callback

    def remove_skills_from_every_avail_day(self):
        """Entfernt alle Skills von allen AvailDays in dieser Planperiode."""

        def refresh_ui():
            """Gemeinsamer UI-Refresh für Execute, Undo und Redo."""
            for avail_date in all_avail_dates:
                signal_handling.handler_actor_plan_period.reset_styling_skills_configs(
                    signal_handling.DataActorPlanPeriodDate(self.actor_plan_period.id, date=avail_date)
                )
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

        def handle_change():
            """Callback für Execute, Undo und Redo – UI-Refresh (kein Patching nötig, da AvailDay kein skills-Feld hat)."""
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        # --- User-Interaktion ---
        reply = QMessageBox.question(
            self,
            self.tr('Remove Skills'),
            self.tr('Do you want to remove skills from all availabilities in this planning period?')
        )
        if reply == QMessageBox.StandardButton.No:
            return

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        all_avail_dates = {avd.date for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
        if not all_avail_dates:
            return

        # --- Ausführung ---
        self._remove_all_skills_from_all_avail_days(
            on_undo_callback=handle_change, on_redo_callback=handle_change)
        handle_change()

        QMessageBox.information(
            self,
            self.tr('Remove Skills'),
            self.tr('All skills have been successfully removed from all availabilities in this planning period.')
        )

    def reset_skills_of_every_avail_day(self):
        """Setzt Skills aller AvailDays auf die Person-Defaults zurück."""

        def refresh_ui():
            """Gemeinsamer UI-Refresh für Execute, Undo und Redo."""
            for avail_date in all_avail_dates:
                signal_handling.handler_actor_plan_period.reset_styling_skills_configs(
                    signal_handling.DataActorPlanPeriodDate(self.actor_plan_period.id, date=avail_date)
                )
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.actor_plan_period.plan_period.id)

        def handle_change():
            """Callback für Execute, Undo und Redo – UI-Refresh (kein Patching nötig, da AvailDay kein skills-Feld hat)."""
            warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end, show_warning=False)
            refresh_ui()

        # --- User-Interaktion ---
        reply = QMessageBox.question(
            self,
            self.tr('Reset Skills'),
            self.tr('Do you want to reset all skills of availabilities in this planning period '
                    'to the employee\'s default values?')
        )
        if reply == QMessageBox.StandardButton.No:
            return

        plan_period = self.actor_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        all_avail_dates = {avd.date for avd in self.actor_plan_period.avail_days if not avd.prep_delete}
        if not all_avail_dates:
            return

        # --- Ausführung ---
        self._reset_all_skills_of_all_avail_days_to_person_defaults(
            on_undo_callback=handle_change, on_redo_callback=handle_change)
        handle_change()

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
