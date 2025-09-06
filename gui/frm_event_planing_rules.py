import datetime
import os
from collections import defaultdict
from functools import partial
from uuid import UUID

from PySide6 import QtCore
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QGridLayout, QComboBox, QSpinBox,
                               QDialogButtonBox, QPushButton, QCheckBox, QMessageBox, QHBoxLayout)
from PySide6.QtGui import QIcon
from PySide6.QtCore import QDate

from commands import command_base_classes
from configuration.event_planing_rules import current_event_planning_rules_handler
from database import db_services
from gui import frm_cast_rule
from gui.custom_widgets.custom_date_and_time_edit import CalendarLocale
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from gui.data_models.schemas import RulesData, Rules
from gui.data_models import RuleDataModel, ValidationResult
from tools import helper_functions
from tools.helper_functions import n_th_weekday_of_period, date_to_string, setup_form_help


class FirstDayFromWeekday(QWidget):
    """Widget zur Auswahl des ersten Tages basierend auf Wochentag und n-ter Occurrence.
    
    Ermöglicht die Auswahl eines Startdatums durch:
    - Auswahl des Wochentages (Montag-Sonntag)  
    - Auswahl der n-ten Occurrence des Wochentages im Zeitraum
    
    Args:
        parent: Übergeordnetes Widget
        period_start: Startdatum des gültigen Zeitraums
        period_end: Enddatum des gültigen Zeitraums
    
    Signals:
        signal_first_day_changed: Wird ausgelöst wenn sich das Datum ändert
    """
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
    """Dialog zur Auswahl des ersten Event-Tages mittels Kalender-Widget.
    
    Bietet eine benutzerfreundliche Kalender-Oberfläche zur Auswahl
    des Startdatums für Event-Planungsregeln.
    
    Args:
        parent: Übergeordnetes Widget
        start_date: Frühestes wählbares Datum
        end_date: Spätestes wählbares Datum  
        current_date: Aktuell ausgewähltes Datum
    """
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
    """Hauptdialog für die Konfiguration von Event-Planungsregeln.
    
    Ermöglicht die Definition komplexer Planungsregeln für Events einer Location:
    - Mehrere Planungsregeln mit verschiedenen Parametern
    - Zeitintervalle und Wiederholungen
    - Cast-Regeln für Events am gleichen Tag
    - Validierung und Speicherung der Konfiguration
    
    Args:
        parent: Übergeordnetes Widget
        location_plan_period_id: ID der LocationPlanPeriod für die Events geplant werden
        first_day_from_weekday: Ob Starttag über Wochentag oder Kalender gewählt wird
    """
    
    # Spalten-Indizes für die Regel-Tabelle
    class ColumnIndex:
        """Definiert die Spalten-Indizes für die Regel-Grid-Tabelle."""
        FIRST_DAY = 0
        TIME_OF_DAY = 1
        INTERVAL = 2
        REPETITIONS = 3
        POSSIBLE_COUNT = 4
        REMOVE_BUTTON = 5
    
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

    def _setup_ui(self) -> None:
        """Initialisiert die Benutzeroberfläche des Dialogs.
        
        Erstellt alle UI-Elemente und Layout-Strukturen für die
        Konfiguration der Event-Planungsregeln.
        """
        self._create_main_layout()
        self._setup_header_section()
        self._setup_rules_grid_section()
        self._setup_special_rules_section()
        self._setup_button_section()
        self._initialize_rules()
        
    def _create_main_layout(self) -> None:
        """Erstellt die Haupt-Layout-Struktur."""
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
        
    def _setup_header_section(self) -> None:
        """Erstellt den Header-Bereich mit Beschreibung."""
        self.lb_description = QLabel()
        self.layout_head.addWidget(self.lb_description)
        
    def _setup_rules_grid_section(self) -> None:
        """Erstellt die Grid-Tabelle für Regeln mit Header-Labels."""
        for column, text in enumerate(self.header_text):
            lb_text = QLabel(text)
            lb_text.setStyleSheet("font-weight: bold; background-color: #00123a; "
                                  "padding-left: 5px; padding-right: 5px; padding-top: 10px; padding-bottom: 10px;")
            self.layout_body.addWidget(lb_text, 0, column)

    def _setup_special_rules_section(self) -> None:
        """Erstellt den Bereich für spezielle Regel-Optionen."""
        # Same Day Rules
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
        
        # Same Partial Days Checkbox
        self.chk_same_partial_days = QCheckBox(self.tr('Same day selection for all rules'))
        self.chk_same_partial_days.setToolTip(
            self.tr('When this option is enabled,\n'
                    'the events defined by the rules will be grouped\n'
                    'so that they are created on the same days.')
        )
        self.chk_same_partial_days.setDisabled(True)
        self.chk_same_partial_days.toggled.connect(self._set_text_description_to_default)
        self.layout_special_rules.addWidget(self.chk_same_partial_days)

    def _setup_button_section(self) -> None:
        """Erstellt den Button-Bereich am unteren Ende des Dialogs."""
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
        
    def _initialize_rules(self) -> None:
        """Initialisiert die Regeln basierend auf gespeicherten Daten."""
        if self._event_planing_rules:
            self._setup_rules_from_data()
        else:
            self._add_rule()
        self.lb_description.setText(self._text_description)

    def _show_calendar(self, rule_index: int) -> None:
        """Zeigt Kalender-Dialog zur Datumsauswahl für eine Regel.
        
        Args:
            rule_index: Index der Regel, für die das Datum gewählt wird
        """
        dlg = DlgFirstDay(self, self.plan_period.start, self.plan_period.end,
                          current_date=self._rules_data[rule_index].first_day)
        if dlg.exec():
            self.widgets_for_rules[rule_index][self.header_text_first_day].setText(date_to_string(dlg.first_day))
            self._rules_data[rule_index].first_day = dlg.first_day
            self._spinbox_repeat_changed(rule_index)
            self._update_ui_state()

    def _setup_data(self) -> None:
        """Initialisiert die Datenstrukturen und lädt bestehende Regeln.
        
        Lädt Location-Plan-Period Daten, konfiguriert Header-Texte
        und initialisiert die Widget-Verwaltungsstrukturen.
        """
        self.header_text_first_day = self.tr('First Day')
        self.header_text_time_of_day = self.tr('Time of Day')
        self.header_text_interval = self.tr('Interval')
        self.header_text_repetitions = self.tr('Repetitions')
        self.header_text_possible_count = self.tr('Possible Count')
        try:
            self.location_plan_period = db_services.LocationPlanPeriod.get(self.location_plan_period_id)
        except Exception as e:
            QMessageBox.critical(self, self.tr('Error'), 
                               self.tr('Could not load location plan period: {error}').format(error=str(e)))
            raise
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
        
        # RuleDataModel Instanziierung für Phase 3.2
        self.data_model = RuleDataModel.load_from_config(
            location_plan_period_id=self.location_plan_period_id,
            first_day_from_weekday=self.first_day_from_weekday,
            rules_handler=self.rules_handler
        )
        if self._event_planing_rules:
            self._text_description = (
                self._text_description_default +
                self.tr('<br>Rules were loaded from a previously stored configuration.'))
            for i, rules_data in enumerate(self._event_planing_rules.planning_rules, start=1):
                try:
                    time_of_day = db_services.TimeOfDay.get(rules_data.time_of_day_id, True)
                except Exception as e:
                    QMessageBox.warning(self, self.tr('Warning'), 
                                      self.tr('Could not load time of day data: {error}').format(error=str(e)))
                    raise
                self._rules_data_from_config[i] = RulesData(
                    first_day=n_th_weekday_of_period(self.plan_period.start,
                                                     self.plan_period.end,
                                                     rules_data.first_day.weekday(),
                                                     1),
                    time_of_day=time_of_day,
                    interval=rules_data.interval,
                    repeat=rules_data.repeat,
                    num_events=rules_data.num_events)

    def _add_rule(self) -> None:
        """Fügt eine neue Regel zur UI hinzu."""
        rule_index = max(self.widgets_for_rules.keys()) + 1 if self.widgets_for_rules else 1
        self.widgets_for_rules[rule_index] = {}
        for column, (text, widget) in enumerate(zip(self.header_text, self.rules_widgets)):
            self.layout_body.addWidget(curr_widget := widget(rule_index), rule_index, column)
            self.widgets_for_rules[rule_index][text] = curr_widget
        self._update_ui_state()

    def _remove_rule(self, rule_index: int) -> None:
        """Entfernt eine Regel aus der UI."""
        for widget in self.widgets_for_rules[rule_index].values():
            widget.deleteLater()
        del self.widgets_for_rules[rule_index]
        del self._rules_data[rule_index]
        self._update_ui_state()
        
    def _update_ui_state(self) -> None:
        """Aktualisiert den gesamten UI-Zustand basierend auf aktuellen Regeln."""
        self._update_same_day_controls()
        self._update_partial_days_checkbox()
        
    def _update_same_day_controls(self) -> None:
        """Aktualisiert Same-Day-Rule Controls basierend auf Anzahl Regeln."""
        has_multiple_rules = len(self._rules_data) > 1
        self.combo_rule_same_day.setEnabled(has_multiple_rules)
        self.bt_rule_same_day.setEnabled(has_multiple_rules)
        
        if not has_multiple_rules:
            self.combo_rule_same_day.setCurrentIndex(0)
            
    def _update_partial_days_checkbox(self) -> None:
        """Aktualisiert Partial-Days Checkbox basierend auf Regel-Kompatibilität."""
        if len(self._rules_data) <= 1:
            if self.chk_same_partial_days.isEnabled():
                self.chk_same_partial_days.setChecked(False)
                self.chk_same_partial_days.setDisabled(True)
            return
            
        # Prüfe ob alle Regeln kompatibel sind für Same Partial Days
        if not self._rules_data:
            return
            
        min_rule_index = min(self._rules_data.keys())
        reference_rule = self._rules_data[min_rule_index]
        
        all_rules_compatible = all(
            r.first_day == reference_rule.first_day
            and r.num_events == reference_rule.num_events
            and r.interval == reference_rule.interval
            for r in self._rules_data.values()
        )
        
        no_full_overlap = all(
            r.repeat + 1 != r.num_events for r in self._rules_data.values()
        )
        
        if all_rules_compatible and no_full_overlap:
            self.chk_same_partial_days.setEnabled(True)
        else:
            self.chk_same_partial_days.setChecked(False)
            self.chk_same_partial_days.setDisabled(True)

    def _setup_rules_from_data(self) -> None:
        """Lädt und konfiguriert Regeln aus gespeicherten Daten.
        
        Erstellt UI-Widgets basierend auf den Daten aus _rules_data_from_config
        und stellt die ursprünglichen Werte wieder her.
        """
        for _ in self._rules_data_from_config:
            self._add_rule()
        for rule_index, rule_data in self._rules_data_from_config.items():
            for column, (text, widget) in enumerate(zip(self.header_text, self.widgets_for_rules[rule_index].values())):

                if column == self.ColumnIndex.FIRST_DAY:
                    if isinstance(widget, QPushButton):
                        widget.setText(date_to_string(rule_data.first_day))
                        self._rules_data[rule_index].first_day = rule_data.first_day
                    elif isinstance(widget, FirstDayFromWeekday):
                        widget.set_date(rule_data.first_day)
                elif column == self.ColumnIndex.TIME_OF_DAY:
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
                elif column == self.ColumnIndex.INTERVAL:
                    widget.setValue(rule_data.interval)
                elif column == self.ColumnIndex.REPETITIONS:
                    widget.setValue(rule_data.repeat)
                elif column == self.ColumnIndex.POSSIBLE_COUNT:
                    widget.setValue(rule_data.num_events)
        self.chk_same_partial_days.setChecked(
            self._event_planing_rules.same_partial_days_for_all_rules)
        if self._event_planing_rules.cast_rule_at_same_day_id:
            try:
                cast_rule = db_services.CastRule.get(self._event_planing_rules.cast_rule_at_same_day_id)
                if (idx := self.combo_rule_same_day.findData(cast_rule)) != -1:
                    self.combo_rule_same_day.setCurrentIndex(idx)
            except Exception as e:
                QMessageBox.warning(self, self.tr('Warning'), 
                                  self.tr('Could not load saved cast rule: {error}').format(error=str(e)))

    def _reset_rule_widgets(self) -> None:
        """Setzt alle Regel-Widgets zurück und erstellt eine neue Standard-Regel.
        
        Entfernt alle existierenden Regeln und erstellt eine neue leere Regel.
        """
        for widgets in self.widgets_for_rules.values():
            for widget in widgets.values():
                widget.deleteLater()
        self.widgets_for_rules.clear()
        self._rules_data.clear()
        self._add_rule()
        self._set_text_description_to_default()


    def _combobox_time_of_day(self, rule_index: int) -> QComboBoxToFindData:
        """Erstellt ComboBox für Tageszeit-Auswahl einer Regel.
        
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            
        Returns:
            QComboBoxToFindData: Konfigurierte ComboBox mit verfügbaren Tageszeiten
        """
        combobox = QComboBoxToFindData()
        times_of_day = sorted(self.location_plan_period.time_of_days,
                                  key=lambda x: (x.time_of_day_enum.time_index, x.start))
        for time_of_day in times_of_day:
            combobox.addItem(time_of_day.name, time_of_day)
        combobox.currentIndexChanged.connect(partial(self._combobox_time_of_day_changed,rule_index))
        self._rules_data[rule_index].time_of_day = times_of_day[0]
        return combobox

    def _button_first_day(self, rule_index: int) -> QPushButton:
        """Erstellt Button zur Kalender-basierten Datumsauswahl.
        
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            
        Returns:
            QPushButton: Button der einen Kalender-Dialog öffnet
        """
        button = QPushButton(date_to_string(self.plan_period.start))
        button.clicked.connect(partial(self._show_calendar, rule_index))
        self._rules_data[rule_index].first_day = self.plan_period.start
        return button

    def _widget_first_day_from_weekday(self, rule_index: int) -> FirstDayFromWeekday:
        """Erstellt Widget für Wochentag-basierte Datumsauswahl.
        
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            
        Returns:
            FirstDayFromWeekday: Widget für Wochentag-Auswahl
        """
        widget = FirstDayFromWeekday(self, self.plan_period.start, self.plan_period.end)
        widget.signal_first_day_changed.connect(partial(self._first_day_from_weekday_changed, rule_index))
        self._rules_data[rule_index].first_day = widget.curr_date
        return widget

    def _spinbox_interval(self, rule_index: int) -> QSpinBox:
        """Erstellt SpinBox für die Intervall-Auswahl einer Regel.

        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird

        Returns:
            QSpinBox: SpinBox für die Intervall-Auswahl
        """
        spinbox = QSpinBox()
        spinbox.setMinimum(1)
        spinbox.valueChanged.connect(partial(self._spinbox_interval_changed, rule_index))
        self._rules_data[rule_index].interval = 1
        return spinbox

    def _spinbox_repeat(self, rule_index: int) -> QSpinBox:
        """Erstellt SpinBox für die Wiederholungs-Auswahl einer Regel.

        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird

        Returns:
            QSpinBox: SpinBox für die Wiederholungs-Auswahl
        """
        spinbox = QSpinBox()
        spinbox.setMinimum(0)
        spinbox.valueChanged.connect(lambda: self._spinbox_repeat_changed(rule_index))
        self._rules_data[rule_index].repeat = 0
        return spinbox

    def _spinbox_num_events(self, rule_index: int) -> QSpinBox:
        """Erstellt SpinBox für die Anzahl-Auswahl einer Regel.

        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird

        Returns:
            QSpinBox: SpinBox für die Anzahl-Auswahl
        """
        spinbox = QSpinBox()
        spinbox.setMinimum(1)
        spinbox.valueChanged.connect(lambda: self._spinbox_num_events_changed(rule_index))
        self._rules_data[rule_index].num_events = 1
        return spinbox

    def _bt_remove_rule(self, rule_index: int) -> QPushButton:
        """Erstellt Button zum Entfernen einer Regel.

        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird

        Returns:
            QPushButton: Button zum Entfernen einer Regel
        """
        button = QPushButton(icon=QIcon(os.path.join(os.path.dirname(__file__), 
                                                     'resources/toolbar_icons/icons/cross.png')))
        button.setToolTip(self.tr('Remove rule'))
        button.clicked.connect(partial(self._remove_rule, rule_index))
        return button

    def _spinbox_repeat_changed(self, rule_index: int, *args) -> None:
        """Wird ausgelöst, wenn sich die Wiederholungs-Auswahl, die Anzahl-Auswahl oder das Intervall ändert.
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            args: Weitere Argumente, die nicht verwendet werden
        """
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
        self._update_ui_state()

    def _spinbox_num_events_changed(self, rule_index: int, *args) -> None:
        """Wird ausgelöst, wenn sich die Anzahl-Auswahl ändert.
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            args: Weitere Argumente, die nicht verwendet werden
        """
        widget_num_events = self.widgets_for_rules[rule_index][self.header_text_possible_count]
        repeats = self.widgets_for_rules[rule_index][self.header_text_repetitions].value()
        if widget_num_events.value() > repeats + 1:
            widget_num_events.setValue(repeats + 1)
        self._set_text_description_to_default()
        self._rules_data[rule_index].num_events = widget_num_events.value()
        self._update_ui_state()

    def _combobox_time_of_day_changed(self, rule_index: int, *args) -> None:
        """Wird ausgelöst, wenn sich die Tageszeit-Auswahl ändert.
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            args: Weitere Argumente, die nicht verwendet werden
        """
        combobox = self.widgets_for_rules[rule_index][self.header_text_time_of_day]
        self._rules_data[rule_index].time_of_day = combobox.currentData()
        self._set_text_description_to_default()

    def _spinbox_interval_changed(self, rule_index: int, value: int) -> None:
        """Wird ausgelöst, wenn sich die Intervall-Auswahl ändert.
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            value: Neuer Wert der SpinBox
        """
        self._rules_data[rule_index].interval = value
        self._spinbox_repeat_changed(rule_index)
        self._update_ui_state()

    def _first_day_from_weekday_changed(self, rule_index: int, date: datetime.date) -> None:
        """Wird ausgelöst, wenn sich der Starttag über Wochentag-Auswahl ändert.
        Args:
            rule_index: Index der Regel, für die das Widget erstellt wird
            date: Neuer Starttag
        """
        self._rules_data[rule_index].first_day = date
        self._spinbox_repeat_changed(rule_index)
        self._update_ui_state()
        self._set_text_description_to_default()

    def _combo_rule_same_day_add_items(self) -> None:
        """Fügt die verfügbaren Cast-Rules zur ComboBox hinzu."""
        self.combo_rule_same_day.clear()
        self.combo_rule_same_day.addItem(self.tr('No rule'), None)
        try:
            rules = sorted((cr for cr in db_services.CastRule.get_all_from__project(self.plan_period.team.project.id)
                            if not cr.prep_delete),
                           key=lambda x: x.name)
        except Exception as e:
            QMessageBox.critical(self, self.tr('Error'),
                               self.tr('Could not load cast rules: {error}').format(error=str(e)))
            raise
        for i, rule in enumerate(rules, start=1):
            self.combo_rule_same_day.addItem(QIcon(os.path.join(os.path.dirname(__file__),
                                                             'resources/toolbar_icons/icons/foaf.png')),
                                          rule.name, rule)



    def _add_rule_same_day(self) -> None:
        """Erstellt eine neue Cast-Regel für die Regelung der Events am selben Tag."""
        dlg = frm_cast_rule.DlgCreateCastRule(self, self.plan_period.team.project.id)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self._combo_rule_same_day_add_items()
        else:
            dlg.controller.undo_all()

    @property
    def planning_rules(self) -> Rules:
        """Gibt die aktuellen Planungsregeln zurück."""
        return Rules(rules_data=list(self._rules_data.values()),
                     cast_rule_at_same_day=self.combo_rule_same_day.currentData(),
                     same_partial_days_for_all_rules=self.chk_same_partial_days.isChecked())

    def _set_text_description_to_default(self) -> None:
        """Setzt die Beschreibung auf den Standard-Text zurück."""
        if self._event_planing_rules:
            self.lb_description.setText(self._text_description_default)

    def _save_rules(self) -> None:
        """Speichert die aktuellen Planungsregeln über das RuleDataModel.
        
        Synchronisiert GUI-Daten in das RuleDataModel und verwendet
        dessen save_to_config() Methode für die Persistierung.
        """
        # Sync GUI-Daten in das data_model
        self._sync_rules_to_data_model()

        # Extrahiere GUI-spezifische Parameter
        cast_rule_at_same_day_id = (
            self.combo_rule_same_day.currentData().id
            if self.combo_rule_same_day.currentIndex() > 0 else None
        )
        same_partial_days_for_all_rules = self.chk_same_partial_days.isChecked()

        # Verwende RuleDataModel für das Speichern
        self.data_model.save_to_config(cast_rule_at_same_day_id, same_partial_days_for_all_rules)

        # Success-Message (bleibt bei GUI)
        QMessageBox.information(self, self.tr('Planning Rules'),
                                self.tr('Planning rules for "{location}" have been saved for later use.').format(
                                    location=self.location_plan_period.location_of_work.name_an_city))


    def validate_rules(self) -> ValidationResult:
        """Validiert die konfigurierten Planungsregeln über das RuleDataModel.
        
        Verwendet das RuleDataModel für strukturierte Validierung mit
        detaillierten Fehlermeldungen.
        
        Returns:
            ValidationResult: Strukturiertes Validierungsergebnis mit Fehlermeldungen
        """
        # Sync aktuelle _rules_data in das data_model für Validierung
        self._sync_rules_to_data_model()
        
        # Verwende RuleDataModel Validierung
        return self.data_model.validate_rules()
    
    def _sync_rules_to_data_model(self) -> None:
        """Synchronisiert aktuelle _rules_data in das RuleDataModel.
        
        Überträgt alle GUI-Regel-Daten in das RuleDataModel für
        Validierung und weitere Operationen.
        """
        # Leere das data_model und füge aktuelle Regeln hinzu
        self.data_model.rules_data.clear()
        
        for rule_index, rule_data in self._rules_data.items():
            # Füge Regel zum data_model hinzu
            self.data_model.add_rule(rule_data)

    def _events_already_exist(self) -> bool:
        """Prüft ob bereits Events für diese LocationPlanPeriod existieren.
        
        Returns:
            bool: True wenn Events existieren, False wenn keine vorhanden
        """
        events = db_services.Event.get_all_from__location_plan_period(self.location_plan_period_id)
        return len(events) > 0

    def plan_exists(self) -> bool:
        """Prüft ob bereits Pläne für diese PlanPeriod existieren.
        
        Returns:
            bool: True wenn Pläne existieren, False wenn keine vorhanden
        """
        return bool(db_services.Plan.get_all_from__plan_period_minimal(self.plan_period.id))

    def accept(self) -> None:
        """Validiert und bestätigt die Planungsregeln vor Dialog-Schließung.
        
        Führt umfassende Validierung durch und warnt bei bestehenden Events
        oder Plänen vor dem Überschreiben.
        """
        validation_result = self.validate_rules()
        if not validation_result.is_valid:
            QMessageBox.critical(self, self.tr('Planning Rules'), validation_result.error_message)
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
