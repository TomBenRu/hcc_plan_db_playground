import datetime
import functools
import logging
import os
from typing import Callable, Literal
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtCore import Qt, Slot, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout, QAbstractItemView, QHeaderView, QTableWidgetItem, QPushButton, QMessageBox, QApplication, \
    QMenu, QSpinBox, QWidgetAction

from database import schemas, db_services
from gui import frm_flag, frm_time_of_day, frm_group_mode, frm_cast_group, widget_styles, data_processing, \
    frm_event_planing_rules, frm_num_actors_app
from gui.custom_widgets import side_menu
from gui.custom_widgets.custom_text_edits import NotesTextEdit
from gui.frm_notes import DlgEventNotes
from gui.frm_num_actors_app import DlgNumEmployeesEvent
from gui.frm_skill_groups import DlgSkillGroups
from tools import helper_functions
from tools.actions import MenuToolbarAction
from commands import command_base_classes
from commands.database_commands import event_commands, cast_group_commands, location_plan_period_commands, \
    time_of_day_commands, location_of_work_commands
from gui.frm_fixed_cast import DlgFixedCastBuilderLocationPlanPeriod, DlgFixedCastBuilderCastGroup
from gui.observer import signal_handling

from tools.helper_functions import time_to_string, date_to_string, setup_form_help, warn_and_clear_undo_redo_if_plans_open

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
        signal_handling.handler_location_plan_period.signal_appointment_moved.connect(
            self.on_appointment_moved
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

        self.setProperty('time_index', str(self.time_of_day.time_of_day_enum.time_index))

        self.set_tooltip()

    def set_stylesheet(self):
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
    
    def get_curr_event(self, state: Literal['checked', 'unchecked'] = 'checked') -> schemas.EventShow | None:
        if (state == 'checked' and self.isChecked()) or (state == 'unchecked' and not self.isChecked()):
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

    def add_spin_box_num_employees(self, nr_actors: int | None = None):
        # Threading-sichere Lösung: Standard QAction mit Dialog statt QWidgetAction
        current_num = nr_actors if nr_actors is not None else self.get_curr_event().cast_group.nr_actors
        action_text = self.tr('Employees: {num_employees}').format(num_employees=current_num)

        self.action_num_employees = MenuToolbarAction(self, None, action_text, None, self.show_num_employees_dialog)
        self.context_menu.addAction(self.action_num_employees)

    def show_num_employees_dialog(self):
        """Zeigt Dialog zur Änderung der Mitarbeiteranzahl."""
        dlg = DlgNumEmployeesEvent(self, self.get_curr_event())
        if dlg.exec():
            self.apply_num_employees_change(dlg.get_num_employees())
    
    def apply_num_employees_change(self, new_value: int):
        """Wendet Änderung der Mitarbeiteranzahl an und schließt Dialog."""
        self.change_num_employees(new_value)
        
        # Context-Menu-Text sofort aktualisieren (zusätzlich zum Signal-Update)
        if self.action_num_employees:
            new_text = self.tr('Employees: {num_employees}').format(num_employees=new_value)
            self.action_num_employees.setText(new_text)
            self.set_tooltip()

    @Slot(object)
    def update_num_employees(self, data: signal_handling.DataEventUpdateNumEmployees):
        if not self.isChecked():
            return
        if (data.plan_period_id != self.location_plan_period.plan_period.id
                and data.location_plan_period_id != self.location_plan_period.id):
            return
        event = self.get_curr_event()
        if event and self.action_num_employees:
            # Action-Text mit neuer Anzahl aktualisieren
            new_text = self.tr('Employees: {num_employees}').format(num_employees=event.cast_group.nr_actors)
            self.action_num_employees.setText(new_text)

    def change_num_employees(self, new_value: int = None):
        # Warnung für Undo/Redo VOR der DB-Operation
        plan_period = self.location_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        event = self.get_curr_event()
        cast_group = event.cast_group

        # Wenn new_value gegeben, verwende diesen, sonst Fallback (sollte nicht passieren)
        value = new_value if new_value is not None else cast_group.nr_actors

        self.controller.execute(
            cast_group_commands.UpdateNrActors(cast_group.id, value))
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

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
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end
            ):
                return

            event = self.get_curr_event()
            event_commands.UpdateTimeOfDay(event, new_time_of_day.id).execute()

        self.time_of_day = new_time_of_day
        self.reload_location_plan_period()
        self.create_actions_times_of_day()
        self.reset_menu_times_of_day(self.location_plan_period)
        self.set_tooltip()
        signal_handling.handler_location_plan_period.reload_location_pp_on__frm_location_plan_period()
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

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
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                return

            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reset_styling_skills_configs(
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id, self.date)
            )
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

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
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end
            ):
                return  # Dialog wurde bereits geschlossen, Änderungen sind in DB

            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id, self.date)
            )
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

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
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id, self.date)
            )


    def set_tooltip(self, nr_actors: int | None = None):
        if nr_actors is not None:
            num_employees = nr_actors
        else:
            event = self.get_curr_event()
            num_employees = event.cast_group.nr_actors if event else self.location_plan_period.nr_actors
        self.setToolTip(
            self.tr('Right click:\n'
                    'Change options for time of day "{time_of_day}" on {date}.\n'
                    'Currently: {name} ({start}-{end})\n'
                    'Number of employees: {num_employees}').format(
                time_of_day=self.time_of_day.time_of_day_enum.name,
                date=date_to_string(self.date),
                name=self.time_of_day.name,
                start=time_to_string(self.time_of_day.start),
                end=time_to_string(self.time_of_day.end),
                num_employees=num_employees
            )
        )

    @Slot(signal_handling.DataLocationPPWithDate)
    def reload_location_plan_period(self, data: signal_handling.DataLocationPPWithDate = None):
        if data is not None:
            self.location_plan_period = data.location_plan_period
        else:
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)

    def _update_time_of_day_from_event(self, event_id: UUID) -> int | None:
        """Aktualisiert time_of_day des Buttons und gibt cast_group.nr_actors zurück.

        Lädt time_of_day + nr_actors in einem einzigen SQL-Statement (keine lazy loads).
        Rückgabewert: nr_actors für add_spin_box_num_employees/set_tooltip, oder None.
        """
        result = db_services.Event.get_time_of_day_and_nr_actors(event_id)
        if result:
            self.time_of_day, nr_actors = result
            self.setProperty('time_index', str(self.time_of_day.time_of_day_enum.time_index))
            return nr_actors
        return None

    def _update_time_of_day_from_position(self):
        """Aktualisiert die time_of_day des Buttons basierend auf dem Event an dieser Position.

        Wird bei 'flip' verwendet, da dort die event_id im Signal das Ausgangs-Event referenziert,
        nicht das Ziel-Event an dieser Position.
        """
        event = db_services.Event.get_from__location_pp_date_time_index(
            self.location_plan_period.id, self.date, self.time_of_day.time_of_day_enum.time_index)
        if event:
            self.time_of_day = event.time_of_day
            self.setProperty('time_index', str(self.time_of_day.time_of_day_enum.time_index))

    @Slot(object)
    def on_appointment_moved(self, data: signal_handling.DataAppointmentMoved):
        """Reagiert auf verschobene Appointments aus der Plan-Ansicht."""
        if data.location_plan_period_id != self.location_plan_period.id:
            return
        if self.date != data.old_date and self.date != data.new_date:
            return
        if (self.time_of_day.time_of_day_enum.time_index != data.old_time_index
                and self.time_of_day.time_of_day_enum.time_index != data.new_time_index):
            return
        if data.undo:
            if data.action_type == 'move':
                if data.new_date == self.date and data.new_time_index == self.time_of_day.time_of_day_enum.time_index:
                    self.setChecked(False)
                    self.context_menu.removeAction(self.action_num_employees)
                else:
                    self.setChecked(True)
                    nr_actors = self._update_time_of_day_from_event(data.event_id)
                    self.create_actions_times_of_day()
                    self.reset_menu_times_of_day(self.location_plan_period)
                    self.add_spin_box_num_employees(nr_actors)
                    self.set_tooltip(nr_actors)
                self.set_stylesheet()
            elif data.action_type == 'move_and_delete':
                if data.old_date == self.date and data.old_time_index == self.time_of_day.time_of_day_enum.time_index:
                    self.setChecked(True)
                    nr_actors = self._update_time_of_day_from_event(data.event_id)
                    self.create_actions_times_of_day()
                    self.reset_menu_times_of_day(self.location_plan_period)
                    self.add_spin_box_num_employees(nr_actors)
                    self.set_tooltip(nr_actors)
                else:
                    self.setChecked(False)
                    self.context_menu.removeAction(self.action_num_employees)
                self.set_stylesheet()
            elif data.action_type == 'flip':
                # Bei flip: Button bleibt checked, aber time_of_day kann sich geändert haben
                # Hier _update_time_of_day_from_position verwenden, da event_id das Ausgangs-Event ist
                if self.date == data.new_date and self.time_of_day.time_of_day_enum.time_index == data.new_time_index:
                    self._update_time_of_day_from_position()
                    self.create_actions_times_of_day()
                    self.reset_menu_times_of_day(self.location_plan_period)
                    self.set_tooltip()
        else:
            if data.action_type == 'move':
                if data.old_date == self.date and data.old_time_index == self.time_of_day.time_of_day_enum.time_index:
                    self.setChecked(False)
                    self.context_menu.removeAction(self.action_num_employees)
                else:
                    self.setChecked(True)
                    nr_actors = self._update_time_of_day_from_event(data.event_id)
                    self.create_actions_times_of_day()
                    self.reset_menu_times_of_day(self.location_plan_period)
                    self.add_spin_box_num_employees(nr_actors)
                    self.set_tooltip(nr_actors)
                self.set_stylesheet()
            elif data.action_type == 'move_and_delete':
                if data.old_date == self.date and data.old_time_index == self.time_of_day.time_of_day_enum.time_index:
                    self.setChecked(False)
                    self.context_menu.removeAction(self.action_num_employees)
                else:
                    nr_actors = self._update_time_of_day_from_event(data.event_id)
                    self.reset_menu_times_of_day(self.location_plan_period)
                    self.add_spin_box_num_employees(nr_actors)
                    self.set_tooltip(nr_actors)
            elif data.action_type == 'flip':
                # Bei flip: Button bleibt checked, aber time_of_day kann sich geändert haben
                # Hier _update_time_of_day_from_position verwenden, da event_id das Ausgangs-Event ist
                if self.date == data.new_date and self.time_of_day.time_of_day_enum.time_index == data.new_time_index:
                    self._update_time_of_day_from_position()
                    self.create_actions_times_of_day()
                    self.reset_menu_times_of_day(self.location_plan_period)
                    self.set_tooltip()

    @Slot()
    def button_clicked(self):
        self.slot__event_toggled(self)
        if self.isChecked():
            self.add_spin_box_num_employees()
        else:
            self.context_menu.removeAction(self.action_num_employees)


