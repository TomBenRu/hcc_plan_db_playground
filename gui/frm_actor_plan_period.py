import datetime
from datetime import timedelta
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QAbstractItemView, QTableWidgetItem, QLabel, \
    QHBoxLayout, QPushButton, QHeaderView, QSplitter, QSpacerItem, QGridLayout, QMessageBox, QScrollArea, QTextEdit

from database import schemas, db_services


class FrmTabActorPlanPeriod(QWidget):
    def __init__(self, plan_period: schemas.PlanPeriodShow):
        super().__init__()

        self.plan_period = plan_period
        self.actor_plan_periods = [a_pp for a_pp in plan_period.actor_plan_periods]
        self.pers_id__actor_pp = {str(a_pp.person.id): a_pp for a_pp in plan_period.actor_plan_periods}
        self.person_id: UUID | None = None
        self.scroll_area_availables: QScrollArea | None = None
        self.frame_availables: FrmActorPlanPeriod | None = None
        self.lb_notes = QLabel('Infos:')
        font_lb_notes = self.lb_notes.font()
        font_lb_notes.setBold(True)
        self.lb_notes.setFont(font_lb_notes)
        self.te_notes = QTextEdit()
        self.te_notes.textChanged.connect(self.save_info)
        self.te_notes.setFixedHeight(180)

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
        self.layout.setStretch(1, 99)

    def setup_selector_table(self):
        self.table_select_actor.setMaximumWidth(175)
        self.table_select_actor.setMinimumWidth(150)
        self.table_select_actor.setSortingEnabled(True)
        self.table_select_actor.setAlternatingRowColors(True)
        self.table_select_actor.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_select_actor.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_select_actor.verticalHeader().setVisible(False)
        self.table_select_actor.horizontalHeader().setHighlightSections(False)
        self.table_select_actor.cellClicked.connect(self.data_setup)
        self.table_select_actor.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_actor.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        headers = ['id', 'Vorname', 'Nachname']
        self.table_select_actor.setColumnCount(len(headers))
        self.table_select_actor.setRowCount(len(self.pers_id__actor_pp))
        self.table_select_actor.setHorizontalHeaderLabels(headers)
        for row, actor_pp in enumerate(sorted(self.pers_id__actor_pp.values(), key=lambda x: x.person.f_name)):
            self.table_select_actor.setItem(row, 0, QTableWidgetItem(str(actor_pp.person.id)))
            self.table_select_actor.setItem(row, 1, QTableWidgetItem(actor_pp.person.f_name))
            self.table_select_actor.setItem(row, 2, QTableWidgetItem(actor_pp.person.l_name))
        self.table_select_actor.hideColumn(0)

    def data_setup(self, r, c):
        self.table_select_actor.setMaximumWidth(10000)
        self.person_id = UUID(self.table_select_actor.item(r, 0).text())
        actor_plan_period = self.pers_id__actor_pp[str(self.person_id)]
        actor_plan_period_show = db_services.ActorPlanPeriod.get(actor_plan_period.id)
        self.lb_title_name.setText(
            f'Verfügbarkeiten: {f"{actor_plan_period.person.f_name} {actor_plan_period.person.l_name}"}')
        if self.scroll_area_availables:
            self.scroll_area_availables.deleteLater()
        self.scroll_area_availables = QScrollArea()
        self.layout_availables.addWidget(self.scroll_area_availables)
        self.frame_availables = FrmActorPlanPeriod(actor_plan_period_show)
        self.scroll_area_availables.setWidget(self.frame_availables)

        self.info_text_setup()

    def info_text_setup(self):
        self.te_notes.textChanged.disconnect()
        self.te_notes.clear()
        self.layout_availables.addWidget(self.lb_notes)
        self.layout_availables.addWidget(self.te_notes)
        self.te_notes.setText(self.pers_id__actor_pp[str(self.person_id)].notes)
        self.te_notes.textChanged.connect(self.save_info)

    def save_info(self):
        saved_actor_plan_period = db_services.ActorPlanPeriod.update(
            schemas.ActorPlanPeriodUpdate(id=self.pers_id__actor_pp[str(self.person_id)].id,
                                          notes=self.te_notes.toPlainText()))
        self.pers_id__actor_pp[str(saved_actor_plan_period.person.id)] = saved_actor_plan_period


