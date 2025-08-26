import datetime
import os
from collections import defaultdict
from functools import partial
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QGridLayout, QComboBox, QCalendarWidget, QSpinBox,
                               QDialogButtonBox, QPushButton, QCheckBox, QMessageBox, QHBoxLayout)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QDate, QSize

from commands import command_base_classes
from configuration.event_planing_rules import current_event_planning_rules_handler, EventPlanningRules, PlanningRules
from database import db_services
from gui import frm_cast_rule
from gui.custom_widgets.custom_date_and_time_edit import CalendarLocale
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from gui.schemas import RulesData, Rules
from tools import helper_functions
from tools.helper_functions import n_th_weekday_of_period, date_to_string, setup_form_help
from tools.size_of_objects import total_size


class FirstDayFromWeekday(QWidget):
    signal_first_day_changed = QtCore.Signal(datetime.date)
    def __init__(self, parent: QWidget, period_start: datetime.date, period_end: datetime.date,):
        super().__init__(parent)
        self.period_start = period_start
        self.period_end = period_end
        self.layout = QHBoxLayout(self)
        self.combo_weekday = QComboBoxToFindData()
        self.weekdays = {0: self.tr('Monday'), 1: self.tr('Tuesday'), 2: self.tr('Wednesday'),
                        3: self.tr('Thursday'), 4: self.tr('Friday'), 5: self.tr('Saturday'),
                        6: self.tr('Sunday')}
        for i, weekday in self.weekdays.items():
            self.combo_weekday.addItem(weekday, i)
        self.combo_weekday.currentIndexChanged.connect(self._weekday_changed)
        self.spin_nth_weekday = QSpinBox()
        self.spin_nth_weekday.valueChanged.connect(self._spin_nth_weekday_changed)
        self.spin_nth_weekday.setMinimum(1)
        self.layout.addWidget(self.combo_weekday)
        self.layout.addWidget(self.spin_nth_weekday)
        self._weekday_changed()

    def _weekday_changed(self):
        try:
            current_weekday = self.combo_weekday.currentData()
        except AttributeError:
            current_weekday = 0
        try:
            current_nth_weekday = self.spin_nth_weekday.value()
        except AttributeError:
            current_nth_weekday = 1
        curr_date = helper_functions.n_th_weekday_of_period(
            self.period_start, self.period_end, current_weekday, current_nth_weekday)
        if not curr_date:
            current_weekday, curr_date = self._get_nearest_weekday(
                current_weekday, current_nth_weekday, self.period_start, self.period_end)
            self.combo_weekday.setCurrentIndex(self.combo_weekday.findData(current_weekday))
            return

        self.curr_date = curr_date
        self.signal_first_day_changed.emit(curr_date)

    def _spin_nth_weekday_changed(self):
        try:
            current_weekday = self.combo_weekday.currentData()
        except AttributeError:
            current_weekday = 0
        try:
            current_nth_weekday = self.spin_nth_weekday.value()
        except AttributeError:
            current_nth_weekday = 1
        curr_date = helper_functions.n_th_weekday_of_period(
            self.period_start, self.period_end, current_weekday, current_nth_weekday)
        if not curr_date:
            self.spin_nth_weekday.setValue(current_nth_weekday - 1)
            return

        self.curr_date = curr_date
        self.signal_first_day_changed.emit(curr_date)

    def _get_nearest_weekday(self, current_weekday: int, current_nth_weekday: int,
                             period_start: datetime.date, period_end: datetime.date) -> tuple[int, datetime.date]:
        delta = 6
        curr_date: datetime.date | None = None
        new_current_weekday = current_weekday
        for weekday in range(7):
            if date :=helper_functions.n_th_weekday_of_period(
                    period_start, period_end, weekday, current_nth_weekday):
                if (new_delta := abs(weekday - current_weekday)) < delta:
                    delta = new_delta
                    new_current_weekday = weekday
                    curr_date = date
        return new_current_weekday, curr_date

    def set_date(self, date: datetime.date):
        self.combo_weekday.setCurrentIndex(self.combo_weekday.findData(date.weekday()))
        self.spin_nth_weekday.setValue(1)
        self._weekday_changed()




class DlgFirstDay(QDialog):
    def __init__(self, parent: QWidget, start_date: datetime.date, end_date: datetime.date,
                 current_date: datetime.date):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Day of first Event"))

        self.start_date = start_date
        self.end_date = end_date
        self.current_date = current_date
        self._setup_ui()
        
        # Help-Integration
        setup_form_help(self, "first_day", add_help_button=True)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.calendar = CalendarLocale()
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


