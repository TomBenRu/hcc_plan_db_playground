import sys
from uuid import UUID

from PySide6.QtCore import QRect
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMainWindow, QMenuBar, QMenu, QWidget, QMessageBox

from database import db_services
from gui.frm_masterdata import FrmMasterData
from gui.actions import Action
from gui.frm_new_team import FrmNewTeam
from gui.tabbars import TabBar
from gui.toolbars import MainToolBar


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowTitle('hcc-plan')
        self.setGeometry(QRect(0, 0, 800, 600))

        self.project_id = UUID('29597466CF7E458DA271E6BDE1AF3338')

        self.actions = {
            Action(self, 'resources/toolbar_icons/icons/blue-document--plus.png', 'Neue Planung...',
                   'Legt eine neue Planung an.', self.new_planperiod, short_cut='Ctrl+n'),
            Action(self, 'resources/toolbar_icons/icons/folder-open-document.png', 'Öffnen... (Pläne)',
                   'Öffnet einen bereits erstellten Plan.', self.open_plan),
            Action(self, 'resources/toolbar_icons/icons/folder-open-document.png', 'Öffnen... (Planungsdaten)',
                   'Öffnet Planungsmasken für Mitarbeiterverfügbarkeiten und Terminen an Einrichtungen',
                   self.open_actor_planperiod_location_planperiod),
            Action(self, 'resources/toolbar_icons/icons/disk.png', 'Plan speichern...', 'Speichert den aktiven Plan',
                   self.save_plan),
            Action(self, 'resources/toolbar_icons/icons/tables.png', 'Listen für Sperrtermine erzeugen...',
                   'Erstellt Listen, in welche Mitarbeiter ihre Sperrtermine eintragen können.',
                   self.sheets_for_availables),
            Action(self, 'resources/toolbar_icons/icons/table-export.png', 'Plan Excel-Export...',
                   'Exportiert den aktiven Plan in einer Excel-Datei', self.plan_export_to_excel),
            Action(self, 'resources/toolbar_icons/icons/blue-folder-open-table.png',
                   'Anzeigen der Pläne im Explorer...', 'Pläne der aktuellen Planung werden im Explorer angezeigt.',
                   self.lookup_for_excel_plan),
            Action(self, 'resources/toolbar_icons/icons/cross-script.png', 'Programm beenden', None, self.exit,
                   'Alt+F4'),
            Action(self, 'resources/toolbar_icons/icons/address-book-blue.png', 'Stammdaten...',
                   'Stammdaten von Mitarbeitern und Einsatzorten bearbeiten.', self.master_data),
            Action(self, 'resources/toolbar_icons/icons/block--plus.png', 'Neues Team...', 'Ein neues Team anlegen.',
                   self.new_team),
            Action(self, 'resources/toolbar_icons/icons/block--pencil.png', 'Teamname ändern',
                   'Ändern des Namens eines Teams.', self.edit_team_names),
            Action(self, None, 'Pläne anzeigen', None, self.show_plans),
            Action(self, None, 'Masken anzeigen', None, self.show_masks),
            Action(self, 'resources/toolbar_icons/icons/table-select-cells.png', 'Übersicht Verfügbarkeiten',
                   'Ansicht aller Verfügbarkeiten der Mitarbeiter in dieser Planung.', self.show_availables),
            Action(self, 'resources/toolbar_icons/icons/chart.png', 'Übersicht Einsätze der Mitarbeiter',
                   'Zeigt eine Übersicht der Einsätze aller Mitarbeiter*innen an.', self.statistics),
            Action(self, 'resources/toolbar_icons/icons/blue-document-attribute-p.png', 'Einsatzpläne erstellen...',
                   'Einen oder mehrere Einsatzpläne einer bestimmten Periode erstellen.', self.calculate_plans),
            Action(self, 'resources/toolbar_icons/icons/notebook--pencil.png', 'Plan-Infos...',
                   'Erstellt oder ändert Infos zur Planung.', self.plan_infos),
            Action(self, 'resources/toolbar_icons/icons/gear.png', 'Einstellungen...',
                   'Einstellungen für die Berechnung der Pläne.', self.plan_calculation_settings),
            Action(self, None, 'Events aus Plan zu Events-Maske...',
                   'Termine aus aktivem Plan in Planungsmaske Einrichtungen übernehmen.',
                   self.apply_events__plan_to_mask),
            Action(self, 'resources/toolbar_icons/icons/mail-send.png', 'Emails...', 'Emails versenden.',
                   self.send_email),
            Action(self, 'resources/toolbar_icons/icons/calendar--arrow.png', 'Termine übertragen',
                   'Termine des aktiven Plans zum Google-Kalender übertragen', self.plan_events_to_google_calendar),
            Action(self, 'resources/toolbar_icons/icons/calendar-blue.png', 'Google-Kalender öffnen...',
                   'Öffnet den Google-Kalender im Browser', self.open_google_calendar),
            Action(self, None, 'Kalender-ID setzen...', 'Kalender-ID des Google-Kalenders dieses Teams',
                   self.set_google_calendar_id),
            Action(self, None, 'Upgrade...', 'Zum Erweitern von "hcc-plan"', self.upgrade_hcc_plan),
            Action(self, 'resources/toolbar_icons/icons/gear--pencil.png', 'Einstellungen',
                   'Allgemeine Programmeinstellungen.', self.general_setting),
            Action(self, 'resources/toolbar_icons/icons/book-question.png', 'Hilfe...', 'Öffnet die Hilfe im Browser.',
                   self.open_help, 'F1'),
            Action(self, None, 'Auf Updates überprüfen...', 'Überprüft, ob Updates zum Programm vorhanden sind.',
                   self.check_for_updates),
            Action(self, 'resources/toolbar_icons/icons/information-italic.png', 'Über...', 'Info über das Programm',
                   self.about_hcc_plan)
        }
        self.actions: dict[str, Action] = {a.slot.__name__: a for a in self.actions}
        self.toolbar_actions: list[QAction | None] = [
            self.actions['new_planperiod'], self.actions['open_plan'], self.actions['save_plan'], None,
            self.actions['sheets_for_availables'], self.actions['plan_export_to_excel'],
            self.actions['lookup_for_excel_plan'], None, self.actions['exit']
        ]
        self.menu_actions = {
            '&Datei': [self.actions['new_planperiod'], None,
                       self.actions['sheets_for_availables'], None, self.actions['exit']],
            '&Klienten': [self.put_clients_to_menu, None, self.actions['master_data'], None, self.actions['new_team'],
                          None, self.actions['edit_team_names']],
            '&Ansicht': [{'toggle_plans_masks': (self.actions['show_plans'], self.actions['show_masks'])},
                         self.actions['show_availables'], self.actions['statistics']],
            '&Spielplan': [self.actions['calculate_plans'], self.actions['plan_infos'],
                           self.actions['plan_calculation_settings'], None,
                           self.actions['open_plan'], self.actions['save_plan'], None,
                           self.actions['plan_export_to_excel'], self.actions['lookup_for_excel_plan'], None,
                           self.actions['apply_events__plan_to_mask']
                           ],
            '&Emails': [self.actions['send_email']],
            '&Google Kalender': [self.actions['plan_events_to_google_calendar'], self.actions['open_google_calendar'],
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

        self.tabs_right = TabBar(self.central_widget, 'west', 16, 200)
        self.tabs_right.currentChanged.connect(self.toggled_plan_events)

        self.widget_planungsmasken = QWidget()
        self.widget_plans = QWidget()
        self.tabs_planungsmasken = TabBar(self.widget_planungsmasken, None, 10, 25)
        self.tabs_planungsmasken.setObjectName('masks')

        self.tabs_plans = TabBar(self.widget_plans, None, 10, 25)
        self.tabs_plans.setObjectName('plans')
        self.tabs_right.addTab(self.tabs_planungsmasken, 'Planungsmasken')
        self.tabs_right.addTab(self.tabs_plans, 'Einsatzpläne')

        self.tabs_planungsmasken.addTab(QWidget(), 'availables/events 1')  # statt QWidget wird das jew. Widget für die Planungsmaske der Einrichtungen verwendet.
        self.tabs_planungsmasken.addTab(QWidget(), 'availables/events 2')  # statt QWidget wird das jew. Widget für die Planungsmaske der Einrichtungen verwendet.
        self.tabs_plans.addTab(QWidget(), 'Planung 1')  # statt QWidget wird das jew. Widget für die Planungsmaske der Actors verwendet.
        self.tabs_plans.addTab(QWidget(), 'Planung 2')  # statt QWidget wird das jew. Widget für die Planungsmaske der Actors verwendet.

        self.frm_master_data = None

    def new_planperiod(self):
        print('neue Planperiode...')

    def open_plan(self):
        ...

    def open_actor_planperiod_location_planperiod(self):
        ...

    def save_plan(self):
        ...

    def sheets_for_availables(self):
        ...

    def plan_export_to_excel(self):
        ...

    def lookup_for_excel_plan(self):
        ...

    def put_clients_to_menu(self) -> tuple[Action]:
        teams = db_services.get_teams_of_project(self.project_id)
        return tuple(Action(self, None, team.name, f'Zu {team.name} wechseln.', self.goto_team) for team in teams)

    def goto_team(self, team_id: UUID):
        ...

    def master_data(self):
        if self.frm_master_data is None:
            self.frm_master_data = FrmMasterData(project_id=self.project_id)
            self.frm_master_data.show()
        self.frm_master_data.activateWindow()
        self.frm_master_data.showNormal()

    def new_team(self):
        FrmNewTeam(self).exec()

    def edit_team_names(self):
        ...

    def show_plans(self):
        for i in range(self.tabs_right.count()):
            if self.tabs_right.widget(i).objectName() == 'plans':
                self.tabs_right.setCurrentIndex(i)

    def show_masks(self):
        for i in range(self.tabs_right.count()):
            if self.tabs_right.widget(i).objectName() == 'masks':
                self.tabs_right.setCurrentIndex(i)

    def show_availables(self):
        ...

    def statistics(self):
        ...

    def calculate_plans(self):
        ...

    def plan_infos(self):
        ...

    def plan_calculation_settings(self):
        ...

    def apply_events__plan_to_mask(self):
        ...

    def send_email(self):
        ...

    def plan_events_to_google_calendar(self):
        ...

    def open_google_calendar(self):
        ...

    def set_google_calendar_id(self):
        ...

    def upgrade_hcc_plan(self):
        ...

    def general_setting(self):
        ...

    def open_help(self):
        print('Hilfe...')

    def check_for_updates(self):
        ...

    def about_hcc_plan(self):
        ...

    def toggled_plan_events(self):
        menu: QMenu = self.main_menu.findChild(QMenu, 'Spielplan')
        if self.tabs_right.currentWidget().objectName() == 'masks':
            menu.setDisabled(True)
            self.actions['show_masks'].setChecked(True)
            for action in menu.actions():
                action.setDisabled(True)
        else:
            menu.setEnabled(True)
            self.actions['show_plans'].setChecked(True)
            for action in menu.actions():
                action.setEnabled(True)

    def exit(self):
        sys.exit()

    def put_actions_to_menu(self, menu: QMenuBar, actions_menu: dict | list | tuple):
        if type(actions_menu) == tuple:
            ag = QActionGroup(self)
            ag.setExclusive(True)
            for action in actions_menu:
                a = ag.addAction(action)
                a.setCheckable(True)
                menu.addAction(a)
        else:
            for value in actions_menu:
                if type(value) == str:
                    current_menu = menu.addMenu(value)
                    current_menu.setObjectName(value.replace('&', ''))
                    self.put_actions_to_menu(current_menu, actions_menu[value])
                elif type(value) == dict:
                    self.put_actions_to_menu(menu, value)
                else:
                    if value is None:
                        menu.addSeparator()
                    else:
                        if type(value) == Action:
                            menu.addAction(value)
                        else:
                            self.put_actions_to_menu(menu, value())


