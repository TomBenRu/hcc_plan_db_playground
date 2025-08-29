import datetime
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox, QLineEdit,
                              QDialogButtonBox, QMessageBox, QTabWidget, QListWidget, QListWidgetItem,
                              QCheckBox, QHBoxLayout, QMenu)
from email_validator import validate_email, EmailNotValidError

from configuration.google_calenders import curr_calendars_handler
from database import db_services
from tools import custom_validators
from tools.custom_validators import validate_email_str
from tools.helper_functions import setup_form_help


class CreateGoogleCalendar(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Create Google Calendar'))
        self.project_id = project_id

        self.add_email_to_team_calendar: str | None = None
        self.calendar_type: str = 'person'  # 'person' oder 'team'
        self.selected_team_members: list[tuple[UUID, str]] = []  # (person_id, email)

        self._setup_data()
        self._setup_ui()
        
        # F1 Help Integration
        setup_form_help(self, "create_google_calendar", add_help_button=True)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)

        # Beschreibung oben
        self.lb_description = QLabel(
            self.tr('Here you can create a Google Calendar in your Google Account.\n'
                   'Choose between creating a personal calendar or a team calendar.')
        )
        self.layout_head.addWidget(self.lb_description)

        # Tab Widget für Personen- und Team-Kalender
        self.tab_widget = QTabWidget()
        self.layout.addWidget(self.tab_widget)

        # Personen-Kalender Tab (bestehende Logik)
        self.tab_person = QWidget()
        self.tab_widget.addTab(self.tab_person, self.tr('Personal Calendar'))
        self._setup_person_tab()

        # Team-Kalender Tab (neue Logik)
        self.tab_team = QWidget()
        self.tab_widget.addTab(self.tab_team, self.tr('Team Calendar'))
        self._setup_team_tab()

        # Employee-Events-Kalender Tab
        self.tab_employee_events = QWidget()
        self.tab_widget.addTab(self.tab_employee_events, self.tr('Employee Events Calendar'))
        self._setup_employee_events_tab()

        # Tab-Wechsel Handler
        self.tab_widget.currentChanged.connect(self._tab_changed)

        self.layout.addLayout(self.layout_foot)

        # Button Box
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_person_tab(self):
        """Setup der UI für Personen-Kalender (bestehende Logik)"""
        person_layout = QFormLayout(self.tab_person)
        
        self.combo_persons = QComboBox()
        self._fill_combo_persons()
        self.le_summary = QLineEdit()
        self.le_description = QLineEdit()
        self.combo_persons.currentIndexChanged.connect(self._combo_persons_index_changed)
        self.le_email = QLineEdit()
        
        person_layout.addRow(self.tr('User:'), self.combo_persons)
        person_layout.addRow(self.tr('Email for user access:'), self.le_email)
        person_layout.addRow(self.tr('Calendar name:'), self.le_summary)
        person_layout.addRow(self.tr('Short description:'), self.le_description)

    def _setup_team_tab(self):
        """Setup der UI für Team-Kalender"""
        team_layout = QFormLayout(self.tab_team)
        
        self.combo_teams = QComboBox()
        self._fill_combo_teams()
        self.le_team_summary = QLineEdit()
        self.le_team_description = QLineEdit()
        self.combo_teams.currentIndexChanged.connect(self._combo_team_index_changed)
        
        team_layout.addRow(self.tr('Team:'), self.combo_teams)
        team_layout.addRow(self.tr('Calendar name:'), self.le_team_summary)
        team_layout.addRow(self.tr('Short description:'), self.le_team_description)
        
        # Team-Mitglieder Auswahl
        self.lw_team_members = QListWidget()
        
        # Context-Menu für E-Mail-Bearbeitung
        self.lw_team_members.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lw_team_members.customContextMenuRequested.connect(self._team_members_context_menu)
        
        # Tooltip für Benutzerführung
        self.lw_team_members.setToolTip(
            self.tr('Select team members for calendar access.\n'
                   'Right-click on a member to edit their email address.')
        )
        
        team_layout.addRow(self.tr('Grant access to team members:'), self.lw_team_members)

    def _setup_employee_events_tab(self):
        """Setup der UI für Employee-Events-Kalender"""
        ee_layout = QFormLayout(self.tab_employee_events)
        
        # Team-Auswahl
        self.combo_ee_teams = QComboBox()
        self._fill_combo_ee_teams()
        self.combo_ee_teams.currentIndexChanged.connect(self._combo_ee_team_index_changed)
        ee_layout.addRow(self.tr('Team:'), self.combo_ee_teams)
        
        # Personen-Filter
        self.combo_person_filter = QComboBox()
        self._fill_combo_person_filter()
        self.combo_person_filter.currentIndexChanged.connect(self._person_filter_changed)
        ee_layout.addRow(self.tr('Filter persons:'), self.combo_person_filter)
        
        # Personen-Liste für Freigabe
        self.lw_ee_persons = QListWidget()
        
        # Context-Menu für E-Mail-Bearbeitung (wie bei Team-Kalender)
        self.lw_ee_persons.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.lw_ee_persons.customContextMenuRequested.connect(self._ee_persons_context_menu)
        
        # Tooltip für Benutzerführung
        self.lw_ee_persons.setToolTip(
            self.tr('Select persons for calendar access.\n'
                   'Right-click on a person to edit their email address.')
        )
        
        ee_layout.addRow(self.tr('Grant access to persons:'), self.lw_ee_persons)
        
        # Kalender-Name (auto-generiert, editierbar)
        self.le_ee_summary = QLineEdit()
        self.le_ee_description = QLineEdit()
        
        ee_layout.addRow(self.tr('Calendar name:'), self.le_ee_summary)
        ee_layout.addRow(self.tr('Short description:'), self.le_ee_description)
        
        # Initial setup
        self._update_ee_calendar_info()
        self._load_ee_persons()

    def _fill_combo_ee_teams(self):
        """Befüllt die ComboBox mit verfügbaren Teams für Employee-Events"""
        self.combo_ee_teams.clear()
        no_team_calendar_exists = len([c for c in self.avail_google_calendars.values()
                                       if c.type == 'employee_events' and (c.team_id is None)])
        if no_team_calendar_exists == 0:
            self.combo_ee_teams.addItem(self.tr('no team'), None)
        for team in sorted(self.teams_for_ee_calendar, key=lambda x: x.name):
            self.combo_ee_teams.addItem(team.name, team.id)

    def _fill_combo_person_filter(self):
        """Befüllt die ComboBox mit Person-Filter-Optionen"""
        self.combo_person_filter.clear()
        self.combo_person_filter.addItem(self.tr('All employees'), 'all')
        self.combo_person_filter.addItem(self.tr('Members of any team'), 'any_team')
        self.combo_person_filter.addItem(self.tr('Members of no team'), 'no_team')
        
        # Spezifische Teams als Filter-Optionen
        for team in sorted(self.teams_of_project, key=lambda x: x.name):
            self.combo_person_filter.addItem(self.tr('Team: {team_name}').format(team_name=team.name), team.id)

    def _combo_ee_team_index_changed(self):
        """Handler für Team-Auswahl Änderungen bei Employee-Events"""
        self._update_ee_calendar_info()
        self._load_ee_persons()

    def _person_filter_changed(self):
        """Handler für Person-Filter Änderungen"""
        self._load_ee_persons()

    def _update_ee_calendar_info(self):
        """Aktualisiert Kalender-Name und Beschreibung basierend auf Auswahl"""
        if self.combo_ee_teams.currentData():
            # Team-spezifische Employee-Events
            team_name = self.combo_ee_teams.currentText()
            team_id = self.combo_ee_teams.currentData()
            
            calendar_name = self.tr('Employee Events - {project_name} {team_name}').format(
                project_name=self.project.name,
                team_name=team_name
            )
            
            description = '{{"description": "Employee events - team", "team_id": "{team_id}"}}'.format(
                team_id=team_id
            )
        else:
            # Employee-Events ohne Team-Zuordnung
            calendar_name = self.tr('Employee Events - {project_name} No team').format(
                project_name=self.project.name
            )
            
            description = '{"description": "Employee events - no team", "team_id": ""}'
        
        self.le_ee_summary.setText(calendar_name)
        self.le_ee_description.setText(description)
        self.le_ee_description.setDisabled(True)  # Nicht editierbar

    def _load_ee_persons(self):
        """Lädt Personen für Employee-Events Kalender basierend auf Filter"""
        self.lw_ee_persons.clear()
        
        filter_value = self.combo_person_filter.currentData()
        persons_to_show = []
        
        if filter_value == 'all':
            # Alle Personen des Projekts
            persons_to_show = self.persons_of_project
        elif filter_value == 'any_team':
            # Personen mit Team-Zugehörigkeit (heute)
            import datetime
            today = datetime.date.today()
            person_ids_with_team = set()
            for team in self.teams_of_project:
                team_assigns = db_services.TeamActorAssign.get_all_at__date(today, team.id)
                for assign in team_assigns:
                    person_ids_with_team.add(assign.person.id)
            persons_to_show = [p for p in self.persons_of_project if p.id in person_ids_with_team]
        elif filter_value == 'no_team':
            # Personen ohne Team-Zugehörigkeit (heute)
            import datetime
            today = datetime.date.today()
            person_ids_with_team = set()
            for team in self.teams_of_project:
                team_assigns = db_services.TeamActorAssign.get_all_at__date(today, team.id)
                for assign in team_assigns:
                    person_ids_with_team.add(assign.person.id)
            persons_to_show = [p for p in self.persons_of_project if p.id not in person_ids_with_team]
        else:
            # Spezifisches Team (filter_value ist team_id)
            import datetime
            team_assigns = db_services.TeamActorAssign.get_all_at__date(datetime.date.today(), filter_value)
            persons_to_show = [assign.person for assign in team_assigns]
        
        # Personen zur Liste hinzufügen
        for person in sorted(persons_to_show, key=lambda x: x.full_name):

            item = QListWidgetItem(f"{person.full_name} ({person.email})")

            item.setData(Qt.ItemDataRole.UserRole, person.id)  # Person ID speichern
            item.setData(Qt.ItemDataRole.UserRole + 1, person.email)  # E-Mail speichern

            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

            self.lw_ee_persons.addItem(item)

    def _ee_persons_context_menu(self, position):
        """Context-Menu für Employee-Events Personen (Rechtsklick)"""
        item = self.lw_ee_persons.itemAt(position)
        if not item:
            return  # Kein Item unter dem Mauszeiger
        
        # Context-Menu erstellen (gleiche Logik wie bei Team-Mitgliedern)
        menu = QMenu(self)
        
        edit_email_action = menu.addAction(
            self.tr('Edit email address...')
        )
        
        # Menu anzeigen und Auswahl abwarten
        action = menu.exec(self.lw_ee_persons.mapToGlobal(position))
        
        if action == edit_email_action:
            self._edit_ee_person_email(item)

    def _edit_ee_person_email(self, item: QListWidgetItem):
        """Öffnet Dialog zur E-Mail-Bearbeitung für Employee-Events Person"""
        person_name = item.text()
        current_email = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        
        # E-Mail-Dialog öffnen (gleicher Dialog wie bei Team-Mitgliedern)
        dialog = EditMemberEmailDialog(self, person_name, current_email)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_email = dialog.get_new_email()
            
            # Item-Data mit neuer E-Mail aktualisieren
            item.setData(Qt.ItemDataRole.UserRole + 1, new_email)
            
            # Tooltip für geänderte E-Mail
            if new_email != current_email:
                original_tooltip = self.tr('Original: {original}\nCurrent: {current}').format(
                    original=current_email,
                    current=new_email
                )
                item.setToolTip(original_tooltip)

    def _tab_changed(self, index: int):
        """Handler für Tab-Wechsel"""
        if index == 0:  # Personen-Tab
            self.calendar_type = 'person'
        elif index == 1:  # Team-Tab
            self.calendar_type = 'team'
        elif index == 2:  # Employee-Events-Tab
            self.calendar_type = 'employee_events'

    def _setup_data(self):
        self.project = db_services.Project.get(self.project_id)
        self.persons_of_project = db_services.Person.get_all_from__project(self.project_id)
        self.teams_of_project = db_services.Team.get_all_from__project(self.project_id)
        self.avail_google_calendars = curr_calendars_handler.get_calenders()
        
        # Personen im Person-Tab ohne bestehenden Kalender
        self.persons_for_new_calendar = sorted(
            (p for p in self.persons_of_project
             if p.id not in {c.person_id for c in self.avail_google_calendars.values()}),
            key=lambda x: x.full_name
        )
        
        # Teams im Team-Tab ohne bestehenden Kalender
        self.teams_for_new_calendar = sorted(
            (t for t in self.teams_of_project
             if t.id not in {c.team_id for c in self.avail_google_calendars.values() if c.team_id}),
            key=lambda x: x.name
        )

        # Teams im Employee-Events-Tab
        self.teams_for_ee_calendar = sorted(
            (t for t in self.teams_of_project if t.id not in {c.team_id for c in self.avail_google_calendars.values()
                                                              if c.type == 'employee_events'}),
            key=lambda x: x.name
        )

    def _fill_combo_persons(self):
        self.combo_persons.addItem(self.tr('no person'), None)
        for person in self.persons_for_new_calendar:
            self.combo_persons.addItem(person.full_name, person.id)

    def _fill_combo_teams(self):
        """Befüllt die ComboBox mit verfügbaren Teams"""
        self.combo_teams.addItem(self.tr('no team'), None)
        for team in self.teams_for_new_calendar:
            self.combo_teams.addItem(team.name, team.id)

    def _combo_persons_index_changed(self):
        if self.combo_persons.currentData():
            self.le_description.setEnabled(True)
            self.le_summary.setText(
                self.tr('{project_name} - Appointments of {person_name}').format(
                    project_name=self.project.name,
                    person_name=self.combo_persons.currentText()
                )
            )
            self.le_description.setText(
                '{{"description": "{desc}", "person_id": "{person_id}"}}'.format(
                    desc=self.tr('Person appointments {person_name}').format(
                        person_name=self.combo_persons.currentText()
                    ),
                    person_id=self.combo_persons.currentData()
                )
            )
            self.le_description.setDisabled(True)
        else:
            self.le_description.setEnabled(True)
            self.le_summary.clear()
            self.le_description.clear()

    def _combo_team_index_changed(self):
        """Handler für Team-Auswahl Änderungen"""
        if self.combo_teams.currentData():
            team_id = self.combo_teams.currentData()
            team_name = self.combo_teams.currentText()
            
            # Automatische Namensgebung für Team-Kalender
            self.le_team_summary.setText(
                self.tr('{project_name} - Team {team_name}').format(
                    project_name=self.project.name,
                    team_name=team_name
                )
            )
            
            # Automatische Beschreibung mit team_id
            self.le_team_description.setText(
                '{{"description": "{desc}", "team_id": "{team_id}"}}'.format(
                    desc=self.tr('Team appointments {team_name}').format(team_name=team_name),
                    team_id=team_id
                )
            )
            self.le_team_description.setDisabled(True)
            
            # Team-Mitglieder laden
            self._load_team_members(team_id)
        else:
            self.le_team_summary.clear()
            self.le_team_description.clear()
            self.le_team_description.setEnabled(True)
            self.lw_team_members.clear()

    def _load_team_members(self, team_id: UUID):
        """Lädt Team-Mitglieder für Zugriffskontrolle"""
        import datetime
        
        self.lw_team_members.clear()
        
        # Aktuelle Team-Mitglieder zum heutigen Datum
        current_members = db_services.TeamActorAssign.get_all_at__date(datetime.date.today(), team_id)
        
        for member_assign in current_members:
            person = member_assign.person
            
            # E-Mail aus Datenbank laden (ist immer vorhanden)
            person_email = person.email
            
            # ListWidget Item mit Checkbox erstellen
            item = QListWidgetItem(f"{person.full_name} ({person_email})")
            item.setData(Qt.ItemDataRole.UserRole, person.id)  # Person ID speichern
            item.setData(Qt.ItemDataRole.UserRole + 1, person_email)  # E-Mail speichern
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            
            self.lw_team_members.addItem(item)

    def _team_members_context_menu(self, position):
        """Context-Menu für Team-Mitglieder (Rechtsklick)"""
        item = self.lw_team_members.itemAt(position)
        if not item:
            return  # Kein Item unter dem Mauszeiger
        
        # Context-Menu erstellen
        menu = QMenu(self)
        
        # "E-Mail bearbeiten" Aktion
        edit_email_action = menu.addAction(
            self.tr('Edit email address...')
        )
        
        # Icon oder weitere visuelle Hinweise könnten hier hinzugefügt werden
        # edit_email_action.setIcon(some_icon)
        
        # Menu anzeigen und Auswahl abwarten
        action = menu.exec(self.lw_team_members.mapToGlobal(position))
        
        if action == edit_email_action:
            self._edit_member_email(item)
    
    def _edit_member_email(self, item: QListWidgetItem):
        """Öffnet Dialog zur E-Mail-Bearbeitung für ein Team-Mitglied"""
        member_name = item.text()
        current_email = item.data(Qt.ItemDataRole.UserRole + 1) or ""
        
        # E-Mail-Dialog öffnen
        dialog = EditMemberEmailDialog(self, member_name, current_email)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_email = dialog.get_new_email()
            
            # Item-Data mit neuer E-Mail aktualisieren
            item.setData(Qt.ItemDataRole.UserRole + 1, new_email)
            
            # Optional: Visuellen Hinweis hinzufügen, dass E-Mail geändert wurde
            if new_email != current_email:
                # Tooltip aktualisieren um zu zeigen, dass E-Mail geändert wurde
                original_tooltip = self.tr('Original: {original}\nCurrent: {current}').format(
                    original=current_email,
                    current=new_email
                )
                item.setToolTip(original_tooltip)

    def accept(self):
        if self.calendar_type == 'person':
            # Bestehende Personen-Kalender Logik
            if self.le_email.text():
                if not (result := validate_email_str(self.le_email.text()))['valid']:
                    QMessageBox.warning(
                        self,
                        self.tr('Invalid Email'),
                        self.tr('The email address is not valid.\n{error}').format(error=result['error'])
                    )
                    return
                taa = db_services.TeamActorAssign.get_at__date(self.combo_persons.currentData(), datetime.date.today())
                team_calendar = next((c for c in curr_calendars_handler.get_calenders().values()
                                      if c.team_id == taa.team.id), None)
                if taa and team_calendar:
                    reply = QMessageBox.question(
                        self,
                        self.tr('Team Calendar Access'),
                        self.tr('Should the user also be granted access rights to the team calendar of team {team_name}?')
                        .format(team_name=taa.team.name)
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.add_email_to_team_calendar = team_calendar.id
        elif self.calendar_type == 'team':  # team
            # Team-Kalender Validierung
            if not self.combo_teams.currentData():
                QMessageBox.warning(
                    self,
                    self.tr('Team Selection'),
                    self.tr('Please select a team for the calendar.')
                )
                return
            
            if not self.le_team_summary.text():
                QMessageBox.warning(
                    self,
                    self.tr('Calendar Name'),
                    self.tr('Please enter a name for the calendar.')
                )
                return
        else:  # employee_events
            # Employee-Events-Kalender Validierung
            if not self.le_ee_summary.text():
                QMessageBox.warning(
                    self,
                    self.tr('Calendar Name'),
                    self.tr('Please enter a name for the calendar.')
                )
                return
            
            # Validierung ist nicht nötig - "no team" ist eine gültige Option
        
        super().accept()

    @property
    def new_calender_data(self) -> dict[str, str]:
        """Kalender-Daten basierend auf ausgewähltem Typ"""
        if self.calendar_type == 'person':
            return {
                'summary': self.le_summary.text(),
                'description': self.le_description.text(),
                'location': 'Berlin',
                'timeZone': 'Europe/Berlin'
            }
        elif self.calendar_type == 'team':
            return {
                'summary': self.le_team_summary.text(),
                'description': self.le_team_description.text(),
                'location': 'Berlin',
                'timeZone': 'Europe/Berlin'
            }
        else:  # employee_events
            return {
                'summary': self.le_ee_summary.text(),
                'description': self.le_ee_description.text(),
                'location': 'Berlin',
                'timeZone': 'Europe/Berlin'
            }

    @property
    def email_for_access_control(self):
        """E-Mail für Zugriffskontrolle - abhängig vom Kalender-Typ"""
        if self.calendar_type == 'person':
            return self.le_email.text()
        elif self.calendar_type == 'team':
            # Bei Team-Kalendern wird die erste ausgewählte E-Mail zurückgegeben
            # oder leerer String wenn keine ausgewählt
            emails = self.selected_team_member_emails
            return emails[0] if emails else ""
        else:  # employee_events
            # Bei Employee-Events-Kalendern wird die erste ausgewählte E-Mail zurückgegeben
            emails = self.selected_ee_person_emails
            return emails[0] if emails else ""

    @property
    def selected_team_member_emails(self) -> list[str]:
        """Liste der E-Mail-Adressen ausgewählter Team-Mitglieder"""
        if self.calendar_type != 'team':
            return []
            
        emails = []
        for index in range(self.lw_team_members.count()):
            item = self.lw_team_members.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                person_id = item.data(Qt.ItemDataRole.UserRole)
                stored_email = item.data(Qt.ItemDataRole.UserRole + 1)
                
                if stored_email:
                    emails.append(stored_email)
                # Note: E-Mail kann über Context-Menu (Rechtsklick) bearbeitet werden
                    
        return emails

    @property
    def selected_ee_person_emails(self) -> list[str]:
        """Liste der E-Mail-Adressen ausgewählter Personen für Employee-Events-Kalender"""
        if self.calendar_type != 'employee_events':
            return []
            
        emails = []
        for index in range(self.lw_ee_persons.count()):
            item = self.lw_ee_persons.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                person_id = item.data(Qt.ItemDataRole.UserRole)
                stored_email = item.data(Qt.ItemDataRole.UserRole + 1)
                
                if stored_email:
                    emails.append(stored_email)
                # Note: E-Mail kann über Context-Menu (Rechtsklick) bearbeitet werden
                    
        return emails



class EditMemberEmailDialog(QDialog):
    """Dialog zur Bearbeitung der E-Mail-Adresse eines Team-Mitglieds"""
    
    def __init__(self, parent: QWidget, member_name: str, current_email: str):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Edit Email Address'))
        self.setModal(True)
        self.resize(400, 150)
        
        self.member_name = member_name
        self.current_email = current_email
        self.new_email = current_email  # Initial auf aktuelle E-Mail setzen
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup der Dialog-UI"""
        layout = QVBoxLayout(self)
        
        # Beschreibung
        description_label = QLabel(
            self.tr('Edit email address for team member: {member_name}').format(
                member_name=self.member_name
            )
        )
        layout.addWidget(description_label)
        
        # Form Layout für E-Mail-Eingaben
        form_layout = QFormLayout()
        
        # Aktuelle E-Mail (nur Anzeige)
        self.current_email_display = QLineEdit(self.current_email)
        self.current_email_display.setReadOnly(True)
        form_layout.addRow(self.tr('Current email from database:'), self.current_email_display)
        
        # Neue E-Mail (Eingabe)
        self.new_email_input = QLineEdit(self.current_email)
        self.new_email_input.selectAll()  # Text vorselektieren für einfache Bearbeitung
        form_layout.addRow(self.tr('New email for Google Calendar:'), self.new_email_input)
        
        layout.addLayout(form_layout)
        
        # Info-Text
        info_label = QLabel(
            self.tr('The new email address will be used for Google Calendar access.\n'
                   'The database email remains unchanged.')
        )
        info_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(info_label)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._accept_dialog)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        
        # Focus auf Eingabefeld
        self.new_email_input.setFocus()
    
    def _accept_dialog(self):
        """Validierung und Übernahme der neuen E-Mail"""
        new_email = self.new_email_input.text().strip()
        
        # E-Mail-Validierung
        if not new_email:
            QMessageBox.warning(
                self,
                self.tr('Invalid Email'),
                self.tr('Please enter an email address.')
            )
            return

        if not (result := validate_email_str(new_email))['valid']:
            QMessageBox.warning(
                self,
                self.tr('Invalid Email'),
                self.tr('The email address is not valid.\n{error}').format(error=result['error'])
            )
            return
        
        # Neue E-Mail speichern und Dialog schließen
        self.new_email = new_email
        self.accept()
    
    def get_new_email(self) -> str:
        """Gibt die neue E-Mail-Adresse zurück"""
        return self.new_email
