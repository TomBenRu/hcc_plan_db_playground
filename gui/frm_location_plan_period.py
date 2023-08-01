from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QScrollArea, QLabel, QTextEdit, QVBoxLayout, QSplitter, QTableWidget, \
    QGridLayout, QHBoxLayout, QAbstractItemView, QHeaderView, QTableWidgetItem

from database import schemas, db_services
from gui import side_menu
from gui.observer import signal_handling


class FrmTabLocationPlanPeriods(QWidget):
    def __init__(self, parent: QWidget, plan_period: schemas.PlanPeriod):
        super().__init__(parent=parent)

        self.plan_period = db_services.PlanPeriod.get(plan_period.id)
        self.location_plan_periods = self.plan_period.location_plan_periods
        self.location_id__location_pp = {str(loc_pp.location_of_work.id): loc_pp
                                         for loc_pp in self.plan_period.location_plan_periods}
        self.location_id: UUID | None = None
        self.location: schemas.PersonShow | None = None
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

        self.lb_notes_location = QLabel('Infos zur Einrichtung:')
        self.lb_notes_location.setFixedHeight(20)
        font_lb_notes = self.lb_notes_location.font()
        font_lb_notes.setBold(True)
        self.lb_notes_location.setFont(font_lb_notes)
        self.te_notes_location = QTextEdit()
        self.te_notes_location.textChanged.connect(self.save_info_location)
        self.te_notes_location.setFixedHeight(180)

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
        self.layout_notes_location = QVBoxLayout()
        self.layout_notes_location_pp = QVBoxLayout()

        self.layout_events.addWidget(self.scroll_area_events, 0, 0)
        self.layout_events.addLayout(self.layout_controllers, 1, 0)
        self.layout_events.addLayout(self.layout_notes, 2, 0)
        self.layout_notes.addLayout(self.layout_notes_location_pp)
        self.layout_notes.addLayout(self.layout_notes_location)
        self.layout_notes_location_pp.addWidget(self.lb_notes_pp)
        self.layout_notes_location_pp.addWidget(self.te_notes_pp)
        self.layout_notes_location.addWidget(self.lb_notes_location)
        self.layout_notes_location.addWidget(self.te_notes_location)

        self.side_menu = side_menu.WidgetSideMenu(self, 250, 10, 'right')

    def setup_selector_table(self):
        self.table_select_location.setSortingEnabled(True)
        self.table_select_location.setAlternatingRowColors(True)
        self.table_select_location.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_select_location.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_select_location.verticalHeader().setVisible(False)
        self.table_select_location.horizontalHeader().setHighlightSections(False)
        self.table_select_location.cellClicked.connect(self.data_setup)
        self.table_select_location.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.table_select_location.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        headers = ['id', 'Name', 'Ort']
        self.table_select_location.setColumnCount(len(headers))
        self.table_select_location.setRowCount(len(self.location_id__location_pp))
        self.table_select_location.setHorizontalHeaderLabels(headers)
        for row, location_pp in enumerate(sorted(self.location_id__location_pp.values(),
                                                 key=lambda x: x.location_of_work.name)):
            self.table_select_location.setItem(row, 0, QTableWidgetItem(str(location_pp.location_of_work.id)))
            self.table_select_location.setItem(row, 1, QTableWidgetItem(location_pp.location_of_work.name))
            self.table_select_location.setItem(row, 2, QTableWidgetItem(location_pp.location_of_work.address.city))
        self.table_select_location.hideColumn(0)

    def set_splitter_sizes(self):
        self.splitter_events.setStretchFactor(0, 0)
        self.splitter_events.setStretchFactor(1, 1)
        header_width = sum(self.table_select_location.horizontalHeader().sectionSize(i)
                           for i in range(self.table_select_location.columnCount()))
        header_width += 3

        self.splitter_events.setSizes([header_width, 10_000])
        self.table_select_location.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def data_setup(self, r, c):
        self.location_id = UUID(self.table_select_location.item(r, 0).text())
        self.location = db_services.LocationOfWork.get(self.location_id)
        location_plan_period = self.location_id__location_pp[str(self.location_id)]
        location_plan_period_show = db_services.LocationPlanPeriod.get(location_plan_period.id)
        self.lb_title_name.setText(f'Termine: {location_plan_period_show.location_of_work.name} '
                                   f'{location_plan_period_show.location_of_work.address.city}')

        if self.frame_events:
            self.disconnect_event_button_signals()
            self.delete_location_plan_period_widgets()
        self.frame_events = FrmLocationPlanPeriod(self, location_plan_period_show, self.side_menu)
        self.scroll_area_events.setWidget(self.frame_events)

        self.info_text_setup()

    def disconnect_event_button_signals(self):
        try:
            signal_handling.handler_location_plan_period.signal_reload_location_pp__event_configs.disconnect()
            signal_handling.handler_location_plan_period.signal_change_location_plan_period_group_mode.disconnect()
        except Exception as e:
            print(f'Fehler: {e}')

    def delete_location_plan_period_widgets(self):
        self.frame_events.deleteLater()
        for widget in (self.layout_controllers.itemAt(i).widget() for i in range(self.layout_controllers.count())):
            widget.deleteLater()

    def info_text_setup(self):
        self.te_notes_pp.textChanged.disconnect()
        self.te_notes_pp.clear()
        self.te_notes_pp.setText(self.location_id__location_pp[str(self.location_id)].notes)
        self.te_notes_pp.textChanged.connect(self.save_info_location_pp)
        self.te_notes_location.textChanged.disconnect()
        self.te_notes_location.clear()
        self.te_notes_location.setText(self.location.notes)
        self.te_notes_location.textChanged.connect(self.save_info_location)

    def save_info_location_pp(self):
        updated_location_plan_period = db_services.LocationPlanPeriod.update_notes(
            self.location_id__location_pp[str(self.location_id)].id, self.te_notes_pp.toPlainText())
        self.location_id__location_pp[str(self.location_id)] = updated_location_plan_period

    def save_info_location(self):
        self.location.notes = self.te_notes_location.toPlainText()
        updated_location = db_services.LocationOfWork.update_notes(
            self.location_id, self.te_notes_location.toPlainText())


class FrmLocationPlanPeriod(QWidget):
    def __init__(self, parent: FrmTabLocationPlanPeriods, location_plan_period: schemas.LocationPlanPeriodShow,
                 side_menu: side_menu.WidgetSideMenu):
        super().__init__(parent)
