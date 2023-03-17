from datetime import timedelta

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout

from database import schemas
from gui.tabbars import TabBar


class FrmTabActorPlanPeriod(QWidget):
    def __init__(self, parent_tabs: TabBar, plan_period: schemas.PlanPeriodShow):
        super().__init__()

        self.plan_period = plan_period
        self.actor_plan_periods = [a_pp for a_pp in plan_period.actor_plan_periods]
        self.persons = {str(p.id): p for p in plan_period.team.persons if not p.prep_delete}
        self.frame_availables: FrmActorPlanPeriod | None = None

        parent_tabs.addTab(self, f'Actor {plan_period.start}-{plan_period.end}')
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel('Verfügbarkeiten'))
        self.layout.addWidget(QLabel(f'{plan_period.start} - {plan_period.end}'))
        self.layout_availables = QHBoxLayout()
        self.layout.addLayout(self.layout_availables)
        self.table_select_actor = QTableWidget()
        self.layout_availables.addWidget(self.table_select_actor)

    def setup_selector_table(self):
        self.table_select_actor.setSortingEnabled(True)
        self.table_select_actor.setAlternatingRowColors(True)
        self.table_select_actor.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_select_actor.cellClicked().connect(self.view_table)
        self.table_select_actor.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        headers = ['Vorname', 'Nachname', 'id']
        self.table_select_actor.setHorizontalHeaderLabels(headers)
        for row, person in enumerate(sorted(self.persons.values(), key=lambda x: x.f_name)):
            self.table_select_actor.setItem(row, 0, QTableWidgetItem(str(person.id)))
            self.table_select_actor.setItem(row, 1, QTableWidgetItem(person.f_name))
            self.table_select_actor.setItem(row, 2, QTableWidgetItem(person.l_name))
        self.table_select_actor.hideColumn(0)

    def view_table(self, r, c):
        person = self.persons[self.table_select_actor.item(r, 0)]
        if self.frame_availables:
            self.frame_availables.deleteLater()
        self.frame_availables = FrmActorPlanPeriod(person)
        self.layout_availables.addWidget(self.frame_availables)


class FrmActorPlanPeriod(QWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.days = [actor_plan_period.plan_period.start+timedelta(delta)
                     for delta in range((actor_plan_period.plan_period.end-actor_plan_period.plan_period.start).days + 1)]

        # for d in self.days:
        #     for tageszeit in person.time_of_days:






