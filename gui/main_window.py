import functools
import json
import os.path
from uuid import UUID

from PySide6.QtCore import QRect, QPoint, Slot, QCoreApplication, QThreadPool
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent
from PySide6.QtWidgets import QMainWindow, QMenuBar, QMenu, QWidget, QMessageBox, QInputDialog, QFileDialog
from httplib2 import ServerNotFoundError
from pydantic_core import ValidationError

import configuration
import google_calendar_api
from commands import command_base_classes
from commands.database_commands import plan_commands, team_commands, plan_period_commands
from configuration import team_start_config, project_paths
from configuration.google_calenders import curr_calendars_handler
from database import db_services, schemas
from export_to_file import plan_to_xlsx
from google_calendar_api.create_calendar import create_new_google_calendar, share_calendar
from google_calendar_api.get_calendars import synchronize_local_calendars, get_calendar_by_id
from google_calendar_api.transfer_appointments import transfer_plan_appointments
from . import frm_comb_loc_possible, frm_calculate_plan, frm_plan, frm_settings_solver_params, frm_excel_settings
from .concurrency.general_worker import WorkerGeneral
from .frm_appointments_to_google_calendar import DlgSendAppointmentsToGoogleCal
from .frm_create_google_calendar import CreateGoogleCalendar
from .frm_notes import DlgPlanPeriodNotes, DlgTeamNotes
from .custom_widgets.progress_bars import GlobalUpdatePlanTabsProgressManager, DlgProgressInfinite
from .frm_actor_plan_period import FrmTabActorPlanPeriods
from .frm_location_plan_period import FrmTabLocationPlanPeriods
from .frm_masterdata import FrmMasterData
from tools.actions import MenuToolbarAction
from .frm_open_panperiod_mask import DlgOpenPlanPeriodMask
from .frm_plan import FrmTabPlan
from .frm_plan_period import DlgPlanPeriodCreate, DlgPlanPeriodEdit
from .frm_plan_period_tab_widget import PlanPeriodTabWidget
from .frm_project_select import DlgProjectSelect
from .frm_project_settings import DlgSettingsProject
from .frm_remote_access_plan_api import DlgRemoteAccessPlanApi
from .observer import signal_handling
from gui.custom_widgets.tabbars import TabBar
from gui.custom_widgets.toolbars import MainToolBar