class ButtonFixedCast(QPushButton):
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow,
                 cast_groups_of_pp: list[schemas.CastGroupForButton]):
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
        self.cast_groups_at_day: list[schemas.CastGroupForButton] = [
            c for c in cast_groups_of_pp if c.event
            and c.event.location_plan_period_id == self.location_plan_period.id
            and c.event.date == self.date]
        self.setObjectName(f'fixed_cast_{date}')
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

        # Prefetched Daten bereits gesetzt – kein DB-Reload nötig
        self.set_stylesheet()
        self.set_tooltip()

    @Slot(signal_handling.DataLocationPlanPeriodDate)
    def reload_cast_groups_at_day(self, data: signal_handling.DataLocationPlanPeriodDate = None):
        if data:
            # Optimierter Pfad: Prüfe zuerst location_plan_period_id (schneller)
            if data.location_plan_period_id is not None:
                if data.location_plan_period_id != self.location_plan_period.id:
                    return
            # Fallback: Prüfe plan_period_id (für Plan-weite Updates)
            elif data.plan_period_id is not None:
                if data.plan_period_id != self.location_plan_period.plan_period.id:
                    return
            if data.date is not None and data.date != self.date:
                return
        self.cast_groups_at_day = db_services.CastGroup.get_all_for_button__location_plan_period_at_date(
            self.location_plan_period.id, self.date)

    def check_fixed_cast__eq_to__local_pp(self):
        if not self.cast_groups_at_day:
            return
        fixed_casts_at_day = [(c.fixed_cast, c.fixed_cast_only_if_available) for c in self.cast_groups_at_day]
        return (
            len(set(fixed_casts_at_day)) == 1
            and fixed_casts_at_day[0] == (self.location_plan_period.fixed_cast,
                                          self.location_plan_period.fixed_cast_only_if_available)
        )

    def set_stylesheet_and_tooltip(self):
        self.reload_cast_groups_at_day()
        self.set_stylesheet()
        self.set_tooltip()

    def set_stylesheet(self):
        check_all_equal = self.check_fixed_cast__eq_to__local_pp()
        _c = widget_styles.buttons.ConfigButtonsInCheckFields
        if check_all_equal is None:
            color, disabled_color = _c.standard_colors, _c.standard_colors_disabled
        elif check_all_equal:
            color, disabled_color = _c.all_properties_are_default, _c.all_properties_are_default_disabled
        else:
            color, disabled_color = _c.any_properties_are_different, _c.any_properties_are_different_disabled
        name = self.objectName()
        self.setStyleSheet(
            f"#{name} {{background-color: {color}; }}"
            f"#{name}:disabled {{background-color: {disabled_color}; }}"
        )

    def set_tooltip(self):
        if not self.cast_groups_at_day:
            additional_txt = ''
        elif len({(cg.fixed_cast, cg.fixed_cast_only_if_available) for cg in self.cast_groups_at_day}) > 1:
            additional_txt = self.tr('\nCast of events on this day:\nDifferent casts.')
        else:
            cast_clear_txt = helper_functions.generate_fixed_cast_clear_text(
                self.cast_groups_at_day[0].fixed_cast,
                self.cast_groups_at_day[0].fixed_cast_only_if_available,
                self.cast_groups_at_day[0].prefer_fixed_cast_events
            )
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

        # Für den Dialog volle CastGroupShow laden (benötigt parent_groups, cast_rule etc.)
        cast_groups_show = db_services.CastGroup.get_all_from__location_plan_period_at_date(
            self.location_plan_period.id, self.date)
        cast_group = next((cg for cg in cast_groups_show if cg.fixed_cast), cast_groups_show[0])
        dlg = DlgFixedCastBuilderCastGroup(self.parent, cast_group, self.location_plan_period).build()
        if dlg.exec():
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end
            ):
                return  # Dialog wurde bereits geschlossen, Änderungen sind in DB

            for cg in cast_groups_show:
                cast_group_commands.UpdateFixedCast(cg.id, dlg.fixed_cast_simplified,
                                                   dlg.object_with_fixed_cast.fixed_cast_only_if_available).execute()
            self.set_stylesheet_and_tooltip()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

    @Slot(signal_handling.DataLocationPPWithDate)
    def reload_location_plan_period(self, data: signal_handling.DataLocationPPWithDate):
        if (data.date and data.date == self.date) or not data.date:
            self.location_plan_period = data.location_plan_period

    @Slot(signal_handling.DataLocationPlanPeriodDate)
    def reset_styling(self, data: signal_handling.DataLocationPlanPeriodDate):
        # Optimierter Pfad: Prüfe zuerst location_plan_period_id (schneller)
        if data.location_plan_period_id is not None:
            if data.location_plan_period_id != self.location_plan_period.id:
                return
        # Fallback: Prüfe plan_period_id (für Plan-weite Updates)
        elif data.plan_period_id is not None:
            if data.plan_period_id != self.location_plan_period.plan_period.id:
                return
        if (data.date and data.date == self.date) or not data.date:
            self.set_stylesheet_and_tooltip()


