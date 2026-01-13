import dataclasses
import datetime
import logging
from collections import defaultdict
from functools import partial
from typing import Literal, Callable
from uuid import UUID

from PySide6.QtCore import Qt, Slot, QTimer, QThreadPool, Signal, QDate, QCoreApplication, QLocale
from PySide6.QtGui import QContextMenuEvent, QColor, QMouseEvent, QAction
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout,
                               QHBoxLayout, QMessageBox, QMenu, QAbstractItemView, QDialog, QFormLayout, QGroupBox,
                               QDialogButtonBox, QComboBox, QPushButton, QCheckBox, QLineEdit, QCalendarWidget, QFrame,
                               QScrollArea, QStyle)

from commands import command_base_classes
from commands.command_base_classes import BatchCommand
from commands.database_commands import plan_commands, appointment_commands, max_fair_shifts_per_app, \
    plan_period_commands, event_commands, cast_group_commands
from configuration.general_settings import general_settings_handler
from database import schemas, db_services
from gui import widget_styles
from gui.concurrency import general_worker
from gui.concurrency.general_worker import WorkerGetMaxFairShifts
from gui.custom_widgets import side_menu
from gui.custom_widgets.custom_date_and_time_edit import CalendarLocale
from gui.custom_widgets.progress_bars import DlgProgressInfinite, GlobalUpdatePlanTabsProgressManager, DlgProgressSteps
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from gui.frm_notes import DlgAppointmentNotes
from gui.observer import signal_handling
from gui.widget_styles.plan_table import horizontal_header_colors, vertical_header_colors, locations_bg_color, \
    cell_backgrounds_statistics, horizontal_header_statistics_color, horizontal_header_statistics_color_guest, \
    vertical_header_statistics_color, plan_table_base_style, plan_note_icon_default_style, \
    plan_note_icon_with_notes_style
# solver_main wird lazy importiert bei Bedarf für Performance-Optimierung
from tools.delayed_execution_timer import DelayedTimerSingleShot
from tools.helper_functions import get_appointments_of_all_actors_from_plan, datetime_date_to_qdate, date_to_string, \
    time_to_string, setup_form_help

logger = logging.getLogger(__name__)


def get_weekday_names() -> list[str]:
    """Gibt die lokalisierten Wochentagsnamen zurück.

    Muss zur Laufzeit aufgerufen werden, nachdem die Translator geladen wurden.
    Nicht beim Modul-Import aufrufen, da dann die Übersetzungen noch nicht verfügbar sind.
    """
    return [
        QCoreApplication.translate("WeekDays", "Monday"),
        QCoreApplication.translate("WeekDays", "Tuesday"),
        QCoreApplication.translate("WeekDays", "Wednesday"),
        QCoreApplication.translate("WeekDays", "Thursday"),
        QCoreApplication.translate("WeekDays", "Friday"),
        QCoreApplication.translate("WeekDays", "Saturday"),
        QCoreApplication.translate("WeekDays", "Sunday")
    ]


def fill_in_data(appointment_field: 'AppointmentField'):
    appointment_field.lb_time_of_day.setText(f'{appointment_field.appointment.event.time_of_day.name}: '
                                             f'{time_to_string(appointment_field.appointment.event.time_of_day.start)}'
                                             f'-{time_to_string(appointment_field.appointment.event.time_of_day.end)}')
    employees = '\n'.join([f'{avd.actor_plan_period.person.f_name} {avd.actor_plan_period.person.l_name}'
                           for avd in sorted(appointment_field.appointment.avail_days,
                                             key=lambda x: (x.actor_plan_period.person.f_name,
                                                            x.actor_plan_period.person.l_name))]
                          + appointment_field.appointment.guests)
    nr_required_persons = db_services.CastGroup.get_cast_group_of_event(
        appointment_field.appointment.event.id).nr_actors

    if missing := (nr_required_persons - len(appointment_field.appointment.avail_days)
                   - len(appointment_field.appointment.guests)):
        missing_txt = QCoreApplication.translate("AppointmentField", "unfilled: %d") % missing
        appointment_field.lb_missing.setText(missing_txt)
        appointment_field.layout.addWidget(appointment_field.lb_missing)
    else:
        appointment_field.lb_missing.setParent(None)

    if nr_required_persons:
        appointment_field.lb_employees.setText(employees)
    else:
        appointment_field.lb_employees.setText(f'<i>{appointment_field.appointment.notes or ""}</i>')


class DlgAvailAtDay(QDialog):
    def __init__(self, parent: QWidget, plan_period_id: UUID, date: datetime.date):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Available'))

        self.plan_period_id = plan_period_id
        self.date = date

        self._generate_data()
        self._setup_ui()
        
        # Help-Integration
        setup_form_help(self, "avail_at_day", add_help_button=True)

    def _setup_ui(self):
        self.setStyleSheet('background-color: none')
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(30)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_body.setSpacing(0)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)
        self.group_actors = QGroupBox()
        self.layout_body.addWidget(self.group_actors)
        self.group_actors.setStyleSheet('background-color: #2b2b2b')
        self.layout_actors = QFormLayout(self.group_actors)
        self.layout_actors.setSpacing(10)
        description_text = self.tr('On %s, %s\nthe following employees are available.') % (
            self.weekday_names[self.date.weekday()],
            date_to_string(self.date))
        self.lb_description = QLabel(description_text)
        self.layout_head.addWidget(self.lb_description)

        if not self.actor_time_of_day:
            self.layout_actors.addRow(self.tr('No employees are available.'), QLabel(''))
        else:
            for name, tz in self.actor_time_of_day.items():
                label = QLabel(", ".join(tz))
                self.layout_actors.addRow(f'{name}:', label)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        self.layout_foot.addWidget(self.button_box)

    def _generate_data(self):
        self.weekday_names = get_weekday_names()
        avail_days = sorted(db_services.AvailDay.get_all_from__plan_period_date(self.plan_period_id, self.date),
                            key=lambda x: (x.actor_plan_period.person.full_name,
                                           x.time_of_day.time_of_day_enum.time_index))
        self.actor_time_of_day: defaultdict[str, list[str]] = defaultdict(list)
        for avd in avail_days:
            self.actor_time_of_day[avd.actor_plan_period.person.full_name].append(avd.time_of_day.name)


class DlgGuest(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr('Guest cast'))

        self._setup_layout()
        
        # Help-Integration
        setup_form_help(self, "guest", add_help_button=True)

    def _setup_layout(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)
        self.lb_explanation = QLabel(self.tr('Insert the name of the guest.'))
        self.le_guest = QLineEdit()
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_head.addWidget(self.lb_explanation)
        self.layout_body.addRow(self.tr('Guest cast'), self.le_guest)
        self.layout_foot.addWidget(self.button_box)


class DlgEditAppointment(QDialog):
    def __init__(self, parent: QWidget, appointment: schemas.Appointment,
                 controller: command_base_classes.ContrExecUndoRedo):
        super().__init__(parent=parent)
        self.appointment = appointment
        self.controller = controller
        self._cleanup_cancelled = False
        self._event_properties_commands: list[command_base_classes.Command] = []

        self._setup_ui()
        self._setup_data()

        # Overflow-Prüfung: Wenn mehr Zuweisungen als nr_actors vorhanden sind
        if not self._check_and_fix_avail_day_overflow():
            self._cleanup_cancelled = True
            return

        self._setup_employee_combos()

        # Help-Integration
        setup_form_help(self, "edit_appointment", add_help_button=True)

    def _setup_ui(self):
        self.setStyleSheet('background-color: none;')
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)
        explanation_text = self.tr('Assignments on:\n%s, %s - %s, %s\nHere you can change the cast.') % (
            date_to_string(self.appointment.event.date),
            self.appointment.event.location_plan_period.location_of_work.name,
            self.appointment.event.location_plan_period.location_of_work.address.city,
            self.appointment.event.time_of_day.name)
        self.lb_explanation = QLabel(explanation_text)
        self.layout_head.addWidget(self.lb_explanation)
        self.group_employees = QGroupBox(self.tr('Employees'))
        self.layout_body.addWidget(self.group_employees)
        self.form_employees = QFormLayout(self.group_employees)

        # Button für Event-Eigenschaften
        self.bt_event_properties = QPushButton(self.tr("Event Properties..."))
        self.bt_event_properties.setToolTip(
            self.tr("Edit Fixed Cast, Staff Count, and Preferences for this event")
        )
        self.bt_event_properties.clicked.connect(self.open_event_properties)
        self.layout_body.addWidget(self.bt_event_properties)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.cast_group = db_services.CastGroup.get_cast_group_of_event(self.appointment.event.id)
        self.possible_avail_days = db_services.AvailDay.get_all_from__plan_period__date__time_of_day__location_prefs(
            self.appointment.event.location_plan_period.plan_period.id,
            self.appointment.event.date,
            self.appointment.event.time_of_day.time_of_day_enum.time_index,
            {self.appointment.event.location_plan_period.location_of_work.id}
        )
        self.possible_avail_days.sort(key=lambda x: x.actor_plan_period.person.f_name)

    def _check_and_fix_avail_day_overflow(self) -> bool:
        """
        Prüft ob das Appointment mehr Zuweisungen als nr_actors hat.
        Wenn ja, wird DlgAvailDayCleanup geöffnet.

        Returns:
            True wenn alles ok oder Cleanup erfolgreich, False bei Abbruch
        """
        current_count = len(self.appointment.avail_days) + len(self.appointment.guests)
        if current_count <= self.cast_group.nr_actors:
            return True

        excess = current_count - self.cast_group.nr_actors

        from gui.custom_widgets.dlg_event_properties import DlgAvailDayCleanup

        dlg = DlgAvailDayCleanup(self, self.appointment, self.cast_group.nr_actors, excess)

        if dlg.exec():
            # Appointment neu laden
            self.appointment = db_services.Appointment.get(self.appointment.id)
            return True

        return False

    def _setup_employee_combos(self):
        self.combos_employees = []
        if self.cast_group.nr_actors == 0:
            self.form_employees.addRow(self.tr('No employees are required.'), QLabel(''))
            return
        for i in range(1, self.cast_group.nr_actors + 1):
            self.combos_employees.append(QComboBoxToFindData())
            self.form_employees.addRow(self.tr('Employee %02d') % i, self.combos_employees[-1])
            self.combos_employees[-1].addItem(self.tr('Unassigned'), None)
            for avd in self.possible_avail_days:
                self.combos_employees[-1].addItem(
                    f'{avd.actor_plan_period.person.f_name} {avd.actor_plan_period.person.l_name}',
                    avd.id
                )
            self.combos_employees[-1].addItem(self.tr('Guest'), UUID('00000000000000000000000000000000'))
            self.combos_employees[-1].currentIndexChanged.connect(partial(self.combo_employees_index_changed, i - 1))
        for j, avd in enumerate(self.appointment.avail_days):
            self.combos_employees[j].setCurrentIndex(self.combos_employees[j].findData(avd.id))
        for k, name in enumerate(self.appointment.guests, start=len(self.appointment.avail_days)):
            self.combos_employees[k].addItem(name, UUID('00000000000000000000000000000001'))
            self.combos_employees[k].setCurrentIndex(self.combos_employees[k].findText(name))

    def combo_employees_index_changed(self, index_in_combos_employees: int, curr_index: int):
        if ((combo := self.combos_employees[index_in_combos_employees])
                .currentData() == UUID('00000000000000000000000000000000')):
            dlg = DlgGuest(self)
            if dlg.exec():
                if (idx := combo.findData(UUID('00000000000000000000000000000001'))) == -1:
                    combo.addItem(dlg.le_guest.text(), UUID('00000000000000000000000000000001'))
                    combo.setCurrentIndex(combo.findData(UUID('00000000000000000000000000000001')))
                else:
                    combo.setItemText(idx, dlg.le_guest.text())
                    combo.setCurrentIndex(idx)

    @property
    def new_avail_days(self) -> set[UUID]:
        """Returns a set of avail_day_ids"""
        return {combo.currentData() for combo in self.combos_employees
                if combo.currentData() and combo.currentData() != UUID('00000000000000000000000000000001')}

    @property
    def new_guests(self) -> set[str]:
        """Returns a set of strings"""
        return {combo.currentText() for combo in self.combos_employees
                if combo.currentData() and combo.currentData() == UUID('00000000000000000000000000000001')}
    @property
    def new_cast_clear_text(self) -> str:
        return ', '.join(sorted(combo.currentText() for combo in self.combos_employees if combo.currentData()))

    def open_event_properties(self):
        """Öffnet den DlgEventProperties Dialog für das Event dieses Appointments."""
        from gui.custom_widgets.dlg_event_properties import DlgEventProperties

        location_plan_period = db_services.LocationPlanPeriod.get(
            self.appointment.event.location_plan_period.id
        )

        dlg = DlgEventProperties(
            self,
            self.cast_group,
            location_plan_period,
            self.appointment,
            defer_execution=True  # Commands werden gesammelt, nicht sofort committed
        )

        if dlg.exec():
            # Commands für spätere Ausführung sammeln (bei OK von DlgEditAppointment)
            self._event_properties_commands.extend(dlg.get_pending_commands())

            # Daten neu laden (nr_actors und AvailDays könnten sich geändert haben)
            self.cast_group = db_services.CastGroup.get_cast_group_of_event(
                self.appointment.event.id
            )
            self.appointment = db_services.Appointment.get(self.appointment.id)

            # ComboBoxen neu aufbauen falls nr_actors geändert
            self._rebuild_employee_combos()

    def get_event_properties_commands(self) -> list[command_base_classes.Command]:
        """Gibt die gesammelten Event-Properties-Commands zurück."""
        return self._event_properties_commands.copy()

    def reject(self):
        """Bei Cancel: Event-Properties-Änderungen rückgängig machen."""
        # Pending Event-Properties-Commands rückgängig machen
        for cmd in reversed(self._event_properties_commands):
            cmd._undo()
        self._event_properties_commands.clear()
        super().reject()

    def _rebuild_employee_combos(self):
        """Baut die Mitarbeiter-ComboBoxen neu auf basierend auf aktuellem nr_actors."""
        # Alle Rows aus dem FormLayout entfernen
        while self.form_employees.rowCount() > 0:
            self.form_employees.removeRow(0)

        # ComboBox-Liste leeren
        self.combos_employees.clear()

        # Neu aufbauen
        self._setup_employee_combos()


