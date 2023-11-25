class LocationPlanPeriodData:
    def __init__(self):
        ...

    def save_event(self, bt: ButtonEvent):

        date = bt.date
        t_o_d = bt.time_of_day
        if bt.isChecked():
            existing_events_on_day = [event for event in self.location_plan_period.events
                                      if event.date == date and not event.prep_delete]
            event_new = schemas.EventCreate(date=date, location_plan_period=self.location_plan_period,
                                            time_of_day=t_o_d, flags=[])
            save_command = event_commands.Create(event_new)
            self.controller.execute(save_command)
            created_event = save_command.created_event

            '''Falls es an diesem Tage schon einen oder mehrere Events gibt,
            werden die fixed_casts vom ersten gefundenen Event übernommen, weil, davon ausgegangen
            wird, dass schon evt. geänderte fixed_casts für alle Events an diesem Tag gelten.'''
            if existing_events_on_day:
                fixed_cast_first_event = db_services.Event.get(existing_events_on_day[0].id).cast_group.fixed_cast
                self.controller.execute(
                   cast_group_commands.UpdateFixedCast(created_event.cast_group.id, fixed_cast_first_event))

            self.reload_location_plan_period()
            self.send_event_changes_to_plans(created_event, True)

        else:
            event = db_services.Event.get_from__location_pp_date_tod(self.location_plan_period.id, date, t_o_d.id)
            del_command = event_commands.Delete(event.id)
            self.controller.execute(del_command)
            deleted_event = del_command.event_to_delete
            self.reload_location_plan_period()
            if not (event_group := deleted_event.event_group.event_group).location_plan_period:
                if len(childs := db_services.EventGroup.get_child_groups_from__parent_group(event_group.id)) < 2:
                    solo_event = childs[0].event
                    QMessageBox.critical(self, 'Verfügbarkeitsgruppen',
                                         f'Durch das Löschen des Termins hat eine Gruppe nur noch einen einzigen '
                                         f'Termin: {solo_event.date.strftime("%d.%m.%y")}\n'
                                         f'Bitte korrigieren Sie dies im folgenden Dialog.')
                    self.change_mode__event_group()
            if del_command.containing_cast_groups:
                for parent_cast_group in del_command.containing_cast_groups:
                    if len(db_services.CastGroup.get(parent_cast_group.id).child_groups) < 2:
                        QMessageBox.critical(self, 'Besetzungsgruppen',
                                             f'Durch das Löschen des Termins hat eine Gruppe nur noch einen einzigen '
                                             f'Termin oder eine einzelne Untergruppe.'
                                             f'Bitte korrigieren Sie dies im folgenden Dialog.')
                        self.parent.edit_cast_groups_plan_period()
            self.send_event_changes_to_plans(deleted_event, False)

        bt.reload_location_plan_period()

        signal_handling.handler_location_plan_period.reload_location_pp__events(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )
        signal_handling.handler_location_plan_period.reload_location_pp__event_configs(
            signal_handling.DataLocationPPWithDate(self.location_plan_period, date)
        )
