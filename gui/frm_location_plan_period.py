import datetime
import functools
import logging
import os
from argparse import Action
from typing import Callable, Literal
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout, QAbstractItemView, QHeaderView, QTableWidgetItem, QPushButton, QMessageBox, QApplication, \
    QMenu, QSpinBox, QWidgetAction

from database import schemas, db_services
from database.special_schema_requests import get_curr_assignment_of_location
from gui import frm_flag, frm_time_of_day, frm_group_mode, frm_cast_group, widget_styles, data_processing, \
    frm_event_planing_rules, frm_num_actors_app
from gui.custom_widgets import side_menu
from gui.frm_notes import DlgEventNotes
from gui.frm_skill_groups import DlgSkillGroups
from tools import helper_functions
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import event_commands, cast_group_commands, event_group_commands, \
    location_plan_period_commands
from gui.frm_fixed_cast import DlgFixedCastBuilderLocationPlanPeriod, DlgFixedCastBuilderCastGroup
from gui.observer import signal_handling
from line_profiler_pycharm import profile

from tools.helper_functions import time_to_string, date_to_string

logger = logging.getLogger(__name__)


# Durch direkte Implementierung von signal.disconnect in die entsprechenden Widget-Klassen
# ist diese Funktion nicht mehr notwendig
def disconnect_event_button_signals():
    print('disconnect_event_button_signals')
    try:
        signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.disconnect()
    except Exception as e:
        print(f'Fehler in disconnect_event_button_signals: {e}')
    try:
        signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.disconnect()
    except Exception as e:
        print(f'Fehler in disconnect_event_button_signals: {e}')