class DlgMoveAppointment(QDialog):
    def __init__(self, parent: QWidget, appointment: schemas.Appointment, plan_period: schemas.PlanPeriod):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Move appointment'))
        self.appointment = appointment
        self.plan_period = plan_period

        self._generate_data()
        self._setup_ui()
        
        # Help-Integration
        setup_form_help(self, "move_appointment", add_help_button=True)

    def _setup_ui(self):
        self.setStyleSheet("background-color: none")
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(30)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(self.tr(
            'Here you can move the appointment\n'
            '%s, %s (%s)\n'
            'to a different day and time.'
        ) % (
            self.appointment.event.location_plan_period.location_of_work.name_an_city,
            date_to_string(self.appointment.event.date),
            self.appointment.event.time_of_day.name
        ))
        self.layout_head.addWidget(self.lb_description)
        self.calendar_select_date = CalendarLocale()
        self.calendar_select_date.setSelectedDate(datetime_date_to_qdate(self.appointment.event.date))
        self.calendar_select_date.setMinimumDate(datetime_date_to_qdate(self.plan_period.start))
        self.calendar_select_date.setMaximumDate(datetime_date_to_qdate(self.plan_period.end))
        self.layout_body.addWidget(self.calendar_select_date)

        self.combo_time_of_day = QComboBox()
        for time_of_day in self.time_of_days:
            self.combo_time_of_day.addItem(time_of_day.name, time_of_day)
        self.combo_time_of_day.setCurrentIndex(self.combo_time_of_day.findText(self.appointment.event.time_of_day.name))
        self.layout_body.addWidget(self.combo_time_of_day)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _generate_data(self):
        self.time_of_days = db_services.TimeOfDay.get_all_from_location_plan_period(
            self.appointment.event.location_plan_period.id)
        self.time_of_days.sort(key=lambda x: x.time_of_day_enum.time_index)

    @property
    def new_date(self) -> datetime.date:
        return self.calendar_select_date.selectedDate().toPython()

    @property
    def new_time_of_day(self) -> schemas.TimeOfDay:
        return self.combo_time_of_day.currentData()

    def accept(self):
        super().accept()


class LabelLocation(QLabel):
    def __init__(self, parent: QWidget,
                 plan_period_id: UUID,
                 location_of_work: schemas.LocationOfWorkShow,
                 contents_margins: tuple[int, ...], fixed_width: int, word_wrap: bool = True):
        super().__init__(parent=parent)
        self.plan_period_id = plan_period_id
        self.location_of_work = location_of_work
        self.setText(location_of_work.name_an_city)
        self.setContentsMargins(*contents_margins)
        self.setStyleSheet('border-left: 1px solid #4d4d4d; border-right: 1px solid black;')
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedWidth(fixed_width)
        self.setToolTip(self.tr('Click:\nOpen planning mask for %s') % location_of_work.name_an_city)
        self.setWordWrap(word_wrap)

    def mouseReleaseEvent(self, event: QMouseEvent):
        signal_handling.handler_plan_period_tabs.show_location_plan_period(
            self.plan_period_id, self.location_of_work.id)



class LabelDayNr(QLabel):
    def __init__(self, day: datetime.date, plan_period: schemas.PlanPeriod):
        super().__init__()
        self.setObjectName(f'LabelDayNr_{day:%d_%m_%y}')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.day = day
        self.plan_period = plan_period

        self.set_font_and_style()

        self.setText(date_to_string(day))
        self.setToolTip(self.tr('Click: Show availabilities for %s.') % date_to_string(day))

    def set_font_and_style(self):
        self.setContentsMargins(0, 0, 0, 0)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        if self.day.isoweekday() % 2:
            self.setStyleSheet(f'QLabel#{self.objectName()}{{background-color: #71bdff; color: #2b2b2b}}')
        else:
            self.setStyleSheet(f'QLabel#{self.objectName()}{{background-color: #91d2ff; color: #2b2b2b}}')
        font = self.font()
        font.setBold(True)
        self.setFont(font)

    def contextMenuEvent(self, event: QContextMenuEvent):
        ...

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        DlgAvailAtDay(self, self.plan_period.id, self.day).exec()


class DayField(QWidget):
    def __init__(self, day: datetime.date, location_ids_order: list[UUID],
                 location_ids_appointments: dict[UUID, list[schemas.Appointment]] | None,
                 plan_period: schemas.PlanPeriod, appointment_widget_width: int, plan_widget: 'FrmTabPlan'):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)

        self.day = day
        self.location_ids_appointments = location_ids_appointments
        self.location_ids_order = location_ids_order
        self.plan_period = plan_period
        self.appointment_widget_width = appointment_widget_width
        self.plan_widget = plan_widget

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lb_date = LabelDayNr(day, plan_period)
        self.layout.addWidget(self.lb_date)
        self.container_locations = QWidget()
        self.container_locations.setContentsMargins(0, 0, 0, 0)
        self.layout_container_locations = QGridLayout(self.container_locations)
        self.layout_container_locations.setSpacing(0)
        self.layout_container_locations.setContentsMargins(0, 0, 0, 0)
        self.layout.addWidget(self.container_locations)
        self.containers_appointments: dict[int, 'ContainerAppointments'] = {
            i: ContainerAppointments(loc_id, appointment_widget_width) for i, loc_id in enumerate(location_ids_order)}
        self.display_appointment_containers()
        self.display_appointments()

    def display_appointment_containers(self):
        for pos, container in self.containers_appointments.items():
            self.layout_container_locations.addWidget(container, 0, pos)
    def display_appointments(self):
        if not self.location_ids_appointments:
            return
        for loc_id, appointments in self.location_ids_appointments.items():
            for pos, container in self.containers_appointments.items():
                if loc_id == container.location_id:
                    for appointment in sorted(appointments,
                                              key=lambda x: x.event.time_of_day.time_of_day_enum.time_index):
                        container.add_appointment_field(AppointmentField(appointment, self.plan_widget))

    # def set_location_ids_order(self, location_ids_order: list[UUID]):
    #     self.location_ids_order = location_ids_order
    #     if self.containers_appointments:
    #         decision = QMessageBox.question(self, 'Neue Locations-Order',
    #                                         'Es gibt bereits Einrichtungen an diesem Tag.\n'
    #                                         'Trotzdem fortfahren?')
    #         if decision == QMessageBox.StandardButton.No:
    #             return
    #     self.containers_appointments: dict[int, 'ContainerAppointments'] = {
    #         i: ContainerAppointments(loc_id, self.appointment_widget_width)
    #         for i, loc_id in enumerate(location_ids_order)}
    #     for i, container_appointments in self.containers_appointments.items():
    #         self.layout_container_locations.addWidget(container_appointments, 0, i)

    def add_appointment_field(self, appointment_field: 'AppointmentField'):
        for key, container in self.containers_appointments.items():
            if appointment_field.location_id == container.location_id:
                container.add_appointment_field(appointment_field)
                break
        else:
            new_container = ContainerAppointments(appointment_field.location_id, self.appointment_widget_width)
            new_container.add_appointment_field(appointment_field)
            self.containers_appointments[len(self.containers_appointments)] = new_container

            self.layout_container_locations.addWidget(new_container, 0, len(self.containers_appointments))

    def remove_appointment_field(self, appointment_field: 'AppointmentField'):
        for key, container in self.containers_appointments.items():
            if appointment_field.location_id == container.location_id:
                container.remove_appointment_field(appointment_field)
                break

    def display_containers_appointments(self):
        for i in range(self.layout_container_locations.count()):
            self.layout_container_locations.itemAt(i).widget().setParent(None)

        for i, container_appointment in self.containers_appointments.items():
            self.layout_container_locations.addWidget(container_appointment, 0, i)


