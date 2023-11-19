from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from database import schemas


class FrmTabPlan(QWidget):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)

        self.plan = plan
        self.schedule_text = '\n'.join([f'{a.event.date:%d.%m.%y} ({a.event.time_of_day.name}), '
                                        f'{a.event.location_plan_period.location_of_work.name}: '
                                        f'{[avd.actor_plan_period.person.f_name for avd in a.avail_days]}\n'
                                        for a in sorted(self.plan.appointments,
                                                        key=lambda x: (x.event.date,
                                                                       x.event.time_of_day.time_of_day_enum.time_index))])

        self.layout = QVBoxLayout(self)

        self.lb_schedule_versions = QLabel(self.schedule_text)
        self.layout.addWidget(self.lb_schedule_versions)