class ButtonEvent(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, time_of_day: schemas.TimeOfDay, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow,
                 controller: command_base_classes.ContrExecUndoRedo, slot__event_toggled: Callable):
        super().__init__(parent)
        self.controller = controller
        self.slot__event_toggled = slot__event_toggled
        self.setObjectName(f'{date}-{time_of_day.time_of_day_enum.name}')
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCheckable(True)
        self.clicked.connect(self.button_clicked)
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.parent = parent

        signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.connect(
            self.set_group_mode)
        signal_handling.handler_location_plan_period.signal_reload_location_pp__events.connect(
            self.reload_location_plan_period
        )
        signal_handling.handler_location_plan_period.signal_event_update_num_employees.connect(
            self.update_num_employees
        )

        self.group_mode = False

        self.location_plan_period = location_plan_period
        self.date = date
        self.time_of_day = time_of_day
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        self.spin_box_num_employees: QSpinBox | None = None
        self.action_num_employees: QWidgetAction | None = None
        self.context_menu = QMenu()
        self.add_context_menu_items()

        self.set_stylesheet()

        self.set_tooltip()

    def set_stylesheet(self):
        self.setStyleSheet(widget_styles.buttons.avail_day__event[self.time_of_day.time_of_day_enum.time_index]
                           .replace('<<ObjectName>>', self.objectName()))
    
    def get_curr_event(self) -> schemas.EventShow | None:
        if self.isChecked():
            return db_services.Event.get_from__location_pp_date_tod(
                self.location_plan_period.id, self.date, self.time_of_day.id
            )
        return None

    @Slot(signal_handling.DataGroupMode)
    def set_group_mode(self, group_mode: signal_handling.DataGroupMode):
        self.group_mode = group_mode.group_mode
        if self.isChecked():
            if self.group_mode:
                if group_mode.date and (group_mode.date == self.date
                                        and group_mode.time_index == self.time_of_day.time_of_day_enum.time_index
                                        and group_mode.location_pp__actor_pp_id == self.location_plan_period.id):
                    self.setText(f'{group_mode.group_nr:02}' if group_mode.group_nr else None)
            else:
                self.setText(None)
        elif self.group_mode:
            self.setDisabled(True)
        else:
            self.setEnabled(True)

    def get_t_o_d_for_selection(self) -> list[schemas.TimeOfDay]:
        location_plan_period_time_of_days = sorted(
            [t_o_d for t_o_d in self.location_plan_period.time_of_days if not t_o_d.prep_delete], key=lambda x: x.start)
        return [t_o_d for t_o_d in location_plan_period_time_of_days
                if t_o_d.time_of_day_enum.time_index == self.time_of_day.time_of_day_enum.time_index]

    def contextMenuEvent(self, pos):
        self.context_menu.exec(pos.globalPos())

    def add_context_menu_items(self):
        self.menu_times_of_day = QMenu(self.tr('Times of Day'))
        self.actions_times_of_day = []
        self.create_actions_times_of_day()
        self.menu_times_of_day.addActions(self.actions_times_of_day)
        self.context_menu.addMenu(self.menu_times_of_day)
        self.create_actions__skills_fixed_flags_notes()

    def create_actions__skills_fixed_flags_notes(self):
        actions = [
            (self.tr('Skills'), self.edit_skills),
            (self.tr('Fixed Cast'), self.edit_fixed_cast),
            (self.tr('Flags'), self.edit_flags),
            (self.tr('Notes'), self.edit_notes)
        ]
        for text, slot in actions:
            self.context_menu.addAction(MenuToolbarAction(self, None, text, None, slot))

    def add_spin_box_num_employees(self):
        container_spin_box_num_employees = QWidget()
        layout_container = QHBoxLayout(container_spin_box_num_employees)
        lb_num_employees = QLabel(self.tr('Num Employees:'))
        self.spin_box_num_employees = QSpinBox()
        self.spin_box_num_employees.setRange(0, 100)
        self.spin_box_num_employees.setValue(self.get_curr_event().cast_group.nr_actors)
        layout_container.addWidget(lb_num_employees)
        layout_container.addWidget(self.spin_box_num_employees)
        self.spin_box_num_employees.valueChanged.connect(self.change_num_employees)
        self.action_num_employees = QWidgetAction(self.context_menu)
        self.action_num_employees.setObjectName('Num Employees')
        self.action_num_employees.setDefaultWidget(container_spin_box_num_employees)
        self.context_menu.addAction(self.action_num_employees)

    @Slot(object)
    def update_num_employees(self, data: signal_handling.DataEventUpdateNumEmployees):
        if not self.isChecked():
            return
        if (data.plan_period_id != self.location_plan_period.plan_period.id
                and data.location_plan_period_id != self.location_plan_period.id):
            return
        event = self.get_curr_event()
        if event:
            self.spin_box_num_employees.blockSignals(True)
            self.spin_box_num_employees.setValue(event.cast_group.nr_actors)
            self.spin_box_num_employees.blockSignals(False)

    def change_num_employees(self):
        event = self.get_curr_event()
        cast_group = event.cast_group
        self.controller.execute(
            cast_group_commands.UpdateNrActors(cast_group.id, self.spin_box_num_employees.value()))

    def reset_menu_times_of_day(self, location_plan_period: schemas.LocationPlanPeriodShow):
        self.location_plan_period = location_plan_period
        self.t_o_d_for_selection = self.get_t_o_d_for_selection()
        for action in self.menu_times_of_day.actions():
            self.menu_times_of_day.removeAction(action)
        self.create_actions_times_of_day()
        self.menu_times_of_day.addActions(self.actions_times_of_day)

    def create_actions_times_of_day(self):
        self.actions_times_of_day = [
            MenuToolbarAction(self, QIcon(os.path.join(os.path.dirname(__file__),
                                            'resources/toolbar_icons/icons/clock-select.png'))
            if t.name == self.time_of_day.name else None,
                   f'{t.name}: {time_to_string(t.start)}-{time_to_string(t.end)}', None,
                              functools.partial(self.set_new_time_of_day, t))
            for t in self.t_o_d_for_selection]

    def set_new_time_of_day(self, new_time_of_day: schemas.TimeOfDay):
        if self.isChecked():
            event = self.get_curr_event()
            event_commands.UpdateTimeOfDay(event, new_time_of_day.id).execute()

        self.time_of_day = new_time_of_day
        self.reload_location_plan_period()
        self.create_actions_times_of_day()
        self.reset_menu_times_of_day(self.location_plan_period)
        self.set_tooltip()
        signal_handling.handler_location_plan_period.reload_location_pp_on__frm_location_plan_period()

    def edit_skills(self):
        if not (event := self.get_curr_event()):
            QMessageBox.critical(
                self,
                self.tr('Skills'),
                self.tr('You must first set an appointment before you can edit the skills.')
            )
            return
        dlg = DlgSkillGroups(self, event)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reset_styling_skills_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, self.date)
            )

    def edit_fixed_cast(self):
        if not self.isChecked():
            QMessageBox.critical(
                self,
                self.tr('Flags'),
                self.tr('You must first set an appointment before you can edit the cast.')
            )
            return
        event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, self.date,
                                                                 self.time_of_day.id)
        cast_group = db_services.CastGroup.get(event.cast_group.id)
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        dlg = DlgFixedCastBuilderCastGroup(self.parent, cast_group, self.location_plan_period).build()
        if dlg.exec():
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, self.date)
            )

    def edit_flags(self):
        if not self.isChecked():
            QMessageBox.critical(
                self,
                self.tr('Flags'),
                self.tr('You must first set an appointment before you can edit the flags.')
            )
            return
        event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, self.date,
                                                                 self.time_of_day.id)
        dlg = frm_flag.DlgFlagsBuilderEvent(self.parent, event).dlg_flags
        if dlg.exec():
            ...

    def edit_notes(self):
        event = self.get_curr_event()
        if event is None:
            QMessageBox.critical(
                self,
                self.tr('Event Notes'),
                self.tr('Notes cannot be set when no appointment is scheduled.')
            )
            return
        dlg = DlgEventNotes(self, event)
        if dlg.exec():
            command = event_commands.UpdateNotes(event, dlg.notes)
            self.controller.execute(command)
            QMessageBox.information(
                self,
                self.tr('Event Notes'),
                self.tr('The new notes have been applied.')
            )
            logger.info(f"Signal will be emitted - event_changed for event {event.id} on {self.date} "
                        f"- {self.time_of_day.name}")
            signal_handling.handler_plan_tabs.event_changed(event.id, True)
            signal_handling.handler_location_plan_period.reset_styling_notes_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, self.date)
            )


    def set_tooltip(self):
        self.setToolTip(
            self.tr('Right click:\n'
                   'Change time span for time of day "{time_of_day}" on {date}.\n'
                   'Currently: {name} ({start}-{end})').format(
                time_of_day=self.time_of_day.time_of_day_enum.name,
                date=date_to_string(self.date),
                name=self.time_of_day.name,
                start=time_to_string(self.time_of_day.start),
                end=time_to_string(self.time_of_day.end)
            )
        )

    @Slot(signal_handling.DataLocationPPWithDate)
    def reload_location_plan_period(self, data: signal_handling.DataLocationPPWithDate = None):
        if data is not None:
            self.location_plan_period = data.location_plan_period
        else:
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)

    @Slot()
    def button_clicked(self):
        self.slot__event_toggled(self)
        if self.isChecked():
            self.add_spin_box_num_employees()
        else:
            self.context_menu.removeAction(self.action_num_employees)


