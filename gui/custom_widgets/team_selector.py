"""Widget zur Team-Auswahl bei Multi-Team-Personen.

Dieses Widget wird automatisch versteckt, wenn eine Person nur einem
oder keinem Team zugeordnet ist. Bei mehreren Teams ermöglicht es
die Auswahl des relevanten Teams für Präferenz-Einstellungen.
"""

import datetime
from uuid import UUID

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox

from database import db_services, schemas
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData



class TeamSelectorWidget(QWidget):
    """Widget zur Team-Auswahl bei Multi-Team-Personen.

    Zeigt eine ComboBox mit allen Teams, denen die Person am Datum zugeordnet ist.
    Wird automatisch versteckt, wenn nur ein oder kein Team vorhanden ist.

    Signals:
        teamChanged(schemas.TeamShow | None): Emittiert wenn ein Team ausgewählt wird.
    """

    teamChanged = Signal(object)  # Emittiert TeamShow oder None

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)

        self._person_id: UUID | None = None
        self._teams: list[schemas.TeamShow] = []
        self._current_team: schemas.TeamShow | None = None

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.lb_team = QLabel(self.tr('Team:'))
        self.cb_team = QComboBoxToFindData()
        self.cb_team.setMinimumWidth(200)
        self.cb_team.currentIndexChanged.connect(self._on_team_changed)

        self.layout.addWidget(self.lb_team)
        self.layout.addWidget(self.cb_team)
        self.layout.addStretch()

    def update_teams(self, person_id: UUID, date: datetime.date) -> schemas.TeamShow | None:
        """Aktualisiert die Team-Liste für die Person am Datum.

        Args:
            person_id: ID der Person
            date: Das Datum für das die Teams ermittelt werden sollen

        Returns:
            Das erste/ausgewählte Team oder None wenn kein Team vorhanden
        """
        self._person_id = person_id

        # Vorher ausgewähltes Team merken, um es nach dem Neuladen wiederherzustellen
        previous_team_id = self._current_team.id if self._current_team else None

        # Alle Teams der Person am Datum holen
        self._teams = db_services.TeamActorAssign.get_all_teams_at_date(person_id, date)

        # ComboBox befüllen
        self.cb_team.blockSignals(True)
        self.cb_team.clear()

        sorted_teams = sorted(self._teams, key=lambda t: t.name)
        for team in sorted_teams:
            self.cb_team.addItem(team.name, team.id)

        # Sichtbarkeit steuern: nur bei >1 Team anzeigen
        self.setVisible(len(self._teams) > 1)

        # Aktuelles Team setzen
        if self._teams:
            # Versuchen, das vorher ausgewählte Team beizubehalten
            idx = self.cb_team.findData(previous_team_id) if previous_team_id else -1

            if idx >= 0:
                self.cb_team.setCurrentIndex(idx)
                # _current_team aus der neuen Team-Liste holen (für aktuelle Daten)
                self._current_team = next((t for t in self._teams if t.id == previous_team_id), sorted_teams[0])
            else:
                # Vorheriges Team nicht mehr verfügbar, erstes Team nehmen
                self.cb_team.setCurrentIndex(0)
                self._current_team = sorted_teams[0]
        else:
            self._current_team = None

        self.cb_team.blockSignals(False)

        return self._current_team

    def _on_team_changed(self, index: int):
        """Wird aufgerufen wenn der Benutzer ein Team auswählt."""
        if index < 0:
            self._current_team = None
        else:
            team_id = self.cb_team.itemData(index)
            self._current_team = next((t for t in self._teams if t.id == team_id), None)

        self.teamChanged.emit(self._current_team)

    def get_current_team(self) -> schemas.TeamShow | None:
        """Gibt das aktuell ausgewählte Team zurück."""
        return self._current_team

    def set_current_team(self, team_id: UUID) -> bool:
        """Setzt das aktuell ausgewählte Team.

        Args:
            team_id: ID des Teams das ausgewählt werden soll

        Returns:
            True wenn das Team gefunden und gesetzt wurde, sonst False
        """
        idx = self.cb_team.findData(team_id)
        if idx >= 0:
            self.cb_team.setCurrentIndex(idx)
            return True
        return False

    def get_teams(self) -> list[schemas.TeamShow]:
        """Gibt alle Teams der Person am Datum zurück."""
        return self._teams.copy()

    def has_multiple_teams(self) -> bool:
        """Gibt True zurück, wenn die Person mehreren Teams zugeordnet ist."""
        return len(self._teams) > 1
