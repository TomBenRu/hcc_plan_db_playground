import datetime
from calendar import calendar
from collections import defaultdict
from functools import partial
from uuid import UUID

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QGridLayout, QComboBox, QCalendarWidget, QSpinBox,
                               QDialogButtonBox, QPushButton, QCheckBox, QMessageBox)
from PySide6.QtCore import QDate
from pydantic import BaseModel

from database import db_services, schemas


class  RulesData(BaseModel):
    first_day: datetime.date | None = None
    time_of_day: schemas.TimeOfDay | None = None
    interval: int | None = None
    repeat: int | None = None
    num_events: int | None = None


class Rules(BaseModel):
    rules_data: list[RulesData] = []
    same_cast_at_same_day: bool = False
    same_partial_days_for_all_rules: bool = False


class DlgFirstDay(QDialog):
    def __init__(self, parent: QWidget, start_date: datetime.date, end_date: datetime.date,
                 current_date: datetime.date):
        super().__init__(parent)
        self.setWindowTitle("Erster Tag der Veranstaltung")

        self.start_date = start_date
        self.end_date = end_date
        self.current_date = current_date
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        self.calendar.setMinimumDate(QDate(self.start_date.year, self.start_date.month, self.start_date.day))
        self.calendar.setMaximumDate(QDate(self.end_date.year, self.end_date.month, self.end_date.day))
        self.calendar.setSelectedDate(QDate(self.current_date.year, self.current_date.month, self.current_date.day))
        self.layout.addWidget(self.calendar)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    @property
    def first_day(self) -> datetime.date:
        return self.calendar.selectedDate().toPython()


