from commands import command_base_classes
from commands.optimizer_commands import pop_out_pop_in_commands
from optimizer.cast_classes import PlanPeriodCast, AppointmentCast


def switch_avail_days__time_of_day_cast(plan_period_cast: PlanPeriodCast, nr_random_appointments: int,
                                        controller: command_base_classes.ContrExecUndoRedo):
    # Weil es sein kann, dass - wegen event_groups - Tageszeiten keine Appointments besitzen:
    random_appointments = []
    while not random_appointments:
        random_time_of_day_cast = plan_period_cast.pick_random_time_of_day_cast()
        random_appointments = random_time_of_day_cast.pick_random_appointments(nr_random_appointments)

    modified_appointments: list[AppointmentCast] = []

    for appointment in random_appointments:
        try:
            avail_day_to_pop = appointment.pick_random_avail_day()
            controller.execute(pop_out_pop_in_commands.TimeOfDayCastPopOutAvailDay(
                plan_period_cast, appointment, avail_day_to_pop))
            modified_appointments.append(appointment)
        except IndexError as e:
            pass
    for appointment in modified_appointments:
        avail_day_to_put_in = random_time_of_day_cast.pick_random_avail_day()
        controller.execute(pop_out_pop_in_commands.TimeOfDayCastPutInAvailDay(
            plan_period_cast, appointment, avail_day_to_put_in))


def switch_event_group_casts(event_group_cast, nr_to_switch: int, controller):
    controller.undo_stack.clear()
    if not event_group_cast.event_group.event and event_group_cast.event_group.nr_event_groups:
        for _ in range(min(nr_to_switch, event_group_cast.event_group.nr_event_groups)):
            controller.execute(pop_out_pop_in_commands.SwitchEventGroupCast(event_group_cast))