class DlgEventPlanningRules(QDialog):
    def __init__(self, parent: QWidget, location_plan_period_id: UUID, first_day_from_weekday: bool):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Event Planning Rules"))

        self.location_plan_period_id = location_plan_period_id
        self.first_day_from_weekday = first_day_from_weekday
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.rules_handler = current_event_planning_rules_handler

        self._setup_data()
        self._setup_ui()
        
        # Help-Integration
        setup_form_help(self, "event_planning_rules", add_help_button=True)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout_head = QVBoxLayout()
        self.layout_body = QGridLayout()
        self.layout_body.setSpacing(0)
        self.layout_special_rules = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_special_rules)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel()
        self.layout_head.addWidget(self.lb_description)


        for column, text in enumerate(self.header_text):
            lb_text = QLabel(text)
            lb_text.setStyleSheet("font-weight: bold; background-color: #00123a; "
                                  "padding-left: 5px; padding-right: 5px; padding-top: 10px; padding-bottom: 10px;")
            self.layout_body.addWidget(lb_text, 0, column)

        self.layout_rule_same_day = QHBoxLayout()
        self.layout_special_rules.addLayout(self.layout_rule_same_day)
        self.lb_rule_same_day = QLabel(self.tr('Rules for events on the same day:'))
        self.combo_rule_same_day = QComboBoxToFindData()
        self._combo_rule_same_day_add_items()
        self.combo_rule_same_day.setDisabled(True)
        self.combo_rule_same_day.currentIndexChanged.connect(self._set_text_description_to_default)
        self.bt_rule_same_day = QPushButton(self.tr('New Day Rule'))
        self.bt_rule_same_day.clicked.connect(self._add_rule_same_day)
        self.bt_rule_same_day.setDisabled(True)
        self.layout_rule_same_day.addWidget(self.lb_rule_same_day)
        self.layout_rule_same_day.addWidget(self.combo_rule_same_day)
        self.layout_rule_same_day.addWidget(self.bt_rule_same_day)
        self.chk_same_partial_days = QCheckBox(self.tr('Same day selection for all rules'))
        self.chk_same_partial_days.setToolTip(
            self.tr('When this option is enabled,\n'
                   'the events defined by the rules will be grouped\n'
                   'so that they are created on the same days.')
        )
        self.chk_same_partial_days.setDisabled(True)
        self.chk_same_partial_days.toggled.connect(self._set_text_description_to_default)
        self.layout_special_rules.addWidget(self.chk_same_partial_days)

        self.bt_add_rule = QPushButton(self.tr('New Rule'))
        self.bt_add_rule.clicked.connect(self._add_rule)
        self.bt_reset_rules = QPushButton(self.tr('Reset Rules'))
        self.bt_reset_rules.clicked.connect(self._reset_rule_widgets)
        self.bt_reset_rules.setToolTip(self.tr('Delete all rules and restore with default values'))
        self.bt_save_rules = QPushButton(self.tr('Save Rules'))
        self.bt_save_rules.clicked.connect(self._save_rules)
        self.bt_save_rules.setToolTip(self.tr('Save rules for later use'))
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_add_rule, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.bt_reset_rules, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.addButton(self.bt_save_rules, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        if self._event_planing_rules:
            self._setup_rules_from_data()
        else:
            self._add_rule()

        self.lb_description.setText(self._text_description)

    def _show_calendar(self, rule_index: int):
        dlg = DlgFirstDay(self, self.plan_period.start, self.plan_period.end,
                          current_date=self._rules_data[rule_index].first_day)
        if dlg.exec():
            self.widgets_for_rules[rule_index][self.header_text_first_day].setText(date_to_string(dlg.first_day))
            self._rules_data[rule_index].first_day = dlg.first_day
            self._spinbox_repeat_changed(rule_index)
            self._enable_same_partial_days_checkbox()

    def _setup_data(self):
        self.header_text_first_day = self.tr('First Day')
        self.header_text_time_of_day = self.tr('Time of Day')
        self.header_text_interval = self.tr('Interval')
        self.header_text_repetitions = self.tr('Repetitions')
        self.header_text_possible_count = self.tr('Possible Count')
        self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period_id)
        self.plan_period = self.location_plan_period.plan_period
        self.header_text = [
            self.tr('Start: Weekday, which one') if self.first_day_from_weekday else self.header_text_first_day,
            self.header_text_time_of_day,
            self.header_text_interval,
            self.header_text_repetitions,
            self.header_text_possible_count,
            '']
        self.widgets_for_rules: defaultdict[int, dict[str, QComboBox | QSpinBox | QPushButton]] = defaultdict(dict)
        self.rules_widgets = [
            self._widget_first_day_from_weekday if self.first_day_from_weekday else self._button_first_day,
            self._combobox_time_of_day, self._spinbox_interval, self._spinbox_repeat, self._spinbox_num_events,
            self._bt_remove_rule]
        self._text_description_default = self.tr(
            'Here you can define how to plan the events for<br>'
            '<b>"{location}"</b> in the period '
            '<b>{start_date}-{end_date}</b>.').format(
                location=self.location_plan_period.location_of_work.name_an_city,
                start_date=date_to_string(self.plan_period.start),
                end_date=date_to_string(self.plan_period.end))
        self._text_description = self._text_description_default
        self._event_planing_rules = self.rules_handler.get_event_planning_rules(
            self.location_plan_period.location_of_work.id)
        self._rules_data: defaultdict[int, RulesData] = defaultdict(RulesData)
        self._rules_data_from_config: defaultdict[int, RulesData] = defaultdict(RulesData)
        if self._event_planing_rules:
            self._text_description = (
                self._text_description_default +
                self.tr('<br>Rules were loaded from a previously stored configuration.'))
            for i, rules_data in enumerate(self._event_planing_rules.planning_rules, start=1):
                time_of_day = db_services.TimeOfDay.get(rules_data.time_of_day_id, True)
                self._rules_data_from_config[i] = RulesData(
                    first_day=n_th_weekday_of_period(self.plan_period.start,
                                                     self.plan_period.end,
                                                     rules_data.first_day.weekday(),
                                                     1),
                    time_of_day=time_of_day,
                    interval=rules_data.interval,
                    repeat=rules_data.repeat,
                    num_events=rules_data.num_events)

    def _add_rule(self):
        rule_index = max(self.widgets_for_rules.keys()) + 1 if self.widgets_for_rules else 1
        self.widgets_for_rules[rule_index] = {}
        for column, (text, widget) in enumerate(zip(self.header_text, self.rules_widgets)):
            self.layout_body.addWidget(curr_widget := widget(rule_index), rule_index, column)
            self.widgets_for_rules[rule_index][text] = curr_widget
        if len(self.widgets_for_rules) > 1:
            self._enable_same_partial_days_checkbox()
            self._enable_rule_at_same_day_checkbox()

    def _remove_rule(self, rule_index: int):
        for widget in self.widgets_for_rules[rule_index].values():
            widget.deleteLater()
        del self.widgets_for_rules[rule_index]
        del self._rules_data[rule_index]
        self._enable_same_partial_days_checkbox()
        self._enable_rule_at_same_day_checkbox()

    def _setup_rules_from_data(self):
        for _ in self._rules_data_from_config:
            self._add_rule()
        for rule_index, rule_data in self._rules_data_from_config.items():
            for column, (text, widget) in enumerate(zip(self.header_text, self.widgets_for_rules[rule_index].values())):

                if column == 0:
                    if isinstance(widget, QPushButton):
                        widget.setText(date_to_string(rule_data.first_day))
                        self._rules_data[rule_index].first_day = rule_data.first_day
                    elif isinstance(widget, FirstDayFromWeekday):
                        widget.set_date(rule_data.first_day)
                elif column == 1:
                    if (idx := widget.findData(rule_data.time_of_day)) != -1:
                        widget.setCurrentIndex(idx)
                    else:
                        time_index = rule_data.time_of_day.time_of_day_enum.time_index
                        for time_of_day in [t for t in [widget.itemData(i) for i in range(widget.count())]]:
                            if time_of_day.time_of_day_enum.time_index == time_index:
                                widget.setCurrentIndex(widget.findData(time_of_day))
                                QMessageBox.warning(
                                    self,
                                    self.tr('Error'),
                                    self.tr('The time of day "{old_time}" stored in the rules is not available.\n'
                                           'It has been replaced with the time of day "{new_time}"').format(
                                               old_time=rule_data.time_of_day.name,
                                               new_time=time_of_day.name)
                                )
                                break
                        else:
                            QMessageBox.warning(
                                self,
                                self.tr('Error'),
                                self.tr('The time of day "{old_time}" stored in the rules is not available.\n'
                                       'It has been replaced with the time of day "{new_time}"').format(
                                           old_time=rule_data.time_of_day.name,
                                           new_time=widget.currentData().name)
                            )
                elif column == 2:
                    widget.setValue(rule_data.interval)
                elif column == 3:
                    widget.setValue(rule_data.repeat)
                elif column == 4:
                    widget.setValue(rule_data.num_events)
        self.chk_same_partial_days.setChecked(
            self._event_planing_rules.same_partial_days_for_all_rules)
        if self._event_planing_rules.cast_rule_at_same_day_id and (idx := self.combo_rule_same_day.findData(
                db_services.CastRule.get(self._event_planing_rules.cast_rule_at_same_day_id))) != -1:
            self.combo_rule_same_day.setCurrentIndex(idx)

    def _reset_rule_widgets(self):
        for widgets in self.widgets_for_rules.values():
            for widget in widgets.values():
                widget.deleteLater()
        self.widgets_for_rules.clear()
        self._rules_data.clear()
        self._add_rule()
        self._set_text_description_to_default()


    def _combobox_time_of_day(self, rule_index: int):
        combobox = QComboBoxToFindData()
        times_of_day = sorted(self.location_plan_period.time_of_days,
                                  key=lambda x: (x.time_of_day_enum.time_index, x.start))
        for time_of_day in times_of_day:
            combobox.addItem(time_of_day.name, time_of_day)
        combobox.currentIndexChanged.connect(partial(self._combobox_time_of_day_changed,rule_index))
        self._rules_data[rule_index].time_of_day = times_of_day[0]
        return combobox

    def _button_first_day(self, rule_index: int):
        button = QPushButton(date_to_string(self.plan_period.start))
        button.clicked.connect(partial(self._show_calendar, rule_index))
        self._rules_data[rule_index].first_day = self.plan_period.start
        return button

    def _widget_first_day_from_weekday(self, rule_index: int):
        widget = FirstDayFromWeekday(self, self.plan_period.start, self.plan_period.end)
        widget.signal_first_day_changed.connect(partial(self._first_day_from_weekday_changed, rule_index))
        self._rules_data[rule_index].first_day = widget.curr_date
        return widget

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

    def _bt_remove_rule(self, rule_index: int):
        button = QPushButton(icon=QIcon(os.path.join(os.path.dirname(__file__),
                                                     'resources/toolbar_icons/icons/cross.png')))
        button.setToolTip(self.tr('Remove rule'))
        button.clicked.connect(partial(self._remove_rule, rule_index))
        return button

    def _spinbox_repeat_changed(self, rule_index: int, *args):
        first_day = self._rules_data[rule_index].first_day
        interval = self._rules_data[rule_index].interval
        widget_repeat = self.widgets_for_rules[rule_index][self.header_text_repetitions]
        widget_num_events = self.widgets_for_rules[rule_index][self.header_text_possible_count]
        if widget_num_events.value() == widget_repeat.value():
            widget_num_events.setValue(widget_repeat.value() + 1)
        if first_day + datetime.timedelta(interval * (widget_repeat.value())) > self.plan_period.end:
            widget_repeat.setValue(widget_repeat.value() - 1)
        self._spinbox_num_events_changed(rule_index)
        self._rules_data[rule_index].repeat = widget_repeat.value()
        self._enable_same_partial_days_checkbox()

    def _spinbox_num_events_changed(self, rule_index: int, *args):
        widget_num_events = self.widgets_for_rules[rule_index][self.header_text_possible_count]
        repeats = self.widgets_for_rules[rule_index][self.header_text_repetitions].value()
        if widget_num_events.value() > repeats + 1:
            widget_num_events.setValue(repeats + 1)
        self._set_text_description_to_default()
        self._rules_data[rule_index].num_events = widget_num_events.value()
        self._enable_same_partial_days_checkbox()

    def _combobox_time_of_day_changed(self, rule_index: int, *args):
        combobox = self.widgets_for_rules[rule_index][self.header_text_time_of_day]
        self._rules_data[rule_index].time_of_day = combobox.currentData()
        self._set_text_description_to_default()

    def _spinbox_interval_changed(self, rule_index: int, value: int):
        self._rules_data[rule_index].interval = value
        self._spinbox_repeat_changed(rule_index)
        self._enable_same_partial_days_checkbox()

    def _first_day_from_weekday_changed(self, rule_index: int, date: datetime.date):
        self._rules_data[rule_index].first_day = date
        self._spinbox_repeat_changed(rule_index)
        self._enable_same_partial_days_checkbox()
        self._set_text_description_to_default()

    def _combo_rule_same_day_add_items(self):
        self.combo_rule_same_day.clear()
        self.combo_rule_same_day.addItem(self.tr('No rule'), None)
        rules = sorted((cr for cr in db_services.CastRule.get_all_from__project(self.plan_period.team.project.id)
                        if not cr.prep_delete),
                       key=lambda x: x.name)
        for i, rule in enumerate(rules, start=1):
            self.combo_rule_same_day.addItem(QIcon(os.path.join(os.path.dirname(__file__),
                                                             'resources/toolbar_icons/icons/foaf.png')),
                                          rule.name, rule)

    def _enable_rule_at_same_day_checkbox(self):
        if len(self._rules_data) > 1:
            self.combo_rule_same_day.setEnabled(True)
            self.bt_rule_same_day.setEnabled(True)
        else:
            self.combo_rule_same_day.setCurrentIndex(0)
            self.combo_rule_same_day.setDisabled(True)
            self.bt_rule_same_day.setDisabled(True)

    def _enable_same_partial_days_checkbox(self):
        if len(self._rules_data) == 1:
            if not self.chk_same_partial_days.isEnabled():
                return

            self.chk_same_partial_days.setChecked(False)
            self.chk_same_partial_days.setDisabled(True)
        min_rule_index = min(self._rules_data.keys())
        if (all(r.first_day == self._rules_data[min_rule_index].first_day
               and r.num_events == self._rules_data[min_rule_index].num_events
               and r.interval == self._rules_data[min_rule_index].interval
               for r in self._rules_data.values())
            and all(r.repeat + 1 != r.num_events for r in self._rules_data.values())):
            self.chk_same_partial_days.setEnabled(True)
        else:
            self.chk_same_partial_days.setChecked(False)
            self.chk_same_partial_days.setDisabled(True)

    def _add_rule_same_day(self):
        dlg = frm_cast_rule.DlgCreateCastRule(self, self.plan_period.team.project.id)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self._combo_rule_same_day_add_items()
        else:
            dlg.controller.undo_all()

    @property
    def rules(self) -> Rules:
        return Rules(rules_data=list(self._rules_data.values()),
                     cast_rule_at_same_day=self.combo_rule_same_day.currentData(),
                     same_partial_days_for_all_rules=self.chk_same_partial_days.isChecked())

    def _set_text_description_to_default(self):
        if self._event_planing_rules:
            self.lb_description.setText(self._text_description_default)

    def _save_rules(self):
        self._rules_data: defaultdict[int, RulesData]
        self._event_planing_rules = EventPlanningRules(
            location_of_work_id=self.location_plan_period.location_of_work.id,
            planning_rules=[PlanningRules(first_day=r.first_day, time_of_day_id=r.time_of_day.id, interval=r.interval,
                                          repeat=r.repeat, num_events=r.num_events) for r in self._rules_data.values()],
            cast_rule_at_same_day_id=(self.combo_rule_same_day.currentData().id
                                      if self.combo_rule_same_day.currentIndex() > 0 else None),
            same_partial_days_for_all_rules=self.chk_same_partial_days.isChecked()
        )
        self.rules_handler.set_event_planning_rules(self._event_planing_rules)
        QMessageBox.information(self, self.tr('Planning Rules'),
                                self.tr('Planning rules for "{location}" have been saved for later use.').format(
                                    location=self.location_plan_period.location_of_work.name_an_city))


    def validate_rules(self) -> bool:
        dict_date_time_indexes: defaultdict[datetime.date, list[int]] = defaultdict(list)
        if len(self._rules_data) > 1:
            for rule_index, rules in self._rules_data.items():
                for i in range(rules.num_events):
                    date = rules.first_day + datetime.timedelta(days=i * rules.interval)
                    dict_date_time_indexes[date].append(rules.time_of_day.time_of_day_enum.time_index)
            for time_indexes in dict_date_time_indexes.values():
                if len(set(time_indexes)) < len(time_indexes):
                    return False
        return True

    def _events_already_exist(self) -> bool:
        events = db_services.Event.get_all_from__location_plan_period(self.location_plan_period_id)
        return len(events) > 0

    def plan_exists(self) -> bool:
        return bool(db_services.Plan.get_all_from__plan_period_minimal(self.plan_period.id))

    def accept(self):
        if not self.validate_rules():
            QMessageBox.critical(self, self.tr('Planning Rules'),
                                 self.tr('Events with the same time of day cannot be created twice on the same day.'))
            return

        if self._events_already_exist():
            reply = QMessageBox.question(
                self, self.tr('Planning Rules'),
                self.tr('There are already events in this planning period.\n'
                        'If you continue, all existing events will be deleted and new events will be created.\n'
                        'Do you want to continue?'))
            if reply == QMessageBox.StandardButton.No:
                return

        if self.plan_exists():
            QMessageBox.information(
                self, self.tr('Planning Rules'),
                self.tr('The newly created events will not be added to the existing plans of the planning period '
                        'from {start_date} to {end_date}.').format(
                            start_date=date_to_string(self.plan_period.start),
                            end_date=date_to_string(self.plan_period.end)))

        super().accept()