class ButtonFixedCast(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow, cast_groups_of_pp: list[schemas.CastGroupShow]):
        super().__init__(parent=parent)

        signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.connect(
            self.reload_location_plan_period
        )
        signal_handling.handler_location_plan_period.signal_reset_styling_fixed_cast_configs.connect(
            self.reset_styling
        )

        signal_handling.handler_location_plan_period.signal_reload_cast_groups__cast_configs.connect(
            self.reload_cast_groups_at_day
        )
        self.clicked.connect(self.set_fixed_casts_of_day)

        self.parent = parent
        self.location_plan_period = location_plan_period
        self.date = date
        self.cast_groups_at_day = [c for c in cast_groups_of_pp if c.event
                                   and c.event.location_plan_period.id == self.location_plan_period.id
                                   and c.event.date == self.date]
        self.setObjectName(f'fixed_cast: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.set_stylesheet_and_tooltip()

    @Slot(signal_handling.DataDate)
    def reload_cast_groups_at_day(self, data: signal_handling.DataDate = None):
        if data:
            if data.plan_period_id != self.location_plan_period.plan_period.id:
                return
            if data.date is not None and data.date != self.date:
                return
        self.cast_groups_at_day = db_services.CastGroup.get_all_from__location_plan_period_at_date(
            self.location_plan_period.id, self.date)

    def check_fixed_cast__eq_to__local_pp(self):
        if not self.cast_groups_at_day:
            return
        fixed_casts_at_day = [c.fixed_cast for c in self.cast_groups_at_day]
        return (
            len(set(fixed_casts_at_day)) == 1
            and fixed_casts_at_day[0] == self.location_plan_period.fixed_cast
        )

    def set_stylesheet_and_tooltip(self):
        self.reload_cast_groups_at_day()
        self.set_stylesheet()
        self.set_tooltip()

    def set_stylesheet(self):
        check_all_equal = self.check_fixed_cast__eq_to__local_pp()
        if check_all_equal is None:
            self.setStyleSheet(
                f"ButtonFixedCast {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonFixedCast::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif check_all_equal:
            self.setStyleSheet(
                f"ButtonFixedCast {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonFixedCast::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonFixedCast {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonFixedCast::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def set_tooltip(self):
        if not self.cast_groups_at_day:
            additional_txt = ''
        elif len({cg.fixed_cast for cg in self.cast_groups_at_day}) > 1:
            additional_txt = self.tr('\nCast of events on this day:\nDifferent casts.')
        else:
            cast_clear_txt = helper_functions.generate_fixed_cast_clear_text(self.cast_groups_at_day[0].fixed_cast)
            additional_txt = self.tr('\nCast of events on this day:\n{cast}').format(
                cast=cast_clear_txt or self.tr('No fixed cast.')
            )

        self.setToolTip(self.tr('Click here to change the fixed cast for this day.{additional}').format(
            additional=additional_txt
        ))

    @Slot()
    def set_fixed_casts_of_day(self):
        if not self.cast_groups_at_day:
            QMessageBox.information(
                self,
                self.tr('Fixed Cast for Day'),
                self.tr('There are no events on {date}.').format(date=date_to_string(self.date))
            )
            return

        cast_group = next((cg for cg in self.cast_groups_at_day if cg.fixed_cast), self.cast_groups_at_day[0])
        dlg = DlgFixedCastBuilderCastGroup(self.parent, cast_group, self.location_plan_period).build()
        if dlg.exec():
            for cg in self.cast_groups_at_day:
                cast_group_commands.UpdateFixedCast(cg.id, dlg.fixed_cast_simplified).execute()
            self.set_stylesheet_and_tooltip()

    @Slot(signal_handling.DataLocationPPWithDate)
    def reload_location_plan_period(self, data: signal_handling.DataLocationPPWithDate):
        if (data.date and data.date == self.date) or not data.date:
            self.location_plan_period = data.location_plan_period

    @Slot(signal_handling.DataDate)
    def reset_styling(self, data: signal_handling.DataDate):
        if data.plan_period_id != self.location_plan_period.plan_period.id:
            return
        if (data.date and data.date == self.date) or not data.date:
            self.reload_cast_groups_at_day()
            self.set_stylesheet_and_tooltip()


class ButtonNotes(QPushButton):  # todo: Fertigstellen... + Tooltip Notes der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow,
                 controller: command_base_classes.ContrExecUndoRedo):
        super().__init__(parent=parent)

        signal_handling.handler_location_plan_period.signal_reset_styling_notes_configs.connect(
            self.reset_stylesheet_and_tooltip)

        self.setObjectName(f'notes: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        self.clicked.connect(self.edit_notes_of_day)

        self.date = date
        self.location_plan_period = location_plan_period
        self.controller = controller
        self.set_stylesheet_and_tooltip()

    def set_stylesheet_and_tooltip(self):
        self._set_events_at_day()
        self._set_stylesheet()
        self._set_tooltip()

    @Slot(object)
    def reset_stylesheet_and_tooltip(self, data: signal_handling.DataDate):
        if data.plan_period_id == self.location_plan_period.plan_period.id and data.date == self.date:
            self.set_stylesheet_and_tooltip()

    def _set_events_at_day(self):
        self.events_at_day = db_services.Event.get_from__location_pp_date(self.location_plan_period.id, self.date)

    def _check_notes_all_equal(self):
        if not self.events_at_day:
            return
        return len({e.notes for e in self.events_at_day}) == 1

    def _set_stylesheet(self):
        if (all_equal := self._check_notes_all_equal()) is None:
            self.setStyleSheet(
                f"ButtonNotes {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonNotes::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif all_equal:
            self.setStyleSheet(
                f"ButtonNotes {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonNotes::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonNotes {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonNotes::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def _set_tooltip(self):
        if not self.events_at_day:
            additional_txt = ''
        elif self._check_notes_all_equal():
            additional_txt = self.tr('\nNotes for events on this day:\n{notes}.').format(
                notes=self.events_at_day[0].notes if self.events_at_day[0].notes else self.tr('none')
            )
        else:
            additional_txt = self.tr('\nNotes for events on this day:\nDifferent notes.')

        self.setToolTip(self.tr('Click here to edit notes for events on {date}{additional}').format(
            date=date_to_string(self.date),
            additional=additional_txt
        ))

    def edit_notes_of_day(self):
        if not self.events_at_day:
            QMessageBox.information(
                self,
                self.tr('Event Notes'),
                self.tr('There are no events on {date}.').format(date=date_to_string(self.date))
            )
            return

        event = next((e for e in self.events_at_day if e.notes), self.events_at_day[0])
        dlg = DlgEventNotes(self, event, True)
        if dlg.exec():
            for event in self.events_at_day:
                command = event_commands.UpdateNotes(event, dlg.notes)
                self.controller.execute(command)
                signal_handling.handler_plan_tabs.event_changed(event.id, True)
            self.set_stylesheet_and_tooltip()
            QMessageBox.information(
                self,
                self.tr('Event Notes'),
                self.tr('Notes for events on {date} have been updated.').format(date=date_to_string(self.date))
            )


class ButtonSkillGroups(QPushButton):  # todo: Fertigstellen... + Tooltip Flags der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow):
        super().__init__(parent=parent)

        self.setObjectName(f'skill_groups: {date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        signal_handling.handler_location_plan_period.signal_reset_styling_skills_configs.connect(
            self.reset_stylesheet_and_tooltip)

        self.clicked.connect(self.edit_skill_groups_of_day)

        self.date = date
        self.location_plan_period = location_plan_period
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.set_stylesheet_and_tooltip()

    def set_stylesheet_and_tooltip(self):
        self._set_events_at_day()
        self._set_stylesheet()
        self._set_tooltip()

    @Slot(object)
    def reset_stylesheet_and_tooltip(self, data: signal_handling.DataDate):
        if data.plan_period_id == self.location_plan_period.plan_period.id and data.date == self.date:
            self.set_stylesheet_and_tooltip()

    def _set_events_at_day(self):
        self.events_at_day = db_services.Event.get_from__location_pp_date(self.location_plan_period.id, self.date)

    def _check_skill_groups_all_equal(self) -> bool | None:
        if not self.events_at_day:
            return
        if len({len(e.skill_groups) for e in self.events_at_day}) > 1:
            return False
        return all(sorted(e.skill_groups, key=lambda x: x.skill.id)
                   == sorted(self.events_at_day[0].skill_groups, key=lambda x: x.skill.id)
                   for e in self.events_at_day)

    def _check_skill_groups_all_equal_to_location_skill_groups(self) -> bool | None:
        if not self.events_at_day:
            return
        if len({len(e.skill_groups) for e in self.events_at_day}) > 1:
            return False
        location_skill_groups = db_services.SkillGroup.get_all_from__location_of_work(
            self.location_plan_period.location_of_work.id)
        return all(sorted(e.skill_groups, key=lambda x: x.skill.id)
                   == sorted(location_skill_groups, key=lambda x: x.skill.id)
                   for e in self.events_at_day)

    def _set_stylesheet(self):
        if (all_equal := self._check_skill_groups_all_equal()) is None:
            self.setStyleSheet(
                f"ButtonSkillGroups {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors}}}"
                f"ButtonSkillGroups::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.standard_colors_disabled}; }}")
        elif all_equal and self._check_skill_groups_all_equal_to_location_skill_groups():
            self.setStyleSheet(
                f"ButtonSkillGroups {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default}}}"
                f"ButtonSkillGroups::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.all_properties_are_default_disabled}; }}")
        else:
            self.setStyleSheet(
                f"ButtonSkillGroups {{background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different}}}"
                f"ButtonSkillGroups::disabled {{ background-color: "
                f"{widget_styles.buttons.ConfigButtonsInCheckFields.any_properties_are_different_disabled}; }}")

    def _set_tooltip(self):
        if not self.events_at_day:
            additional_txt = ''
        elif self._check_skill_groups_all_equal():
            if not self.events_at_day[0].skill_groups:
                additional_txt = (
                    self.tr('\nNo skills selected.\nThis is the default setting for this location.')
                    if self._check_skill_groups_all_equal_to_location_skill_groups()
                    else self.tr('\nNo skills selected.\nThis differs from the location\'s skills.')
                )
            elif self._check_skill_groups_all_equal_to_location_skill_groups():
                additional_txt = self.tr('\nSkills for events on this day\nare identical to the location\'s skills.')
            else:
                additional_txt = self.tr('\nSkills for events on this day\nare equal but different from the location\'s skills.')
        else:
            additional_txt = self.tr('\nSkills for events on this day are different.')

        self.setToolTip(self.tr('Click here to edit skills for events on {date}{additional}').format(
            date=date_to_string(self.date),
            additional=additional_txt
        ))

    def edit_skill_groups_of_day(self):
        if not self.events_at_day:
            QMessageBox.information(
                self,
                self.tr('Event Skills'),
                self.tr('There are no events on {date}.').format(date=date_to_string(self.date))
            )
            return

        event = next((e for e in self.events_at_day if e.skill_groups), self.events_at_day[0])
        dlg = DlgSkillGroups(self, event)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            for event in self.events_at_day:
                for skill_group in event.skill_groups:
                    command_remove = event_commands.RemoveSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command_remove)
                for skill_group in dlg.object_with_skill_groups.skill_groups:
                    command_add = event_commands.AddSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command_add)
                signal_handling.handler_plan_tabs.event_changed(event.id)
            self.set_stylesheet_and_tooltip()
            QMessageBox.information(
                self,
                self.tr('Event Skills'),
                self.tr('Skills for events on {date} have been updated.').format(date=date_to_string(self.date))
            )
        else:
            dlg.controller.undo_all()


class FrmTabLocationPlanPeriods(QWidget):
    resize_signal = Signal()

    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        self.setObjectName('tab_location_plan_periods')

        signal_handling.handler_show_dialog.signal_show_dlg_cast_group_pp.connect(self._edit_cast_groups_plan_period)

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.location_plan_periods = self.plan_period.location_plan_periods
        self.location_id__location_pp = {
            str(loc_pp.location_of_work.id): loc_pp for loc_pp in self.plan_period.location_plan_periods
            if db_services.TeamLocationAssign.get_all_of_location_between_dates(
                loc_pp.location_of_work.id, plan_period.team.id, plan_period.start, plan_period.end)
        }
        self.location_id: UUID | None = None
        self.location: schemas.LocationOfWorkShow | None = None
        self.frame_events: FrmLocationPlanPeriod | None = None
        self.lb_notes_pp = QLabel(self.tr('Planning Period Notes for Location:'))
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_pp.setFixedHeight(180)
        self.te_notes_pp.setDisabled(True)

        self.lb_notes_location = QLabel(self.tr('Location Notes:'))
        self.lb_notes_location.setFixedHeight(20)
        font_lb_notes = self.lb_notes_location.font()
        font_lb_notes.setBold(True)
        self.lb_notes_location.setFont(font_lb_notes)
        self.te_notes_location = QTextEdit()
        self.te_notes_location.textChanged.connect(self.save_info_location)
        self.te_notes_location.setFixedHeight(180)
        self.te_notes_location.setDisabled(True)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lb_title_name = QLabel(self.tr('Location Events'))
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
        self.layout_events = QVBoxLayout()
        self.layout_events.setContentsMargins(0, 0, 0, 0)
        self.widget_events.setLayout(self.layout_events)
        self.splitter_events.addWidget(self.widget_events)
        self.set_splitter_sizes()

        self.scroll_area_events = QScrollArea()

        self.bt_cast_groups_plan_period = QPushButton(
            self.tr('Edit Cast and Cast Groups for Planning Period...'),
            clicked=self.edit_cast_groups_plan_period
        )

        self.layout_controllers = QHBoxLayout()
        self.layout_notes = QHBoxLayout()
        self.layout_notes_location = QVBoxLayout()
        self.layout_notes_location_pp = QVBoxLayout()

        self.layout_events.addWidget(self.scroll_area_events)
        self.layout_events.addLayout(self.layout_controllers)
        self.layout_events.addLayout(self.layout_notes)
        self.layout_notes.addLayout(self.layout_notes_location_pp)
        self.layout_notes.addLayout(self.layout_notes_location)
        self.layout_notes_location_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_location_pp.addWidget(self.te_notes_pp)
        self.layout_notes_location.addWidget(self.lb_notes_location)
        self.layout_notes_location.addWidget(self.te_notes_location)

        self.layout.addWidget(self.bt_cast_groups_plan_period)

        self.side_menu = side_menu.SlideInMenu(self, 250, 10, 'right')

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_signal.emit()

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

        headers = ['id', self.tr('Name'), self.tr('City')]
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

    def data_setup(self, row: int = None, col: int = None, location_id: UUID = None):
        if location_id is None:
            self.location_id = UUID(self.table_select_location.item(row, 0).text())
        else:
            self.location_id = location_id
        self.te_notes_location.setEnabled(True)
        self.te_notes_pp.setEnabled(True)
        self.location = db_services.LocationOfWork.get(self.location_id)
        location_plan_period = self.location_id__location_pp[str(self.location_id)]
        location_plan_period_show = db_services.LocationPlanPeriod.get(location_plan_period.id)
        self.lb_title_name.setText(
            self.tr('Events: {location_name} {location_city}').format(
                location_name=location_plan_period_show.location_of_work.name,
                location_city=location_plan_period_show.location_of_work.address.city
            )
        )

        if self.frame_events:
            self.delete_location_plan_period_widgets()
        self.frame_events = FrmLocationPlanPeriod(self, location_plan_period_show, self.side_menu)
        self.scroll_area_events.setWidget(self.frame_events)
        self.scroll_area_events.setMinimumHeight(
            10000)  # brauche ich seltsamerweise, damit die Scrollarea expandieren kann.
        self.scroll_area_events.setMinimumHeight(0)

        self.info_text_setup()

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

    def edit_cast_groups_plan_period(self):
        visible_plan_period_ids = {location_pp.id for location_pp in self.plan_period.location_plan_periods}
        dlg = frm_cast_group.DlgCastGroups(self, self.plan_period, visible_plan_period_ids)
        if dlg.exec():
            signal_handling.handler_location_plan_period.reload_cast_groups__cast_configs(
                signal_handling.DataDate(self.plan_period.id)
            )
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(self.plan_period.id)
            )
            signal_handling.handler_location_plan_period.event_update_num_employees(
                plan_period_id=self.plan_period.id, location_plan_period_id=None
            )

    @Slot(UUID)
    def _edit_cast_groups_plan_period(self, plan_period_id: UUID):
        if plan_period_id == self.plan_period.id:
            self.edit_cast_groups_plan_period()


class FrmLocationPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabLocationPlanPeriods, location_plan_period: schemas.LocationPlanPeriodShow,
                 side_menu: side_menu.SlideInMenu):
        super().__init__(parent)

        self.setContentsMargins(0, 0, 0, 10)

        self.parent = parent
        self.layout_controllers = parent.layout_controllers

        signal_handling.handler_location_plan_period.signal_reload_location_pp__frm_location_plan_period.connect(
            self.reload_location_plan_period)
        signal_handling.handler_show_dialog.signal_show_dlg_event_group.connect(self._change_mode__event_group)
        signal_handling.handler_location_plan_period.signal_reset_check_field.connect(self._reset_chk_field)

        self.layout = QGridLayout(self)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.side_menu = side_menu
        self.setup_side_menu()

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.data_processor = data_processing.LocationPlanPeriodData(self, location_plan_period, self.controller)
        self.location_plan_period = location_plan_period
        self.t_o_d_standards: list[schemas.TimeOfDay] = []
        self.t_o_d_enums: list[schemas.TimeOfDayEnum] = []
        self.days: list[datetime.date] = []
        self.set_instance_variables()

        self.weekdays = {0: self.tr('Mon'), 1: self.tr('Tue'), 2: self.tr('Wed'), 3: self.tr('Thu'),
                         4: self.tr('Fri'), 5: self.tr('Sat'), 6: self.tr('Sun')}
        self.months = {1: self.tr('January'), 2: self.tr('February'), 3: self.tr('March'), 4: self.tr('April'),
                       5: self.tr('May'), 6: self.tr('June'), 7: self.tr('July'), 8: self.tr('August'),
                       9: self.tr('September'), 10: self.tr('October'), 11: self.tr('November'),
                       12: self.tr('December')}

        self.set_headers_months()
        self.set_chk_field()
        self.bt_event_group_mode: QPushButton | None = None
        self.bt_cast_group_mode: QPushButton | None = None
        self.setup_controllers()
        self.get_events()

    def setup_side_menu(self):
        self.side_menu.delete_all_buttons()
        bt_nr_actors = QPushButton(self.tr('Cast Size'), clicked=self.set_nr_actors)
        self.side_menu.add_button(bt_nr_actors)
        bt_event_planing_rules = QPushButton(
            self.tr('Set Events According to Rules'),
            clicked=self.make_events_from_planing_rules
        )
        self.side_menu.add_button(bt_event_planing_rules)
        bt_time_of_days = QPushButton(self.tr('Times of Day...'), clicked=self.edit_time_of_days)
        self.side_menu.add_button(bt_time_of_days)
        bt_reset_all_event_t_o_ds = QPushButton(
            self.tr('Reset Time of Day Input Field'),
            clicked=self.reset_all_event_t_o_ds
        )
        self.side_menu.add_button(bt_reset_all_event_t_o_ds)
        bt_fixed_cast = QPushButton(self.tr('Fixed Cast'), clicked=self.edit_fixed_cast)
        self.side_menu.add_button(bt_fixed_cast)

    def reload_location_plan_period(self):
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        self.set_instance_variables()

    def set_instance_variables(self):
        self.t_o_d_standards = sorted([t_o_d for t_o_d in self.location_plan_period.time_of_day_standards
                                       if not t_o_d.prep_delete], key=lambda x: x.time_of_day_enum.time_index)
        self.t_o_d_enums = [t_o_d.time_of_day_enum for t_o_d in self.t_o_d_standards]
        self.days = [
            self.location_plan_period.plan_period.start + datetime.timedelta(delta) for delta in
            range((self.location_plan_period.plan_period.end - self.location_plan_period.plan_period.start).days + 1)]
        self.data_processor.location_plan_period = self.location_plan_period

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

    def set_chk_field(self):  # todo: Config-Zeile Anzahl der Termine am Tag. Wird automatisch über Group-Mode gelöst
        location_of_work = db_services.LocationOfWork.get(self.location_plan_period.location_of_work.id)
        cast_groups_of_pp = db_services.CastGroup.get_all_from__plan_period(
            self.location_plan_period.plan_period.id)

        # Time of day row labels
        for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
            self.layout.addWidget(QLabel(time_of_day.time_of_day_enum.name), row, 0)

        # Day config row labels / buttons
        bt_fixed_cast_reset = QPushButton(self.tr('Cast -> Reset'), clicked=self.reset_all_fixed_cast)
        bt_fixed_cast_reset.setStatusTip(
            self.tr('Reset fixed cast for all availabilities in this period to the standard values of the planning period.')
        )
        self.layout.addWidget(bt_fixed_cast_reset, row + 2, 0)

        lb_notes = QLabel(self.tr('Notes'))
        self.layout.addWidget(lb_notes, row + 3, 0)

        bt_skills_reset_all = QPushButton(self.tr('Skills'))
        bt_skills_reset_all.setStatusTip(self.tr('Edit skills for all availabilities in this period.'))
        self.menu_bt_skills_reset_all = QMenu()
        bt_skills_reset_all.setMenu(self.menu_bt_skills_reset_all)
        actions_menu_bt_skills = [
            MenuToolbarAction(
                self,
                os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons', 'screwdriver--minus.png'),
                self.tr('Remove Skills'),
                self.tr('Remove all skills from events in this period.'),
                self.remove_skills_from_every_event,
            ),
            MenuToolbarAction(
                self,
                os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons', 'screwdriver.png'),
                self.tr('Reset Skills'),
                self.tr('Reset all skills from events in this period to the standard values of the facility.'),
                self.reset_skills_of_every_event,
            )
        ]
        for action in actions_menu_bt_skills:
            self.menu_bt_skills_reset_all.addAction(action)
        self.layout.addWidget(bt_skills_reset_all, row + 4, 0)

        # Day config buttons
        for col, d in enumerate(self.days, start=1):
            curr_assignment_of_location = get_curr_assignment_of_location(location_of_work, d)
            if curr_assignment_of_location is None:
                disable_buttons = True
            else:
                disable_buttons = curr_assignment_of_location.team.id != self.location_plan_period.team.id
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            if not self.t_o_d_standards:
                QMessageBox.critical(
                    self,
                    self.tr('Availabilities'),
                    self.tr('Error:\nNo time of day standards are defined for this planning period of {name} {city}').format(
                        name=self.location_plan_period.location_of_work.name,
                        city=self.location_plan_period.location_of_work.address.city
                    )
                )
                return
            for row, time_of_day in enumerate(self.t_o_d_standards, start=2):
                button_event = self.create_event_button(d, time_of_day)
                button_event.setDisabled(disable_buttons)
                self.layout.addWidget(button_event, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet(
                    f'background-color: rgba{widget_styles.labels.check_field_weekend_color_rgba_string}')
            self.layout.addWidget(lb_weekday, row + 1, col)
            bt_fixed_cast = ButtonFixedCast(self, d, 24, self.location_plan_period, cast_groups_of_pp)
            bt_fixed_cast.setDisabled(disable_buttons)
            self.layout.addWidget(bt_fixed_cast, row + 2, col)
            bt_notes = ButtonNotes(self, d, 24, self.location_plan_period, self.controller)
            bt_notes.setDisabled(disable_buttons)
            self.layout.addWidget(bt_notes, row + 3, col)
            bt_skills = ButtonSkillGroups(self, d, 24, self.location_plan_period)
            bt_skills.setDisabled(disable_buttons)
            self.layout.addWidget(bt_skills, row + 4, col)

    def reset_chk_field(self):
        self.parent.data_setup(location_id=self.location_plan_period.location_of_work.id)

    @Slot(UUID)
    def _reset_chk_field(self, location_plan_period_id: UUID):
        if location_plan_period_id == self.location_plan_period.id:
            self.reset_chk_field()

    def create_event_button(self, date: datetime.date, time_of_day: schemas.TimeOfDay) -> ButtonEvent:
        # sourcery skip: inline-immediately-returned-variable
        button = ButtonEvent(self, date, time_of_day, 24, self.location_plan_period,
                             self.controller, self.save_event)
        return button

    def setup_controllers(self):
        """Buttons in self.layout_controllers area"""
        self.bt_event_group_mode = QPushButton(
            self.tr('Switch to Group Mode'),
            clicked=self.change_mode__event_group
        )
        self.layout_controllers.addWidget(self.bt_event_group_mode)
        self.bt_cast_group_mode = QPushButton(
            self.tr('Switch to Fixed Cast Group Mode'),
            clicked=self.change_mode__cast_group
        )
        self.layout_controllers.addWidget(self.bt_cast_group_mode)

    def save_event(self, bt: ButtonEvent):
        date = bt.date
        t_o_d = bt.time_of_day
        mode: Literal['added', 'deleted'] = 'added' if bt.isChecked() else 'deleted'
        self.data_processor.save_event(date, t_o_d, mode)

    def change_mode__event_group(self):
        dlg = frm_group_mode.DlgGroupModeBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('All changes have been applied.'))
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__events(
                signal_handling.DataLocationPPWithDate(self.location_plan_period))
        else:
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('No changes were made.'))

        signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
            signal_handling.DataGroupMode(False))

    @Slot(UUID)
    def _change_mode__event_group(self, location_plan_period_id: UUID):
        if location_plan_period_id == self.location_plan_period.id:
            self.change_mode__event_group()

    def change_mode__cast_group(self):
        plan_period = db_services.PlanPeriod.get(self.location_plan_period.plan_period.id)
        dlg = frm_cast_group.DlgCastGroups(self, plan_period, {self.location_plan_period.id})
        if dlg.exec():
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('All changes have been applied.'))
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__events(
                signal_handling.DataLocationPPWithDate(self.location_plan_period))
            signal_handling.handler_location_plan_period.reload_cast_groups__cast_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id)
            )
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id)
            )
            signal_handling.handler_location_plan_period.event_update_num_employees(
                plan_period_id=None, location_plan_period_id=self.location_plan_period.id
            )
        else:
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('No changes were made.'))

    def get_events(self):
        events = (e for e in db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id)
                  if not e.prep_delete)
        for event in events:
            button: ButtonEvent = self.findChild(ButtonEvent, f'{event.date}-{event.time_of_day.time_of_day_enum.name}')
            if not button:
                QMessageBox.critical(
                    self,
                    self.tr('Missing Standards'),
                    self.tr('Error:\nCannot display available times.\nYou may have subsequently deleted "{}" from the standards.').format(
                        event.time_of_day.time_of_day_enum.name
                    )
                )
                return
            button.setChecked(True)
            button.time_of_day = event.time_of_day
            button.create_actions_times_of_day()
            button.reset_menu_times_of_day(self.location_plan_period)
            button.add_spin_box_num_employees()
            button.set_tooltip()

    def set_nr_actors(self):
        dlg = frm_num_actors_app.DlgNumActorsApp(self, self.location_plan_period.id)
        if dlg.exec():
            self.reload_location_plan_period()
            command = location_plan_period_commands.UpdateNumActors(self.location_plan_period.id, dlg.num_actors)
            self.controller.execute(command)
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__events(
                signal_handling.DataLocationPPWithDate(self.location_plan_period))

    def make_events_from_planing_rules(self):
        dlg = frm_event_planing_rules.DlgEventPlanningRules(
            self, self.location_plan_period.id, True)
        if dlg.exec():
            self.data_processor.make_events_from_planning_rules(dlg)
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            return
        else:
            dlg.controller.undo_all()

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            self.reload_location_plan_period()
            buttons_event: list[ButtonEvent] = self.findChildren(ButtonEvent)
            for bt in buttons_event:
                bt.reset_menu_times_of_day(self.location_plan_period)
            self.reset_chk_field()

    def reset_all_event_t_o_ds(self):
        """übernimmt bei allen events die time_of_days der Planperiode."""
        events = [e for e in db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id)
                  if not e.prep_delete]
        for event in events:
            self.controller.execute(
                event_commands.UpdateTimeOfDays(event.id, self.location_plan_period.time_of_days))
            time_of_day = next(t_o_d for t_o_d in self.location_plan_period.time_of_day_standards
                               if t_o_d.time_of_day_enum.time_index == event.time_of_day.time_of_day_enum.time_index)
            self.controller.execute(
                event_commands.UpdateTimeOfDay(
                    event,
                    time_of_day.id)
            )
        db_services.TimeOfDay.delete_unused(self.location_plan_period.project.id)
        db_services.TimeOfDay.delete_prep_deletes(self.location_plan_period.project.id)

        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        self.reset_chk_field()

    def remove_skills_from_every_event(self):
        reply = QMessageBox.question(
            self,
            self.tr('Remove Skills'),
            self.tr('Do you really want to remove all skills from all events in this planning period of {}?').format(
                self.location_plan_period.location_of_work.name_an_city
            )
        )
        if reply == QMessageBox.StandardButton.No:
            return

        for event in db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id):
            if not event.prep_delete:
                for skill_group in event.skill_groups:
                    command = event_commands.RemoveSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command)

            signal_handling.handler_location_plan_period.reset_styling_skills_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, event.date)
            )
        QMessageBox.information(
            self,
            self.tr('Remove Skills'),
            self.tr('All skills have been successfully removed from all events.')
        )

    def reset_skills_of_every_event(self):
        reply = QMessageBox.question(
            self,
            self.tr('Reset Skills'),
            self.tr('Do you really want to reset all skills of all events in this planning period of {} to the facility\'s standard values?').format(
                self.location_plan_period.location_of_work.name_an_city
            )
        )
        if reply == QMessageBox.StandardButton.No:
            return

        for event in db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id):
            if not event.prep_delete:
                for skill_group in event.skill_groups:
                    command_remove = event_commands.RemoveSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command_remove)
                location_of_work = db_services.LocationOfWork.get(self.location_plan_period.location_of_work.id)
                for skill_group in location_of_work.skill_groups:
                    command_add = event_commands.AddSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command_add)

            signal_handling.handler_location_plan_period.reset_styling_skills_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, event.date)
            )
        QMessageBox.information(
            self,
            self.tr('Reset Skills'),
            self.tr('All skills have been successfully reset for all events.')
        )

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
                signal_handling.DataLocationPPWithDate(self.location_plan_period)
            )
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(plan_period_id=self.location_plan_period.plan_period.id)
            )

    def reset_all_fixed_cast(self):
        reply = QMessageBox.question(
            self,
            self.tr('Reset Cast'),
            self.tr('Do you really want to reset the fixed cast of all events to the cast standard of this planning period of {} {}?').format(
                self.location_plan_period.location_of_work.name,
                self.location_plan_period.location_of_work.address.city
            )
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        cast_groups_of_plan_period = db_services.CastGroup.get_all_from__plan_period(
            self.location_plan_period.plan_period.id)
        event_cast_groups = (c for c in cast_groups_of_plan_period
                             if c.event
                             and c.event.location_plan_period.id == self.location_plan_period.id
                             and c.fixed_cast != self.location_plan_period.fixed_cast)
        for c in event_cast_groups:
            command = cast_group_commands.UpdateFixedCast(c.id,  self.location_plan_period.fixed_cast)
            self.controller.execute(command)
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataDate(self.location_plan_period.plan_period.id, c.event.date)
            )

        QMessageBox.information(
            self,
            self.tr('Reset Cast'),
            self.tr('The cast of all events has been successfully reset.')
        )




if __name__ == '__main__':
    app = QApplication()
    plan_periods = [pp for pp in db_services.PlanPeriod.get_all_from__project(UUID('72F1D1E9BF554F11AE44916411A9819E'))
                    if not pp.prep_delete]
    window = FrmTabLocationPlanPeriods(None, plan_periods[0])
    window.show()
    app.exec()

# todo: Reset-Buttons in event-frame sollten Signale senden