class FrmActorPlanPeriod(QWidget):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()

        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.layout.setVerticalSpacing(0)
        self.layout.setHorizontalSpacing(2)

        self.actor_plan_period = actor_plan_period
        self.t_o_d_standards = [t_o_d for t_o_d in actor_plan_period.person.time_of_day_standards if not t_o_d.prep_delete]
        self.t_o_d_enums = sorted([t_o_d.time_of_day_enum for t_o_d in self.t_o_d_standards], key=lambda x: x.time_index)
        self.actor_time_of_days = sorted(db_services.Person.get(self.actor_plan_period.person.id).time_of_days,
                                         key=lambda t: t.start)
        self.days = [actor_plan_period.plan_period.start+timedelta(delta) for delta in
                     range((actor_plan_period.plan_period.end - actor_plan_period.plan_period.start).days + 1)]
        self.weekdays = {0: 'Mo', 1: 'Di', 2: 'Mi', 3: 'Do', 4: 'Fr', 5: 'Sa', 6: 'So'}
        self.months = {1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni', 7: 'Juli', 8: 'August',
                       9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember'}

        self.set_headers_months()
        self.set_chk_field()
        self.get_avail_days()

    def set_headers_months(self):
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

    def set_chk_field(self):
        for col, d in enumerate(self.days, start=1):
            label = QLabel(f'{d.day}')
            label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.layout.addWidget(label, 1, col)
            for row, time_of_day_enum in enumerate(self.t_o_d_enums, start=2):
                self.layout.addWidget(QLabel(time_of_day_enum.name), row, 0)
                self.create_time_of_day_button(d, time_of_day_enum, row, col)
            lb_weekday = QLabel(self.weekdays[d.weekday()])
            lb_weekday.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if d.weekday() in (5, 6):
                lb_weekday.setStyleSheet('background-color: #ffdc99')
            self.layout.addWidget(lb_weekday, row+1, col)

    def create_time_of_day_button(self, day: datetime.date, time_of_day_enum: schemas.TimeOfDayEnumShow, row: int, col: int):
        button = QPushButton(objectName=f'{day}-{time_of_day_enum.name}')
        button.setCheckable(True)
        button.setMaximumWidth(23)
        button.setMinimumHeight(23)
        button.released.connect(lambda bt=button, t_o_d=time_of_day_enum: self.save_avail_day(bt, day, t_o_d))
        if time_of_day_enum.time_index == 1:
            button.setStyleSheet("QPushButton {background-color: #cae4f4}"
                                 "QPushButton::checked { background-color: #002aaa; border: none;}")
        elif time_of_day_enum.time_index == 2:
            button.setStyleSheet("QPushButton {background-color: #fff4d6}"
                                 "QPushButton::checked { background-color: #ff4600; border: none;}")
        elif time_of_day_enum.time_index == 3:
            button.setStyleSheet("QPushButton {background-color: #daa4c9}"
                                 "QPushButton::checked { background-color: #84033c; border: none;}")
            '#daa4c9'
        self.layout.addWidget(button, row, col)

    def save_avail_day(self, bt: QPushButton, date: datetime.date, t_o_d: schemas.TimeOfDayShow):
        if bt.isChecked():
            new_avail_day = db_services.AvailDay.create(
                schemas.AvailDayCreate(day=date, actor_plan_period=self.actor_plan_period, time_of_day=t_o_d))
            # QMessageBox.information(self, 'new time_of_day', f'{new_avail_day}')
        else:
            avail_day = db_services.AvailDay.get(self.actor_plan_period.id, date, t_o_d.id)
            deleted_avail_day = db_services.AvailDay.delete(avail_day.id)

    def get_avail_days(self):
        avail_days = [ad for ad in db_services.AvailDay.get_all_from__actor_plan_period(self.actor_plan_period.id)
                      if not ad.prep_delete]
        for ad in avail_days:
            button: QPushButton = self.findChild(QPushButton, f'{ad.day}-{ad.time_of_day.name}')
            button.setChecked(True)
