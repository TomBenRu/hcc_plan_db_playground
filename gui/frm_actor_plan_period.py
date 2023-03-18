from datetime import timedelta

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout

from database import schemas, db_services
from gui.tabbars import TabBar


class FrmTabActorPlanPeriod(QWidget):
    def __init__(self, plan_period: schemas.PlanPeriodShow):
        super().__init__()

        self.plan_period = plan_period
        self.actor_plan_periods = [a_pp for a_pp in plan_period.actor_plan_periods]
        self.pers_id__actor_pp = {str(a_pp.person.id): a_pp for a_pp in plan_period.actor_plan_periods}
        self.frame_availables: FrmActorPlanPeriod | None = None

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout.addWidget(QLabel('Verfügbarkeiten'))
        self.layout.addWidget(QLabel(f'{plan_period.start} - {plan_period.end}'))
        self.layout_availables = QHBoxLayout()
        self.layout.addLayout(self.layout_availables)
        self.table_select_actor = QTableWidget()
        self.layout_availables.addWidget(self.table_select_actor)
        self.setup_selector_table()

    def setup_selector_table(self):
        self.table_select_actor.setSortingEnabled(True)
        self.table_select_actor.setAlternatingRowColors(True)
        self.table_select_actor.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_select_actor.cellClicked.connect(self.view_table)
        self.table_select_actor.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        headers = ['id', 'Vorname', 'Nachname']
        self.table_select_actor.setColumnCount(len(headers))
        self.table_select_actor.setRowCount(len(self.pers_id__actor_pp))
        self.table_select_actor.setHorizontalHeaderLabels(headers)
        for row, actor_pp in enumerate(sorted(self.pers_id__actor_pp.values(), key=lambda x: x.person.f_name)):
            self.table_select_actor.setItem(row, 0, QTableWidgetItem(str(actor_pp.person.id)))
            self.table_select_actor.setItem(row, 1, QTableWidgetItem(actor_pp.person.f_name))
            self.table_select_actor.setItem(row, 2, QTableWidgetItem(actor_pp.person.l_name))
        self.table_select_actor.hideColumn(0)

    def view_table(self, r, c):
        print(f'{self.table_select_actor.item(r, 0).text()=}')
        actor_plan_period = self.pers_id__actor_pp[self.table_select_actor.item(r, 0).text()]
        if self.frame_availables:
            self.frame_availables.deleteLater()
        self.frame_availables = FrmActorPlanPeriod(actor_plan_period)
        self.layout_availables.addWidget(self.frame_availables)


class FrmActorPlanPeriod(QWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriod):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)



        self.days = [actor_plan_period.plan_period.start+timedelta(delta) for delta in
                     range((actor_plan_period.plan_period.end-actor_plan_period.plan_period.start).days + 1)]

        # for d in self.days:
        #     for tageszeit in person.time_of_days:






