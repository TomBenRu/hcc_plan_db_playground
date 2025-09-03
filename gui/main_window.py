import functools
import logging
import os.path
import sys
from uuid import UUID

from PySide6.QtCore import QRect, QPoint, Slot, QCoreApplication, QThreadPool, Qt
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent
from PySide6.QtWidgets import (QMainWindow, QMenuBar, QMenu, QWidget, QMessageBox, QInputDialog, QFileDialog,
                               QApplication)
from httplib2 import ServerNotFoundError
from xlsxwriter.exceptions import FileCreateError

from commands import command_base_classes
from commands.database_commands import plan_commands, team_commands, plan_period_commands
from configuration import team_start_config, project_paths
from configuration.google_calenders import curr_calendars_handler
from database import db_services, schemas
from export_to_file import plan_to_xlsx, avail_days_to_xlsx
from export_to_file.avail_days_to_xlsx import export_avail_days_to_xlsx
from google_calendar_api.add_access import add_or_update_access_to_calendar
from google_calendar_api.authenticate import save_credentials
from google_calendar_api.create_calendar import create_new_google_calendar, share_calendar
from google_calendar_api.get_calendars import synchronize_local_calendars, get_calendar_by_id
from google_calendar_api.show_google_calendar import open_google_calendar_in_browser
from google_calendar_api.transfer_appointments import transfer_appointments_with_batch_requests
from google_calendar_api.sync_employee_events import sync_employee_events_to_calendar