class DlgEventPlaningRules(QDialog):
    def __init__(self, parent: QWidget, location_plan_period_id: UUID):
        super().__init__(parent)
        self.setWindowTitle("Event Planing Rules")

        self.location_plan_period_id = location_plan_period_id

        self._setup_data()
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout_head = QVBoxLayout()
        self.layout_body = QGridLayout()
        self.layout_body.setSpacing(0)
        self.layout_check_boxes = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_check_boxes)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel("Hier können Sie festlegen, wie Sie die Events planen möchten.")
        self.layout_head.addWidget(self.lb_description)


        for column, text in enumerate(self.header_text):
            lb_text = QLabel(text)
            lb_text.setStyleSheet("font-weight: bold; background-color: #00123a;")
            self.layout_body.addWidget(lb_text, 0, column)
        self._add_rule()

        self.chk_same_cast_at_same_day = QCheckBox('Gleiche Besetzung am selben Tag')
        self.layout_check_boxes.addWidget(self.chk_same_cast_at_same_day)
        self.chk_same_partial_days_for_all_rules = QCheckBox('Gleiche Tageswahl für alle Regeln')
        self.chk_same_partial_days_for_all_rules.setDisabled(True)
        self.layout_check_boxes.addWidget(self.chk_same_partial_days_for_all_rules)

        self.bt_add_rule = QPushButton('Neue Regel')
        self.bt_add_rule.clicked.connect(self._add_rule)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_add_rule, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _show_calendar(self, row: int):
        dlg = DlgFirstDay(self, self.plan_period.start, self.plan_period.end,
                          current_date=self._rules_data[row].first_day)
        if dlg.exec():
            self.widgets_for_rules[row]['1. Tag'].setText(dlg.first_day.strftime('%d.%m.%Y'))
            self._rules_data[row].first_day = dlg.first_day
            self._enable_same_partial_days_checkbox()

    def _setup_data(self):
        self.header_text = ['1. Tag', 'Tageszeit', 'Abstand', 'Wiederholungen', 'mögl. Anzahl']
        self.widgets_for_rules: defaultdict[int, dict[str, QComboBox | QSpinBox | QPushButton]] = defaultdict(dict)
        self.rules_widgets = [self._button_first_day, self._combobox_time_of_day, self._spinbox_interval,
                              self._spinbox_repeat, self._spinbox_num_events]
        self._rules_data: defaultdict[int, RulesData] = defaultdict(RulesData)
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period_id)
        self.plan_period = self.location_plan_period.plan_period

    def _add_rule(self):
        rule_index = max(self.widgets_for_rules.keys()) + 1 if self.widgets_for_rules else 1
        self.widgets_for_rules[rule_index] = {}
        for column, (text, widget) in enumerate(zip(self.header_text, self.rules_widgets)):
            self.layout_body.addWidget(curr_widget := widget(rule_index), rule_index, column)
            self.widgets_for_rules[rule_index][text] = curr_widget
        if len(self.widgets_for_rules) > 1:
            self._enable_same_partial_days_checkbox()

    def _combobox_time_of_day(self, rule_index: int):
        combobox = QComboBox()
        times_of_day = sorted(self.location_plan_period.time_of_day_standards, key=lambda x: x.time_of_day_enum.time_index)
        for time_of_day in times_of_day:
            combobox.addItem(time_of_day.name, time_of_day)
        combobox.currentIndexChanged.connect(partial(self._combobox_time_of_day_changed,rule_index))
        self._rules_data[rule_index].time_of_day = times_of_day[0]
        return combobox

    def _button_first_day(self, rule_index: int):
        button = QPushButton(self.plan_period.start.strftime('%d.%m.%Y'))
        button.clicked.connect(partial(self._show_calendar, rule_index))
        self._rules_data[rule_index].first_day = self.plan_period.start
        return button

    def _spinbox_interval(self, rule_index: int):
        spinbox = QSpinBox()
        spinbox.setMinimum(1)
        spinbox.valueChanged.connect(partial(self._spinbox_interval_changed, rule_index))
        self._rules_data[rule_index].interval = 1
        return spinbox

    def _spinbox_repeat(self, rule_index: int):
        spinbox = QSpinBox()
        spinbox.setMinimum(0)
        spinbox.valueChanged.connect(lambda: self._spinbox_repeat_changed(rule_index))
        self._rules_data[rule_index].repeat = 0
        return spinbox

    def _spinbox_num_events(self, rule_index: int):
        spinbox = QSpinBox()
        spinbox.setMinimum(1)
        spinbox.valueChanged.connect(lambda: self._spinbox_num_events_changed(rule_index))
        self._rules_data[rule_index].num_events = 1
        return spinbox

    def _spinbox_repeat_changed(self, rule_index: int, *args):
        first_day = datetime.datetime.strptime(self.widgets_for_rules[rule_index]['1. Tag'].text(), '%d.%m.%Y').date()
        interval = self.widgets_for_rules[rule_index]['Abstand'].value()
        widget_repeat = self.widgets_for_rules[rule_index]['Wiederholungen']
        widget_num_events = self.widgets_for_rules[rule_index]['mögl. Anzahl']
        if widget_num_events.value() == widget_repeat.value():
            widget_num_events.setValue(widget_repeat.value() + 1)
        if first_day + datetime.timedelta(interval * (widget_repeat.value())) > self.plan_period.end:
            widget_repeat.setValue(widget_repeat.value() - 1)
        self._spinbox_num_events_changed(rule_index)
        self._rules_data[rule_index].repeat = widget_repeat.value()
        self._enable_same_partial_days_checkbox()

    def _spinbox_num_events_changed(self, rule_index: int, *args):
        widget_num_events = self.widgets_for_rules[rule_index]['mögl. Anzahl']
        repeats = self.widgets_for_rules[rule_index]['Wiederholungen'].value()
        if widget_num_events.value() > repeats + 1:
            widget_num_events.setValue(repeats + 1)
        self._rules_data[rule_index].num_events = widget_num_events.value()
        self._enable_same_partial_days_checkbox()

    def _combobox_time_of_day_changed(self, rule_index: int, *args):
        combobox = self.widgets_for_rules[rule_index]['Tageszeit']
        self._rules_data[rule_index].time_of_day = combobox.currentData()

    def _spinbox_interval_changed(self, rule_index: int, value: int):
        self._rules_data[rule_index].interval = value
        self._enable_same_partial_days_checkbox()

    def _enable_same_partial_days_checkbox(self):
        if len(self._rules_data) == 1:
            if not self.chk_same_partial_days_for_all_rules.isEnabled():
                return

            self.chk_same_partial_days_for_all_rules.setChecked(False)
            self.chk_same_partial_days_for_all_rules.setDisabled(True)
        if (all(r.first_day == self._rules_data[1].first_day
               and r.num_events == self._rules_data[1].num_events
               and r.interval == self._rules_data[1].interval
               for r in self._rules_data.values())
            and all(r.repeat + 1 != r.num_events for r in self._rules_data.values())):
            self.chk_same_partial_days_for_all_rules.setEnabled(True)
        else:
            self.chk_same_partial_days_for_all_rules.setChecked(False)
            self.chk_same_partial_days_for_all_rules.setDisabled(True)


    @property
    def rules(self) -> Rules:
        return Rules(rules_data=list(self._rules_data.values()),
                     same_cast_at_same_day=self.chk_same_cast_at_same_day.isChecked(),
                     same_partial_days_for_all_rules=self.chk_same_partial_days_for_all_rules.isChecked())

    def validate_rules(self) -> bool:
        dict_date_time_indexes: defaultdict[datetime.date, set[int]] = defaultdict(set)
        if len(self._rules_data) > 1:
            for rule_index, rules in self._rules_data.items():
                dict_date_time_indexes[rules.first_day].add(rules.time_of_day.time_of_day_enum.time_index)
            for time_indexes in dict_date_time_indexes.values():
                if len(time_indexes) == 1:
                    return False
        return True

    def accept(self):
        if not self.validate_rules():
            QMessageBox.critical(self, 'Planungsregeln',
                                 'Am selben Tag können nicht 2 Mal die gleichen Tageszeiten gewählt werden.')
            return

        super().accept()
