from datetime import timedelta

from PySide6 import QtCore
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QSpacerItem, QGridLayout

from database import schemas, db_services


class FrmTabActorPlanPeriod(QWidget):
    def __init__(self, plan_period: schemas.PlanPeriodShow):
        super().__init__()

        self.plan_period = plan_period
        self.actor_plan_periods = [a_pp for a_pp in plan_period.actor_plan_periods]
        self.pers_id__actor_pp = {str(a_pp.person.id): a_pp for a_pp in plan_period.actor_plan_periods}
        self.frame_availables: FrmActorPlanPeriod | None = None

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.lb_title_name = QLabel('Verfügbarkeiten')
        self.lb_title_name.setContentsMargins(10, 10, 10, 10)

        self.lb_title_name_font = self.lb_title_name.font()
        self.lb_title_name_font.setPointSize(16)
        self.lb_title_name_font.setBold(True)
        self.lb_title_name.setFont(self.lb_title_name_font)
        self.layout.addWidget(self.lb_title_name)

        self.splitter_availables = QSplitter()
        self.layout.addWidget(self.splitter_availables)

        self.table_select_actor = QTableWidget()
        self.splitter_availables.addWidget(self.table_select_actor)
        self.widget_availables = QWidget()
        self.layout_availables = QVBoxLayout()
        self.layout_availables.setContentsMargins(0, 0, 0, 0)
        self.widget_availables.setLayout(self.layout_availables)
        self.splitter_availables.addWidget(self.widget_availables)
        self.setup_selector_table()
        self.splitter_availables.setSizes([175, 10000])
        self.layout.setStretch(0, 2)
        self.layout.setStretch(1, 96)

    def setup_selector_table(self):
        self.table_select_actor.setMaximumWidth(175)
        self.table_select_actor.setMinimumWidth(150)
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
        self.table_select_actor.setMaximumWidth(10000)
        actor_plan_period: schemas.ActorPlanPeriodShow = self.pers_id__actor_pp[self.table_select_actor.item(r, 0).text()]
        self.lb_title_name.setText(f'Verfügbarkeiten: {f"{actor_plan_period.person.f_name} {actor_plan_period.person.l_name}"}')
        if self.frame_availables:
            self.frame_availables.deleteLater()
        else:
            self.layout_availables.addStretch(10000)
        self.frame_availables = FrmActorPlanPeriod(actor_plan_period)
        self.layout_availables.insertWidget(0, self.frame_availables)




class _FrmActorPlanPeriod(QTableWidget):
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


class FrmActorPlanPeriod(QWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()

        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.actor_plan_period = actor_plan_period
        self.days = [actor_plan_period.plan_period.start+timedelta(delta) for delta in
                     range((actor_plan_period.plan_period.end - actor_plan_period.plan_period.start).days + 1)]
        self.weekdays = {0: 'Mo', 1: 'Di', 2: 'Mi', 3: 'Do', 4: 'Fr', 5: 'Sa', 6: 'So'}
        self.months = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
                       9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}
        month_year = [(d.month, d.year) for d in self.days]
        header_items_months = {m_y: month_year.count(m_y) for m_y in sorted({my for my in month_year},
                                                                            key=lambda x: f'{x[1]}{x[0]:02}')}
        col = 1
        for (month, year), count in header_items_months.items():
            label = QLabel(f'{self.months[month]} {year}')
            label.setStyleSheet('background: qlineargradient( x1:0 y1:0, x2:1 y2:0, stop:0 #a9ffaa, stop:1 #137100)')
            label_font = label.font()
            label_font.setPointSize(12)
            label_font.setBold(True)
            label.setFont(label_font)
            label.setContentsMargins(5, 5, 5, 5)
            self.layout.addWidget(label, 0, col, 1, count)
            col += count

        for col, d in enumerate(self.days, start=1):
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            t_o_d = db_services.get_person(actor_plan_period.person.id).time_of_days
            for row, tageszeit in enumerate(sorted(t_o_d, key=lambda t: t.start), start=2):
                self.layout.addWidget(QLabel(tageszeit.name), row, 0)
                button = QPushButton()
                button.setCheckable(True)
                button.setMaximumWidth(23)
                button.setMinimumHeight(23)
                if tageszeit.name == 'Morgen':
                    button.setStyleSheet("QPushButton {background-color: #cae4f4}"
                                         "QPushButton::checked { background-color: #002aaa; border: none;}")
                else:
                    button.setStyleSheet("QPushButton {background-color: #fff4d6}"
                                         "QPushButton::checked { background-color: #ff4600; border: none;}")
                    '#a7c1d1'
                self.layout.addWidget(button, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet('background-color: #ffdc99')
            self.layout.addWidget(lb_weekday, row+1, col)