from tools import open_file_or_folder
from . import frm_comb_loc_possible, frm_calculate_plan, frm_settings_solver_params, frm_excel_settings
from .concurrency.general_worker import WorkerGeneral
from .frm_appointments_to_google_calendar import DlgSendAppointmentsToGoogleCal
from .frm_create_google_calendar import CreateGoogleCalendar
from .frm_create_project import DlgCreateProject
from .frm_excel_export import DlgPlanToXLSX
from .frm_general_settings import DlgGeneralSettings
from .frm_notes import DlgPlanPeriodNotes, DlgTeamNotes
from .custom_widgets.progress_bars import GlobalUpdatePlanTabsProgressManager, DlgProgressInfinite
from .frm_masterdata import FrmMasterData
from tools.actions import MenuToolbarAction
from .frm_open_plan_period_mask import DlgOpenPlanPeriodMask
from .frm_plan import FrmTabPlan
from .frm_plan_period import DlgPlanPeriodCreate, DlgPlanPeriodEdit
from .frm_project_select import DlgProjectSelect
from .frm_project_settings import DlgSettingsProject
from .frm_remote_access_plan_api import DlgRemoteAccessPlanApi
from .observer import signal_handling
from .tab_manager import TabManager
from .cache.main_window_integration import TabCacheIntegration
from gui.custom_widgets.tabbars import TabBar
from gui.custom_widgets.toolbars import MainToolBar

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow, TabCacheIntegration):
    """
    Hauptfenster der hcc-plan Anwendung.
    
    Diese Klasse koordiniert die UI-Komponenten und delegiert die Tab-Verwaltung
    an den TabManager. Die MainWindow ist verantwortlich für:
    - UI-Koordination und Layout
    - Menu/Toolbar-Management  
    - Dialog-Anzeige
    - Signal-Weiterleitung an entsprechende Handler
    - Tab-Cache Management und Performance-Monitoring
    
    Tab-Management (Öffnen/Schließen/Navigation) wird vollständig vom
    TabManager mit intelligentem Caching übernommen.
    """

    def __init__(self, app: QApplication, screen_width: int, screen_height: int):
        super().__init__()

        self.setWindowTitle('hcc-plan')
        self.setGeometry(QRect(0, 0, screen_width - 100, screen_height - 100))

        # db_services.Project.create('Humor Hilft Heilen')

        # self.project_id = UUID('A2468BCF064F4A69BACFFD00F929671E')
        self._choose_project()
        self.curr_team: schemas.TeamShow | None = None

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.thread_pool = QThreadPool()
        self.worker_general: WorkerGeneral | None = None

        self.global_update_plan_tabs_progress_bar = DlgProgressInfinite(
            self, 'Update Plan-Tabs', 'Die betreffenden geöffneten Pläne werden aktualisiert.', 'Abbruch')
        self.global_update_plan_tabs_progress_manager = GlobalUpdatePlanTabsProgressManager(
            self.global_update_plan_tabs_progress_bar)

        path_to_toolbar_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.actions = {
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'folder-open-table.png'),
                              self.tr('Open... (Planning)'),
                              self.tr('Opens planning data for locations and employees of a specific planning period'),
                              self.open_plan_period_masks),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-document--plus.png'),
                              self.tr('New Planning...'),
                              self.tr('Creates a new planning.'), self.new_plan_period, short_cut='Ctrl+n'),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-document--pencil.png'),
                              self.tr('Edit Planning...'),
                              self.tr('Edit or delete an existing planning.'), self.edit_plan_period),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'gear--pencil.png'),
                              self.tr('Project Settings...'),
                              self.tr('Edit basic project settings'), self.settings_project),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'folder-open-document.png'),
                              self.tr('Open... (Plans)'),
                              self.tr('Opens an existing plan.'), self.open_plan),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'disk.png'),
                              self.tr('Save Plan...'),
                              self.tr('Saves the active plan'),
                              self.plan_save),
            MenuToolbarAction(self, None,
                              self.tr('Excel Settings'),
                              self.tr('Color settings for the exported Excel file...'),
                              self.plan_excel_configs),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'tables.png'),
                              self.tr('Generate Blocked Dates Lists...'),
                              self.tr('Creates lists where employees can enter their blocked dates.'),
                              self.sheets_for_availables),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'download-mac-os.png'),
                              self.tr('Import Data from Online API...'),
                              self.tr('Import data from API'),
                              self.import_from_plan_api),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'table-export.png'),
                              self.tr('Export Plan to Excel...'),
                              self.tr('Exports the active plan to an Excel file'),
                              self.plan_export_to_excel),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-folder-open-table.png'),
                              self.tr('Open Excel Export Folder'),
                              self.tr('Shows current plans and availabilities in Explorer.'),
                              self.lookup_for_excel_plan_folder),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'cross-script.png'),
                              self.tr('Exit Program'),
                              None, self.exit,
                              'Alt+F4'),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'address-book-blue.png'),
                              self.tr('Master Data...'),
                              self.tr('Edit master data of employees and work locations.'),
                              self.master_data),
            MenuToolbarAction(self, None, self.tr('Show Plans'), None, self.show_plans),
            MenuToolbarAction(self, None, self.tr('Show Masks'), None, self.show_masks),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'table-select-cells.png'),
                              self.tr('Export Availability Overview to Excel'),
                              self.tr('Exports an overview of employee availabilities in this planning.'),
                              self.export_avail_days_to_excel),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'chart.png'),
                              self.tr('Employee Assignments Overview'),
                              self.tr('Shows an overview of all employee assignments.'),
                              self.statistics),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-document-attribute-p.png'),
                              self.tr('Create Assignment Plans...'),
                              self.tr('Create one or more assignment plans for a specific period.'),
                              self.calculate_plans),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'notebook--pencil.png'),
                              self.tr('Plan Information...'),
                              self.tr('Create or modify planning information.'),
                              self.plan_infos),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'gear.png'),
                              self.tr('Settings for Plan Creation...'),
                              self.tr('Settings for plan calculation.'),
                              self.plan_calculation_settings),
            MenuToolbarAction(self, None, self.tr('Excel Output Folder...'),
                              self.tr('Set folder for Excel file output'),
                              self.determine_excel_output_folder),
            MenuToolbarAction(self, None, self.tr('Open Log File'),
                              self.tr('Open log file'),
                              self.open_log_file),
            MenuToolbarAction(self, None, self.tr('Permanently Delete Current Team\'s Plans...'),
                              self.tr('The marked plans of the current team will be permanently deleted'),
                              self.plans_of_team_delete_prep_deletes),
            MenuToolbarAction(self, None, self.tr('Events from Plan to Events Mask...'),
                              self.tr('Transfer appointments from active plan to facilities planning mask.'),
                              self.apply_events__plan_to_mask),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'mail-send.png'),
                              self.tr('Send custom Mails...'),
                              self.tr('Send custom emails.'),
                              self.send_custom_emails),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'mail-send.png'),
                              self.tr('Send Bulk Email...'),
                              self.tr('Send bulk emails.'),
                              self.send_bulk_email),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'mail-send.png'),
                              self.tr('Send Plan Notifications...'),
                              self.tr('Send plan notifications.'),
                              self.send_plan_notifications),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'mail-send.png'),
                              self.tr('Send Availability Requests...'),
                              self.tr('Send availability requests.'),
                              self.send_availability_requests),
            MenuToolbarAction(self, None, self.tr('Email Configuration...'),
                              self.tr('Configure email settings.'),
                              self.show_email_config_dialog),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar--arrow.png'),
                              self.tr('Transfer Appointments'),
                              self.tr('Transfer appointments from active plan to Google Calendar'),
                              self.plan_events_to_google_calendar),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar--plus.png'),
                              self.tr('Create Google Calendar'),
                              self.tr('Create a new Google Calendar'),
                              self.create_google_calendar),
            MenuToolbarAction(self, None, self.tr('Synchronize Local Calendar List'),
                              self.tr('Synchronizes the local calendar list with available online Google calendars'),
                              self.synchronize_google_calenders),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar-blue.png'),
                              self.tr('Open Google Calendar...'),
                              self.tr('Opens Google Calendar in browser'),
                              self.open_google_calendar),
            MenuToolbarAction(self, None, self.tr('Import Google API Credentials...'),
                              self.tr('Import Credentials of a Google Calendar for this team from JSON file.'),
                              self.import_google_api_credentials),
            MenuToolbarAction(self, None, self.tr('Upgrade...'),
                              self.tr('To extend "hcc-plan"'),
                              self.upgrade_hcc_plan),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'gear--pencil.png'),
                              self.tr('General Program Settings'),
                              self.tr('General program settings.'),
                              self.general_setting),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'book-question.png'),
                              self.tr('Help...'),
                              self.tr('Opens help in browser.'),
                              self.open_help),
            MenuToolbarAction(self, None, self.tr('Check for Updates...'),
                              self.tr('Checks if program updates are available.'),
                              self.check_for_updates),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'information-italic.png'),
                              self.tr('About...'),
                              self.tr('Information about the program'),
                              self.about_hcc_plan),
            MenuToolbarAction(self, None, self.tr('Show DB Structure...'),
                              self.tr('Shows the database structure.'),
                              self.show_db_structure),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar-task.png'),
                              self.tr('Employee Events...'),
                              self.tr('Manage employee events and activities.'),
                              self.show_employee_events_window),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar--arrow.png'),
                              self.tr('Sync Employee Events...'),
                              self.tr('Synchronize Employee Events to Google Calendar'),
                              self.sync_employee_events_to_google_calendar)
        }
        self.actions: dict[str, MenuToolbarAction] = {a.slot.__name__: a for a in self.actions}
        self.toolbar_actions: list[QAction | None] = [
            self.actions['new_plan_period'],
            self.actions['open_plan'],
            self.actions['plan_save'], None,
            self.actions['plan_export_to_excel'],
            self.actions['export_avail_days_to_excel'],
            self.actions['lookup_for_excel_plan_folder'], None,
            self.actions['master_data'],
            self.actions['show_employee_events_window'], None,
            self.actions['exit']
        ]
        self.menu_actions = {
            self.tr('&File'): [self.actions['open_plan_period_masks'], self.actions['new_plan_period'],
                               self.actions['edit_plan_period'], None, self.actions['sheets_for_availables'], None,
                               self.actions['import_from_plan_api'], None,
                               {
                                   self.tr('Export'): [self.actions['plan_export_to_excel'],
                                                       self.actions['export_avail_days_to_excel']]
                               },
                               self.actions['lookup_for_excel_plan_folder'],
                               None, self.actions['exit']],
            self.tr('&Teams'): [{self.tr('Edit Teams'): [self.put_teams_to__teams_edit_menu]}, None,
                                self._put_clients_to_menu,
                                None, self.actions['master_data']],
            self.tr('&View'): [{'toggle_plans_masks': (self.actions['show_plans'], self.actions['show_masks'])},
                               self.actions['statistics'], None,
                               self.actions['show_employee_events_window']],
            self.tr('&Schedule'): [self.actions['calculate_plans'], self.actions['plan_infos'],
                                   self.actions['plan_excel_configs'], None,
                                   self.actions['open_plan'], self.actions['plan_save'],
                                   self.actions['plans_of_team_delete_prep_deletes'], None,
                                   self.actions['apply_events__plan_to_mask']
                                   ],
            self.tr('&Emails'): [self.actions['send_custom_emails'],
                                 self.actions['send_bulk_email'],
                                 # self.actions['send_plan_notifications'],
                                 # self.actions['send_availability_requests'],
                                 None, self.actions['show_email_config_dialog']],
            self.tr('&Google Calendar'): [self.actions['plan_events_to_google_calendar'],
                                          self.actions['sync_employee_events_to_google_calendar'],
                                          None,
                                          self.actions['open_google_calendar'],
                                          None,
                                          self.actions['create_google_calendar'],
                                          self.actions['synchronize_google_calenders'],
                                          None,
                                          self.actions['import_google_api_credentials']],
            self.tr('E&xtras'): [self.actions['upgrade_hcc_plan'], None,
                                 self.actions['general_setting'],
                                 self.actions['settings_project'],
                                 self.actions['plan_calculation_settings'], None,
                                 self.actions['determine_excel_output_folder'], None,
                                 self.actions['open_log_file']],
            self.tr('&Help'): [self.actions['open_help'], None, self.actions['check_for_updates'], None,
                               self.actions['about_hcc_plan'], None,
                               {self.tr('Expert Mode'): [self.actions['show_db_structure']]}]
        }

        self.toolbar = MainToolBar('Main Toolbar', self.toolbar_actions, icon_size=16)

        self.addToolBar(self.toolbar)

        self.main_menu = self.menuBar()
        self.put_actions_to_menu(self.main_menu, self.menu_actions)

        self.statusBar()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.tabs_left = TabBar(self.central_widget, 'west', 16, 200)
        # Signal wird jetzt vom TabManager verwaltet

        self.widget_planungsmasken = QWidget()
        self.widget_plans = QWidget()

        self.tabs_planungsmasken = TabBar(self.widget_planungsmasken, None, 10, 25, None, True, True)
        self.tabs_planungsmasken.setObjectName('masks')

        self.tabs_plans = TabBar(self.widget_plans, None, 10, 25, None, True,
                                 True, lambda point, index: self.context_menu_tabs_plans(point, index))
        self.tabs_plans.setObjectName('plans')
        self.tabs_left.addTab(self.tabs_planungsmasken, self.tr('Planning masks'))
        self.tabs_left.addTab(self.tabs_plans, self.tr('Schedules'))

        # === TAB MANAGER INTEGRATION ===

        # TabManager instanziieren
        self.tab_manager = TabManager(
            self,
            self.controller,
            self.global_update_plan_tabs_progress_manager
        )

        # TabBars an TabManager übergeben
        self.tab_manager.initialize_tabs(
            self.tabs_left,
            self.tabs_planungsmasken,
            self.tabs_plans
        )

        # TabManager Signals verbinden
        self._connect_tab_manager_signals()

        # === ENDE TAB MANAGER INTEGRATION ===

        self.frm_master_data = None
        self.employee_events_window = None  # Employee Events Window Instance

        self._activate_signals()

        # === CACHE-INTEGRATION SETUP (nach Menu-Erstellung) ===
        self.setup_cache_integration()
        self.connect_cache_signals()

    def _activate_signals(self):
        signal_handling.handler_plan_period_tabs.signal_show_location_plan_period.connect(
            self._show_location_plan_period_mask)
        signal_handling.handler_plan_period_tabs.signal_show_actor_plan_period.connect(
            self._show_actor_plan_period_mask)

    def _connect_tab_manager_signals(self):
        """Verbindet TabManager-Signals mit entsprechenden MainWindow-Methoden"""

        # Tab-Events
        self.tab_manager.tab_opened.connect(self._on_tab_opened)
        self.tab_manager.tab_closed.connect(self._on_tab_closed)
        self.tab_manager.tab_activated.connect(self._on_tab_activated)

        # Config-Events
        self.tab_manager.team_config_saved.connect(self._on_team_config_saved)

        # UI-Update Events
        self.tab_manager.menu_toolbar_update_needed.connect(self._update_menu_toolbar_for_tab_type)
        self.tab_manager.status_message.connect(self.statusBar().showMessage)

        # Error-Events
        self.tab_manager.error_occurred.connect(self._show_error_message)

        # === SIGNALS FÜR INTERNE KOMMUNIKATION ===
        self.tab_manager.plan_export_requested.connect(self.plan_export_to_excel)

    # === TAB MANAGER SIGNAL HANDLERS ===

    @Slot(str, object)
    def _on_tab_opened(self, tab_type: str, widget: object):
        """Handler für geöffnete Tabs"""
        if tab_type == "plan":
            # Plan-Tab geöffnet - weitere Aktionen wenn nötig
            pass
        elif tab_type == "plan_period":
            # Planungsmasken-Tab geöffnet
            pass

    @Slot(str, object)
    def _on_tab_closed(self, tab_type: str, widget: object):
        """Handler für geschlossene Tabs"""
        # Cleanup wenn nötig
        pass

    @Slot(str, object)
    def _on_tab_activated(self, tab_type: str, widget: object):
        """Handler für aktivierte Tabs"""
        # UI-Updates wenn bestimmter Tab aktiv wird
        pass

    @Slot(UUID)
    def _on_team_config_saved(self, team_id: UUID):
        """Handler für gespeicherte Team-Konfiguration"""
        pass

    @Slot(str, str)
    def _show_error_message(self, title: str, message: str):
        """Zeigt Fehlermeldungen an"""
        QMessageBox.critical(self, title, message)

    @Slot(str)
    def _update_menu_toolbar_for_tab_type(self, tab_type: str):
        """Aktualisiert Menü/Toolbar basierend auf aktivem Tab-Typ"""
        menu_plan: QMenu = self.main_menu.findChild(QMenu, self.tr('Schedule'))
        file_menu_name = self.tr('File')

        if tab_type == 'masks':
            menu_plan.setDisabled(True)
            self.actions['show_masks'].setChecked(True)
            for action in menu_plan.actions():
                action.setDisabled(True)
            self.actions['plan_export_to_excel'].setDisabled(True)
            self.actions['new_plan_period'].setEnabled(True)
            self._replace_action_in_menu(
                self.main_menu.findChild(QMenu, file_menu_name),
                self.actions['open_plan'],
                self.actions['open_plan_period_masks']
            )
            self._replace_action_in_toolbar(
                self.toolbar,
                self.actions['open_plan'],
                self.actions['open_plan_period_masks']
            )
            self._replace_action_in_toolbar(
                self.toolbar,
                self.actions['calculate_plans'],
                self.actions['new_plan_period']
            )

        elif tab_type == 'plans':
            menu_plan.setEnabled(True)
            self.actions['show_plans'].setChecked(True)
            for action in menu_plan.actions():
                action.setEnabled(True)
            self.actions['plan_export_to_excel'].setEnabled(True)
            self.actions['new_plan_period'].setDisabled(True)
            self._replace_action_in_menu(
                self.main_menu.findChild(QMenu, file_menu_name),
                self.actions['open_plan_period_masks'],
                self.actions['open_plan']
            )
            self._replace_action_in_toolbar(
                self.toolbar,
                self.actions['open_plan_period_masks'],
                self.actions['open_plan']
            )
            self._replace_action_in_toolbar(
                self.toolbar,
                self.actions['new_plan_period'],
                self.actions['calculate_plans']
            )

    def _choose_project(self):
        start_config = team_start_config.curr_start_config_handler.get_start_config()
        if not db_services.Project.get_all():
            QMessageBox.information(self, 'Projekt',
                                    'Sie haben noch kein Projekt angelegt.\n'
                                    'Legen Sie im folgenden Dialog ein neues Projekt an.')
            self._create_new_project(start_config)
            return
        dlg = DlgProjectSelect(self, start_config.project_id)
        if dlg.exec():
            self.project_id = dlg.project_id
            if dlg.chk_save_for_next_time.isChecked():
                start_config.project_id = self.project_id
                team_start_config.curr_start_config_handler.save_config_to_file(start_config)
        else:
            sys.exit()

    def _create_new_project(self, start_config: team_start_config.StartConfig):
        dlg = DlgCreateProject(self)
        if dlg.exec():
            project = db_services.Project.create(dlg.project_name)
            self.project_id = project.id
            start_config.project_id = self.project_id
            team_start_config.curr_start_config_handler.save_config_to_file(start_config)

    def new_plan_period(self):
        if not db_services.Team.get_all_from__project(self.project_id):
            QMessageBox.critical(self, 'Neuer Planungszeitraum', 'Sie müssen Ihrem Projekt zuerst ein Team hinzufügen.')
            return
        if not db_services.LocationOfWork.get_all_from__project(self.project_id):
            QMessageBox.critical(self, 'Neuer Planungszeitraum',
                                 'Sie müssen Ihrem Projekt zuerst eine Einrichtung hinzufügen.')
            return
        dlg = DlgPlanPeriodCreate(self, project_id=self.project_id)
        dlg.exec()

    def edit_plan_period(self):
        if not db_services.PlanPeriod.get_all_from__project(self.project_id):
            QMessageBox.critical(self, 'Planungszeitraum Ändern', 'Es wurden noch keine Planungszeiträume angelegt.')
            return
        else:
            dlg = DlgPlanPeriodEdit(self, self.project_id)
            if dlg.exec():
                if dlg.delete_plan_period:
                    reply = QMessageBox.question(self, 'Planungsperiode löschen',
                                                 'Wollen Sie diese Planungsperiode wirklich löschen?')
                    if reply == QMessageBox.StandardButton.Yes:
                        self.controller.execute(plan_period_commands.Delete(dlg.cb_planperiods.currentData().id))
                else:
                    self.controller.execute(plan_period_commands.Update(dlg.updated_plan_period))
                    signal_handling.handler_plan_tabs.reload_all_plan_period_plans_from_db(dlg.updated_plan_period.id)

    def open_plan(self):
        """Refactored: Nutzt TabManager"""
        if not self.curr_team:
            QMessageBox.critical(self, 'Aktuelles Team', 'Sie müssen zuerst ein Team auswählen.')
            return

        # TabManager übernimmt die komplette Logik
        self.tab_manager.current_team = self.curr_team  # Team setzen
        self.tab_manager.open_plan_from_dialog()

    def context_menu_tabs_plans(self, point: QPoint, index: int):
        """Delegiert Kontextmenü an TabManager"""
        self.tab_manager.create_plan_context_menu(point, index)

    def delete_plan(self, index: int):
        """Delegiert Plan-Löschung an TabManager"""
        self.tab_manager.delete_plan_tab(index)

    def plans_of_team_delete_prep_deletes(self):
        num_plans_to_delete = len(db_services.Plan.get_prep_deleted_from__team(self.curr_team.id))
        if not num_plans_to_delete:
            QMessageBox.information(self, 'Pläne löschen',
                                    f'Es gibt keine Pläne des Teams "{self.curr_team.name}, '
                                    f'die zum Löschen markiert sind.')
            return

        confirmation = QMessageBox.warning(self, 'Pläne endgültig löschen',
                                           f'Sollen wirklich alle {num_plans_to_delete} zum Löschen markierte Pläne '
                                           f'des Teams "{self.curr_team.name}" endgültig gelöscht werden?\n'
                                           f'Dieser Vorgang kann nicht rückgängig gemacht werden.',
                                           QMessageBox.Yes, QMessageBox.Cancel)
        if confirmation == QMessageBox.Yes:
            db_services.Plan.delete_prep_deletes_from__team(self.curr_team.id)

    def settings_project(self):
        dlg = DlgSettingsProject(self, self.project_id)
        dlg.exec()

    def edit_team(self, team: schemas.Team):
        ...

    def edit_comb_loc_poss(self, team: schemas.Team):
        """Legt die mögl. Einrichtungskombinationen zum aktuellen Datum fest.
        Differenzierungen werden erst bei Person, ActorPlanPeriod u. AvailDay vorgenommen."""
        team = db_services.Team.get(team.id)
        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(self, team, None, None)
        dlg.disable_reset_bt()
        dlg.exec()

    def edit_team_excel_export_settings(self, team: schemas.Team):
        team = db_services.Team.get(team.id)
        project = db_services.Project.get(team.project.id)
        dlg = frm_excel_settings.DlgExcelExportSettings(self, team.excel_export_settings,
                                                        project)
        if dlg.exec():
            if dlg.curr_excel_settings_id == dlg.excel_settings.id:
                db_services.ExcelExportSettings.update(dlg.excel_settings)
            elif dlg.curr_excel_settings_id is None:
                self.controller.execute(
                    team_commands.NewExcelExportSettings(
                        team.id, schemas.ExcelExportSettingsCreate(**dlg.excel_settings.model_dump())
                    )
                )
            else:
                self.controller.execute(
                    team_commands.PutInExcelExportSettings(team.id, dlg.curr_excel_settings_id)
                )

        signal_handling.handler_plan_tabs.reload_plan_from_db()

    def edit_team_notes(self, team: schemas.TeamShow):
        dlg = DlgTeamNotes(self, team)
        if dlg.exec():
            self.controller.execute(team_commands.UpdateNotes(team.id, dlg.notes))

    def plan_excel_configs(self):
        """Minimal angepasst: Nutzt TabManager Properties"""
        plan_widget = self.tab_manager.current_plan_widget
        if not plan_widget:
            QMessageBox.critical(self, 'Excel-Einstellungen', 'Sie müssen zuerst einen Plan öffnen.')
            return

        team = plan_widget.plan.plan_period.team
        dlg = frm_excel_settings.DlgExcelExportSettings(
            self, plan_widget.plan.excel_export_settings, team)
        if dlg.exec():
            if dlg.curr_excel_settings_id == dlg.excel_settings.id:
                db_services.ExcelExportSettings.update(dlg.excel_settings)
            elif dlg.curr_excel_settings_id is None:
                self.controller.execute(
                    plan_commands.NewExcelExportSettings(
                        plan_widget.plan.id, schemas.ExcelExportSettingsCreate(**dlg.excel_settings.model_dump())
                    )
                )
            else:
                self.controller.execute(
                    plan_commands.PutInExcelExportSettings(plan_widget.plan.id, dlg.curr_excel_settings_id)
                )

        signal_handling.handler_plan_tabs.reload_plan_from_db(plan_widget.plan.id)

    def determine_excel_output_folder(self):
        path_handler = project_paths.curr_user_path_handler
        paths = path_handler.get_config()
        output_folder = QFileDialog.getExistingDirectory(
            self, "Ordner auswählen, an dem die Excel-Pläne gespeichert werden sollen", paths.excel_output_path)
        if not output_folder:
            return
        paths.excel_output_path = output_folder
        path_handler.save_config_to_file(paths)

    def open_log_file(self):
        path_handler = project_paths.curr_user_path_handler
        log_file_path = path_handler.get_config().log_file_path
        try:
            open_file_or_folder.open_file_or_folder(log_file_path)
        except Exception as e:
            QMessageBox.critical(self, 'Log-File', f'Beim Öffnen der Log-Datei ist ein Fehler aufgetreten:\n{e}')

    def plan_save(self):
        """Minimal angepasst: Nutzt TabManager Properties"""

        def generate_name_suggestion(plan: schemas.PlanShow):
            return f'{plan.plan_period.team.name} {plan.plan_period.start:%d.%m.%y}-{plan.plan_period.end:%d.%m.%y}'

        def new_name_suggestion_is_same_as_plan_name(name_suggestion: str, active_widget: FrmTabPlan) -> bool:
            if name_suggestion == active_widget.plan.name:
                QMessageBox.critical(self, 'Neuer Plan-Name',
                                     f'Der aktuelle Plan hat bereits den Namen "{new_name_suggestion}".')
                return True
            return False

        def confirm_plan_deletion(plan: schemas.PlanShow):
            info_prep_deleted = 'Dieser Plan ist allerdings bereits zum Löschen markiert.\n' if plan.prep_delete else ''
            confirmation = QMessageBox.question(self, 'Neuer Plan-Name',
                                                f'Ein Plan mit dem Namen "{plan.name}" existiert bereits.\n'
                                                f'{info_prep_deleted}'
                                                f'Falls Sie den aktuellen Plan unter diesem Namen abspeichern, '
                                                f'wird der bereits existierende Plan mit dem gleichen Namen gelöscht.\n'
                                                f'Dieser Vorgang kann nicht rückgängig gemacht werden!\n'
                                                f'Möchten Sie dies tun?')
            return confirmation == QMessageBox.Yes

        def delete_existing_plan(plan: schemas.PlanShow):
            self.controller.execute(plan_commands.Delete(plan.id))
            self.controller.execute(plan_commands.DeletePrepDeleted(plan.id))

        def remove_tab_with_name(tab_name: str):
            tab_to_remove_index = next(
                (i for i in range(self.tabs_plans.count())
                 if self.tabs_plans.tabText(i) == tab_name), -1
            )
            self.tabs_plans.close_tab_and_delete_widget(tab_to_remove_index)

        def update_plan_name(widget: FrmTabPlan, new_name: str):
            update_name_command = plan_commands.UpdateName(widget.plan.id, new_name)
            self.controller.execute(update_name_command)
            widget.plan = update_name_command.updatet_plan

        def update_tab_text(new_text):
            self.tabs_plans.setTabText(self.tabs_plans.currentIndex(), new_text)

        # TabManager Property nutzen
        active_widget = self.tab_manager.current_plan_widget
        if not active_widget:
            QMessageBox.critical(self, 'Plan speichern', 'Sie müssen zuerst einen Plan öffnen.')
            return

        new_name_suggestion = generate_name_suggestion(active_widget.plan)

        if new_name_suggestion_is_same_as_plan_name(new_name_suggestion, active_widget):
            return

        if existing_plan_with_same_name := db_services.Plan.get_from__name(new_name_suggestion):
            if not confirm_plan_deletion(existing_plan_with_same_name):
                return
            delete_existing_plan(existing_plan_with_same_name)
            remove_tab_with_name(new_name_suggestion)

        update_plan_name(active_widget, new_name_suggestion)
        update_tab_text(new_name_suggestion)

    def sheets_for_availables(self):
        ...

    def plan_export_to_excel(self, index: int = None):
        @Slot(bool)
        def export_finished(success: bool, output_path: str):
            print(f'{success=}, {output_path=}')
            if success:
                QMessageBox.information(self, 'Plan Excel-Export',
                                        f'Plan wurde erfolgreich unter\n{output_path}\nexportiert.')
                signal_handling.handler_excel_export.signal_finished.disconnect()
                reply = QMessageBox.question(self, 'Plan Excel-Export',
                                             'Soll die Excel-Datei jetzt geöffnet werden?', )
                if reply == QMessageBox.StandardButton.Yes:
                    try:
                        open_file_or_folder.open_file_or_folder(output_path)
                    except Exception as e:
                        QMessageBox.critical(self, 'Plan Excel-Export', f'{e}')
            else:
                QMessageBox.critical(self, 'Plan Excel-Export', 'Plan konnte nicht exportiert werden.')

        def create_dir_if_not_exist(path: str):
            dir_path = path.rsplit(os.sep, 1)[0]
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

        # TabManager Property nutzen
        widget = self.tab_manager.current_plan_widget
        if not widget:
            QMessageBox.critical(self, 'Plan Excel-Export', 'Sie müssen zuerst einen Plan öffnen.')
            return

        dlg = DlgPlanToXLSX(self, widget.plan)
        if dlg.exec():
            widget.reload_plan()

            excel_output_path = os.path.join(self._get_excel_folder_output_path(widget.plan.plan_period),
                                             f'{widget.plan.name}.xlsx')
            create_dir_if_not_exist(excel_output_path)

            signal_handling.handler_excel_export.signal_finished.connect(
                functools.partial(export_finished, output_path=excel_output_path)
            )

            plan_to_xlsx.export_plan_to_xlsx(self, widget, excel_output_path,
                                             dlg.note_in_empty_fields, dlg.note_in_employee_fields,
                                             dlg.include_employee_events)

    def lookup_for_excel_plan_folder(self):
        """Minimal angepasst: Nutzt TabManager Properties"""
        if self.tab_manager.current_tab_type == 'plans':
            curr_widget = self.tab_manager.current_plan_widget
            if not curr_widget:
                QMessageBox.critical(self, 'Excel-Ordner', 'Sie müssen zuerst einen Plan öffnen.')
                return
            plan_period = curr_widget.plan.plan_period
        elif self.tab_manager.current_tab_type == 'masks':
            curr_widget = self.tab_manager.current_plan_period_widget
            if not curr_widget:
                QMessageBox.critical(self, 'Excel-Ordner', 'Sie müssen zuerst eine Planungsperiode öffnen.')
                return
            plan_period = db_services.PlanPeriod.get(curr_widget.plan_period_id)
        else:
            QMessageBox.critical(self, 'Excel-Ordner', 'Unbekannter Tab-Typ.')
            return

        excel_output_path = self._get_excel_folder_output_path(plan_period)
        try:
            open_file_or_folder.open_file_or_folder(excel_output_path)
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                QMessageBox.critical(self, 'Excel-Ordner',
                                     f'Es wurde noch keine Excel-Datei für den Zeitraum '
                                     f'{plan_period.start:%d.%m.%y}-{plan_period.end:%d.%m.%y} '
                                     f'des Teams {plan_period.team.name} erstellt.')
            else:
                QMessageBox.critical(self, 'Fehler beim Öffnen',
                                     f'Beim Öffnen der Excel-Datei ist ein Fehler aufgetreten:\n{e}')

    def _get_excel_folder_output_path(self, plan_period: schemas.PlanPeriod) -> str:
        path_handler = project_paths.curr_user_path_handler
        if not (output_folder := path_handler.get_config().excel_output_path):
            output_folder = 'excel_output'
        excel_output_path = os.path.join(
            output_folder, plan_period.team.name,
            f"{plan_period.start.strftime('%d.%m.%y')}-"
            f"{plan_period.end.strftime('%d.%m.%y')}")
        return excel_output_path

    def _put_clients_to_menu(self) -> tuple[MenuToolbarAction, ...] | None:
        try:
            teams = sorted(db_services.Team.get_all_from__project(self.project_id), key=lambda x: x.name)
        except Exception as e:
            QMessageBox.critical(self, 'put_clients_to_menu', f'Fehler: {e}')
            return
        self.actions_teams_in_clients_menu = {
            team.id: MenuToolbarAction(self, None, team.name, f'Zu {team.name} wechseln.',
                                       lambda event=1, team_id=team.id: self.goto_team(team_id)) for team in teams
        }
        return tuple(self.actions_teams_in_clients_menu.values())

    def put_teams_to__teams_edit_menu(self) -> dict[str, list[MenuToolbarAction]] | None:
        try:
            teams = sorted(db_services.Team.get_all_from__project(self.project_id), key=lambda x: x.name)
        except Exception as e:
            QMessageBox.critical(self, 'put_teams_to__teams_edit_menu', f'Fehler: {e}')
            return None
        return {team.name: [MenuToolbarAction(self, None, self.tr('Facility Combinations...'),
                                              self.tr('Edit possible combinations of facilities.'),
                                              functools.partial(self.edit_comb_loc_poss, team)),
                            MenuToolbarAction(self, None, self.tr('Excel Settings...'),
                                              self.tr('Edit settings for Excel export of the schedule.'),
                                              functools.partial(self.edit_team_excel_export_settings, team)),
                            MenuToolbarAction(self, None, self.tr('Notes...'),
                                              self.tr('Edit team notes.'),
                                              functools.partial(self.edit_team_notes, team))]
                for team in teams}

    @Slot(UUID, UUID)
    def _show_location_plan_period_mask(self, plan_period_id: UUID, location_id: UUID):
        """Refactored: Nutzt TabManager vollständig"""
        self.show_masks()  # UI-Koordination bleibt in MainWindow

        # TabManager übernimmt alles Tab-bezogene
        self.tab_manager.current_team = self.curr_team if self.curr_team else None
        self.tab_manager.show_location_plan_period_mask(plan_period_id, location_id)

    @Slot(UUID, UUID)
    def _show_actor_plan_period_mask(self, plan_period_id: UUID, person_id: UUID):
        """Refactored: Nutzt TabManager vollständig"""
        self.show_masks()  # UI-Koordination bleibt in MainWindow

        # TabManager übernimmt alles Tab-bezogene
        self.tab_manager.current_team = self.curr_team if self.curr_team else None
        self.tab_manager.show_actor_plan_period_mask(plan_period_id, person_id)

    def open_plan_period_masks(self, plan_period_id: UUID = None):
        """Refactored: Nutzt TabManager für Planungsmasken"""
        if not self.curr_team:
            QMessageBox.critical(self, 'Planungsmasken', 'Sie müssen zuerst ein Team auswählen.')
            return

        # Team an TabManager setzen
        self.tab_manager.current_team = self.curr_team

        if plan_period_id:
            # Direktes Öffnen
            self.tab_manager.open_plan_period_tab(plan_period_id)
        else:
            # Dialog anzeigen
            dlg = DlgOpenPlanPeriodMask(self, self.curr_team.id, self.tabs_planungsmasken)
            if dlg.exec():
                self.tab_manager.open_plan_period_tab(dlg.curr_plan_period_id)

    def open_plan_period_tab(self, plan_period_id: UUID, current_index_actors_locals_tabs: int,
                             curr_person_id: UUID | None, curr_location_id: UUID | None):
        """
        Legacy-Wrapper: Delegiert an TabManager.
        
        Diese Methode wird für Rückwärtskompatibilität beibehalten und 
        delegiert die Funktionalität an den TabManager.
        """
        self.tab_manager.current_team = self.curr_team  # Team setzen falls nötig
        return self.tab_manager.open_plan_period_tab(
            plan_period_id, current_index_actors_locals_tabs, curr_person_id, curr_location_id
        )

    def goto_team(self, team_id: UUID):
        """Erweiterte Team-Wechsel-Logik mit Cache-Performance-Monitoring"""
        # Nutze erweiterte Implementierung aus TabCacheIntegration
        self.enhanced_goto_team(team_id)

    def master_data(self):
        if self.frm_master_data is None:
            self.frm_master_data = FrmMasterData(self, project_id=self.project_id)
        self.frm_master_data.raise_()
        self.frm_master_data.activateWindow()
        self.frm_master_data.showNormal()

    def show_employee_events_window(self):
        """Öffnet Employee Events in separatem Fenster."""
        if self.employee_events_window is None:
            from .employee_events_window import EmployeeEventsWindow
            self.employee_events_window = EmployeeEventsWindow(self, self.project_id)

        self.employee_events_window.showNormal()
        self.employee_events_window.activateWindow()
        self.employee_events_window.raise_()

    def show_plans(self):
        """Refactored: Delegiert an TabManager"""
        self.tab_manager.show_plans()

    def show_masks(self):
        """Refactored: Delegiert an TabManager"""
        self.tab_manager.show_masks()

    def export_avail_days_to_excel(self):
        """Minimal angepasst: Nutzt TabManager Properties"""

        def create_dir_if_not_exist(path: str):
            dir_path = path.rsplit(os.sep, 1)[0]
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

        if self.tab_manager.current_tab_type == 'plans':
            curr_plan_widget = self.tab_manager.current_plan_widget
            if not curr_plan_widget:
                QMessageBox.critical(self, 'Verfügbarkeiten exportieren', 'Sie müssen zuerst einen Plan öffnen.')
                return
            plan_period = curr_plan_widget.plan.plan_period
        elif self.tab_manager.current_tab_type == 'masks':
            curr_plan_widget = self.tab_manager.current_plan_period_widget
            if not curr_plan_widget:
                QMessageBox.critical(self, 'Verfügbarkeiten exportieren',
                                     'Sie müssen zuerst eine Planungsperiode öffnen.')
                return
            plan_period = db_services.PlanPeriod.get(curr_plan_widget.plan_period_id)
        else:
            QMessageBox.critical(self, 'Verfügbarkeiten exportieren', 'Unbekannter Tab.')
            return
        excel_output_path = os.path.join(
            self._get_excel_folder_output_path(plan_period),
            f'Verfügbarkeiten {plan_period.team.name} {plan_period.start:%d.%m.%y}-{plan_period.end:%d.%m.%y}.xlsx'
        )
        create_dir_if_not_exist(excel_output_path)
        try:
            export_avail_days_to_xlsx(self, plan_period.id, excel_output_path)
        except FileCreateError as e:
            QMessageBox.critical(self, 'Verfügbarkeiten exportieren',
                                 f'Fehler beim Erstellen der Excel-Datei:\n{e}')
        QMessageBox.information(self,
                                'Verfügbarkeiten exportieren',
                                f'Verfügbarkeiten wurden unter\n{excel_output_path}\nexportiert.')

    def statistics(self):
        """Öffnet den Employment Statistics Dialog"""
        from gui.employment_statistics import EmploymentStatisticsDialog

        dlg = EmploymentStatisticsDialog(self)
        dlg.exec()

    def calculate_plans(self):
        """Refactored: Nutzt TabManager zum Öffnen neuer Pläne"""
        if not self.curr_team:
            QMessageBox.critical(self, 'Aktuelles Team', 'Es ist kein Team ausgewählt.')
            return

        dlg = frm_calculate_plan.DlgCalculate(self, self.curr_team.id)
        if dlg.exec():
            reply = QMessageBox.question(self, 'Plänen anzeigen', 'Sollen die erstellten Pläne angezeigt werden?')
            if reply == QMessageBox.StandardButton.Yes:
                # TabManager öffnet die Pläne
                self.tab_manager.current_team = self.curr_team  # Team setzen
                for plan_id in dlg.get_created_plan_ids():
                    self.tab_manager.open_plan_tab(plan_id)
                    QCoreApplication.processEvents()

    def plan_infos(self):
        """Minimal angepasst: Nutzt TabManager Properties"""
        curr_plan_widget = self.tab_manager.current_plan_widget
        if not curr_plan_widget:
            QMessageBox.critical(self, 'Plan-Informationen', 'Sie müssen zuerst einen Plan öffnen.')
            return

        curr_plan: schemas.PlanShow = curr_plan_widget.plan
        dlg = DlgPlanPeriodNotes(self, curr_plan)
        if dlg.exec():
            self.controller.execute(plan_commands.UpdateNotes(curr_plan.id, dlg.notes))
            if dlg.chk_sav_to_plan_period.isChecked():
                self.controller.execute(plan_period_commands.UpdateNotes(curr_plan.plan_period.id, dlg.notes))
                signal_handling.handler_plan_tabs.reload_all_plan_period_plans_from_db(curr_plan.plan_period.id)
            else:
                signal_handling.handler_plan_tabs.reload_plan_from_db(curr_plan.id)

    def plan_calculation_settings(self):
        dlg = frm_settings_solver_params.DlgSettingsSolverParams(self)
        dlg.exec()

    def apply_events__plan_to_mask(self):
        ...

    def send_custom_emails(self):
        from gui.email_to_users.gui_integration_main import show_custom_email_dialog
        show_custom_email_dialog(self, self.project_id)

    def send_bulk_email(self):
        from gui.email_to_users.gui_integration_main import show_bulk_email_dialog
        show_bulk_email_dialog(self, self.project_id)

    def send_plan_notifications(self):
        from gui.email_to_users.gui_integration_main import show_plan_notification_dialog
        show_plan_notification_dialog(self)

    def send_availability_requests(self):
        """Minimal angepasst: Nutzt TabManager Properties"""
        curr_plan_widget = self.tab_manager.current_plan_widget
        if not curr_plan_widget:
            QMessageBox.critical(self, 'Verfügbarkeiten anfragen', 'Sie müssen zuerst einen Plan öffnen.')
            return
        plan_period = curr_plan_widget.plan.plan_period

    def show_email_config_dialog(self):
        from gui.email_to_users.gui_integration_main import show_config_dialog
        show_config_dialog(self)

    def plan_events_to_google_calendar(self):
        """Minimal angepasst: Nutzt TabManager Properties"""

        def transfer(plan: schemas.PlanShow):
            try:
                transfer_appointments_with_batch_requests(plan)
                return True
            except Exception as e:
                return e

        def finished(result):
            progressbar.close()
            if result is True:
                QMessageBox.information(
                    self, 'Übertragung der Termine',
                    f'Die Termine des Teams {plan.plan_period.team.name}\n'
                    f'im Planungszeitraum {plan.plan_period.start:%d.%m.%y} - {plan.plan_period.end:%d.%m.%y}\n'
                    f'wurden erfolgreich zu den betreffenden Google-Kalendern übertragen.')
            else:
                QMessageBox.critical(self, 'Übertragungsfehler',
                                     f'Bei der Übertragung der Termine ist ein Fehler aufgetreten:\n'
                                     f'{result}')

        curr_widget = self.tab_manager.current_plan_widget
        if curr_widget:
            plan = curr_widget.plan
        else:
            QMessageBox.critical(self, 'Termine übertragen', 'Es muss ein Plan geöffnet sein.')
            return
        if DlgSendAppointmentsToGoogleCal(self, plan).exec():
            self.worker_general = WorkerGeneral(transfer, True, plan)
            self.worker_general.signals.finished.connect(finished, Qt.ConnectionType.QueuedConnection)
            progressbar = DlgProgressInfinite(
                self, 'Termine übertragen',
                f'Termine des Teams {plan.plan_period.team.name}\n'
                f'des Planungszeitraums {plan.plan_period.start:%d.%m.%y} - {plan.plan_period.end:%d.%m.%y}\n'
                f'werden zu den betreffenden Google-Kalendern übertragen.',
                'Abbruch',
                None,
                signal_handling.handler_google_cal_api.signal_transfer_appointments_progress
            )
            progressbar.show()
            self.thread_pool.start(self.worker_general)

    def open_google_calendar(self):
        """Öffnet den Google-Kalender des aktuellen Projekts im Browser."""
        open_google_calendar_in_browser()

    def sync_employee_events_to_google_calendar(self):
        """Synchronisiert Employee Events mit einem bestehenden Google Calendar."""
        
        def sync_events():
            """Führt die Synchronisation durch."""
            try:
                sync_results = sync_employee_events_to_calendar(self.project_id)
                return {'success': True, 'sync_results': sync_results}
            except Exception as e:
                return {'error': 'Exception', 'message': str(e)}

        @Slot(object)
        def finished(result):
            progressbar.close()
            if isinstance(result, dict) and result.get('success'):
                sync_results = result.get('sync_results')
                if sync_results:
                    # Nutzerfreundliche Message aus der Sync-Funktion verwenden
                    sync_text = sync_results.get('message', self.tr('Employee Events synchronized.'))
                    
                    # Bei Fehlern zusätzliche Details anhängen
                    if sync_results['failed_events']:
                        failed_titles = [title for title, _ in sync_results['failed_events'][:3]]
                        sync_text += (f'\n' + self.tr('Errors with: {failed_titles}')
                                      .format(failed_titles=", ".join(failed_titles)))
                        if len(sync_results['failed_events']) > 3:
                            additional_count = len(sync_results["failed_events"]) - 3
                            sync_text += ' ' + self.tr('(+{count} more)').format(count=additional_count)
                else:
                    sync_text = self.tr('Employee Events synchronization completed.')

                QMessageBox.information(self, self.tr('Employee Events Synchronization'), sync_text)
            else:
                error_text = result.get('message', self.tr('Unknown error'))
                QMessageBox.critical(
                    self, 
                    self.tr('Synchronization Error'),
                    self.tr('An error occurred while synchronizing Employee Events:\n{error_text}')
                    .format(error_text=error_text)
                )

        available_calendars = [c for c in curr_calendars_handler.get_calenders().values()
                               if c.type == 'employee_events']
        if not available_calendars:
            QMessageBox.critical(
                self,
                self.tr('No Calendars Available'),
                self.tr('No Google calendars are available.\n'
                        'Please create a calendar first or synchronize the calendar list.')
            )
            return

        # Synchronisation starten
        self.worker_general = WorkerGeneral(
            sync_events, True
        )
        self.worker_general.signals.finished.connect(finished, Qt.ConnectionType.QueuedConnection)
        
        progressbar = DlgProgressInfinite(
            self, 
            self.tr('Employee Events Synchronization'),
            self.tr('Synchronizing Employee Events...'),  # German: 'Employee Events werden synchronisiert...'
            self.tr('Cancel')  # German: 'Abbruch'
        )
        progressbar.show()
        self.thread_pool.start(self.worker_general)

    def create_google_calendar(self):
        def create():
            try:
                created_calendar = create_new_google_calendar(dlg.new_calender_data)

                # Zugriffskontrolle für Personen-Kalender (bestehende Logik)
                if dlg.calendar_type == 'person' and dlg.email_for_access_control:
                    share_calendar(created_calendar['id'], dlg.email_for_access_control)
                
                # Zugriffskontrolle für Team-Kalender (neue Logik)
                elif dlg.calendar_type == 'team' and dlg.selected_team_member_emails:
                    for email in dlg.selected_team_member_emails:
                        share_calendar(created_calendar['id'], email, 'reader')
                
                # NEU: Employee-Events Zugriffskontrolle
                elif dlg.calendar_type == 'employee_events' and dlg.selected_ee_person_emails:
                    for email in dlg.selected_ee_person_emails:
                        share_calendar(created_calendar['id'], email, 'reader')
                calendar = get_calendar_by_id(created_calendar['id'])
                curr_calendars_handler.save_calendar_json_to_file(calendar)
                return {'success': True}
            except ServerNotFoundError as e:
                return {'error': 'ServerNotFoundError', 'message': e}
            except Exception as e:
                return {'error': 'Exception', 'message': e}

        @Slot(object)
        def finished(result):
            progressbar.close()
            if isinstance(result, dict) and result.get('success'):
                if dlg.calendar_type == 'person':
                    calendar_name = person_name
                    if email := dlg.email_for_access_control:
                        text_access_control = f'\nDer Nutzer hat Zugriff auf diesen Kalender über:\n{email}'
                    else:
                        text_access_control = ('\nSie haben noch keinen Zugriff für den Nutzer über eine Email '
                                               'eingerichtet.')
                elif dlg.calendar_type == 'team':
                    calendar_name = f"Team {dlg.combo_teams.currentText()}"
                    if dlg.selected_team_member_emails:
                        emails_text = '\n'.join(dlg.selected_team_member_emails)
                        text_access_control = (f'\nDie folgenden Team-Mitglieder haben Zugriff auf diesen Kalender:\n'
                                               f'{emails_text}')
                    else:
                        text_access_control = '\nEs wurden keine Team-Mitglieder für den Zugriff ausgewählt.'
                
                # NEU: Employee-Events Success-Message
                elif dlg.calendar_type == 'employee_events':
                    team_text = dlg.combo_ee_teams.currentText()
                    calendar_name = f"Employee-Events ({team_text})"
                    
                    # Access Control Text
                    if dlg.selected_ee_person_emails:
                        emails_text = '\n'.join(dlg.selected_ee_person_emails)
                        text_access_control = f'\nZugriff für folgende Personen:\n{emails_text}'
                    else:
                        text_access_control = '\nKein Personenzugriff konfiguriert.'

                QMessageBox.information(
                    self, 'Google-Kalender erstellen',
                    f'Ein neuer Google-Kalender für {calendar_name} wurde erstellt.{text_access_control}')
            else:
                if result['error'] == 'ServerNotFoundError':
                    error_text = f'{result["message"]}\nBitte prüfen Sie Ihre Internetverbindung.'
                else:
                    error_text = f'{result["message"]}'
                if dlg.calendar_type == 'team':
                    calendar_for_name = f"Team {person_name}"
                elif dlg.calendar_type == 'employee_events':
                    calendar_for_name = f"Employee-Events ({person_name})"
                else:
                    calendar_for_name = person_name
                QMessageBox.critical(
                    self, 'Fehler beim Erstellen des Kalenders',
                    f'Beim Versuch, den Kalender für {calendar_for_name} zu erstellen\n'
                    f'ist folgender Fehler aufgetreten:\n'
                    f'{error_text}')

        dlg = CreateGoogleCalendar(self, self.project_id)
        if dlg.exec():
            self.worker_general = WorkerGeneral(create, True)
            self.worker_general.signals.finished.connect(finished)
            # Namen und Progressbar-Text basierend auf Kalender-Typ
            if dlg.calendar_type == 'person':
                person_name = dlg.combo_persons.currentText()
                progress_text = f'Ein neuer Google-Kalender für {person_name} wird erstellt.'
            elif dlg.calendar_type == 'team':
                person_name = dlg.combo_teams.currentText()  # Wird für Error-Handling verwendet
                progress_text = f'Ein neuer Google-Kalender für Team {person_name} wird erstellt.'
            elif dlg.calendar_type == 'employee_events':
                team_text = dlg.combo_ee_teams.currentText()
                person_name = team_text  # Für Error-Handling
                progress_text = f'Employee-Events Kalender ({team_text}) wird erstellt...'
            
            progressbar = DlgProgressInfinite(
                self, 'Google-Kalender erstellen',
                progress_text,
                'Abbruch'
            )
            progressbar.show()
            self.thread_pool.start(self.worker_general)

    def synchronize_google_calenders(self):
        def synchronize():
            try:
                synchronize_local_calendars()
                return True
            except ServerNotFoundError as e:
                return {'error': 'ServerNotFoundError', 'message': e}
            except Exception as e:
                return {'error': 'Exception', 'message': e}

        @Slot(object)
        def finished(result):
            progressbar.close()
            if result is True:
                QMessageBox.information(
                    self, 'Kalender-Synchronisation',
                    'Die lokale Kalenderliste enthält jetzt alle online verfügbaren Google-Kalender.')
            else:
                if result['error'] == 'ServerNotFoundError':
                    error_text = f'{result["message"]}\nBitte prüfen Sie Ihre Internetverbindung.'
                else:
                    error_text = f'{result["message"]}'
                QMessageBox.critical(
                    self, 'Synchronisationsfehler',
                    f'Beim Versuch, die lokale Kalenderliste mit den\n'
                    f'online verfügbaren Google-Kalendern abzugleichen ist folgender Fehler aufgetreten:\n'
                    f'{error_text}')

        self.worker_general = WorkerGeneral(synchronize, True)
        self.worker_general.signals.finished.connect(finished, Qt.ConnectionType.QueuedConnection)
        progressbar = DlgProgressInfinite(self, 'Kalendersynchronisation',
                                          'Google-Kalender werden heruntergeladen...', 'Abbruch')
        progressbar.show()
        self.thread_pool.start(self.worker_general)

    def import_google_api_credentials(self):
        """Dialog zum Importieren der Google API Credentials"""
        dlg = QFileDialog(self, 'Google API Credentials importieren', '', 'JSON-Datei (*.json)')
        dlg.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        if dlg.exec():
            file_path = dlg.selectedFiles()[0]
            try:
                save_credentials(file_path)
            except Exception as e:
                QMessageBox.critical(self, 'Fehler beim Importieren der Google API Credentials',
                                     f'Beim Versuch, die Google API Credentials zu importieren ist '
                                     f'folgender Fehler aufgetreten:\n'
                                     f'{e}')
                return
            QMessageBox.information(self, 'Google API Credentials importieren',
                                    'Die Google API Credentials wurden erfolgreich importiert.')

    def upgrade_hcc_plan(self):
        ...

    def general_setting(self):
        dlg = DlgGeneralSettings(self)
        if dlg.exec():
            ...

    def open_help(self):
        """
        Öffnet das Hilfe-System im Browser.
        
        Nutzt das vorhandene Help-System mit Fallback-Mechanismen für
        optimale Benutzerfreundlichkeit.
        """
        try:
            # Help-System importieren
            from help import get_help_manager, init_help_system
            
            # Help Manager abrufen oder initialisieren
            help_manager = get_help_manager()
            if not help_manager:
                help_manager = init_help_system()
            
            # Hilfe anzeigen wenn verfügbar
            if help_manager and help_manager.is_help_available():
                success = help_manager.show_main_help()
                if success:
                    logger.info("Hilfe-System erfolgreich geöffnet")
                    return
                else:
                    logger.warning("Hilfe konnte nicht im Browser geöffnet werden")
            
            # Fallback-Information für Benutzer
            QMessageBox.information(
                self, 
                self.tr("Help"),
                self.tr("Loading help documentation...\n\n"
                       "If the help does not open automatically, you can find "
                       "the documentation in help/content/de/ directory of the project.")
            )
            
        except ImportError as e:
            logger.error(f"Help-System konnte nicht importiert werden: {e}")
            QMessageBox.information(
                self, 
                self.tr("Help"),
                self.tr("Help system is not available at the moment.\n\n"
                       "Please check the README.md or contact support.")
            )
            
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Öffnen der Hilfe: {e}")
            QMessageBox.warning(
                self, 
                self.tr("Help"),
                self.tr("An error occurred while opening the help.\n\n"
                       "Try again later or contact support.")
            )

    def import_from_plan_api(self):
        dlg = DlgRemoteAccessPlanApi(self, self.project_id)
        if not dlg.exec():
            return

    def check_for_updates(self):
        ...

    def about_hcc_plan(self):
        ...

    def _replace_action_in_menu(self, menu: QMenu, old_action: QAction, new_action: QAction):
        if menu:
            actions = menu.actions()
            if old_action in actions:
                index = actions.index(old_action)
                menu.insertAction(actions[index] if index < len(actions) else None, new_action)
                menu.removeAction(old_action)

    def _replace_action_in_toolbar(self, toolbar: MainToolBar, old_action: QAction, new_action: QAction):
        if toolbar:
            actions = toolbar.actions()
            if old_action in actions:
                index = actions.index(old_action)
                toolbar.insertAction(actions[index] if index < len(actions) else None, new_action)
                toolbar.removeAction(old_action)

    def restore_tabs(self):
        """Refactored: Delegiert an TabManager"""
        self.tab_manager.restore_startup_tabs()

        # Window-Title setzen wenn Team geladen wurde
        if self.tab_manager.current_team:
            self.curr_team = self.tab_manager.current_team
            self.setWindowTitle(f'hcc-plan  —  Team: {self.curr_team.name}')
            # Actions-Menu aktualisieren falls vorhanden
            if hasattr(self,
                       'actions_teams_in_clients_menu') and self.curr_team.id in self.actions_teams_in_clients_menu:
                self.actions_teams_in_clients_menu[self.curr_team.id].setChecked(True)

    def exit(self):
        self.close()

    def closeEvent(self, event=QCloseEvent):
        """Erweiterte Close-Event Behandlung mit Cache-Management"""
        # Nutze erweiterte Cache-Behandlung
        self.enhanced_close_event(event)

        # Original closeEvent aufrufen
        super().closeEvent(event)

    def show_db_structure(self):
        import urllib.parse
        import webbrowser
        import os
        import tempfile
        import threading
        from jinja2 import Template

        tools_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tools')
        template_path = os.path.join(tools_dir, 'db_model_graph_template.html')
        models_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'models.py')
        print(f'🎯 DB Structure: {template_path=}')
        print(f'🎯 DB Structure: {models_path=}')
        print(f'🎯 DB Structure: {os.path.exists(template_path)=}')
        print(f'🎯 DB Structure: {os.path.exists(models_path)=}')

        try:
            # ✅ FIX: Read models.py content and embed it directly in template
            with open(models_path, 'r', encoding='utf-8') as f:
                models_content = f.read()

            # Template laden und rendern
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())

            # ✅ FIX: Pass both path and content to avoid CORS issues
            rendered_html = template.render(
                models_path=models_path,
                models_content=models_content,
                models_filename=os.path.basename(models_path)
            )

            # ✅ FIX: Use temporary file instead of data URL (Windows length limit)
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html',
                                             delete=False, encoding='utf-8') as f:
                f.write(rendered_html)
                temp_path = f.name

            # Öffnen der temporären Datei
            file_url = f'file:///{temp_path.replace(os.sep, "/")}'
            webbrowser.open(file_url)

            print(f'🎯 DB Structure opened with models: {models_path}')
            print(f'📁 Temporary file: {temp_path}')

            # ✅ Cleanup nach 60 Sekunden (genug Zeit zum Laden)
            def cleanup():
                try:
                    os.unlink(temp_path)
                    print(f'🧹 Temporary file cleaned up: {temp_path}')
                except Exception as e:
                    print(f'⚠️ Cleanup failed: {e}')

            threading.Timer(60.0, cleanup).start()

        except FileNotFoundError as e:
            if 'db_model_graph_template.html' in str(e):
                QMessageBox.critical(self, 'DB-Struktur Template',
                                     f'Template-Datei nicht gefunden:\n{template_path}\n\n'
                                     f'Stellen Sie sicher, dass db_model_graph_template.html existiert.')
            else:
                QMessageBox.critical(self, 'DB-Struktur Models',
                                     f'Models-Datei nicht gefunden:\n{models_path}\n\n'
                                     f'Stellen Sie sicher, dass models.py existiert.')
        except Exception as e:
            print(f'❌ Error in show_db_structure: {e}')
            QMessageBox.critical(self, 'DB-Struktur',
                                 f'Fehler beim Öffnen der DB-Struktur:\n{e}\n\n'
                                 f'Template: {template_path}\n'
                                 f'Models: {models_path}')

    def put_actions_to_menu(self, menu: QMenuBar | QMenu, actions_menu: dict | list | tuple):
        """
        menu: ist immer eine Menübar (Hauptmenü oder Untermenü)
        actions_menu: actions_menus können entweder Listen oder Dictionaries sein.
                      dictionaries listen immer Menüpunkte (keys) auf. Diese Untermenüs beinhalten entweder Listen von
                      QActions oder weitere Untermenüs oder Mischungen daraus.
                      Beinhaltende Tuples zeigen an, dass die QActions in einer ActionGroup zusammengefasst werden
                      sollen, um Radiobuttons oder Checkboxes zu erhalten.
                      Beinhaltet das actions_menu ein Callable, wird durch Ausführen dieser Funktion dynamisch ein
                      actions_meu erzeugt.
                      Der Wert None erzeugt einen Separator.
        """
        if isinstance(actions_menu, tuple):
            ag = QActionGroup(self)
            ag.setExclusive(True)
            for action in actions_menu:
                a = ag.addAction(action)
                a.setCheckable(True)
                menu.addAction(a)
        else:
            for value in actions_menu:
                if isinstance(value, str):
                    current_menu = menu.addMenu(value)
                    current_menu.setObjectName(value.replace('&', ''))
                    self.put_actions_to_menu(current_menu, actions_menu[value])
                elif isinstance(value, dict):
                    self.put_actions_to_menu(menu, value)
                elif value is None:
                    menu.addSeparator()
                elif isinstance(value, MenuToolbarAction):
                    menu.addAction(value)
                else:  # callable
                    self.put_actions_to_menu(menu, value())

# todo: Funktion zur Komprimierung der Datenbank hinzufügen.