class MainWindow(QMainWindow):
    def __init__(self, app, screen_width: int, screen_height: int):
        super().__init__()
        self.setWindowTitle('hcc-plan')
        self.setGeometry(QRect(0, 0, screen_width-100, screen_height-100))

        # db_services.Project.create('Humor Hilft Heilen')

        self.project_id = UUID('A2468BCF064F4A69BACFFD00F929671E')
        # self.choose_project()
        self.curr_team: schemas.TeamShow | None = None

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.thread_pool = QThreadPool()

        self.global_update_plan_tabs_progress_bar = DlgProgressInfinite(
            self, 'Update Plan-Tabs', 'Die betreffenden geöffneten Pläne werden aktualisiert.', 'Abbruch')
        self.global_update_plan_tabs_progress_manager = GlobalUpdatePlanTabsProgressManager(
            self.global_update_plan_tabs_progress_bar)

        path_to_toolbar_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.actions = {
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'folder-open-table.png'), 'Öffenen... (Planung)',
                              'Öffnet Planungsdaten für Locations und Mitarbeiter einer bestimmten Planungsperiode',
                              self.open_plan_period_masks),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-document--plus.png'), 'Neue Planung...',
                              'Legt eine neue Planung an.', self.new_plan_period, short_cut='Ctrl+n'),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-document--pencil.png'),
                              'Planung ändern...',
                              'Ändern oder Löschen einer vorhandenen Planung.', self.edit_plan_period),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'gear--pencil.png'), 'Projekt-Einstellungen...',
                              'Bearbeiten der Grundeinstellungen des Projekts', self.settings_project),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'folder-open-document.png'),
                              'Öffnen... (Pläne)',
                              'Öffnet einen bereits erstellten Plan.', self.open_plan),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'disk.png'), 'Plan speichern...',
                              'Speichert den aktiven Plan',
                              self.plan_save),
            MenuToolbarAction(self, None, 'Excel-Einstellungen',
                              'Einstellungen der Farben in der exportierten Excel-Datei...',
                              self.plan_excel_configs),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'tables.png'),
                              'Listen für Sperrtermine erzeugen...',
                              'Erstellt Listen, in welche Mitarbeiter ihre Sperrtermine eintragen können.',
                              self.sheets_for_availables),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'download-mac-os.png'),
                              'Daten von Online-API importieren...', 'Import von Daten aus der API',
                              self.import_from_plan_api),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'table-export.png'), 'Plan Excel-Export...',
                              'Exportiert den aktiven Plan in einer Excel-Datei', self.plan_export_to_excel),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-folder-open-table.png'),
                              'Anzeigen der Pläne im Explorer...',
                              'Pläne der aktuellen Planung werden im Explorer angezeigt.',
                              self.lookup_for_excel_plan),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'cross-script.png'), 'Programm beenden',
                              None, self.exit,
                              'Alt+F4'),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'address-book-blue.png'), 'Stammdaten...',
                              'Stammdaten von Mitarbeitern und Einsatzorten bearbeiten.', self.master_data),
            MenuToolbarAction(self, None, 'Pläne anzeigen', None, self.show_plans),
            MenuToolbarAction(self, None, 'Masken anzeigen', None, self.show_masks),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'table-select-cells.png'),
                              'Übersicht Verfügbarkeiten',
                              'Ansicht aller Verfügbarkeiten der Mitarbeiter in dieser Planung.', self.show_availables),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'chart.png'),
                              'Übersicht Einsätze der Mitarbeiter',
                              'Zeigt eine Übersicht der Einsätze aller Mitarbeiter*innen an.', self.statistics),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'blue-document-attribute-p.png'),
                              'Einsatzpläne erstellen...',
                              'Einen oder mehrere Einsatzpläne einer bestimmten Periode erstellen.',
                              self.calculate_plans),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'notebook--pencil.png'), 'Plan-Infos...',
                              'Erstellt oder ändert Infos zur Planung.', self.plan_infos),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'gear.png'), 'Einstellungen (Erstellung)...',
                              'Einstellungen für die Berechnung der Pläne.', self.plan_calculation_settings),
            MenuToolbarAction(self, None, 'Excel Output-Ordner...',
                              'Ordner für die Ausgabe von Excel-Files festlegen', self.determine_excel_output_folder),
            MenuToolbarAction(self, None, 'Pläne des aktuellen Teams endgültig löschen...',
                              f'Die zum Löschen markierten Pläne des aktuellen Teams werden endgültig gelöscht',
                              self.plans_of_team_delete_prep_deletes),
            MenuToolbarAction(self, None, 'Events aus Plan zu Events-Maske...',
                              'Termine aus aktivem Plan in Planungsmaske Einrichtungen übernehmen.',
                              self.apply_events__plan_to_mask),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'mail-send.png'), 'Emails...', 'Emails versenden.',
                              self.send_email),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar--arrow.png'), 'Termine übertragen',
                              'Termine des aktiven Plans zum Google-Kalender übertragen',
                              self.plan_events_to_google_calendar),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar--plus.png'),
                              'Google-Kalender anlegen',
                              'Einen neuen Google-Kalender anlegen', self.create_google_calendar),
            MenuToolbarAction(self, None, 'Lokale Kalenderliste abgleichen',
                              'Gleicht die lokale Kalenderliste mit den online verfügbarn Google-kalendern ab',
                              self.synchronize_google_calenders),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'calendar-blue.png'),
                              'Google-Kalender öffnen...',
                              'Öffnet den Google-Kalender im Browser', self.open_google_calendar),
            MenuToolbarAction(self, None, 'Kalender-ID setzen...', 'Kalender-ID des Google-Kalenders dieses Teams',
                              self.set_google_calendar_id),
            MenuToolbarAction(self, None, 'Upgrade...', 'Zum Erweitern von "hcc-plan"', self.upgrade_hcc_plan),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'gear--pencil.png'), 'Einstellungen',
                              'Allgemeine Programmeinstellungen.', self.general_setting),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'book-question.png'), 'Hilfe...',
                              'Öffnet die Hilfe im Browser.', self.open_help, 'F1'),
            MenuToolbarAction(self, None, 'Auf Updates überprüfen...',
                              'Überprüft, ob Updates zum Programm vorhanden sind.', self.check_for_updates),
            MenuToolbarAction(self, os.path.join(path_to_toolbar_icons, 'information-italic.png'), 'Über...',
                              'Info über das Programm', self.about_hcc_plan)
        }
        self.actions: dict[str, MenuToolbarAction] = {a.slot.__name__: a for a in self.actions}
        self.toolbar_actions: list[QAction | None] = [
            self.actions['new_plan_period'], self.actions['master_data'], self.actions['open_plan'],
            self.actions['plan_save'], None,
            self.actions['sheets_for_availables'], self.actions['plan_export_to_excel'],
            self.actions['lookup_for_excel_plan'], None, self.actions['exit']
        ]
        self.menu_actions = {
            '&Datei': [self.actions['open_plan_period_masks'], self.actions['new_plan_period'],
                       self.actions['edit_plan_period'], None, self.actions['sheets_for_availables'], None,
                       self.actions['import_from_plan_api'], None, self.actions['exit'],
                       self.actions['settings_project']],
            '&Klienten': [{'Teams bearbeiten': [self.put_teams_to__teams_edit_menu]}, None, self._put_clients_to_menu,
                          None, self.actions['master_data']],
            '&Ansicht': [{'toggle_plans_masks': (self.actions['show_plans'], self.actions['show_masks'])},
                         self.actions['show_availables'], self.actions['statistics']],
            '&Spielplan': [self.actions['calculate_plans'], self.actions['plan_infos'],
                           self.actions['plan_calculation_settings'], self.actions['plan_excel_configs'],
                           self.actions['determine_excel_output_folder'], None,
                           self.actions['open_plan'], self.actions['plan_save'],
                           self.actions['plans_of_team_delete_prep_deletes'], None,
                           self.actions['plan_export_to_excel'], self.actions['lookup_for_excel_plan'], None,
                           self.actions['apply_events__plan_to_mask']
                           ],
            '&Emails': [self.actions['send_email']],
            '&Google Kalender': [self.actions['plan_events_to_google_calendar'], self.actions['open_google_calendar'],
                                 None, self.actions['create_google_calendar'],
                                 self.actions['synchronize_google_calenders'],
                                 None, self.actions['set_google_calendar_id']],
            'E&xtras': [self.actions['upgrade_hcc_plan'], None, self.actions['general_setting']],
            '&Hilfe': [self.actions['open_help'], None, self.actions['check_for_updates'], None,
                       self.actions['about_hcc_plan']]
        }

        self.toolbar = MainToolBar('Main Toolbar', self.toolbar_actions, icon_size=16)

        self.addToolBar(self.toolbar)

        self.main_menu = self.menuBar()
        self.put_actions_to_menu(self.main_menu, self.menu_actions)

        self.statusBar()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.tabs_left = TabBar(self.central_widget, 'west', 16, 200)
        self.tabs_left.currentChanged.connect(self.toggled_plan_events)

        self.widget_planungsmasken = QWidget()
        self.widget_plans = QWidget()

        self.tabs_planungsmasken = TabBar(self.widget_planungsmasken, None, 10, 25, None, True, True)
        self.tabs_planungsmasken.setObjectName('masks')

        self.tabs_plans = TabBar(self.widget_plans, None, 10, 25, None, True,
                                 True, lambda point, index: self.context_menu_tabs_plans(point, index))
        self.tabs_plans.setObjectName('plans')
        self.tabs_left.addTab(self.tabs_planungsmasken, 'Planungsmasken')
        self.tabs_left.addTab(self.tabs_plans, 'Einsatzpläne')

        self.frm_master_data = None

        self.restore_tabs()

    def choose_project(self):
        dlg = DlgProjectSelect(self)
        if dlg.exec():
            self.project_id = dlg.project_id

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
        if not (plan_periods := db_services.PlanPeriod.get_all_from__project(self.project_id)):
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
        if not self.curr_team:
            QMessageBox.critical(self, 'Aktuelles Team', 'Sie müssen zuerst eine Team auswählen.')
            return
        plans = {
            name: p_id
            for name, p_id in db_services.Plan.get_all_from__team(self.curr_team.id, True).items()
            if p_id not in {
                tab.plan.id for tab in [self.tabs_plans.widget(i) for i in range(self.tabs_plans.count())]
            }
        }
        if not plans:
            QMessageBox.critical(self, 'Plan öffnen',
                                 f'Es sind keine weiteren Pläne des Teams {self.curr_team.name} vorhanden. ')
            return

        # Zeige den Dialog an, um einen Plan auszuwählen
        chosen_plan_name, ok = QInputDialog.getItem(self, "Plan auswählen", "Wähle einen Plan aus:",
                                                    reversed(list(plans)), editable=False)
        plan_id = plans[chosen_plan_name] if ok else None

        if ok:
            self.open_plan_tab(plan_id)

    def context_menu_tabs_plans(self, point: QPoint, index: int):
        context_menu = QMenu()
        context_menu.addAction(MenuToolbarAction(context_menu, None, 'Plan löschen...', None,
                                                 lambda: self.delete_plan(index)))
        context_menu.addAction(MenuToolbarAction(context_menu, None, 'Plan als Excel-File exportieren...', None,
                                                 lambda: self.plan_export_to_excel(index)))
        context_menu.exec(self.tabs_plans.mapToGlobal(point))

    def remove_plan(self, index: int):
        self.tabs_plans.removeTab(index)

    def delete_plan(self, index: int):
        widget: FrmTabPlan = self.tabs_plans.widget(index)
        confirmation = QMessageBox.question(self, 'Plan löschen',
                                            f'Möchten Sie den Plan {widget.plan.name} wirklich löschen?')
        if confirmation == QMessageBox.StandardButton.Yes:
            self.remove_plan(index)
            self.controller.execute(plan_commands.Delete(widget.plan.id))

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
        plan_widget: FrmTabPlan = self.tabs_plans.currentWidget()
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
        path_handler = configuration.project_paths.curr_user_path_handler
        paths = path_handler.get_config()
        output_folder = QFileDialog.getExistingDirectory(
            self, "Ordner auswählen, an dem die Excel-Pläne gespeichert werden sollen", paths.excel_output_path)
        if not output_folder:
            return
        paths.excel_output_path = output_folder
        path_handler.save_config_to_file(paths)


    def plan_save(self):
        """Der active Plan von self.tabs_plans wird unter vorgegebenem Namen gespeichert.
        Falls ein Plan dieses Namens schon vorhanden ist, wird angeboten diesen Plan zu löschen und den aktuellen Plan
         unter diesem Namen abzuspeichern."""
        # todo: Dialog, um Namensvorlage für das Speichern von Plänen festzulegen.

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
            self.tabs_plans.removeTab(tab_to_remove_index)

        def update_plan_name(widget: FrmTabPlan, new_name: str):
            update_name_command = plan_commands.UpdateName(widget.plan.id, new_name)
            self.controller.execute(update_name_command)
            widget.plan = update_name_command.updatet_plan

        def update_tab_text(new_text):
            self.tabs_plans.setTabText(self.tabs_plans.currentIndex(), new_text)

        if not self.tabs_plans.count():
            QMessageBox.critical(self, 'Plan speichern', 'Sie müssen zuerst ein Plan öffnen.')
            return
        active_widget: FrmTabPlan = self.tabs_plans.currentWidget()
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
        def export_finished(success: bool):
            if success:
                QMessageBox.information(self, 'Plan Excel-Export',
                                        f'Plan wurde erfolgreich unter\n{excel_output_path}\nexportiert.')
                signal_handling.handler_excel_export.signal_finished.disconnect()
                reply = QMessageBox.question(self, 'Plan Excel-Export', 'Soll die Excel-Datei jetzt geöffnet werden?',)
                if reply == QMessageBox.StandardButton.Yes:
                    os.startfile(excel_output_path)
            else:
                QMessageBox.critical(self, 'Plan Excel-Export', 'Plan konnte nicht exportiert werden.')

        def create_dir_if_not_exist(path: str):
            dir_path = path.rsplit(os.sep, 1)[0]
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

        signal_handling.handler_excel_export.signal_finished.connect(export_finished)

        widget: FrmTabPlan = self.tabs_plans.currentWidget()

        excel_output_path = os.path.join(self._get_excel_folder_output_path(widget), f'{widget.plan.name}.xlsx')
        create_dir_if_not_exist(excel_output_path)
        export_to_file = plan_to_xlsx.ExportToXlsx(self, widget, excel_output_path)
        export_to_file.execute()

    def lookup_for_excel_plan(self):
        widget: FrmTabPlan = self.tabs_plans.currentWidget()
        if not widget:
            QMessageBox.critical(self, 'Excel-Ordner', 'Sie müssen zuerst einen Plan öffnen.')
            return
        excel_output_path = os.path.join(self._get_excel_folder_output_path(widget), '')
        try:
            os.startfile(os.path.dirname(excel_output_path))
        except FileNotFoundError:
            QMessageBox.critical(self, 'Excel-Ordner',
                                 f'Es wurde noch keine Excel-Datei für den Zeitraum '
                                 f'{widget.plan.plan_period.start:%d.%m.%y}-{widget.plan.plan_period.end:%d.%m.%y} '
                                 f'des Teams {widget.plan.plan_period.team.name} erstellt.')
            return

    def _get_excel_folder_output_path(self, plan_tab: FrmTabPlan) -> str:
        path_handler = configuration.project_paths.curr_user_path_handler
        if not (output_folder := path_handler.get_config().excel_output_path):
            output_folder = 'excel_output'
        excel_output_path = os.path.join(
                output_folder, plan_tab.plan.plan_period.team.name,
                f"{plan_tab.plan.plan_period.start.strftime('%d.%m.%y')}-"
                f"{plan_tab.plan.plan_period.end.strftime('%d.%m.%y')}")
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
            return
        return {team.name: [MenuToolbarAction(self, None, 'Einrichtunskombis...',
                                              'Mögliche Kombinationen von Einrichtungen bearbeiten.',
                                              functools.partial(self.edit_comb_loc_poss, team)),
                            MenuToolbarAction(self, None, 'Excel-Settings...', 'Settings für Excel-Export des Plans bearbeiten.',
                                              functools.partial(self.edit_team_excel_export_settings, team)),
                            MenuToolbarAction(self, None, 'Bemerkungen...', 'Bemerkungen des Teams bearbeiten.',
                                              functools.partial(self.edit_team_notes, team))]
                for team in teams}

    def open_plan_period_masks(self, plan_period_id: UUID):
        if not self.curr_team:
            QMessageBox.critical(self, 'Planungsmasken', 'Sie müssen zuerst ein Team auswählen.')
            return
        dlg = DlgOpenPlanPeriodMask(self, self.curr_team.id, self.tabs_planungsmasken)
        if not dlg.exec():
            return
        self.open_plan_period_tab(dlg.curr_plan_period_id, 0, None, None)

    def open_plan_period_tab(self, plan_period_id: UUID, current_index_actors_locals_tabs: int,
                             curr_person_id: UUID | None, curr_location_id: UUID | None):
        plan_period = db_services.PlanPeriod.get(plan_period_id)
        widget_pp_tab = PlanPeriodTabWidget(self, plan_period_id)
        self.tabs_planungsmasken.addTab(widget_pp_tab, f'{plan_period.start:%d.%m.%y} - {plan_period.end:%d.%m.%y}')
        tabs_period = TabBar(widget_pp_tab, 'north', 10, None, None, True, False)

        tab_actor_plan_periods = FrmTabActorPlanPeriods(tabs_period, plan_period)
        if curr_person_id:
            tab_actor_plan_periods.data_setup(person_id=curr_person_id)
        tab_location_plan_periods = FrmTabLocationPlanPeriods(tabs_period, plan_period)
        if curr_location_id:
            tab_location_plan_periods.data_setup(location_id=curr_location_id)
        tabs_period.addTab(tab_actor_plan_periods, 'Mitarbeiter')
        tabs_period.addTab(tab_location_plan_periods, 'Einrichtungen')
        tabs_period.setCurrentIndex(current_index_actors_locals_tabs)

    def goto_team(self, team_id: UUID):
        if self.curr_team:
            self.save_current_team_config()
            while self.tabs_planungsmasken.count():
                self.tabs_planungsmasken.removeTab(0)
            while self.tabs_plans.count():
                self.tabs_plans.removeTab(0)

        self.curr_team = db_services.Team.get(team_id)
        self.load_current_team_config()
        self.setWindowTitle(f'hcc-plan  —  Team: {self.curr_team.name}')

    def master_data(self):
        if self.frm_master_data is None:
            self.frm_master_data = FrmMasterData(project_id=self.project_id)
            self.frm_master_data.show()
        self.frm_master_data.activateWindow()
        self.frm_master_data.showNormal()

    def show_plans(self):
        for i in range(self.tabs_left.count()):
            if self.tabs_left.widget(i).objectName() == 'plans':
                self.tabs_left.setCurrentIndex(i)

    def show_masks(self):
        for i in range(self.tabs_left.count()):
            if self.tabs_left.widget(i).objectName() == 'masks':
                self.tabs_left.setCurrentIndex(i)

    def show_availables(self):
        ...

    def statistics(self):
        ...

    def calculate_plans(self):
        if not self.curr_team:
            QMessageBox.critical(self, 'Aktuelles Team', 'Es ist kein Team ausgewählt.')
            return

        dlg = frm_calculate_plan.DlgCalculate(self, self.curr_team.id)
        if dlg.exec():
            reply = QMessageBox.question(self, 'Plänen anzeigen', 'Sollen die erstellten Pläne angezeigt werden?')
            if reply == QMessageBox.StandardButton.Yes:
                for plan_id in dlg.get_created_plan_ids():
                    self.open_plan_tab(plan_id)
                    QCoreApplication.processEvents()

    def open_plan_tab(self, plan_id: UUID):
        try:
            plan = db_services.Plan.get(plan_id)
        except Exception as e:
            QMessageBox.critical(self, 'Plan öffnen',
                                 f'Der Plan mit der ID {plan_id} konnte nicht geöffnet werden.\n'
                                 f'Fehler: {e}')
            return
        new_widget = frm_plan.FrmTabPlan(self.tabs_plans, plan, self.global_update_plan_tabs_progress_manager)
        self.tabs_plans.addTab(new_widget, plan.name)
        self.tabs_plans.setTabToolTip(self.tabs_plans.indexOf(new_widget), 'plan tooltip')
        self.tabs_plans.setCurrentIndex(self.tabs_plans.indexOf(new_widget))

    def plan_infos(self):
        curr_plan: schemas.PlanShow = self.tabs_plans.currentWidget().plan
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

    def send_email(self):
        ...

    def plan_events_to_google_calendar(self):
        plan = self.tabs_plans.currentWidget().plan
        if DlgSendAppointmentsToGoogleCal(self, plan).exec():
            transfer_plan_appointments(plan)


    def open_google_calendar(self):
        ...

    def create_google_calendar(self):
        def create():
            try:
                created_calendar = create_new_google_calendar(dlg.new_calender_data)
                if dlg.email_for_access_control:
                    share_calendar(created_calendar['id'], dlg.email_for_access_control)
                calendar = get_calendar_by_id(created_calendar['id'])
                curr_calendars_handler.save_calendar_json_to_file(calendar)
                return True
            except ServerNotFoundError as e:
                return {'error': 'ServerNotFoundError', 'message': e}
            except Exception as e:
                return {'error': 'Exception', 'message': e}

        @Slot(object)
        def finished(result):
            progressbar.close()
            if result is True:
                if email := dlg.email_for_access_control:
                    text_access_control = f'\nDer Nutzer kann hat Zugriff auf diesen Kalender über:\n {email}'
                else:
                    text_access_control = ('\n Sie haben noch keinen Zugriff für den Nutzer über eine Email '
                                           'eingerichtet.')
                QMessageBox.information(
                    self, 'Google-Kalender erstellen',
                    f'Ein neuer Google-Kalender für {person_name} wurde erstellt.{text_access_control}')
            else:
                if result['error'] == 'ServerNotFoundError':
                    error_text = f'{result["message"]}\nBitte prüfen Sie Ihre Internetverbindung.'
                else:
                    error_text = f'{result["message"]}'
                QMessageBox.critical(
                    self, 'Fehler beim Erstellen des Kalenders',
                    f'Beim Versuch, den Kalender für {person_name} zu erstellen\n'
                    f'ist folgender Fehler aufgetreten:\n'
                    f'{error_text}')

        dlg = CreateGoogleCalendar(self, self.project_id)
        if dlg.exec():
            worker = WorkerGeneral(create, True)
            worker.signals.finished.connect(finished)
            person_name = dlg.combo_persons.currentText()
            progressbar = DlgProgressInfinite(
                self, 'Google-Kalender erstellen',
                f'Ein neuer Google-Kalender für {person_name} wird erstellt.',
                'Abbruch'
            )
            progressbar.show()
            self.thread_pool.start(worker)

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

        worker = WorkerGeneral(synchronize, True)
        worker.signals.finished.connect(finished)
        progressbar = DlgProgressInfinite(self, 'Kalendersynchronisation',
                                          'Google-Kalender werden heruntergeladen...', 'Abbruch')
        progressbar.show()
        self.thread_pool.start(worker)


    def set_google_calendar_id(self):
        ...

    def upgrade_hcc_plan(self):
        ...

    def general_setting(self):
        ...

    def open_help(self):
        print('Hilfe...')

    def import_from_plan_api(self):
        dlg = DlgRemoteAccessPlanApi(self, self.project_id)
        if not dlg.exec():
            return

    def check_for_updates(self):
        ...

    def about_hcc_plan(self):
        ...

    def toggled_plan_events(self):
        menu: QMenu = self.main_menu.findChild(QMenu, 'Spielplan')
        if self.tabs_left.currentWidget().objectName() == 'masks':
            menu.setDisabled(True)
            self.actions['show_masks'].setChecked(True)
            for action in menu.actions():
                action.setDisabled(True)
        else:
            menu.setEnabled(True)
            self.actions['show_plans'].setChecked(True)
            for action in menu.actions():
                action.setEnabled(True)

    def restore_tabs(self):
        curr_team_id = team_start_config.curr_start_config_handler.get_start_config().default_team_id
        if curr_team_id:
            try:
                self.curr_team = db_services.Team.get(curr_team_id)
                self.actions_teams_in_clients_menu[curr_team_id].setChecked(True)
            except ValidationError:
                config = team_start_config.curr_start_config_handler.load_config_from_file()
                config.default_team_id = None
                config.teams = []
                team_start_config.curr_start_config_handler.save_config_to_file(config)
                return
            self.load_current_team_config()
            self.setWindowTitle(f'hcc-plan  —  Team: {self.curr_team.name}')

    def load_current_team_config(self):
        start_config_handler = team_start_config.curr_start_config_handler
        config_curr_team = start_config_handler.get_start_config_for_team(self.curr_team.id)
        for plan_period_id, pp_tab_config in config_curr_team.tabs_planungsmasken.items():
            self.open_plan_period_tab(plan_period_id,
                                      pp_tab_config['curr_index_actors_locals_tabs'],
                                      pp_tab_config.get('person_id'), pp_tab_config.get('location_id'))
        for plan_id in config_curr_team.tabs_plans:
            self.open_plan_tab(plan_id)
        self.tabs_planungsmasken.setCurrentIndex(config_curr_team.current_index_planungsmasken_tabs)
        self.tabs_plans.setCurrentIndex(config_curr_team.current_index_plans_tabs)
        self.tabs_left.setCurrentIndex(config_curr_team.current_index_left_tabs)

    def exit(self):
        self.close()

    def closeEvent(self, event=QCloseEvent):
        self.save_current_team_config()
        super().closeEvent(event)

    def save_current_team_config(self):
        start_config_handler = team_start_config.curr_start_config_handler
        curr_index_planungsmasken = self.tabs_planungsmasken.currentIndex()
        curr_index_plans = self.tabs_plans.currentIndex()
        curr_left_tabs_index = self.tabs_left.currentIndex()
        tabs_planungsmasken = {
            self.tabs_planungsmasken.widget(i).plan_period_id:
                {'person_id': self.tabs_planungsmasken.widget(i).findChild(FrmTabActorPlanPeriods).person_id,
                 'location_id': self.tabs_planungsmasken.widget(i).findChild(FrmTabLocationPlanPeriods).location_id,
                 'curr_index_actors_locals_tabs': self.tabs_planungsmasken.widget(i).findChild(TabBar).currentIndex()
                 }
            for i in range(self.tabs_planungsmasken.count())
        }
        tabs_plans = [self.tabs_plans.widget(i).plan.id for i in range(self.tabs_plans.count())]
        start_config_handler.save_config_for_team(
            self.curr_team.id if self.curr_team else None,
            team_start_config.StartConfigTeam(
                team_id=self.curr_team.id if self.curr_team else None,
                tabs_planungsmasken=tabs_planungsmasken, tabs_plans=tabs_plans,
                current_index_planungsmasken_tabs=curr_index_planungsmasken,
                current_index_plans_tabs=curr_index_plans,
                current_index_left_tabs=curr_left_tabs_index
            )
        )

    def put_actions_to_menu(self, menu: QMenuBar, actions_menu: dict | list | tuple):
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
        if type(actions_menu) == tuple:
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
# not_sure: team_start_config.toml wird korrupt, falls zwischen Teams gewechselt wird und die Team keine
#  geöffneten Planperioden haben.
