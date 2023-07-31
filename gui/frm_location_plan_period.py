from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout

from database import schemas, db_services
from gui import side_menu


class FrmTabLocationPlanPeriods(QWidget):
    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.actor_plan_periods = self.plan_period.actor_plan_periods
        self.pers_id__actor_pp = {str(a_pp.person.id): a_pp for a_pp in self.plan_period.actor_plan_periods}
        self.person_id: UUID | None = None
        self.person: schemas.PersonShow | None = None
        self.scroll_area_events = QScrollArea()
        self.frame_events: FrmLocationPlanPeriod | None = None
        self.lb_notes_pp = QLabel('Infos zum Planungszeitraum:')
        self.lb_notes_pp.setFixedHeight(20)
        font_lb_notes = self.lb_notes_pp.font()
        font_lb_notes.setBold(True)
        self.lb_notes_pp.setFont(font_lb_notes)
        self.te_notes_pp = QTextEdit()
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_pp.setFixedHeight(180)

        self.lb_notes_actor = QLabel('Infos zur Einrichtung:')
        self.lb_notes_actor.setFixedHeight(20)
        font_lb_notes = self.lb_notes_actor.font()
        font_lb_notes.setBold(True)
        self.lb_notes_actor.setFont(font_lb_notes)
        self.te_notes_actor = QTextEdit()
        self.te_notes_actor.textChanged.connect(self.save_info_location)
        self.te_notes_actor.setFixedHeight(180)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.lb_title_name = QLabel('Einrichtungstermine')
        self.lb_title_name.setContentsMargins(10, 10, 10, 10)

        self.lb_title_name_font = self.lb_title_name.font()
        self.lb_title_name_font.setPointSize(16)
        self.lb_title_name_font.setBold(True)
        self.lb_title_name.setFont(self.lb_title_name_font)
        self.layout.addWidget(self.lb_title_name)

        self.splitter_events = QSplitter()
        self.layout.addWidget(self.splitter_events)

        self.table_select_location = QTableWidget()
        self.splitter_events.addWidget(self.table_select_location)
        self.setup_selector_table()
        self.widget_events = QWidget()
        self.layout_events = QGridLayout()
        self.layout_events.setContentsMargins(0, 0, 0, 0)
        self.widget_events.setLayout(self.layout_events)
        self.splitter_events.addWidget(self.widget_events)
        self.set_splitter_sizes()


        self.layout_controllers = QHBoxLayout()
        self.layout_notes = QHBoxLayout()
        self.layout_notes_actor = QVBoxLayout()
        self.layout_notes_actor_pp = QVBoxLayout()

        self.layout_events.addWidget(self.scroll_area_events, 0, 0)
        self.layout_events.addLayout(self.layout_controllers, 1, 0)
        self.layout_events.addLayout(self.layout_notes, 2, 0)
        self.layout_notes.addLayout(self.layout_notes_actor_pp)
        self.layout_notes.addLayout(self.layout_notes_actor)
        self.layout_notes_actor_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_actor_pp.addWidget(self.te_notes_pp)
        self.layout_notes_actor.addWidget(self.lb_notes_actor)
        self.layout_notes_actor.addWidget(self.te_notes_actor)

        self.side_menu = side_menu.WidgetSideMenu(self, 250, 10, 'right')

    def setup_selector_table(self):
        ...

    def set_splitter_sizes(self):
        ...

    def save_info_location_pp(self):
        ...

    def save_info_location(self):
        ...


class FrmLocationPlanPeriod(QWidget):
    def __init__(self):
        super().__init__()
