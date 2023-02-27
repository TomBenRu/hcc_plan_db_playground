import sys

from PySide6.QtCore import QRect
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QMainWindow, QToolBar, QMenuBar, QMenu, QTabWidget, QWidget, QStyle, QPushButton, \
    QVBoxLayout, QSizePolicy

from gui.actions import Action
from gui.tabbars import TabBar
from gui.toolbars import MainToolBar


class MainWindow(QMainWindow):
    def __init__(self, app):
        super().__init__()
        self.setWindowTitle('hcc-plan')
        self.setGeometry(QRect(0, 0, 800, 600))

        self.actions = {
            'new_planperiod': Action(self, 'resources/toolbar_icons/icons/blue-document--plus.png', 'Neue Planung...',
                                     'Legt eine neue Planung an.', self.new_planperiod),
            'open_plan': Action(self, 'resources/toolbar_icons/icons/folder-open-document.png', 'Öffnen... (Pläne)',
                                'Öffnet einen bereits erstellten Plan.', self.open_plan),
            'open_actor_planperiod_location_planperiod': Action(
                self, 'resources/toolbar_icons/icons/folder-open-document.png', 'Öffnen... (Planungsdaten)',
                'Öffnet Planungsmasken für Mitarbeiterverfügbarkeiten und Terminen an Einrichtungen',
                self.open_actor_planperiod_location_planperiod),
            'save_plan': Action(self, 'resources/toolbar_icons/icons/disk.png', 'Plan speichern...',
                                'Speichert den aktiven Plan', self.save_plan),
            'new_sheets_for_availables': Action(
                self, 'resources/toolbar_icons/icons/tables.png',
                'Listen für Sperrtermine erzeugen...',
                'Erstellt Listen, in welche Mitarbeiter ihre Sperrtermine eintragen können.',
                self.sheets_for_availables),
            'plan_export_to_excel': Action(
                self, 'resources/toolbar_icons/icons/table-export.png', 'Plan Excel-Export...',
                'Exportiert den aktiven Plan in einer Excel-Datei', self.plan_export_to_excel),
            'lookup_for_excel_plan': Action(
                self, 'resources/toolbar_icons/icons/blue-folder-open-table.png', 'Anzeigen der Pläne im Explorer...',
                'Pläne der aktuellen Planung werden im Explorer angezeigt.', self.lookup_for_excel_plan),
            'exit': Action(self, 'resources/toolbar_icons/icons/cross-script.png', 'Programm beenden', None, sys.exit)
        }
        self.actions_toolbar: list[QAction | None] = [self.actions['new_planperiod'], self.actions['open_plan'], self.actions['save_plan'], None,
                       self.actions['new_sheets_for_availables'], self.actions['plan_export_to_excel'],
                       self.actions['lookup_for_excel_plan'], None, self.actions['exit']]
        self.actions_menu = {
            '&Datei': [self.actions['new_planperiod'], self.actions['open_plan'], self.actions['save_plan'], None,
                       self.actions['new_sheets_for_availables'], self.actions['plan_export_to_excel'],
                       self.actions['lookup_for_excel_plan'], None, self.actions['exit']],
            '&Klienten': [],
            '&Ansicht': [],
            '&Spielplan': [],
            '&Emails': [],
            '&Google Kalender': [],
            'E&xtras': [],
            '&Hilfe': []
        }

        self.toolbar = MainToolBar('Main Toolbar', self.actions_toolbar, icon_size=16)

        self.addToolBar(self.toolbar)

        self.put_actions_to_menu(self.menuBar(), self.actions_menu)

        self.statusBar()

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.tabs_right = TabBar(self.central_widget, 'west', 16, 200)

        self.widget_planungsmasken = QWidget()
        self.widget_availables = QWidget()
        self.tabs_planungsmasken = TabBar(self.widget_planungsmasken, None, 10, 25)
        self.tabs_plans = TabBar(self.widget_availables, None, 10, 25)
        self.tabs_right.addTab(self.tabs_planungsmasken, 'Planungsmasken')
        self.tabs_right.addTab(self.tabs_plans, 'Einsatzpläne')

        print(f'{self.tabs_right.count()=}')
        for i in range(self.tabs_right.count()):
            print(f'{self.tabs_right.widget(i)=}')

        self.tabs_planungsmasken.addTab(QWidget(), 'availables/events 1')  # statt QWidget wird das jew. Widget für die Planungsmaske der Einrichtungen verwendet.
        self.tabs_planungsmasken.addTab(QWidget(), 'availables/events 2')  # statt QWidget wird das jew. Widget für die Planungsmaske der Einrichtungen verwendet.
        self.tabs_plans.addTab(QWidget(), 'Planung 1')  # statt QWidget wird das jew. Widget für die Planungsmaske der Actors verwendet.
        self.tabs_plans.addTab(QWidget(), 'Planung 2')  # statt QWidget wird das jew. Widget für die Planungsmaske der Actors verwendet.

    def new_planperiod(self):
        ...

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

    def put_actions_to_menu(self, menu: QMenuBar, actions_menu: dict | list):
        for value in actions_menu:
            if type(value) == str:
                current_menu = menu.addMenu(value)
                self.put_actions_to_menu(current_menu, actions_menu[value])
            elif type(value) == dict:
                self.put_actions_to_menu(menu, value)
            else:
                if value is None:
                    menu.addSeparator()
                else:
                    menu.addAction(value)


