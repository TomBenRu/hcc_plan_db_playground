import datetime
from dataclasses import dataclass
from uuid import UUID

from PySide6.QtCore import Signal, QObject

from database import schemas


"""Wenn Signale mittels Lambda-Funktion innerhalb eines QWidgets aufgerufen werden, muss die Verbindung zum Signal vor 
dem Löschen des QWidgets explizit getrennt werden.
Am besten geschieht dies innerhalb der deleteLater()-Methode des QWidgets.
Wenn eine Widget gelöscht werden soll, welches ein Layout mit mehreren QWidgets enthält, die Signalverbindungen über
Lambda-Funktionen enthalten, müssen diese QWidgets kann das Löschen der einzelnen QWidgets am einfachsten mit
gui.tools.clear_layout erfolgen, Bevor das Parent-Widget gelöscht wird."""


@dataclass
class DataActorPPWithDate:
    actor_plan_period: schemas.ActorPlanPeriodShow
    date: datetime.date | None = None


@dataclass
class DataLocationPPWithDate:
    location_plan_period: schemas.LocationPlanPeriodShow
    date: datetime.date | None = None


@dataclass
class DataGroupMode:
    group_mode: bool
    date: datetime.date | None = None
    time_index: int | None = None
    group_nr: int | None = None


@dataclass
class DataPlanEvent:
    """Wenn added==True: Event wurde hinzugefügt.
    Wenn added==False: Event wurde entfernt."""
    plan_id: UUID
    event_id: UUID
    added: bool

@dataclass
class DataDate:
    date: datetime.date | None = None


class HandlerActorPlanPeriod(QObject):

    signal_reload_actor_pp__avail_configs = Signal(object)
    signal_reload_actor_pp__avail_days = Signal(object)
    signal_reload_actor_pp__frm_actor_plan_period = Signal(object)
    signal_change_actor_plan_period_group_mode = Signal(object)

    def reload_actor_pp__avail_configs(self, data: DataActorPPWithDate):
        self.signal_reload_actor_pp__avail_configs.emit(data)

    def reload_actor_pp__avail_days(self, data: DataActorPPWithDate):
        self.signal_reload_actor_pp__avail_days.emit(data)

    def reload_actor_pp__frm_actor_plan_period(self, data: schemas.ActorPlanPeriodShow = None):
        self.signal_reload_actor_pp__frm_actor_plan_period.emit(data)

    def change_actor_plan_period_group_mode(self, group_mode: DataGroupMode):
        self.signal_change_actor_plan_period_group_mode.emit(group_mode)


class HandlerLocationPlanPeriod(QObject):

    signal_reload_location_pp__event_configs = Signal(object)
    signal_reset_styling_fixed_cast_configs = Signal(object)
    signal_reload_location_pp__events = Signal(object)
    signal_reload_location_pp__frm_location_plan_period = Signal(object)
    signal_change_location_plan_period_group_mode = Signal(object)

    def reload_location_pp__event_configs(self, data: DataLocationPPWithDate):
        self.signal_reload_location_pp__event_configs.emit(data)

    def reset_styling_fixed_cast_configs(self, data: DataDate):
        self.signal_reset_styling_fixed_cast_configs.emit(data)

    def reload_location_pp__events(self, data: DataLocationPPWithDate):
        self.signal_reload_location_pp__events.emit(data)

    def reload_location_pp_on__frm_location_plan_period(self, data: schemas.LocationPlanPeriodShow = None):
        self.signal_reload_location_pp__frm_location_plan_period.emit(data)

    def change_location_plan_period_group_mode(self, group_mode: DataGroupMode):
        self.signal_change_location_plan_period_group_mode.emit(group_mode)


class HandlerPlanTabs(QObject):
    signal_event_changed = Signal(object)
    signal_reload_plan_from_db = Signal()

    def event_changed(self, plan_event: DataPlanEvent):
        self.signal_event_changed.emit(plan_event)

    def reload_plan_from_db(self):
        self.signal_reload_plan_from_db.emit()


class HandlerShowDialog(QObject):
    signal_show_dlg_cast_group_pp = Signal()
    signal_show_dlg_event_group = Signal()

    def show_dlg_cast_group_pp(self):
        self.signal_show_dlg_cast_group_pp.emit()

    def show_dlg_event_group(self):
        self.signal_show_dlg_event_group.emit()


class HandlerExcelExport(QObject):
    signal_finished = Signal(bool)

    def finished(self, success: bool):
        self.signal_finished.emit(success)


handler_actor_plan_period = HandlerActorPlanPeriod()
handler_location_plan_period = HandlerLocationPlanPeriod()
handler_plan_tabs = HandlerPlanTabs()
handler_show_dialog = HandlerShowDialog()
handler_excel_export = HandlerExcelExport()
