import datetime
from typing import Literal
from uuid import UUID

from PySide6.QtWidgets import QWidget, QMessageBox

from commands import command_base_classes
from commands.database_commands import event_commands, cast_group_commands, appointment_commands, plan_commands
from database import schemas, db_services
from gui.observer import signal_handling


class LocationPlanPeriodData:
    def __init__(self, parent: QWidget, location_plan_period: schemas.LocationPlanPeriodShow):
        self.parent = parent
        self.location_plan_period = location_plan_period
        self.controller = command_base_classes.ContrExecUndoRedo()

    def reload_location_plan_period(self):
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period.id)
        (signal_handling.handler_location_plan_period
         .reload_location_pp_on__frm_location_plan_period(self.location_plan_period))

    def save_event(self, date: datetime.date, time_of_day: schemas.TimeOfDay, mode: Literal['added', 'deleted']):
        if mode == 'added':
            event = self._save_new_event(date, time_of_day)
        elif mode == 'deleted':
            event = self._delete_event(date, time_of_day)
        else:
            raise NameError('Keyword mode: only literals "added" or "deleted" are allowed.')
        self.reload_location_plan_period()
        self._emit_reload_signals(date)
        self._send_event_changes_to_plans(event, mode)

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

                signal_handling.handler_show_dialog.show_dlg_event_group()
        if containing_cast_groups:
            for parent_cast_group in containing_cast_groups:
                if len(db_services.CastGroup.get(parent_cast_group.id).child_groups) < 2:
                    QMessageBox.critical(self.parent, 'Besetzungsgruppen',
                                         'Durch das Löschen des Termins hat eine Gruppe nur noch einen einzigen '
                                         'Termin oder eine einzelne Untergruppe.'
                                         'Bitte korrigieren Sie dies im folgenden Dialog.')

                    signal_handling.handler_show_dialog.show_dlg_cast_group_pp()

    def _emit_reload_signals(self, date):
        signal_handling.handler_location_plan_period.reload_location_pp__events(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )
        signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )

    def _send_event_changes_to_plans(self, event: schemas.EventShow, mode: Literal['added', 'deleted']):
        plans = db_services.Plan.get_all_from__plan_period(self.location_plan_period.plan_period.id)
        for plan in plans:
            if mode == 'added':
                self._create_new_empty_appointment_in_plan(plan.id, event)
            if plan.location_columns:
                self._reset_plan_location_columns(plan)
            signal_handling.handler_plan_tabs.event_changed(
                signal_handling.DataPlanEvent(
                    plan.id, event.id, mode == 'added'
                )
            )

    def _create_new_empty_appointment_in_plan(self, plan_id: UUID, event: schemas.Event):
        self.controller.execute(
            appointment_commands.Create(schemas.AppointmentCreate(avail_days=[], event=event), plan_id))

    def _reset_plan_location_columns(self, plan: schemas.PlanShow):
        self.controller.execute(plan_commands.UpdateLocationColumns(plan.id, {}))
        QMessageBox.information(self.parent, 'Plan Layout',
                                f'Die Reihenfolge der Spalten im Plan {plan.name} wurde zurückgesetzt.')
