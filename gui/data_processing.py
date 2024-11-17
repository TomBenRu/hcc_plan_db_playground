import datetime
from typing import Literal
from uuid import UUID

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QWidget, QMessageBox
from line_profiler_pycharm import profile

import gui.schemas
from commands import command_base_classes
from commands.database_commands import event_commands, cast_group_commands, appointment_commands, plan_commands, \
    event_group_commands
from database import schemas, db_services
from gui import concurrency, frm_event_planing_rules
from gui.concurrency import general_worker
from gui.custom_widgets.progress_bars import DlgProgressInfinite
from gui.observer import signal_handling


class LocationPlanPeriodData:
    def __init__(self, parent: QWidget, location_plan_period: schemas.LocationPlanPeriodShow,
                 controller: command_base_classes.ContrExecUndoRedo):
        self.parent = parent
        self.location_plan_period = location_plan_period
        self.controller = controller
        self.thread_pool = QThreadPool()
        self.worker_save_event = None
        self.progress_bar_save_event = DlgProgressInfinite(
            parent, 'Terminänderung',
            'Die Terminänderung wird in den vorhandenen Plänen gespeichert.',
            'Abbruch')

    def reload_location_plan_period(self):
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        (signal_handling.handler_location_plan_period
         .reload_location_pp_on__frm_location_plan_period(self.location_plan_period))

    def reset_check_field(self):
        signal_handling.handler_location_plan_period.reset_check_field(self.location_plan_period.id)

    def save_event(self, date: datetime.date, time_of_day: schemas.TimeOfDay, mode: Literal['added', 'deleted']):
        if mode == 'added':
            event = self._save_new_event(date, time_of_day)
        elif mode == 'deleted':
            event = self._delete_event(date, time_of_day)
        else:
            raise NameError('Keyword mode: only literals "added" or "deleted" are allowed.')
        self.reload_location_plan_period()
        self._emit_reload_signals(date)
        start, end = self.location_plan_period.plan_period.start, self.location_plan_period.plan_period.end
        existing_plans = db_services.Plan.get_all_from__plan_period_minimal(self.location_plan_period.plan_period.id)
        if mode == 'added' and existing_plans:
            reply = QMessageBox.question(self.parent, 'Appointments in Plänen',
                                         f'Möchten Sie einen neuen unbesetzten Termin in allen bestehenden Plänen des '
                                         f'Zeitraums {start:%d.%m.%y} - {start:%d.%m.%y} erzeugen?')
            if reply == QMessageBox.StandardButton.Yes:
                self._send_event_changes_to_plans(event, mode, existing_plans)
        else:
            self._send_event_changes_to_plans(event, mode, existing_plans)

    def _save_new_event(self, date, t_o_d):
        existing_events_on_day = [event for event in self.location_plan_period.events
                                  if event.date == date and not event.prep_delete]
        event_new = schemas.EventCreate(date=date, location_plan_period=self.location_plan_period,
                                        time_of_day=t_o_d, flags=[])
        save_command = event_commands.Create(event_new)
        self.controller.execute(save_command)
        created_event = save_command.created_event

        '''Falls es an diesem Tag schon einen oder mehrere Events gibt, werden die fixed_casts vom ersten gefundenen 
        Event übernommen, weil davon ausgegangen wird, dass schon evt. geänderte fixed_casts für alle Events an diesem 
        Tag gelten.'''
        if existing_events_on_day:
            fixed_cast_first_event = db_services.Event.get(existing_events_on_day[0].id).cast_group.fixed_cast
            self.controller.execute(
                cast_group_commands.UpdateFixedCast(created_event.cast_group.id, fixed_cast_first_event))
        return created_event

    def _delete_event(self, date, t_o_d):
        event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, date, t_o_d.id)
        del_command = event_commands.Delete(event.id)
        self.controller.execute(del_command)
        deleted_event = del_command.event_to_delete
        containing_cast_groups = del_command.containing_cast_groups
        self._handle_deleted_event(containing_cast_groups, event.event_group.event_group)
        return deleted_event

    def _handle_deleted_event(self, containing_cast_groups, event_group):
        self.reload_location_plan_period()
        if not event_group.location_plan_period:
            if len(childs := db_services.EventGroup.get_child_groups_from__parent_group(event_group.id)) < 2:
                solo_event = childs[0].event
                QMessageBox.critical(self.parent, 'Verfügbarkeitsgruppen',
                                     f'Durch das Löschen des Termins hat eine Gruppe nur noch einen einzigen '
                                     f'Termin: {solo_event.date.strftime("%d.%m.%y")}\n'
                                     f'Bitte korrigieren Sie dies im folgenden Dialog.')

                signal_handling.handler_show_dialog.show_dlg_event_group(self.location_plan_period.id)
        if containing_cast_groups:
            for parent_cast_group in containing_cast_groups:
                if len(db_services.CastGroup.get(parent_cast_group.id).child_groups) < 2:
                    QMessageBox.critical(self.parent, 'Besetzungsgruppen',
                                         'Durch das Löschen des Termins hat eine Gruppe nur noch einen einzigen '
                                         'Termin oder eine einzelne Untergruppe.'
                                         'Bitte korrigieren Sie dies im folgenden Dialog.')

                    signal_handling.handler_show_dialog.show_dlg_cast_group_pp(self.location_plan_period.plan_period.id)

    def _emit_reload_signals(self, date):
        signal_handling.handler_location_plan_period.reload_location_pp__events(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )
        signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )

        signal_handling.handler_location_plan_period.reset_styling_fixed_cast_configs(
            signal_handling.DataDate(self.location_plan_period.plan_period.id, date)
        )
        signal_handling.handler_location_plan_period.reset_styling_skills_configs(
            signal_handling.DataDate(self.location_plan_period.plan_period.id, date)
        )
        signal_handling.handler_location_plan_period.reset_styling_notes_configs(
            signal_handling.DataDate(self.location_plan_period.plan_period.id, date)
        )

    def _send_event_changes_to_plans(self, event: schemas.EventShow, mode: Literal['added', 'deleted'],
                                     existing_plans: dict[str, UUID]):
        if not existing_plans:
            return

        if mode == 'added':
            QMessageBox.information(self.parent, 'Pläne',
                                    'Durch das Einfügen des Termins in die bereits bestehenden Pläne muss die '
                                    'Spaltenreihenfolge der betreffenden Pläne zurückgesetzt werden.')
        else:
            QMessageBox.information(self.parent, 'Pläne',
                                    'Durch das Entfernen des Termins in bereits bestehenden Plänen muss die '
                                    'Spaltenreihenfolge der betreffenden Pläne zurückgesetzt werden.')

        self.worker_save_event = general_worker.WorkerGeneral(
            self._save_new_empty_appointment_in_plan_and_reset_columns,
            False, event, existing_plans, mode
        )
        self.worker_save_event.signals.finished.connect(
            lambda: signal_handling.handler_plan_tabs.reload_and_refresh_plan_tab(
                self.location_plan_period.plan_period.id
            )
        )
        self.worker_save_event.signals.finished.connect(self.progress_bar_save_event.close)
        self.progress_bar_save_event.show()
        self.thread_pool.start(self.worker_save_event)

    def _save_new_empty_appointment_in_plan_and_reset_columns(self, event: schemas.EventShow,
                                                              plans: dict[str, UUID],
                                                              mode: Literal['added', 'deleted']):
        for plan_id in plans.values():
            if mode == 'added':
                self._create_new_empty_appointment_in_plan(plan_id, event)
            self._reset_plan_location_columns(plan_id)

    def _create_new_empty_appointment_in_plan(self, plan_id: UUID, event: schemas.Event):
        self.controller.execute(
            appointment_commands.Create(schemas.AppointmentCreate(avail_days=[], event=event), plan_id))

    def _reset_plan_location_columns(self, plan_id: UUID):
        self.controller.execute(plan_commands.UpdateLocationColumns(plan_id, {}))

    def make_events_from_planning_rules(self, dlg: frm_event_planing_rules.DlgEventPlanningRules):
        master_event_group = db_services.EventGroup.get_master_from__location_plan_period(
            self.location_plan_period.id)
        if existing_events := db_services.Event.get_all_from__location_plan_period(self.location_plan_period.id):
            for event in existing_events:
                command = event_commands.Delete(event.id)
                self.controller.execute(command)

        events = self._create_events_from_rules(dlg.rules.rules_data,
                                                dlg.rules.same_partial_days_for_all_rules,
                                                master_event_group.id)

        if dlg.rules.same_partial_days_for_all_rules:
            event_groups_same_day = self._group_events_by_day(events, master_event_group, dlg.rules.rules_data)

        if (rule := dlg.rules.cast_rule_at_same_day) is not None and len(events) > 1:
            self._create_cast_groups_for_same_day_events(events, rule)

        self.reload_location_plan_period()
        self.reset_check_field()

    def _create_events_from_rules(self, rules: list[gui.schemas.RulesData],
                                  same_partial_days_for_all_rules: bool, master_event_group_id: UUID):
        """Erstellt Ereignisse basierend auf den gegebenen Regeln."""
        events = []
        for rule in rules:
            events.append({})
            for n in range(rule.repeat + 1):
                event = schemas.EventCreate(
                    location_plan_period=self.location_plan_period,
                    date=rule.first_day + datetime.timedelta(n * rule.interval),
                    time_of_day=rule.time_of_day, flags=[]
                )
                command = event_commands.Create(event)
                self.controller.execute(command)
                events[-1][command.created_event.date] = command.created_event

            if rule.num_events < rule.repeat + 1 and not same_partial_days_for_all_rules:
                new_event_group = self._create_event_group(master_event_group_id, rule.num_events)
                self._assign_events_to_group(events[-1], new_event_group)
        return events

    def _group_events_by_day(self, events, master_event_group, rules: list[gui.schemas.RulesData]):
        """Gruppiert Ereignisse nach Tagen und erstellt neue Eventgruppen."""
        event_groups_same_day = []
        for date in events[-1]:
            events_same_day = [e[date] for e in events]
            new_group = self._create_event_group(master_event_group.id)
            event_groups_same_day.append(new_group)
            for e in events_same_day:
                command = event_group_commands.SetNewParent(e.event_group.id, new_group.id)
                self.controller.execute(command)

        rule_0 = rules[0]
        if rule_0.num_events < rule_0.repeat + 1:
            new_event_group = self._create_event_group(master_event_group.id)
            for eg in event_groups_same_day:
                command = event_group_commands.SetNewParent(eg.id, new_event_group.id)
                self.controller.execute(command)
            self.controller.execute(
                event_group_commands.UpdateNrEventGroups(new_event_group.id, rule_0.num_events)
            )
        return event_groups_same_day

    def _create_cast_groups_for_same_day_events(self, events, rule: schemas.CastRuleShow):
        """Erstellt und verbindet Cast-Gruppen für Ereignisse am gleichen Tag."""
        for date, event in events[0].items():
            if same_day_events := [e[date] for e in events[1:] if date in e]:
                command = cast_group_commands.Create(self.location_plan_period.plan_period.id)
                self.controller.execute(command)
                new_cast_group = command.created_cast_group

                same_day_events.append(event)
                for e in same_day_events:
                    command = cast_group_commands.SetNewParent(e.cast_group.id, new_cast_group.id)
                    self.controller.execute(command)
                self.controller.execute(
                    cast_group_commands.UpdateCastRule(new_cast_group.id, rule.id)
                )
                self.controller.execute(
                    cast_group_commands.UpdateNrActors(new_cast_group.id, self.location_plan_period.nr_actors)
                )

    def _create_event_group(self, master_group_id, num_events=None):
        """Erstellt eine neue Ereignisgruppe und aktualisiert, falls erforderlich, die Anzahl der Events."""
        command = event_group_commands.Create(event_avail_day_group_id=master_group_id)
        self.controller.execute(command)
        new_event_group = command.created_group
        if num_events is not None:
            self.controller.execute(
                event_group_commands.UpdateNrEventGroups(new_event_group.id, num_events)
            )
        return new_event_group

    def _assign_events_to_group(self, events, event_group):
        """Weist Ereignisse einer Gruppe zu."""
        for event in events.values():
            command = event_group_commands.SetNewParent(event.event_group.id, event_group.id)
            self.controller.execute(command)