class ContainerAppointments(QWidget):
    def __init__(self, location_id: UUID, width: int):
        super().__init__()
        self.setContentsMargins(0, 0, 0, 0)
        self.setFixedWidth(width)
        self.location_id = location_id
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)
        self.appointment_fields: list['AppointmentField'] = []

    def add_appointment_field(self, appointment_field: 'AppointmentField'):
        self.appointment_fields.append(appointment_field)
        self.appointment_fields.sort(key=lambda x: x.appointment.event.time_of_day.time_of_day_enum.time_index)
        self.display_appointments_fields()

    def remove_appointment_field(self, appointment_field: 'AppointmentField'):
        self.appointment_fields = [a for a in self.appointment_fields
                                   if a.appointment.id != appointment_field.appointment.id]
        self.display_appointments_fields()

    def display_appointments_fields(self):
        # Alle Items entfernen (inklusive Stretch)
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.spacerItem():  # Stretch-Items explizit löschen
                del item

        for appointment_field in self.appointment_fields:
            self.layout.addWidget(appointment_field)
        self.layout.addStretch()


class ClickableLabel(QLabel):
    """Ein QLabel, das Klick-Events unterstützt."""
    clicked = Signal()
    
    def __init__(self, text: str, parent: QWidget = None):
        super().__init__(text, parent)
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()  # Event konsumieren, damit es nicht zum Parent propagiert
        else:
            super().mouseReleaseEvent(event)


