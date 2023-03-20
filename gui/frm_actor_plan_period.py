from datetime import timedelta

from PySide6 import QtCore
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QSpacerItem

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

        self.layout_availables = QSplitter()
        self.layout.addWidget(self.layout_availables)
        self.table_select_actor = QTableWidget()
        self.layout_availables.addWidget(self.table_select_actor)
        self.setup_selector_table()
        # self.layout.addStretch()
        self.layout.setStretch(0, 2)
        self.layout.setStretch(1, 2)
        self.layout.setStretch(2, 96)

    def setup_selector_table(self):
        self.table_select_actor.setMaximumWidth(250)
        self.table_select_actor.setSortingEnabled(True)
        self.table_select_actor.setAlternatingRowColors(True)
        self.table_select_actor.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_select_actor.cellClicked.connect(self.view_table)
        self.table_select_actor.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_actor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        headers = ['id', 'Vorname', 'Nachname']
        self.table_select_actor.setColumnCount(len(headers))
        self.table_select_actor.setRowCount(len(self.pers_id__actor_pp)+5)
        self.table_select_actor.setHorizontalHeaderLabels(headers)
        for row, actor_pp in enumerate(sorted(self.pers_id__actor_pp.values(), key=lambda x: x.person.f_name)):
            self.table_select_actor.setItem(row, 0, QTableWidgetItem(str(actor_pp.person.id)))
            self.table_select_actor.setItem(row, 1, QTableWidgetItem(actor_pp.person.f_name))
            self.table_select_actor.setItem(row, 2, QTableWidgetItem(actor_pp.person.l_name))
        self.table_select_actor.hideColumn(0)

    def view_table(self, r, c):
        actor_plan_period: schemas.ActorPlanPeriodShow = self.pers_id__actor_pp[self.table_select_actor.item(r, 0).text()]
        if self.frame_availables:
            self.frame_availables.deleteLater()
        self.frame_availables = FrmActorPlanPeriod(actor_plan_period)
        self.layout_availables.addWidget(self.frame_availables)


class FrmActorPlanPeriod(QTableWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()
        self.horizontalHeader().setMaximumSectionSize(35)
        self.horizontalHeader().setMinimumSectionSize(35)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.days = [actor_plan_period.plan_period.start+timedelta(delta) for delta in
                     range((actor_plan_period.plan_period.end - actor_plan_period.plan_period.start).days + 1)]
        header_items = [d.strftime('%d.%m') for d in self.days]
        self.setColumnCount(len(header_items))
        self.setRowCount(10)
        self.setHorizontalHeaderLabels(header_items)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")
        self.weekdays = {0: 'Mo', 1: 'Di', 2: 'Mi', 3: 'Do', 4: 'Fr', 5: 'Sa', 6: 'So'}

        for col, d in enumerate(self.days):
            t_o_d = db_services.get_person(actor_plan_period.person.id).time_of_days
            for row, tageszeit in enumerate(sorted(t_o_d, key=lambda t: t.start), start=0):
                chkbox_item = QTableWidgetItem()

                chkbox_item.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
                chkbox_item.setCheckState(QtCore.Qt.Unchecked)
                self.setItem(row, col, chkbox_item)
            self.item_weekday = QTableWidgetItem(self.weekdays[d.weekday()])
            if d.weekday() in (5, 6):
                self.item_weekday.setBackground(QColor('#ffdc99'))
            self.setItem(row+1, col, self.item_weekday)

                # button = QPushButton(tageszeit.name[0])
                # button.setCheckable(True)
                # self.setCellWidget(row, col, button)
                # if tageszeit.name == 'Morgen':
                #     button.setStyleSheet('QPushButton {background-color: #a4cfff} '
                #                          'QPushButton::checked {background-color: blue}')
                # else:
                #     button.setStyleSheet('QPushButton {background-color: #fffcb6} '
                #                          'QPushButton::checked {background-color: orange}')







