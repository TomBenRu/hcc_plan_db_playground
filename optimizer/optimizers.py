import pickle
import random
from typing import Generator
from uuid import UUID

from commands import command_base_classes
from commands.optimizer_commands import pop_out_pop_in_commands
from database import db_services, schemas
from optimizer.base_cast_classes import BaseAppointmentCast
from optimizer.cast_classes import PlanPeriodCast, event_group_cast_levels, EventGroupCast
from optimizer.fitness_avaluation import potential_assignments_of_persons, fitness_of_plan_period_cast__time_of_day_cast


class TimeOfDayCastOptimizer:
    def __init__(self, plan_period: schemas.PlanPeriodShow, nr_random_appointments: int):
        self.plan_period_cast: PlanPeriodCast | None = None
        self.plan_period = plan_period
        self.nr_random_appointments = nr_random_appointments

    def optimize(self, plan_period_cast: PlanPeriodCast) -> tuple[float, dict[str, float]]:
        self.plan_period_cast = plan_period_cast

        potential_assignments_of_actors = potential_assignments_of_persons(plan_period_cast)
        all_persons_from__plan_period: list[UUID] = [  # wird für fixed_cast_score benötigt
            p.id for p in db_services.Person.get_all_from__plan_period(plan_period_cast.plan_period_id)
        ]

        best_fitness, best_errors = float('inf'), {}
        nr_iterations = 0
        curr_fitness, curr_errors = fitness_of_plan_period_cast__time_of_day_cast(
            plan_period_cast, self.plan_period, potential_assignments_of_actors,
            all_persons_from__plan_period
        )
        while True:
            controller = command_base_classes.ContrExecUndoRedo()

            self.switch_avail_days__time_of_day_cast(controller)

            nr_iterations += 1

            fitness_new, new_errors = fitness_of_plan_period_cast__time_of_day_cast(
                plan_period_cast, self.plan_period, potential_assignments_of_actors,
                all_persons_from__plan_period
            )
            if fitness_new > curr_fitness:
                controller.undo_all()
            else:
                curr_fitness, curr_errors = fitness_new, new_errors

            # if not nr_iterations % 100:
            #     print(f'{nr_iterations=}, {curr_fitness=}')
            #     print(f'{curr_errors=}')

            if not nr_iterations % 600:
                if curr_fitness >= best_fitness:
                    # print(plan_period_cast)
                    # print(f'{best_fitness=}')
                    # print(f'{best_errors=}')
                    # print(f'nr of switches: {nr_iterations=}')
                    break
                else:
                    best_fitness, best_errors = curr_fitness, curr_errors
                    # print(f'{nr_iterations=}, {best_fitness=}')
                    # print(f'{best_errors=}')

        return best_fitness, best_errors

    def switch_avail_days__time_of_day_cast(self, controller: command_base_classes.ContrExecUndoRedo):
        # Weil es sein kann, dass - wegen event_groups - Tageszeiten keine Appointments besitzen:
        random_appointments = []
        while not random_appointments:
            random_time_of_day_cast = self.plan_period_cast.pick_random_time_of_day_cast()
            random_appointments = random_time_of_day_cast.pick_random_appointments(self.nr_random_appointments)

        modified_appointments: list[BaseAppointmentCast] = []

        for appointment in random_appointments:
            try:
                avail_day_to_pop = appointment.pick_random_avail_day()
                controller.execute(pop_out_pop_in_commands.TimeOfDayCastPopOutAvailDay(
                    self.plan_period_cast, appointment, avail_day_to_pop))
                modified_appointments.append(appointment)
            except IndexError as e:
                pass
        for appointment in modified_appointments:
            avail_day_to_put_in = random_time_of_day_cast.pick_random_avail_day()
            controller.execute(pop_out_pop_in_commands.TimeOfDayCastPutInAvailDay(
                self.plan_period_cast, appointment, avail_day_to_put_in))

    def set_plan_period_cast(self, plan_period_cast: PlanPeriodCast):
        self.plan_period_cast = plan_period_cast


class EventGroupCastOptimizer:
    def __init__(self, plan_period_cast: PlanPeriodCast, initial_event_group_casts: list[EventGroupCast],
                 nr_event_group_casts_to_switch: int, nr_random_appointments: int, highest_level: int = None):
        self.event_group_casts = initial_event_group_casts
        self.plan_period = db_services.PlanPeriod.get(plan_period_cast.plan_period_id)
        self.plan_period_cast = plan_period_cast
        self.nr_event_group_casts_to_switch = nr_event_group_casts_to_switch
        self.nr_random_appointments = nr_random_appointments
        self.event_group_cast_levels = event_group_cast_levels
        self.highest_level = max(self.event_group_cast_levels) if highest_level is None else highest_level

        self.nr_iterations_for_best_check = {0: 16, 1: 8, 2: 4, 3: 4, 4: 2, 5: 2, 6: 1}

        self.time_of_day_cast_optimizer = TimeOfDayCastOptimizer(self.plan_period, nr_random_appointments)

        self.best_group_cast_state: bytes | None = None
        self.best_plan_period_cast_fitness = float('inf')
        self.best_plan_period_cast_state: bytes | None = None

        self.curr_group_for_switching: EventGroupCast | None = None
        self.plan_period_cast_before_switch = None
        self.group_cast_state_before_switch = None

    def optimize(self, level: int | None = None) -> tuple[float, PlanPeriodCast]:

        # def optimize_recursive(level: int) -> float:
        #     if level == 0:
        #         return self.optimize_level(level)
        #     for level in self.event_group_cast_level_to_optimize(level):
        #         print(f'{level=}')
        #         return optimize_recursive(level)

        for level in self.event_group_cast_level_to_optimize(self.highest_level if level is None else level):
            print(f'optimize({level=})')
            fitness = self.optimize_level(level)
            if fitness < self.best_plan_period_cast_fitness:  # fixme: ...
                print(f'optimize({level=})')
                print('better fitness')
                print(f'try: {fitness=}')
                print(f'try: {[[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]] for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values() if list(todc.appointments_active)]}')
                self.best_plan_period_cast_fitness = fitness
                self.best_group_cast_state = pickle.dumps(self.event_group_casts)
                self.best_plan_period_cast_state = pickle.dumps(self.plan_period_cast)
            elif fitness > self.best_plan_period_cast_fitness:
                print(f'optimize({level=})')
                print('worse')
                print(f'try: {fitness=}')
                print(
                    f'try: {[[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]] for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values() if list(todc.appointments_active)]}')

                self.event_group_casts = pickle.loads(self.best_group_cast_state)
                self.plan_period_cast = pickle.loads(self.best_plan_period_cast_state)
            else:
                print(f'optimize({level=})')
                print('equal')
                print(f'try: {fitness=}')
                print(
                    f'try: {[[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]] for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values() if list(todc.appointments_active)]}')
            if level > 0:
                input(f'stop: {level=}')

        print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')
        print(f'{self.best_plan_period_cast_fitness=}')
        print([[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]]
                for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values()
               if list(todc.appointments_active)])
        print('++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++')

        return self.best_plan_period_cast_fitness, self.plan_period_cast

    def optimize_level(self, level: int) -> float:
        best_fitness, best_errors = float('inf'), {}
        nr_iterations = 0

        curr_fitness, curr_errors = self.time_of_day_cast_optimizer.optimize(self.plan_period_cast)

        while True:
            nr_iterations += 1

            switch_success = self.switch_event_group_casts(level)
            if not switch_success:
                if nr_iterations > self.nr_iterations_for_best_check[level]:
                    break
                continue

            print(f'..................... switch: {level=} ......................................')

            if level > 0:
                new_event_group_cast_optimizer = EventGroupCastOptimizer(
                    self.plan_period_cast, self.event_group_casts,
                    self.nr_event_group_casts_to_switch, self.nr_random_appointments, level - 1)
                fitness_new, _ = new_event_group_cast_optimizer.optimize(level - 1)
                new_errors = {'from': 'sublevel'}
            else:
                fitness_new, new_errors = self.time_of_day_cast_optimizer.optimize(self.plan_period_cast)

            if fitness_new > curr_fitness:
                print(f'before undo'
                      f'{[[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]] for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values() if list(todc.appointments_active)]}')
                self.undo_switch_event_group_casts()
                print(f' after undo'
                      f'{[[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]] for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values() if list(todc.appointments_active)]}')
            else:
                print('no undo')
                curr_fitness = fitness_new
                curr_errors = new_errors

            if not nr_iterations % self.nr_iterations_for_best_check[level]:
                if curr_fitness >= best_fitness:
                    print(f'{nr_iterations}        switch event_group_cast nr_iterations_for_best_check:\n          worse/equal {best_fitness=}')
                    print(f'          {best_errors=}')
                    print('         ', [[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]]
                            for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values()
                           if list(todc.appointments_active)])
                    break
                else:
                    best_fitness, best_errors = curr_fitness, curr_errors
                    print(f'{nr_iterations}        switch event_group_cast nr_iterations_for_best_check:\n          better {best_fitness=}')
                    print(f'          {best_errors=}')
                    print('         ', [[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]]
                            for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values()
                           if list(todc.appointments_active)])

        print('.......................................................................................')
        print(f'{best_fitness=}, {best_errors=}')
        print([[[a.event.date, [avd.actor_plan_period.person.f_name if avd else None for avd in a.avail_days]]
                for a in todc.appointments_active] for todc in self.plan_period_cast.time_of_day_casts.values()
               if list(todc.appointments_active)])
        print('.......................................................................................')

        return best_fitness

    def event_group_cast_level_to_optimize(self, base_level: int) -> Generator[int, None, None]:

        def recursive_level(level):
            yield level
            for sub_level in range(level):
                yield from recursive_level(sub_level)

        for level in range(base_level + 1):
            yield from recursive_level(level)

    def switch_event_group_casts(self, level: int) -> bool:
        try:
            self.curr_group_for_switching: EventGroupCast = random.choice(
                [egc for egc in event_group_cast_levels[level] if egc.active])
        except IndexError:
            # Kann vorkommen, wenn einzelne Termine mit Cast-Groups zu einer Parent-Cast-Group gehören
            self.curr_group_for_switching = None
            return False
        self.group_cast_state_before_switch = pickle.dumps(self.event_group_casts)
        self.plan_period_cast_before_switch = pickle.dumps(self.plan_period_cast)
        self.curr_group_for_switching.switch_event_group_casts(self.nr_event_group_casts_to_switch)
        return True

    def undo_switch_event_group_casts(self):
        if self.curr_group_for_switching:
            # self.curr_group_for_switching.undo_switch_event_group_casts()
            self.event_group_casts = pickle.loads(self.group_cast_state_before_switch)
            self.plan_period_cast = pickle.loads(self.plan_period_cast_before_switch)

    def print_event_group_cast_levels(self):
        print('#####################################################################################')
        print([f'{level}: {[f"(childs: {len(egc.child_groups) + len(egc.active_groups)}, nr_event_groups: {egc.event_group.nr_event_groups})" for egc in egcs]}'
               for level, egcs in event_group_cast_levels.items()])
        print('#####################################################################################')