class AppointmentField(QWidget):
    def __init__(self, appointment: schemas.Appointment, plan_widget: 'FrmTabPlan'):
        super().__init__()
        signal_handling.handler_plan_tabs.signal_event_changed.connect(self._event_changed)

        self.setObjectName(str(appointment.id))
        self.plan_widget = plan_widget
        self.appointment = appointment
        self.location_id = appointment.event.location_plan_period.location_of_work.id
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.lb_time_of_day = QLabel()
        self.lb_employees = QLabel()
        self.lb_missing = QLabel()

        self.set_styling()

        self.layout.addWidget(self.lb_time_of_day)
        self.layout.addWidget(self.lb_employees)

        fill_in_data(self)

        # Notiz-Icon Setup
        self._setup_note_icon()

        self.execution_timer_plan_post_cast_change = DelayedTimerSingleShot(200, self._handle_post_cast_change_actions)
        self.batch_command: BatchCommand | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setToolTip(self._tool_tip_text())

    def _setup_note_icon(self):
        """Erstellt und konfiguriert das Notiz-Icon für die obere rechte Ecke."""
        self.lb_note_icon = ClickableLabel('📝', self)
        self.lb_note_icon.setObjectName('note_icon')
        
        # Klick-Handler verbinden
        self.lb_note_icon.clicked.connect(self._edit_notes)
        
        # Styling
        self.lb_note_icon.setStyleSheet(widget_styles.plan_table.appointment_field_note_icon_style)
        
        # Cursor und initialer Zustand
        self.lb_note_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lb_note_icon.setFixedSize(18, 18)
        self.lb_note_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Sichtbarkeit initial setzen
        self._update_note_icon_visibility()
        
        # Position wird in resizeEvent gesetzt
        self._position_note_icon()

    def _update_note_icon_visibility(self):
        """Aktualisiert die Sichtbarkeit des Notiz-Icons basierend auf vorhandenen Notizen."""
        has_notes = bool(self.appointment.notes and self.appointment.notes.strip())
        self.lb_note_icon.setVisible(has_notes)
        
        if has_notes:
            # Tooltip mit der Notiz setzen
            notes = self.appointment.notes.replace('\n', '<br>')
            self.lb_note_icon.setToolTip(
                self.tr('<b>Notes:</b><br>{notes}<br><br><i>Click to edit</i>').format(notes=notes)
            )

    def _position_note_icon(self):
        """Positioniert das Notiz-Icon in der oberen rechten Ecke."""
        if hasattr(self, 'lb_note_icon'):
            # Position: 5px vom rechten Rand, 5px vom oberen Rand
            x = self.width() - self.lb_note_icon.width() - 1
            y = 1
            self.lb_note_icon.move(x, y)
            # Icon über allen anderen Widgets anzeigen
            self.lb_note_icon.raise_()

    def resizeEvent(self, event):
        """Wird aufgerufen wenn das Widget die Größe ändert - positioniert das Notiz-Icon neu."""
        super().resizeEvent(event)
        self._position_note_icon()

    def _tool_tip_text(self):
        return self.tr(
            '<b>%s on %s:</b><br>'
            '◦ Click: Change cast.<br>'
            '◦ Right-click: More actions.<br>'
            '<i><b>Notes:</b><br>%s</i>'
        ) % (
            self.appointment.event.location_plan_period.location_of_work.name_an_city,
            date_to_string(self.appointment.event.date),
            self.appointment.notes or ""
        )

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        dlg = DlgEditAppointment(self, self.appointment, self.plan_widget.controller)
        # Wenn der Cleanup-Dialog abgebrochen wurde, Dialog nicht anzeigen
        if dlg._cleanup_cancelled:
            return
        if dlg.exec():
            # Alle Commands sammeln (Event-Properties + Cast)
            all_commands: list[command_base_classes.Command] = []

            # 1. Event-Properties-Commands (bereits ausgeführt im deferred Mode)
            event_props_commands = dlg.get_event_properties_commands()
            all_commands.extend(event_props_commands)

            # 2. Cast-Commands erstellen (noch nicht ausgeführt)
            cast_commands: list[appointment_commands.UpdateAvailDays | appointment_commands.UpdateGuests] = []
            if (new_avail_days := sorted(dlg.new_avail_days)) != sorted(avd.id for avd in self.appointment.avail_days):
                command_avail_days = appointment_commands.UpdateAvailDays(self.appointment.id, new_avail_days)
                cast_commands.append(command_avail_days)

            if (new_guests := sorted(dlg.new_guests)) != sorted(self.appointment.guests):
                command_guests = appointment_commands.UpdateGuests(self.appointment.id, new_guests)
                cast_commands.append(command_guests)

            all_commands.extend(cast_commands)

            if not all_commands:
                # Keine Änderungen - nichts zu tun
                return

            # Cast-Commands ausführen (Event-Properties sind bereits ausgeführt)
            for cmd in cast_commands:
                cmd.execute()

            # Unified BatchCommand erstellen mit detaillierter Beschreibung
            event_location = self.appointment.event.location_plan_period.location_of_work.name_an_city
            event_date = date_to_string(self.appointment.event.date)
            event_time = self.appointment.event.time_of_day.name

            description_lines = [f"{event_location} - {event_date} ({event_time})"]

            # Event-Properties-Änderungen detailliert aufführen
            for cmd in event_props_commands:
                # Nutze __str__-Methode der Commands (falls vorhanden)
                description_lines.append(f"  • {cmd}")

            # Cast-Änderungen aufführen
            for cmd in cast_commands:
                if isinstance(cmd, appointment_commands.UpdateAvailDays):
                    description_lines.append("  • Besetzung geändert")
                elif isinstance(cmd, appointment_commands.UpdateGuests):
                    description_lines.append("  • Gäste geändert")

            description = "\n".join(description_lines)

            self.batch_command = BatchCommand(self, all_commands, description=description)
            self.batch_command.appointment = self.appointment  # notwendig für undo undo nach automatischer Validierung und für undo/redo Highlighting
            self.plan_widget.controller.add_to_undo_stack(self.batch_command)

            # Appointment neu laden
            if cast_commands:
                # Letztes Command enthält das aktualisierte Appointment
                self.appointment = cast_commands[-1].updated_appointment
            else:
                self.appointment = db_services.Appointment.get(self.appointment.id)

            # UI aktualisieren
            fill_in_data(self)

            if self.plan_widget.permanent_plan_check and cast_commands:
                self._start_plan_check()
            else:
                self.execution_timer_plan_post_cast_change.start_timer()

    def _handle_post_cast_change_actions(self):
        signal_handling.handler_plan_tabs.reload_and_refresh_plan_tab(self.plan_widget.plan.plan_period.id)
        signal_handling.handler_plan_tabs.refresh_specific_plan_statistics_plan(self.plan_widget.plan.id)

    def _start_plan_check(self):
        self.progress_bar = DlgProgressInfinite(self, self.tr('Verification'),
                                                self.tr('Cast changes are being tested for errors.'), self.tr('Cancel'),
                                                signal_handling.handler_solver.cancel_solving)
        self.progress_bar.show()
        # Lazy Import: OR-Tools nur laden wenn Plan-Test benötigt (Performance-Optimierung)
        from functools import partial
        from sat_solver import solver_main
        
        # Versuche gecachte Entities vom TabManager zu holen
        cached_entities = None
        main_window = self.window()
        if hasattr(main_window, 'tab_manager'):
            cached_entities = main_window.tab_manager.get_cached_entities(
                self.plan_widget.plan.plan_period.id
            )
        
        # Wrapper-Funktion die gecachte Entities verwendet
        if cached_entities is not None:
            check_func = partial(solver_main.test_plan, cached_entities=cached_entities)
        else:
            check_func = solver_main.test_plan
        
        worker = general_worker.WorkerCheckPlan(check_func, self.plan_widget.plan.id)
        worker.signals.finished.connect(self.check_finished, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    @Slot(bool, list, list)
    def check_finished(self, success: bool, problems: list[str], infos: list[str]):
        self.progress_bar.close()
        
        # Speichere Referenzen für die Undo-Aktion
        self._check_success = success
        
        # Nicht-modaler Dialog für Validierungsergebnisse
        dlg = DlgValidationResult(
            self, 
            success, 
            problems, 
            infos,
            title=self.tr('Cast Change'),
            show_undo_option=not success  # Undo-Option nur bei Fehlern
        )
        
        # Verbinde Signale
        dlg.undo_requested.connect(self._on_validation_undo)
        dlg.changes_accepted.connect(self._on_validation_accepted)
        
        dlg.show()
    
    def _on_validation_undo(self):
        """Wird aufgerufen wenn der User Undo im Validierungsdialog wählt."""
        self.plan_widget.controller.undo()
        self.appointment = self.batch_command.appointment
        fill_in_data(self)
    
    def _on_validation_accepted(self):
        """Wird aufgerufen wenn der User die Änderungen akzeptiert."""
        self.execution_timer_plan_post_cast_change.start_timer()

    def contextMenuEvent(self, event: QContextMenuEvent):
        context_menu = QMenu(self)
        context_menu.setStyleSheet("background-color: none")
        context_menu.addAction(
            self.tr('Move %s on %s (%s)') % (
                self.appointment.event.location_plan_period.location_of_work.name_an_city,
                date_to_string(self.appointment.event.date),
                self.appointment.event.time_of_day.name
            ),
            self._move_appointment)
        context_menu.addAction(
            self.tr('Notes for %s on %s (%s)') % (
                self.appointment.event.location_plan_period.location_of_work.name_an_city,
                date_to_string(self.appointment.event.date),
                self.appointment.event.time_of_day.name
            ),
            self._edit_notes)
        context_menu.exec(event.globalPos())

    def _move_appointment(self):
        dlg = DlgMoveAppointment(self, self.appointment, self.plan_widget.plan.plan_period)

        if dlg.exec():
            def handle_appointment_move(
                    appointments_in_plan: list[schemas.Appointment],
                    appointment: schemas.Appointment,
                    new_date: datetime.date,
                    new_time_of_day: schemas.TimeOfDay,
                    batch_command_redo_undo_callback: Callable[[signal_handling.DataAppointmentMoved], None],
                    controller: command_base_classes.ContrExecUndoRedo
            ) -> Literal['move', 'flip', 'move_and_delete'] | None:
                """
                Verschiebt das Appointment.
                Aktionen bei Verschiebung eines Appointments:
                * in jedem Fall werden die AvailDays aus dem Appointment entfernt.
                - Verschiebung auf einen Tag, auf dem kein anderes Event ist:
                  Das Ausgangs-Event wird verschoben und bleibt dem Appointment zugeordnet.
                - Verschiebung auf einen Tag, auf dem ein anderes Event der gleichen EventGroup ist:
                  Kein Event wird verändert. Dem Appointment wird das neue Event zugeordnet.
                - Verschiebung auf einen Tag, auf dem ein anderes Event einer anderen EventGroup ist:
                  Das Ausgangs-Event verschoben und bleibt dem Appointment zugeordnet und das Ziel-Event wird gelöscht.
                """

                old_date = appointment.event.date
                old_time_index = appointment.event.time_of_day.time_of_day_enum.time_index
                old_time_of_day_name = appointment.event.time_of_day.name
                old_grand_parent_event_group_id = db_services.EventGroup.get_grand_parent_event_group_id_from_event(
                    appointment.event.id)
                location_plan_period_id = appointment.event.location_plan_period.id
                new_time_index = new_time_of_day.time_of_day_enum.time_index
                new_time_of_day_name = new_time_of_day.name
                target_event = db_services.Event.get_from__location_pp_date_time_index(
                    location_plan_period_id, new_date, new_time_index)
                target_event_id = target_event.id if target_event else None
                target_grand_parent_event_group_id = db_services.EventGroup.get_grand_parent_event_group_id_from_event(
                    target_event_id) if target_event_id else None
                description = (
                    f"Verschiebe {appointment.event.location_plan_period.location_of_work.name_an_city}\n"
                    f"von {date_to_string(old_date)} ({old_time_of_day_name}) "
                    f"nach {date_to_string(new_date)} ({new_time_of_day_name}).\n"
                    f"Entfernen der Cast-Zuweisungen."
                )

                # Prüfe ob Appointment an Zielort bereits existiert
                if [a for a in appointments_in_plan
                    if a.event.date == new_date
                       and a.event.time_of_day.time_of_day_enum.time_index == new_time_of_day.time_of_day_enum.time_index
                       and a.event.location_plan_period.id == appointment.event.location_plan_period.id]:
                    return None

                batch_command = BatchCommand(self, [])
                command_remove_avail_days = appointment_commands.UpdateAvailDays(appointment.id, [])
                command_remove_guests = appointment_commands.UpdateGuests(appointment.id, [])
                # location_columns leeren, damit sie beim Refresh neu generiert werden
                command_reset_location_columns = plan_commands.UpdateLocationColumns(
                    self.plan_widget.plan.id, {})
                batch_command.commands.extend([command_remove_avail_days, command_remove_guests,
                                               command_reset_location_columns])

                data_undo = signal_handling.DataAppointmentMoved(
                    undo=True,
                    event_id=appointment.event.id,
                    old_date=old_date,
                    new_date=new_date,
                    old_time_index=old_time_index,
                    new_time_index=new_time_index,
                    location_plan_period_id=location_plan_period_id
                )
                data_redo = dataclasses.replace(data_undo, undo=False)

                if not target_event_id:
                    # Ziel-Event existiert nicht - verschiebe Ausgangs-Event
                    event_move_command = event_commands.UpdateDateTimeOfDay(appointment.event, new_date, new_time_of_day.id)
                    batch_command.commands.append(event_move_command)
                    batch_command.on_undo_callback = lambda: batch_command_redo_undo_callback(
                        data_undo.set_action_type('move'))
                    batch_command.on_redo_callback = lambda: batch_command_redo_undo_callback(
                        data_redo.set_action_type('move'))
                    batch_command.description = description
                else:
                    if target_grand_parent_event_group_id == old_grand_parent_event_group_id:
                        # Ziel-Event ist Teil derselben EventGroup - ändere Appointment-Zuordnung
                        appointment_flip_event_command = appointment_commands.UpdateEvent(appointment, target_event_id)
                        batch_command.commands.append(appointment_flip_event_command)
                        # Falls die Tageszeit des Ziel-Events von der gewählten abweicht, aktualisiere sie
                        if target_event.time_of_day.id != new_time_of_day.id:
                            event_update_time_of_day_command = event_commands.UpdateTimeOfDay(
                                target_event, new_time_of_day.id)
                            batch_command.commands.append(event_update_time_of_day_command)
                        batch_command.on_undo_callback = lambda: batch_command_redo_undo_callback(
                            data_undo.set_action_type('flip'))
                        batch_command.on_redo_callback = lambda: batch_command_redo_undo_callback(
                            data_redo.set_action_type('flip'))
                        batch_command.description = description

                    else:
                        # Ziel-Event ist Teil einer anderen EventGroup, da Ziel-Event nicht teil eines Appointments ist
                        # - lösche Ziel-Event und verschiebe Ausgangs-Event
                        event_delete_command = event_commands.Delete(target_event_id)
                        event_move_command = event_commands.UpdateDateTimeOfDay(appointment.event, new_date, new_time_of_day.id)
                        batch_command.commands.extend([event_delete_command, event_move_command])
                        batch_command.on_undo_callback = lambda: batch_command_redo_undo_callback(
                            data_undo.set_action_type('move_and_delete'))
                        batch_command.on_redo_callback = lambda: batch_command_redo_undo_callback(
                            data_redo.set_action_type('move_and_delete'))
                        batch_command.description = description

                batch_command.appointment = appointment  # notwendig für undo/redo Highlighting
                controller.execute(batch_command)
                batch_command.on_redo_callback()

                return data_redo.action_type

            def batch_command_redo_undo_callback(data: signal_handling.DataAppointmentMoved):
                signal_handling.handler_plan_tabs.invalidate_entities_cache(
                    self.appointment.event.location_plan_period.plan_period.id)
                signal_handling.handler_location_plan_period.appointment_moved(data)
                signal_handling.handler_location_plan_period.reset_styling_all_configs_at_day(
                    signal_handling.DataLocationPlanPeriodDate(
                        self.appointment.event.location_plan_period.id, date=data.old_date
                    )
                )
                signal_handling.handler_location_plan_period.reset_styling_all_configs_at_day(
                    signal_handling.DataLocationPlanPeriodDate(
                        self.appointment.event.location_plan_period.id, date=data.new_date
                    )
                )
                self.execution_timer_plan_post_cast_change.finished.connect(
                    lambda: signal_handling.handler_plan_tabs.load_entities_from_cache(
                        self.appointment.event.location_plan_period.plan_period.id
                    ),
                    Qt.ConnectionType.SingleShotConnection)
                self.execution_timer_plan_post_cast_change.start_timer()

            result = handle_appointment_move(self.plan_widget.plan.appointments,
                                             self.appointment,
                                             dlg.new_date,
                                             dlg.new_time_of_day,
                                             batch_command_redo_undo_callback,
                                             self.plan_widget.controller)
            if not result:
                QMessageBox.critical(self, self.tr('Move appointment'),
                                     self.tr('On %s (%s)\nan appointment for %s already exists') % (
                                         date_to_string(dlg.new_date),
                                         dlg.new_time_of_day.name,
                                         self.appointment.event.location_plan_period.location_of_work.name_an_city))

    def _edit_notes(self):
        dlg = DlgAppointmentNotes(self, self.appointment)
        if dlg.exec():
            command = appointment_commands.UpdateNotes(self.appointment, dlg.notes)
            self.plan_widget.controller.execute(command)
            self._reload_appointment_and_tooltip()
            QMessageBox.information(self, self.tr('Appointment Notes'),
                                    self.tr('The new notes have been applied.'))
            fill_in_data(self)

    def _reload_appointment_and_tooltip(self):
        self.appointment = db_services.Appointment.get(self.appointment.id)
        self.setToolTip(self._tool_tip_text())
        self._update_note_icon_visibility()

    def set_styling(self):
        self.setStyleSheet(widget_styles.plan_table.appointment_field_default)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setContentsMargins(2, 2, 2, 2)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.lb_time_of_day.setContentsMargins(5, 2, 0, 0)
        self.lb_employees.setContentsMargins(10, 5, 0, 5)
        font_lb_time_of_day = self.lb_time_of_day.font()
        font_lb_employees = self.lb_employees.font()
        font_lb_time_of_day.setPointSizeF(font_lb_time_of_day.pointSize() * 0.8)
        font_lb_employees.setBold(True)
        self.lb_time_of_day.setFont(font_lb_time_of_day)
        self.lb_employees.setFont(font_lb_employees)
        font_lb_missing = self.lb_missing.font()
        font_lb_missing.setPointSizeF(font_lb_missing.pointSize() * 0.8)
        self.lb_missing.setFont(font_lb_missing)
        self.lb_missing.setContentsMargins(5, 0, 0, 2)
        self.lb_missing.setStyleSheet('color: #ff7c00')

    @Slot(UUID, bool)
    def _event_changed(self, event_id: UUID, notes_changed: bool):
        if event_id == self.appointment.event.id:
            logger.info(f'Signal received - _event_changed in AppointmentField {event_id} '
                        f'- Plan {self.plan_widget.plan.name}')
            self._reload_appointment_and_tooltip()
            if notes_changed:
                reply = QMessageBox.question(
                    self, self.tr('Notes changed'),
                    f'Die Anmerkungen des Events\n'
                    f'am {date_to_string(self.appointment.event.date)} ({self.appointment.event.time_of_day.name})\n'
                    f'an {self.appointment.event.location_plan_period.location_of_work.name_an_city}\n'
                    f'wurden geändert.\n'
                    f'Sollen die Änderungen für den entsprechenden Termin im Plan\n'
                    f'{self.plan_widget.plan.name} übernommen werden?')
                if reply == QMessageBox.StandardButton.Yes:
                    appointment_commands.UpdateNotes(self.appointment, self.appointment.event.notes).execute()
                    self._reload_appointment_and_tooltip()
                    fill_in_data(self)


class DlgValidationResult(QDialog):
    """
    Nicht-modaler Dialog zur Anzeige von Validierungsergebnissen.
    
    Zeigt Erfolgs- oder Fehlermeldungen an und bietet optional
    einen Button zur Anzeige von Hinweisen (ValidationInfo).
    
    Bei show_undo_option=True werden statt "Schließen" die Buttons
    "Rückgängig" und "Änderungen behalten" angezeigt.
    """
    
    # Signale für Undo-Entscheidung
    undo_requested = Signal()
    changes_accepted = Signal()
    
    def __init__(self, parent: QWidget, success: bool, problems: list[str], infos: list[str],
                 title: str = None, show_undo_option: bool = False):
        super().__init__(parent)
        self.infos = infos
        self._show_undo_option = show_undo_option
        
        # Nicht-modal
        self.setModal(False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        
        self.setWindowTitle(title or self.tr('Verification of plan'))
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Icon und Haupttext
        header_layout = QHBoxLayout()
        
        icon_label = QLabel()
        icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxInformation if success 
            else QStyle.StandardPixmap.SP_MessageBoxCritical
        )
        icon_label.setPixmap(icon.pixmap(48, 48))
        header_layout.addWidget(icon_label)
        
        if success:
            title_text = self.tr('<h3>No errors were found in this plan.</h3>')
        else:
            title_text = self.tr('<h3>Conflicts were found in this plan.</h3>')
        
        title_label = QLabel(title_text)
        title_label.setWordWrap(True)
        header_layout.addWidget(title_label, 1)
        layout.addLayout(header_layout)
        
        # Details (Probleme) in scrollbarem Bereich
        if problems:
            problems_label = QLabel(self.tr('<h4>Incompatibilities:</h4>'))
            layout.addWidget(problems_label)
            
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setMaximumHeight(300)
            
            problems_content = QLabel("".join(problems))
            problems_content.setWordWrap(True)
            problems_content.setTextFormat(Qt.TextFormat.RichText)
            scroll_area.setWidget(problems_content)
            layout.addWidget(scroll_area)
        
        # Hinweis wenn Infos vorhanden
        if infos:
            info_hint = QLabel(self.tr('<i>There are %n note(s) available.</i>', '', len(infos)))
            info_hint.setWordWrap(True)
            layout.addWidget(info_hint)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if infos:
            btn_show_infos = QPushButton(self.tr('Show notes'))
            btn_show_infos.clicked.connect(self._show_infos)
            button_layout.addWidget(btn_show_infos)
        
        if show_undo_option and not success:
            # Undo-Frage bei Fehlern
            btn_undo = QPushButton(self.tr('Undo'))
            btn_undo.clicked.connect(self._on_undo)
            button_layout.addWidget(btn_undo)
            
            btn_keep = QPushButton(self.tr('Keep changes'))
            btn_keep.clicked.connect(self._on_keep)
            btn_keep.setDefault(True)
            button_layout.addWidget(btn_keep)
        else:
            btn_close = QPushButton(self.tr('Close'))
            btn_close.clicked.connect(self._on_close)
            btn_close.setDefault(True)
            button_layout.addWidget(btn_close)
        
        layout.addLayout(button_layout)
    
    def _show_infos(self):
        """Zeigt die Hinweise in einer separaten MessageBox an."""
        infos_txt = "".join(self.infos)
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Information)
        msg_box.setWindowTitle(self.tr('Notes'))
        msg_box.setText(self.tr('<h3>Notes from plan verification</h3>'))
        msg_box.setInformativeText(infos_txt)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
    
    def _on_undo(self):
        """Undo-Button geklickt."""
        self.undo_requested.emit()
        self.close()
    
    def _on_keep(self):
        """Änderungen behalten geklickt."""
        self.changes_accepted.emit()
        self.close()
    
    def _on_close(self):
        """Normaler Schließen-Button."""
        self.changes_accepted.emit()
        self.close()