class ButtonNotes(QPushButton):  # todo: Fertigstellen... + Tooltip Notes der Events am Tag
    def __init__(self, parent: QWidget, date: datetime.date, width_height: int,
                 location_plan_period: schemas.LocationPlanPeriodShow,
                 controller: command_base_classes.ContrExecUndoRedo,
                 events_at_day: list | None = None):
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
        self._prefetched_events = events_at_day
        self.set_stylesheet_and_tooltip()

    def set_stylesheet_and_tooltip(self):
        self._set_events_at_day()
        self._set_stylesheet()
        self._set_tooltip()

    @Slot(signal_handling.DataLocationPlanPeriodDate)
    def reset_stylesheet_and_tooltip(self, data: signal_handling.DataLocationPlanPeriodDate):
        # Optimierter Pfad: Prüfe zuerst location_plan_period_id (schneller)
        if data.location_plan_period_id is not None:
            if data.location_plan_period_id != self.location_plan_period.id:
                return
        # Fallback: Prüfe plan_period_id (für Plan-weite Updates)
        elif data.plan_period_id is not None:
            if data.plan_period_id != self.location_plan_period.plan_period.id:
                return
        if (data.date and data.date == self.date) or not data.date:
            if data.prefetched_events is not None:
                self._prefetched_events = data.prefetched_events
            self.set_stylesheet_and_tooltip()

    def _set_events_at_day(self):
        if self._prefetched_events is not None:
            self.events_at_day = self._prefetched_events
            self._prefetched_events = None  # Consume-once: danach immer aus DB laden
        else:
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
        # Vollständiges EventShow für den Dialog laden (einmaliger DB-Call beim Öffnen)
        event_show = db_services.Event.get(event.id)
        dlg = DlgEventNotes(self, event_show, True)
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
                 location_plan_period: schemas.LocationPlanPeriodShow,
                 controller: command_base_classes.ContrExecUndoRedo,
                 events_at_day: list | None = None,
                 location_skill_groups: list | None = None):
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
        self.controller = controller
        self._prefetched_events = events_at_day
        self._prefetched_location_skill_groups = location_skill_groups
        self.set_stylesheet_and_tooltip()

    def set_stylesheet_and_tooltip(self):
        self._set_events_at_day()
        self._set_stylesheet()
        self._set_tooltip()

    @Slot(signal_handling.DataLocationPlanPeriodDate)
    def reset_stylesheet_and_tooltip(self, data: signal_handling.DataLocationPlanPeriodDate):
        # Optimierter Pfad: Prüfe zuerst location_plan_period_id (schneller)
        if data.location_plan_period_id is not None:
            if data.location_plan_period_id != self.location_plan_period.id:
                return
        # Fallback: Prüfe plan_period_id (für Plan-weite Updates)
        elif data.plan_period_id is not None:
            if data.plan_period_id != self.location_plan_period.plan_period.id:
                return
        if (data.date and data.date == self.date) or not data.date:
            if data.prefetched_events is not None:
                self._prefetched_events = data.prefetched_events
            self.set_stylesheet_and_tooltip()

    def _set_events_at_day(self):
        if self._prefetched_events is not None:
            self.events_at_day = self._prefetched_events
            self._prefetched_events = None  # Consume-once: danach immer aus DB laden
        else:
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
        if self._prefetched_location_skill_groups is not None:
            location_skill_groups = self._prefetched_location_skill_groups
        else:
            location_skill_groups = db_services.SkillGroup.get_all_from__location_of_work(
                self.location_plan_period.location_of_work.id)
            self._prefetched_location_skill_groups = location_skill_groups
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

        dialog_event = next((e for e in self.events_at_day if e.skill_groups), self.events_at_day[0])
        # Vollständiges EventShow für den Dialog laden (einmaliger DB-Call beim Öffnen des Dialogs)
        dialog_event_show = db_services.Event.get(dialog_event.id)
        dlg = DlgSkillGroups(self, dialog_event_show)
        if dlg.exec():
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                return

            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            for event in self.events_at_day:
                if event.id == dialog_event.id:
                    continue  # bereits durch den Dialog bearbeitet, Befehle schon im Undo-Stack
                for skill_group in event.skill_groups:
                    command_remove = event_commands.RemoveSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command_remove)
                for skill_group in dlg.object_with_skill_groups.skill_groups:
                    command_add = event_commands.AddSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command_add)
                signal_handling.handler_plan_tabs.event_changed(event.id)
            self.set_stylesheet_and_tooltip()
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)
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

        # Help-System Integration
        setup_form_help(self, "location_plan_period", add_help_button=True)

        signal_handling.handler_show_dialog.signal_show_dlg_cast_group_pp.connect(self._edit_cast_groups_plan_period)

        self.controller = command_base_classes.ContrExecUndoRedo()

        # Alle Anzeigedaten in einer einzigen DB-Session laden
        mask_data = db_services.LocationPlanPeriod.get_location_mask_data(plan_period.id)

        self.plan_period_id: UUID = mask_data.plan_period_id
        self.plan_period_start = mask_data.plan_period_start
        self.plan_period_end = mask_data.plan_period_end
        self.team_location_assigns = mask_data.team_location_assigns
        self.cast_groups_of_pp: list[schemas.CastGroupForButton] = mask_data.cast_groups_of_pp
        self.lpp_id__events_for_buttons: dict[UUID, list[schemas.EventForButton]] = mask_data.lpp_id__events_for_buttons
        self.location_id__skill_groups: dict[UUID, list[schemas.SkillGroup]] = mask_data.location_id__skill_groups
        self.location_plan_periods = mask_data.location_plan_periods

        active_location_ids = {
            tla.location_of_work_id for tla in self.team_location_assigns
            if tla.start <= self.plan_period_end and (tla.end is None or tla.end >= self.plan_period_start)
        }
        self.location_id__location_pp = {
            str(lpp.location_of_work.id): lpp for lpp in self.location_plan_periods
            if lpp.location_of_work.id in active_location_ids
        }
        self.loc_id__location_pp_show: dict[str, schemas.LocationPlanPeriodForMask] = mask_data.loc_id__location_pp_for_mask
        self.location_id: UUID | None = None
        self.location: schemas.LocationOfWorkShow | None = None
        self.frame_events: FrmLocationPlanPeriod | None = None
        self.lb_notes_pp = QLabel(self.tr('Planning Period Notes for Location:'))
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = NotesTextEdit()
        self.te_notes_pp.editing_finished.connect(self.save_info_location_pp)
        self.te_notes_pp.setFixedHeight(180)
        self.te_notes_pp.setDisabled(True)

        self.lb_notes_location = QLabel(self.tr('Location Notes:'))
        self.lb_notes_location.setFixedHeight(20)
        font_lb_notes = self.lb_notes_location.font()
        font_lb_notes.setBold(True)
        self.lb_notes_location.setFont(font_lb_notes)
        self.te_notes_location = NotesTextEdit()
        self.te_notes_location.editing_finished.connect(self.save_info_location)
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

        self.side_menu = side_menu.SlideInMenu(self,
                                               250,
                                               10,
                                               'right',
                                               (20, 30, 0, 20),
                                               (130, 205, 203, 100),
                                               True)

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
        location_plan_period = self.location_id__location_pp[str(self.location_id)]
        location_plan_period_show = (
            self.loc_id__location_pp_show.get(str(self.location_id))
            or db_services.LocationPlanPeriod.get(location_plan_period.id))
        # location_of_work aus bereits geladenem LPP-Show (kein separater DB-Call)
        self.location = location_plan_period_show.location_of_work
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
        self.te_notes_pp.clear()
        self.te_notes_pp.setText(self.location_id__location_pp[str(self.location_id)].notes)

        self.te_notes_location.clear()
        self.te_notes_location.setText(self.location.notes)

    def save_info_location_pp(self):
        lpp = self.location_id__location_pp[str(self.location_id)]
        new_notes = self.te_notes_pp.toPlainText()
        if new_notes == (lpp.notes or ''):
            return
        cmd = location_plan_period_commands.UpdateNotes(lpp.id, new_notes, notes_old=lpp.notes or '')
        self.controller.execute(cmd)
        if cmd.updated_location_plan_period is not None:
            self.location_id__location_pp[str(self.location_id)] = cmd.updated_location_plan_period

    def save_info_location(self):
        new_notes = self.te_notes_location.toPlainText()
        if new_notes == (self.location.notes or ''):
            return
        self.controller.execute(
            location_of_work_commands.UpdateNotes(
                self.location_id, new_notes, notes_old=self.location.notes or ''))
        self.location.notes = new_notes

    def edit_cast_groups_plan_period(self):
        visible_plan_period_ids = {location_pp.id for location_pp in self.location_plan_periods}
        dlg = frm_cast_group.DlgCastGroups(
            self, db_services.PlanPeriod.get(self.plan_period_id), visible_plan_period_ids)
        if dlg.exec():
            signal_handling.handler_location_plan_period.reload_cast_groups__cast_configs(
                signal_handling.DataLocationPlanPeriodDate(plan_period_id=self.plan_period_id)
            )
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataLocationPlanPeriodDate(plan_period_id=self.plan_period_id)
            )
            signal_handling.handler_location_plan_period.event_update_num_employees(
                plan_period_id=self.plan_period_id, location_plan_period_id=None
            )

    @Slot(UUID)
    def _edit_cast_groups_plan_period(self, plan_period_id: UUID):
        if plan_period_id == self.plan_period_id:
            self.edit_cast_groups_plan_period()


class FrmLocationPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabLocationPlanPeriods,
                 location_plan_period: schemas.LocationPlanPeriodShow | schemas.LocationPlanPeriodForMask,
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

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.data_processor = data_processing.LocationPlanPeriodData(self, location_plan_period, self.controller)
        self.location_plan_period = location_plan_period
        self.t_o_d_standards: list[schemas.TimeOfDay] = []
        self.t_o_d_enums: list[schemas.TimeOfDayEnum] = []
        self.days: list[datetime.date] = []
        self.set_instance_variables()
        self.setup_side_menu()

        self.weekdays = {0: self.tr('Mon'), 1: self.tr('Tue'), 2: self.tr('Wed'), 3: self.tr('Thu'),
                         4: self.tr('Fri'), 5: self.tr('Sat'), 6: self.tr('Sun')}
        self.months = {1: self.tr('January'), 2: self.tr('February'), 3: self.tr('March'), 4: self.tr('April'),
                       5: self.tr('May'), 6: self.tr('June'), 7: self.tr('July'), 8: self.tr('August'),
                       9: self.tr('September'), 10: self.tr('October'), 11: self.tr('November'),
                       12: self.tr('December')}

        self.set_headers_months()
        self.setStyleSheet(widget_styles.buttons.avail_day__event_parent_css)
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
        bt_reset_all_event_t_o_ds.setToolTip(
            self.tr("Adopts the time of day standards of the facility's planning period\n"
                    "for all of the facility's events between {start} - {end}.").format(
                start=date_to_string(self.location_plan_period.plan_period.start),
                end=date_to_string(self.location_plan_period.plan_period.end)
            )
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
        self.setUpdatesEnabled(False)
        try:
            self._set_chk_field()
        finally:
            self.setUpdatesEnabled(True)

    def _set_chk_field(self):
        # Aus Startup-Caches lesen (kein DB-Call) – Fallback auf DB wenn Cache invalidiert
        cast_groups_of_pp = self.parent.cast_groups_of_pp
        all_events = self.parent.lpp_id__events_for_buttons.get(self.location_plan_period.id)
        if all_events is None:
            all_events = db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id)
        events_by_date: dict = {}
        for e in all_events:
            events_by_date.setdefault(e.date, []).append(e)
        location_skill_groups = self.parent.location_id__skill_groups.get(
            self.location_plan_period.location_of_work.id)
        if location_skill_groups is None:
            location_skill_groups = db_services.SkillGroup.get_all_from__location_of_work(
                self.location_plan_period.location_of_work.id)
        # TeamLocationAssigns für diesen Standort aus Team-Cache (kein DB-Call)
        location_id = self.location_plan_period.location_of_work.id
        location_assigns = [
            tla for tla in self.parent.team_location_assigns
            if tla.location_of_work_id == location_id
        ]

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
            disable_buttons = not any(
                tla.start <= d and (tla.end is None or tla.end > d)
                for tla in location_assigns
            )
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
            bt_notes = ButtonNotes(self, d, 24, self.location_plan_period, self.controller,
                                   events_at_day=events_by_date.get(d, []))
            bt_notes.setDisabled(disable_buttons)
            self.layout.addWidget(bt_notes, row + 3, col)
            bt_skills = ButtonSkillGroups(self, d, 24, self.location_plan_period, self.controller,
                                          events_at_day=events_by_date.get(d, []),
                                          location_skill_groups=location_skill_groups)
            bt_skills.setDisabled(disable_buttons)
            self.layout.addWidget(bt_skills, row + 4, col)

    def reset_chk_field(self):
        loc_id = self.location_plan_period.location_of_work.id
        # Caches invalidieren: nächstes data_setup lädt frische Daten vom DB
        self.parent.lpp_id__events_for_buttons.pop(self.location_plan_period.id, None)
        self.parent.loc_id__location_pp_show.pop(str(loc_id), None)
        self.parent.data_setup(location_id=loc_id)

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
        # WARNUNG AM ANFANG - VOR DB-Operation
        plan_period = self.location_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end,
            on_cancel=bt.toggle  # Button-Status zurücksetzen
        ):
            return

        date = bt.date
        t_o_d = bt.time_of_day
        mode: Literal['added', 'deleted'] = 'added' if bt.isChecked() else 'deleted'

        success = self.data_processor.save_event(date, t_o_d, mode)

        if not success and mode == 'deleted':
            # Löschung wurde abgebrochen - Button-Status zurücksetzen
            bt.setChecked(True)
            return

        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

    def change_mode__event_group(self):
        dlg = frm_group_mode.DlgGroupModeBuilderLocationPlanPeriod(self, self.location_plan_period).build()
        if dlg.exec():
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                signal_handling.handler_location_plan_period.change_location_plan_period_group_mode(
                    signal_handling.DataGroupMode(False))
                return

            QMessageBox.information(self, self.tr('Group Mode'), self.tr('All changes have been applied.'))
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)
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

    def _update_fixed_cast_buttons(self, cast_groups: list) -> None:
        """Verteilt vorab geladene CastGroupForButton-Daten an alle ButtonFixedCast-Kinder.

        Ersetzt reload_cast_groups__cast_configs + reset_styling_fixed_cast_configs (je 30 DB-Calls)
        durch eine einzige In-Memory-Verteilung ohne weitere DB-Zugriffe.
        """
        date__cast_groups: dict = {}
        for cg in cast_groups:
            if cg.event:
                date__cast_groups.setdefault(cg.event.date, []).append(cg)
        for btn in self.findChildren(ButtonFixedCast):
            btn.cast_groups_at_day = date__cast_groups.get(btn.date, [])
            btn.set_stylesheet()
            btn.set_tooltip()

    def change_mode__cast_group(self, *args):
        plan_period = db_services.PlanPeriod.get(self.location_plan_period.plan_period.id)
        dlg = frm_cast_group.DlgCastGroups(self, plan_period, {self.location_plan_period.id})
        if dlg.exec():
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end
            ):
                return  # Dialog wurde bereits geschlossen, Änderungen sind in DB

            QMessageBox.information(self, self.tr('Group Mode'), self.tr('All changes have been applied.'))
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__events(
                signal_handling.DataLocationPPWithDate(self.location_plan_period))
            cast_groups = db_services.CastGroup.get_all_for_button__location_plan_period(
                self.location_plan_period.id)
            self._update_fixed_cast_buttons(cast_groups)
            signal_handling.handler_location_plan_period.event_update_num_employees(
                plan_period_id=None, location_plan_period_id=self.location_plan_period.id
            )
        else:
            QMessageBox.information(self, self.tr('Group Mode'), self.tr('No changes were made.'))

    def get_events(self):
        cached = self.parent.lpp_id__events_for_buttons.get(self.location_plan_period.id)
        if cached is not None:
            raw_events = cached
            # nr_actors aus Cast-Group-Cache — vermeidet DB-Call pro Event
            event_id__nr_actors: dict = {
                cg.event.id: cg.nr_actors
                for cg in self.parent.cast_groups_of_pp
                if cg.event is not None
            }
        else:
            raw_events = db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id)
            event_id__nr_actors = {}
        events = (e for e in raw_events if not e.prep_delete)
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
            nr_actors = event_id__nr_actors.get(event.id)
            button.setChecked(True)
            button.time_of_day = event.time_of_day
            button.create_actions_times_of_day()
            button.reset_menu_times_of_day(self.location_plan_period)
            button.add_spin_box_num_employees(nr_actors)
            button.set_tooltip(nr_actors)

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
            plan_period = self.location_plan_period.plan_period
            if not warn_and_clear_undo_redo_if_plans_open(
                self, plan_period.id, plan_period.start, plan_period.end,
                on_cancel=dlg.controller.undo_all
            ):
                return

            self.data_processor.make_events_from_planning_rules(dlg)
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)
            return
        else:
            dlg.controller.undo_all()

    def edit_time_of_days(self):
        lpp = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderLocationPlanPeriod(self, lpp).build()
        if dlg.exec():
            self.reload_location_plan_period()
            buttons_event: list[ButtonEvent] = self.findChildren(ButtonEvent)
            for bt in buttons_event:
                bt.reset_menu_times_of_day(self.location_plan_period)
            self.reset_chk_field()

    def reset_all_event_t_o_ds(self):
        """übernimmt für alle Events der LocationPlanPeriod die TimeOfDays-Standards der LocationPlanPeriod."""
        # Warnung für Undo/Redo VOR den Änderungen
        plan_period = self.location_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

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
        self.controller.execute(
            time_of_day_commands.DeleteUnusedInProject(self.location_plan_period.project.id))
        self.controller.execute(
            time_of_day_commands.DeletePrepDeletesInProject(self.location_plan_period.project.id))

        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        self.reset_chk_field()
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

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

        # NEU: Warnung für Undo/Redo VOR den Änderungen
        plan_period = self.location_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        for event in db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id):
            if not event.prep_delete:
                for skill_group in event.skill_groups:
                    command = event_commands.RemoveSkillGroup(event.id, skill_group.id)
                    self.controller.execute(command)

            signal_handling.handler_location_plan_period.reset_styling_skills_configs(
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id, date=event.date)
            )
        QMessageBox.information(
            self,
            self.tr('Remove Skills'),
            self.tr('All skills have been successfully removed from all events.')
        )
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

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

        # NEU: Warnung für Undo/Redo VOR den Änderungen
        plan_period = self.location_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
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
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id, date=event.date)
            )
        QMessageBox.information(
            self,
            self.tr('Reset Skills'),
            self.tr('All skills have been successfully reset for all events.')
        )
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)

    def edit_fixed_cast(self):
        lpp = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        dlg = DlgFixedCastBuilderLocationPlanPeriod(self, lpp).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.reload_location_plan_period()
            signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
                signal_handling.DataLocationPPWithDate(self.location_plan_period)
            )
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id)
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

        # NEU: Warnung für Undo/Redo VOR den Änderungen
        plan_period = self.location_plan_period.plan_period
        if not warn_and_clear_undo_redo_if_plans_open(
            self, plan_period.id, plan_period.start, plan_period.end
        ):
            return

        cast_groups_of_plan_period = db_services.CastGroup.get_all_from__plan_period(
            self.location_plan_period.plan_period.id)
        event_cast_groups = (
            c for c in cast_groups_of_plan_period
            if c.event
               and c.event.location_plan_period.id == self.location_plan_period.id
               and (c.fixed_cast != self.location_plan_period.fixed_cast
                    or c.fixed_cast_only_if_available != self.location_plan_period.fixed_cast_only_if_available)
        )
        for c in event_cast_groups:
            command = cast_group_commands.UpdateFixedCast(c.id,  self.location_plan_period.fixed_cast,
                                                          self.location_plan_period.fixed_cast_only_if_available)
            self.controller.execute(command)
            signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
                signal_handling.DataLocationPlanPeriodDate(self.location_plan_period.id, date=c.event.date)
            )

        QMessageBox.information(
            self,
            self.tr('Reset Cast'),
            self.tr('The cast of all events has been successfully reset.')
        )
        signal_handling.handler_plan_tabs.invalidate_entities_cache(self.location_plan_period.plan_period.id)




if __name__ == '__main__':
    app = QApplication()
    plan_periods = db_services.PlanPeriod.get_all_from__project(UUID('72F1D1E9BF554F11AE44916411A9819E'))
    window = FrmTabLocationPlanPeriods(None, plan_periods[0])
    window.show()
    app.exec()

# todo: Reset-Buttons in event-frame sollten Signale senden