class FrmTabPlan(QWidget):
    resize_signal = Signal()
    def __init__(self, parent: QWidget, plan: schemas.PlanShow,
                 update_progress_manager: GlobalUpdatePlanTabsProgressManager):
        super().__init__(parent=parent)

        signal_handling.handler_plan_tabs.signal_reload_plan_from_db.connect(self.reload_specific_plan)
        signal_handling.handler_plan_tabs.signal_reload_and_refresh_plan_tab.connect(self.reload_and_refresh_specific_plan)
        signal_handling.handler_plan_tabs.signal_reload_all_plan_period_plans_from_db.connect(self.reload_plan_period_plan)
        signal_handling.handler_plan_tabs.signal_refresh_all_plan_period_plans_from_db.connect(self.refresh_plan_period_plan)
        signal_handling.handler_plan_tabs.signal_refresh_plan.connect(self.refresh_specific_plan)

        self.plan = plan

        self.general_settings = general_settings_handler.get_general_settings()

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.permanent_plan_check = True

        self.weekday_names = {i: name for i, name in enumerate(get_weekday_names(), start=1)}

        self.layout = QVBoxLayout(self)

        self._generate_plan_data()

        self._setup_table()

        self._setup_side_menu()
        self._setup_bottom_menu()
        self._setup_rating_menu()

        # Hilfe-System Integration
        self._setup_help_integration()
        
        # Plan-Notizen Icon einrichten
        self._setup_plan_note_icon()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resize_signal.emit()
        # Notiz-Icon neu positionieren
        if hasattr(self, 'plan_note_icon'):
            self._position_plan_note_icon()
    
    def _setup_side_menu(self):
        self.side_menu = side_menu.SlideInMenu(self,
                                               250,
                                               10,
                                               'right',
                                               (20, 30, 0, 20),
                                               (130, 205, 203, 100),
                                               True)
        self.chk_permanent_plan_check = QCheckBox(self.tr('Background Verification'))
        self.chk_permanent_plan_check.setToolTip(self.tr('Verification of errors for each cast change.'))
        self.chk_permanent_plan_check.setChecked(True)
        self.chk_permanent_plan_check.toggled.connect(self._chk_permanent_plan_check_toggled)
        self.side_menu.add_check_box(self.chk_permanent_plan_check)
        self.bt_check_plan = QPushButton(self.tr('Verify plan'))
        self.bt_check_plan.clicked.connect(self._check_plan)
        self.side_menu.add_button(self.bt_check_plan)
        self.bt_get_max_fair_shifts = QPushButton(self.tr('Update statistics'))
        self.bt_get_max_fair_shifts.clicked.connect(self._update_statistics)
        self.side_menu.add_button(self.bt_get_max_fair_shifts)
        self.bt_undo = QPushButton('Undo')
        self.bt_undo.clicked.connect(self._undo_shift_command)
        self.side_menu.add_button(self.bt_undo)
        self.bt_redo = QPushButton('Redo')
        self.bt_redo.clicked.connect(self._redo_shift_command)
        self.side_menu.add_button(self.bt_redo)
        # Tooltip-Updates für Undo/Redo-Buttons
        self.controller.set_on_stacks_changed_callback(self._update_undo_redo_tooltips)
        self._update_undo_redo_tooltips()  # Initial-Zustand setzen
        # Rechtsklick-Kontextmenüs für Undo/Redo-History
        self.bt_undo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bt_undo.customContextMenuRequested.connect(self._show_undo_context_menu)
        self.bt_redo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bt_redo.customContextMenuRequested.connect(self._show_redo_context_menu)
        self.bt_refresh = QPushButton(self.tr('Refresh view'))
        self.bt_refresh.clicked.connect(self.reload_and_refresh_plan)
        self.side_menu.add_button(self.bt_refresh)

    def _setup_bottom_menu(self):
        self.bottom_menu = side_menu.SlideInMenu(self,
                                                 215,
                                                 10,
                                                 'bottom',
                                                 (20, 10, 20, 5),
                                                 (130, 205, 203, 100),
                                                 True)
        self.plan_statistics = TblPlanStatistics(self, self, self.plan.id)
        self.bottom_menu.add_widget(self.plan_statistics)

    def _setup_rating_menu(self):
        """Erstellt das linke Slide-In-Menu für die Planbewertung."""
        from gui.plan_rating.rating_widgets import PlanRatingWidget

        self.rating_menu = side_menu.SlideInMenu(
            self,
            menu_size=280,      # Breiter für Karten-Layout
            snap_size=10,
            align='left',       # Linke Seite
            content_margins=(15, 30, 15, 20),
            menu_background=(130, 205, 203, 100),
            pinnable=True
        )

        # Bewertungs-Widget
        self.rating_widget = PlanRatingWidget()
        self.rating_menu.add_widget(self.rating_widget)

        # "Bewertung aktualisieren" Button
        self.bt_calculate_rating = QPushButton(self.tr('Bewertung aktualisieren'))
        self.bt_calculate_rating.setToolTip(self.tr('Berechnet die Qualitätsbewertung des aktuellen Plans'))
        self.bt_calculate_rating.clicked.connect(self._calculate_rating)
        self.rating_menu.add_button(self.bt_calculate_rating)

        # Session-Cache für die Bewertung
        self._cached_rating = None

    def _calculate_rating(self):
        """Startet die manuelle Bewertungsberechnung im Hintergrund."""
        from gui.concurrency import general_worker

        self.bt_calculate_rating.setEnabled(False)
        self.bt_calculate_rating.setText(self.tr('Berechne...'))

        worker = general_worker.WorkerCalculatePlanRating(self.plan)
        worker.signals.finished.connect(self._on_rating_calculated)
        QThreadPool.globalInstance().start(worker)

    @Slot(object)
    def _on_rating_calculated(self, rating):
        """Callback wenn die Bewertung berechnet wurde."""
        # Prüfe ob die Bewertung für diesen Plan ist
        if rating.plan_id != self.plan.id:
            return

        self.rating_widget.set_rating(rating)
        self._cached_rating = rating

        # Container-Größe neu berechnen (wichtig für dynamische Inhalte)
        self.rating_menu._adjust_container_size()

        self.bt_calculate_rating.setEnabled(True)
        self.bt_calculate_rating.setText(self.tr('Bewertung aktualisieren'))

    def _setup_help_integration(self):
        """Integriert das vereinfachte Hilfe-System in das Plan-Formular."""
        from tools.helper_functions import setup_form_help
        setup_form_help(self, "plan", add_help_button=True)

    def _generate_plan_data(self):
        self.appointment_widget_width = self.general_settings.plan_settings.column_width_plan
        self.all_days_of_month = self.generate_all_days()
        self.all_week_nums_of_month = self.generate_all_week_nums_of_month()
        self.week_num_rows = self.generate_week_num_row()
        self.weekday_cols = self.generate_weekday_col()

        self.week_num_weekday = self.generate_week_num_weekday()
        self.weekdays_locations = self.get_weekdays_locations()
        self.column_assignments = self.generate_column_assignments()
        self.day_location_id_appointments = self.generate_day_appointments()

    def _chk_permanent_plan_check_toggled(self, checked: bool):
        self.permanent_plan_check = checked

    def _check_plan(self):
        self.progress_bar = DlgProgressInfinite(self, self.tr('Verification'),
                                                self.tr('Plan is tested for errors.'), self.tr('Cancel'),
                                                signal_handling.handler_solver.cancel_solving)
        self.progress_bar.show()

        # Lazy Import: OR-Tools nur laden wenn Plan-Test benötigt (Performance-Optimierung)
        from functools import partial
        from sat_solver import solver_main
        
        # Versuche gecachte Entities vom TabManager zu holen
        cached_entities = None
        main_window = self.window()
        if hasattr(main_window, 'tab_manager'):
            cached_entities = main_window.tab_manager.get_cached_entities(
                self.plan.plan_period.id
            )
        
        # Wrapper-Funktion die gecachte Entities verwendet
        if cached_entities is not None:
            check_func = partial(solver_main.test_plan, cached_entities=cached_entities)
        else:
            check_func = solver_main.test_plan
        
        worker = general_worker.WorkerCheckPlan(check_func, self.plan.id)
        worker.signals.finished.connect(self._check_finished, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    @Slot(bool, list, list)
    def _check_finished(self, success: bool, problems: list[str], infos: list[str]):
        self.progress_bar.close()
        
        # Nicht-modaler Dialog für Validierungsergebnisse
        dlg = DlgValidationResult(self, success, problems, infos)
        dlg.show()


    def _update_statistics(self):
        num_actor_plan_periods = len(db_services.PlanPeriod.get(self.plan.plan_period.id).actor_plan_periods)
        progress_bar = DlgProgressSteps(self, self.tr('Update statistics'),
                                             self.tr('The cast statistics are being updated.'),
                                             0, num_actor_plan_periods + 1,
                                             self.tr('Cancel'), signal_handling.handler_solver.cancel_solving)
        # Lazy Import: OR-Tools nur laden wenn Fair-Shifts-Berechnung benötigt (Performance-Optimierung)
        from sat_solver import solver_main
        worker = WorkerGetMaxFairShifts(solver_main.get_max_fair_shifts_per_app, self.plan.plan_period.id, 20, 80)
        progress_bar.show()
        worker.signals.finished.connect(self._update_statistics_finished, Qt.ConnectionType.QueuedConnection)
        worker.signals.finished.connect(progress_bar.deleteLater, Qt.ConnectionType.QueuedConnection)
        QThreadPool.globalInstance().start(worker)

    @Slot(object, object)
    def _update_statistics_finished(self, max_shifts: dict[UUID, int], fair_shifts: dict[UUID, float]):
        for app_id in max_shifts:
            max_fair_shifts_create = schemas.MaxFairShiftsOfAppCreate(max_shifts=max_shifts[app_id],
                                                                      fair_shifts=fair_shifts[app_id],
                                                                      actor_plan_period_id=app_id)
            command = max_fair_shifts_per_app.Create(max_fair_shifts_create)
            self.controller.execute(command)
        signal_handling.handler_plan_tabs.refresh_plan_statistics(self.plan.plan_period.id)

    def _undo_shift_command(self):
        command: appointment_commands.UpdateAvailDays | BatchCommand | None = (
            self.controller.get_recent_undo_command())
        if command is None:
            self._undo_redo_no_more_action(self.bt_undo, 'undo')
            return
        if command.appointment:
            appointment = command.appointment
            appointment_field: AppointmentField = self.findChild(AppointmentField, str(appointment.id))
            self._highlight_undo_redo_appointment_field(appointment_field)
            appointment_field.appointment = appointment
            fill_in_data(appointment_field)
        self.controller.undo()
        self._handle_post_undo_redo_actions()

    def _redo_shift_command(self):
        command: appointment_commands.UpdateAvailDays | appointment_commands.UpdateCurrEvent | None = (
            self.controller.get_recent_redo_command())
        if command is None:
            self._undo_redo_no_more_action(self.bt_redo, 'redo')
            return
        if appointment := command.appointment:
            appointment_field: AppointmentField = self.findChild(AppointmentField, str(appointment.id))
            self._highlight_undo_redo_appointment_field(appointment_field)
            appointment_field.appointment = appointment
            fill_in_data(appointment_field)
        self.controller.redo()
        self._handle_post_undo_redo_actions()

    def _highlight_undo_redo_appointment_field(self, appointment_field: AppointmentField):
        """Setzt Highlight auf ein AppointmentField.

        Das Highlight wird automatisch durch refresh_plan() entfernt,
        das nach 1000ms via _handle_post_undo_redo_actions() aufgerufen wird.
        """
        appointment_field.setStyleSheet('background-color: rgba(0, 0, 255, 128);')

    def _handle_post_undo_redo_actions(self):
        if not hasattr(self, '_execution_handler_post_undo_redo'):
            self._execution_handler_post_undo_redo = DelayedTimerSingleShot(
                1000, self._post_undo_redo_actions)
        if self._execution_handler_post_undo_redo.isActive():
            self._execution_handler_post_undo_redo.stop()
        self._execution_handler_post_undo_redo.start_timer()

    def _post_undo_redo_actions(self):
        self.reload_plan()
        self.refresh_plan()
        signal_handling.handler_plan_tabs.refresh_specific_plan_statistics_plan(self.plan.id)

    def _update_undo_redo_tooltips(self):
        """Aktualisiert Tooltips der Undo/Redo-Buttons basierend auf den Command-Stacks."""
        # Undo-Tooltip
        undo_command = self.controller.get_recent_undo_command()
        if undo_command:
            undo_text = f"Rückgängig:\n{str(undo_command)}"
            self.bt_undo.setToolTip(undo_text)
            self.bt_undo.setEnabled(True)
        else:
            self.bt_undo.setToolTip("Keine Aktion zum Rückgängigmachen")
            self.bt_undo.setEnabled(False)

        # Redo-Tooltip
        redo_command = self.controller.get_recent_redo_command()
        if redo_command:
            redo_text = f"Wiederholen:\n{str(redo_command)}"
            self.bt_redo.setToolTip(redo_text)
            self.bt_redo.setEnabled(True)
        else:
            self.bt_redo.setToolTip("Keine Aktion zum Wiederholen")
            self.bt_redo.setEnabled(False)

    def _show_undo_context_menu(self, pos):
        """Zeigt Kontextmenü mit Undo-History (max. 10 Einträge, neueste oben)."""
        undo_stack = self.controller.get_undo_stack()
        if not undo_stack:
            return

        menu = QMenu(self)
        menu.setStyleSheet(widget_styles.context_menu_undo_redo.undo_redo_context_menu_style)
        # Neueste oben: reversed(undo_stack), begrenzt auf 10
        for i, command in enumerate(reversed(undo_stack[-10:])):
            action_text = f"{i + 1}. {str(command)}"
            # Truncate lange Texte
            if len(action_text) > 80:
                action_text = action_text[:77] + "..."
            action: QAction = menu.addAction(action_text)
            # steps_back = Anzahl der Schritte vom Ende des Stacks
            steps_back = i + 1
            action.triggered.connect(partial(self._undo_multiple_steps, steps_back))

        # Hinweis wenn mehr als 10 Aktionen
        if len(undo_stack) > 10:
            menu.addSeparator()
            info_action = menu.addAction(f"... und {len(undo_stack) - 10} weitere")
            info_action.setEnabled(False)

        menu.exec(self.bt_undo.mapToGlobal(pos))

    def _show_redo_context_menu(self, pos):
        """Zeigt Kontextmenü mit Redo-History (max. 10 Einträge, nächste Aktion oben)."""
        redo_stack = self.controller.redo_stack
        if not redo_stack:
            return

        menu = QMenu(self)
        menu.setStyleSheet(widget_styles.context_menu_undo_redo.undo_redo_context_menu_style)
        # Nächste Redo-Aktion oben: reversed(redo_stack), begrenzt auf 10
        for i, command in enumerate(reversed(redo_stack[-10:])):
            action_text = f"{i + 1}. {str(command)}"
            if len(action_text) > 80:
                action_text = action_text[:77] + "..."
            action: QAction = menu.addAction(action_text)
            steps_forward = i + 1
            action.triggered.connect(partial(self._redo_multiple_steps, steps_forward))

        if len(redo_stack) > 10:
            menu.addSeparator()
            info_action = menu.addAction(f"... und {len(redo_stack) - 10} weitere")
            info_action.setEnabled(False)

        menu.exec(self.bt_redo.mapToGlobal(pos))

    def _undo_multiple_steps(self, steps: int):
        """Führt mehrere Undo-Schritte auf einmal aus.

        Nutzt die bestehende _undo_shift_command() Methode, um Code-Duplizierung
        zu vermeiden. Der DelayedTimerSingleShot in _handle_post_undo_redo_actions()
        wird bei jedem Aufruf neu gestartet, sodass refresh_plan() erst nach
        dem letzten Schritt ausgeführt wird.
        """
        undo_stack = self.controller.get_undo_stack()
        if steps > len(undo_stack):
            steps = len(undo_stack)

        for _ in range(steps):
            self._undo_shift_command()

    def _redo_multiple_steps(self, steps: int):
        """Führt mehrere Redo-Schritte auf einmal aus."""
        redo_stack = self.controller.redo_stack
        if steps > len(redo_stack):
            steps = len(redo_stack)

        for _ in range(steps):
            self._redo_shift_command()

    def _undo_redo_no_more_action(self, button: QPushButton, action: Literal['undo', 'redo']):
        def reset_button():
            # Setze den Button-Text und die Farbe zurück
            if action == 'undo':
                button.setText(self._original_undo_bt_text)
                button.setStyleSheet(self._original_undo_bt_style_sheet)
            else:
                button.setText(self._original_redo_bt_text)
                button.setStyleSheet(self._original_redo_bt_style_sheet)

        # Verhindert, dass auch bei mehrfach schnellem Auslösen der Action immer auf das originale Stylesheet
        # und den originalen Button-Text zurückgesetzt wird:
        if action == 'undo':
            if not hasattr(self, '_original_undo_bt_text'):
                self._original_undo_bt_text = button.text()
            if not hasattr(self, '_original_undo_bt_style_sheet'):
                self._original_undo_bt_style_sheet = button.styleSheet()
        if action == 'redo':
            if not hasattr(self, '_original_redo_bt_text'):
                self._original_redo_bt_text = button.text()
            if not hasattr(self, '_original_redo_bt_style_sheet'):
                self._original_redo_bt_style_sheet = button.styleSheet()
        # Ändere den Button-Text und die Farbe
        button.setText(self.tr("No remaining action"))
        button.setStyleSheet("color: red")
        # Timer für 1 Sekunde starten
        QTimer.singleShot(1000, reset_button)

    def reload_plan(self):
        self.plan = db_services.Plan.get(self.plan.id)
        # Plan-Notizen Icon aktualisieren
        if hasattr(self, 'plan_note_icon'):
            self._update_plan_note_icon()

    def refresh_plan(self):
        self.table_plan.deleteLater()
        self._generate_plan_data()
        self._setup_table()
        self.side_menu.raise_()
        self.bottom_menu.raise_()
        self.rating_menu.raise_()
        # Plan-Notizen Icon aktualisieren
        if hasattr(self, 'plan_note_icon'):
            self._update_plan_note_icon()

    def reload_and_refresh_plan(self):
        self.reload_plan()
        self.refresh_plan()

    @Slot(object)
    def reload_specific_plan(self, plan_id: UUID | None):
        if plan_id and self.plan.id == plan_id:
            self.reload_plan()

    @Slot(UUID)
    def refresh_specific_plan(self, plan_id: UUID):
        if plan_id == self.plan.id:
            self.refresh_plan()

    @Slot(UUID)
    def reload_and_refresh_specific_plan(self, plan_period_id: UUID):
        if self.plan.plan_period.id == plan_period_id:
            self.reload_and_refresh_plan()

    @Slot(UUID)
    def refresh_plan_period_plan(self, plan_period_id: UUID):
        if self.plan.plan_period.id == plan_period_id:
            self.refresh_plan()

    @Slot(UUID)
    def reload_plan_period_plan(self, plan_period_id: UUID):
        if self.plan.plan_period.id == plan_period_id:
            self.reload_plan()

    def get_weekdays_locations(self):
        if self.plan.location_columns:
            return {k: [db_services.LocationOfWork.get(u) for u in v]
                    for k, v in self.plan.location_columns.items()}

        weekdays_locations = self.generate_weekdays_locations()

        location_columns = {k: [loc.id for loc in v] for k, v in weekdays_locations.items()}
        plan_commands.UpdateLocationColumns(self.plan.id, location_columns).execute()
        return weekdays_locations

    def generate_weekdays_locations(self):
        weekdays_locations: dict[int, list[schemas.LocationOfWork]] = {weekday_num: [] for weekday_num in self.weekday_names}
        for appointment in self.plan.appointments:
            weekday = appointment.event.date.isoweekday()
            if (appointment.event.location_plan_period.location_of_work.id
                    not in {loc.id for loc in weekdays_locations[weekday]}):
                weekdays_locations[weekday].append(appointment.event.location_plan_period.location_of_work)
        for weekday, locations in weekdays_locations.items():
            weekdays_locations[weekday] = sorted(locations, key=lambda x: (x.name, x.address.city))

        return weekdays_locations

    def generate_week_num_weekday(self):
        kws_wds: defaultdict[int, defaultdict[int, list[schemas.Appointment]]] = defaultdict(lambda: defaultdict(list))
        for appointment in self.plan.appointments:
            week_number, weekday = appointment.event.date.isocalendar()[1:3]
            kws_wds[week_number][weekday].append(appointment)
        for week in kws_wds.values():
            for appointments in week.values():
                appointments.sort(key=lambda x: (x.event.location_plan_period.location_of_work.name,
                                                 x.event.location_plan_period.location_of_work.address.city))
        return kws_wds

    def generate_column_assignments(self):
        column_assignments: defaultdict[int, defaultdict[UUID, int]] = defaultdict(lambda: defaultdict(int))
        curr_column = 0
        for weekday in sorted(self.weekdays_locations.keys()):
            for location in self.weekdays_locations[weekday]:
                column_assignments[weekday][location.id] = curr_column
                curr_column += 1
        return column_assignments

    def _setup_table(self):
        self.table_plan = QTableWidget()
        self.layout.addWidget(self.table_plan)
        num_rows = max(self.week_num_rows.values()) + 1
        num_cols = max(self.weekday_cols.values()) + 1
        self.table_plan.setRowCount(num_rows)
        self.table_plan.setColumnCount(num_cols)
        
        # Basis-Stylesheet für Tabelle
        self.table_plan.setStyleSheet(plan_table_base_style)
        
        self.display_headers_week_day_names()
        self.display_headers_calender_weeks()

        self.table_plan.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table_plan.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.display_headers_locations()
        self.display_days()

        self.resize_table_plan_headers()

    def _setup_plan_note_icon(self):
        """Erstellt das Notiz-Icon für Plan-Notizen"""
        self.plan_note_icon = ClickableLabel("📝", self)
        self.plan_note_icon.setObjectName("plan_note_icon")
        self.plan_note_icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plan_note_icon.setFixedSize(32, 42)
        self.plan_note_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Signal verbinden
        self.plan_note_icon.clicked.connect(self.edit_plan_notes)
        
        # Initial Sichtbarkeit und Style setzen
        self._update_plan_note_icon()
    
    def _update_plan_note_icon(self):
        """Aktualisiert Sichtbarkeit und Style des Notiz-Icons"""
        has_notes = bool(self.plan.notes and self.plan.notes.strip())
        
        # Icon ist immer sichtbar
        self.plan_note_icon.setVisible(True)
        
        if has_notes:
            # Türkiser Hintergrund wenn Notizen vorhanden
            self.plan_note_icon.setStyleSheet(plan_note_icon_with_notes_style)
            
            # Tooltip mit Notizen-Preview
            notes_preview = self.plan.notes[:200] + "..." if len(self.plan.notes) > 200 else self.plan.notes
            notes_preview = notes_preview.replace('\n', '<br>')
            tooltip = self.tr("<b>Notes:</b><br>{notes_preview}<br><br><i>Click to edit</i>").format(
                notes_preview=notes_preview
            )
            self.plan_note_icon.setToolTip(tooltip)
        else:
            # Standard-Style ohne Notizen
            self.plan_note_icon.setStyleSheet(plan_note_icon_default_style)
            self.plan_note_icon.setToolTip("Plan-Notizen erstellen (Klick)")
        
        # Icon neu positionieren
        self._position_plan_note_icon()
    
    def _position_plan_note_icon(self):
        """Positioniert das Notiz-Icon in der oberen linken Ecke"""
        if hasattr(self, 'plan_note_icon') and hasattr(self, 'table_plan'):
            # Position relativ zur Tabelle
            x = self.table_plan.x() + 5
            y = self.table_plan.y() + 5
            self.plan_note_icon.move(x, y)
            self.plan_note_icon.raise_()  # Immer oben anzeigen
    
    def edit_plan_notes(self):
        """Öffnet den Dialog zum Bearbeiten der Plan-Notizen"""
        from gui.frm_notes import DlgPlanPeriodNotes
        
        dlg = DlgPlanPeriodNotes(self, self.plan)
        if dlg.exec():
            # Plan-Notizen speichern
            self.controller.execute(plan_commands.UpdateNotes(self.plan.id, dlg.notes))
            
            # Optional: Auch PlanPeriod-Notizen aktualisieren
            if dlg.chk_sav_to_plan_period.isChecked():
                self.controller.execute(
                    plan_period_commands.UpdateNotes(self.plan.plan_period.id, dlg.notes)
                )
                # Alle Pläne der PlanPeriod neu laden
                signal_handling.handler_plan_tabs.reload_all_plan_period_plans_from_db(
                    self.plan.plan_period.id
                )
            else:
                # Nur aktuellen Plan neu laden
                signal_handling.handler_plan_tabs.reload_plan_from_db(self.plan.id)

    def display_headers_week_day_names(self):
        # funktioniert nur mit app.setStyle(QStyleFactory.create('Fusion'))
        for i, weekday_name in enumerate(self.weekday_names.values()):
            item = QTableWidgetItem(weekday_name)
            item.setBackground(horizontal_header_colors[i % 2])
            self.table_plan.setHorizontalHeaderItem(i, item)

    def display_headers_calender_weeks(self):
        # funktioniert nur mit app.setStyle(QStyleFactory.create('Fusion'))
        first_item = QTableWidgetItem('')
        first_item.setBackground(QColor('#252525'))
        self.table_plan.setVerticalHeaderItem(0, first_item)
        for week_num, i in self.week_num_rows.items():
            item = QTableWidgetItem(f'KW {week_num}')
            item.setBackground(vertical_header_colors[i % 2])
            self.table_plan.setVerticalHeaderItem(i, item)

    def resize_table_plan_headers(self):
        self.table_plan.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_plan.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def generate_all_days(self):
        start, end = self.plan.plan_period.start, self.plan.plan_period.end
        days_between = (end - start).days + 1
        return [start + datetime.timedelta(days=i) for i in range(days_between)]

    def generate_all_week_nums_of_month(self) -> list[int]:
        all_weeks_of_month = []
        for day in self.all_days_of_month:
            if (week_num := day.isocalendar()[1]) not in all_weeks_of_month:
                all_weeks_of_month.append(week_num)
        return all_weeks_of_month

    def generate_week_num_row(self):
        min_week_num = self.all_week_nums_of_month[0]
        week_num_row = {}
        for i, week_num in enumerate(self.all_week_nums_of_month):
            if i == 0 or week_num > self.all_week_nums_of_month[i-1]:
                week_num_row[week_num] = week_num - min_week_num + 1
            else:
                week_num_row[week_num] = week_num + max(self.all_week_nums_of_month) - min_week_num + 1

        return week_num_row

    def generate_weekday_col(self):
        return {weekday: weekday - min(self.weekday_names) for weekday in self.weekday_names}

    def generate_day_appointments(self):
        day_location_id_appointments: defaultdict[datetime.date, defaultdict[UUID, list]] = defaultdict(lambda: defaultdict(list))
        for appointment in self.plan.appointments:
            date = appointment.event.date
            location_id = appointment.event.location_plan_period.location_of_work.id
            day_location_id_appointments[date][location_id].append(appointment)
        return day_location_id_appointments

    def display_days(self):
        for day in self.all_days_of_month:
            row = self.week_num_rows[day.isocalendar()[1]]
            col = self.weekday_cols[day.isoweekday()]
            location_ids_order = [loc.id for loc in self.weekdays_locations[day.isoweekday()]]
            day_field = DayField(day,
                                 location_ids_order,
                                 self.day_location_id_appointments.get(day),
                                 self.plan.plan_period,
                                 self.appointment_widget_width,
                                 self)
            self.table_plan.setCellWidget(row, col, day_field)

    def display_headers_locations(self):
        for weekday, locations in self.weekdays_locations.items():
            container = QWidget()
            container.setContentsMargins(0, 0, 0, 0)
            container.setStyleSheet(f'background-color: {locations_bg_color};')
            container_layout = QHBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(0)
            for location in locations:
                widget = LabelLocation(self, self.plan.plan_period.id, location,
                                       (7, 7, 7, 7),self.appointment_widget_width, True)
                container_layout.addWidget(widget)
            self.table_plan.setCellWidget(0, self.weekday_cols[weekday], container)

    # def display_appointments(self):
    #     for day, location_ids_appointments in self.day_location_id_appointments.items():
    #         row = self.week_num_rows[day.isocalendar()[1]]
    #         col = self.weekday_cols[day.isoweekday()]
    #         day_field = self.table_plan.cellWidget(row, col)
    #         day_field: DayField
    #         day_field.set_location_ids_order([loc.id for loc in self.weekdays_locations[day.isoweekday()]])
    #         for loc_id, appointments in location_ids_appointments.items():
    #             for appointment in appointments:
    #                 day_field.add_appointment_field(
    #                     AppointmentField(appointment, self))



class CustomHeaderView(QHeaderView):
    def __init__(self, parent: 'TblPlanStatistics', orientation, height: int, section_width: int, set_clickable: bool):
        super().__init__(orientation, parent)
        self.parent = parent
        self.setMouseTracking(True)  # Damit mouseMoveEvent auch ohne Mausklick ausgelöst wird
        self.setDefaultSectionSize(section_width)
        self.setFixedHeight(height)
        self.setSectionsClickable(set_clickable)

    def mouseMoveEvent(self, event):
        # Bestimmt, über welcher Spalte sich der Mauszeiger befindet
        index = self.logicalIndexAt(event.pos())
        if index >= 0 and (person_id := self.parent.horizontalHeaderItem(index).data(Qt.ItemDataRole.UserRole)):
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
        # Weitergabe an die Basisklasse
        super().mouseMoveEvent(event)


class TblPlanStatistics(QTableWidget):
    def __init__(self, parent: QWidget, frm_plan: FrmTabPlan, plan_id: UUID):
        super().__init__(parent)

        signal_handling.handler_plan_tabs.signal_refresh_plan_statistics.connect(self.refresh_statistics)
        signal_handling.handler_plan_tabs.signal_refresh_specific_plan_statistics_plan.connect(self._refresh_statistics)

        self.frm_plan = frm_plan
        self.plan_id = plan_id
        self.plan_settings = general_settings_handler.get_general_settings().plan_settings
        custom_header = CustomHeaderView(self,Qt.Orientation.Horizontal,
                                         30, self.plan_settings.column_width_statistics, True)
        self.setHorizontalHeader(custom_header)
        self.horizontalHeader().sectionClicked.connect(self._on_header_clicked)
        self._setup_data()
        self._setup_table()
        self._fill_in_table_cells()

        self.cellClicked.connect(self._on_cell_clicked)
        self.setMouseTracking(True)

    def _on_header_clicked(self, column: int):
        if person_id := self.horizontalHeaderItem(column).data(Qt.ItemDataRole.UserRole):
            signal_handling.handler_plan_period_tabs.show_actor_plan_period(
                self.frm_plan.plan.plan_period.id, person_id)
        else:
            # Das Hauptfenster hat wahrscheinlich neutraleres Styling.
            # window() traversiert die Parent-Widget-Hierarchie nach oben und gibt das oberste Window-Widget zurück
            # (normalerweise das Hauptfenster der Anwendung).
            main_window = self.window()
            QMessageBox.information(main_window, self.tr('Info'),
                                    self.tr('No planning mask found for this person\n'
                                            'Person has guest status.'))

    def _on_cell_clicked(self, row: int, column: int):
        item = self.item(row, column)
        data = item.data(Qt.ItemDataRole.UserRole)
        actor_plan_period: schemas.ActorPlanPeriod = data['app']
        if row == self.row_kind_of_dates['current']:
            self._highlight_set_cell_item(row, column, 'current')
            self._highlight_plan_appointment_fields(row, column)
        elif row == self.row_kind_of_dates['able'] and actor_plan_period:
            self._highlight_set_cell_item(row, column, 'able')
            self._highlight_plan_labels_day_num(row, column)

    def mouseMoveEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item is None:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        elif (item.row(), item.column()) in self.cells_with_action:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _highlight_set_cell_item(self, row: int, column: int, kind: Literal['able', 'current']):
        item = self.item(row, column)
        if self.item_statistics_selected[(row, column)]:
            item.setBackground(self.item_statistics_stylesheets[(row, column)]['bg'])
            item.setForeground(self.item_statistics_stylesheets[(row, column)]['fg'])
            self.item_statistics_selected[(row, column)] = False
        else:
            self.item_statistics_stylesheets[(row, column)]['bg'] = item.background()
            self.item_statistics_stylesheets[(row, column)]['fg'] = item.foreground()
            if kind == 'able':
                item.setBackground(QColor(widget_styles.plan_table.label_day_num_marked_bg))
                item.setForeground(QColor(widget_styles.plan_table.label_day_num_marked_fg))
            else:
                item.setBackground(QColor(widget_styles.plan_table.appointment_field_marked_bg))
            for key in self.item_statistics_selected.keys():
                if self.item_statistics_selected[key] and key[0] == self.row_kind_of_dates[kind]:
                    self.item_statistics_selected[key] = False
                    self.item(*key).setBackground(self.item_statistics_stylesheets[key]['bg'])
                    self.item(*key).setForeground(self.item_statistics_stylesheets[key]['fg'])
            self.item_statistics_selected[(row, column)] = True

    def _highlight_plan_labels_day_num(self, row: int, column: int):
        item = self.item(row, column)
        data = item.data(Qt.ItemDataRole.UserRole)
        actor_plan_period: schemas.ActorPlanPeriod = data['app']
        all_avail_days = db_services.AvailDay.get_all_from__actor_plan_period(actor_plan_period.id)
        for label_day_num in self.frm_plan.findChildren(LabelDayNr):
            label_day_num: LabelDayNr
            label_day_num.setText(self.label_day_text_and_style_sheet[label_day_num.day]['text'])
            label_day_num.setStyleSheet(self.label_day_text_and_style_sheet[label_day_num.day]['style_sheet'])
            if ((avds := sorted([avd for avd in all_avail_days if avd.date == label_day_num.day],
                                key=lambda x: x.time_of_day.time_of_day_enum.time_index))
                    and self.item_statistics_selected[(row, column)]):
                label_day_num.setText(
                    f'{label_day_num.text()} '
                    f'({", ".join([avd.time_of_day.time_of_day_enum.abbreviation for avd in avds])})')
                label_day_num.setStyleSheet(f'QLabel#{label_day_num.objectName()}'
                                            f'{{{widget_styles.plan_table.label_day_num_marked}}}')

    def _highlight_plan_appointment_fields(self, row: int, column: int):
        item = self.item(row, column)
        data = item.data(Qt.ItemDataRole.UserRole)
        actor_plan_period: schemas.ActorPlanPeriod = data['app']
        for appointment_field in self.frm_plan.findChildren(AppointmentField):
            appointment_field.setStyleSheet(widget_styles.plan_table.appointment_field_default)
            appointment_field: AppointmentField
            if self.item_statistics_selected[(row, column)]:
                if actor_plan_period:
                    if actor_plan_period.id in [avd.actor_plan_period.id
                                                for avd in appointment_field.appointment.avail_days]:
                        appointment_field.setStyleSheet(widget_styles.plan_table.appointment_field_marked)
                elif data['name'] in appointment_field.appointment.guests:
                    appointment_field.setStyleSheet(widget_styles.plan_table.appointment_field_marked)

    def _setup_table(self):
        self.setColumnCount(len(self.appointments_of_employees))
        self.setRowCount(4)
        for i, (full_name, (actor_plan_period, _)) in enumerate(self.appointments_of_employees.items()):
            header_item = QTableWidgetItem(full_name)
            if actor_plan_period:
                header_item.setData(Qt.ItemDataRole.UserRole, actor_plan_period.person.id)
                header_item.setBackground(horizontal_header_statistics_color)
                header_item.setToolTip(self.tr('Click:\nOpen planning mask for %s') % full_name)
            else:
                # Gast - andere Hintergrundfarbe für Items ohne UserRole-Daten
                header_item.setBackground(horizontal_header_statistics_color_guest)  # Dunkelgrau für Gäste
                header_item.setToolTip(self.tr('No planning mask found for this person\n'
                                              'Person has guest status.'))
            self.setHorizontalHeaderItem(i, header_item)
        # for i in range(self.columnCount()):
        #     self.setColumnWidth(i, 100)
        self.setVerticalHeaderLabels((self.tr('desired'), self.tr('possible'),
                                      self.tr('fair'), self.tr('assigned')))
        # Background-Color für Vertical-Header-Items
        for i in range(self.rowCount()):
            item = self.verticalHeaderItem(i)
            item.setBackground(vertical_header_statistics_color)
        self.setShowGrid(True)
        self.setGridStyle(Qt.PenStyle.SolidLine)
        self.setStyleSheet("""
            QTableView {
                gridline-color: black;
            }
            QTableView QTableCornerButton::section {
                background-color: transparent;
                border: none;
            }
        """)
        # self.setStyleSheet("QTableView::item { border: 1px solid blue; }")
        self.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        
        # Macht das obere rechte Eckfeld transparent
        self.setCornerButtonEnabled(False)

    def _fill_in_table_cells(self):
        max_fair_shifts_of_app_ids = db_services.MaxFairShiftsOfApp.get_all_from__plan_period_minimal(
            self.frm_plan.plan.plan_period.id)
        for c, (name, (actor_plan_period, appointments)) in enumerate(self.appointments_of_employees.items()):
            requested = actor_plan_period.requested_assignments if actor_plan_period else 0
            if actor_plan_period and (max_fair_shifts := max_fair_shifts_of_app_ids.get(actor_plan_period.id)):
                max_shifts, fair_shifts = max_fair_shifts
            else:
                max_shifts, fair_shifts = len(appointments), len(appointments)
            self._create_item_datas_of_actor(c, requested, 'requested', actor_plan_period, name)
            self._create_item_datas_of_actor(c, max_shifts, 'able', actor_plan_period, name)
            self._create_item_datas_of_actor(c, fair_shifts, 'fair', actor_plan_period, name)
            self._create_item_datas_of_actor(c, len(appointments), 'current', actor_plan_period, name)

    def _create_item_datas_of_actor(self, column: int, num_dates: int | float,
                                    kind: Literal['requested', 'able', 'fair', 'current'],
                                    actor_plan_period: schemas.ActorPlanPeriod | None, full_name: str) -> None:
        # todo: actor_plan_period cachen
        num_dates = f'{num_dates:.2f}' if kind == 'fair' else str(num_dates)
        item = QTableWidgetItem(num_dates)
        item.setData(Qt.ItemDataRole.UserRole, {'app': actor_plan_period, 'name': full_name, 'kind': kind})
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(QColor('black'))
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        color = QColor(self.cell_backgrounds[kind][column % 2])
        item.setBackground(color)
        self.set_tool_tip(item, kind, actor_plan_period, full_name, column)
        # Deaktiviere die Editierbarkeit des Items
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.setItem(self.row_kind_of_dates[kind], column, item)

    def set_tool_tip(self, item: QTableWidgetItem, kind: str, actor_plan_period: schemas.ActorPlanPeriod | None,
                     full_name: str, column: int):
        if kind == 'able' and actor_plan_period:
            item.setToolTip(self.tr('Click:\nMark possible assignments of %s\nin the plan.') % full_name)
            self.cells_with_action.add((self.row_kind_of_dates['able'], column))
        if kind == 'current':
            item.setToolTip(self.tr('Click:\nMark current assignments of %s\nin the plan.') % full_name)
            self.cells_with_action.add((self.row_kind_of_dates['current'], column))

    def _setup_data(self):
        self.appointments_of_employees = get_appointments_of_all_actors_from_plan(self.frm_plan.plan)
        self.cell_backgrounds = cell_backgrounds_statistics
        self.row_kind_of_dates = {'requested': 0, 'able': 1, 'fair': 2, 'current': 3}
        self.label_day_text_and_style_sheet = {lb.day: {'text': lb.text(), 'style_sheet': lb.styleSheet()}
                                               for lb in self.frm_plan.findChildren(LabelDayNr)}
        self.item_statistics_stylesheets: defaultdict[tuple[int, int], dict] = defaultdict(dict)
        self.item_statistics_selected: defaultdict[tuple[int, int], bool] = defaultdict(lambda: False)
        self.cells_with_action = set()

    @Slot(UUID)
    def refresh_statistics(self, plan_period_id: UUID | None):
        if self.frm_plan.plan.plan_period.id == plan_period_id or plan_period_id is None:
            self.clear()
            self.frm_plan.refresh_plan()  # damit eventuell vorhandene Markierungen entfernt werden
            self._setup_data()
            self._setup_table()
            self._fill_in_table_cells()

    @Slot(UUID)
    def _refresh_statistics(self, plan_id: UUID):
        if plan_id == self.plan_id:
            self.refresh_statistics(None)
