"""
Dialog zur Bearbeitung von Event-spezifischen Eigenschaften.

Dieser Dialog enthält nur Event-relevante Felder:
- Fixed Cast (Button -> DlgFixedCast)
- Prefer Fixed Cast Events (Checkbox)
- Number of Staff (SpinBox)

CastGroup-spezifische Felder (Cast Rule, Strict Cast Preference) sind hier NICHT enthalten.
"""
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QPushButton, QSpinBox, QCheckBox, QDialogButtonBox,
                               QMessageBox, QListWidget, QListWidgetItem)

from commands import command_base_classes
from commands.database_commands import cast_group_commands, appointment_commands
from database import schemas, db_services
from gui.frm_fixed_cast import DlgFixedCastBuilderCastGroup, SimplifyFixedCastAndInfo
from tools.helper_functions import generate_fixed_cast_clear_text, date_to_string, setup_form_help


class DlgEventProperties(QDialog):
    """
    Dialog für Event-spezifische Eigenschaften.

    Args:
        parent: Übergeordnetes Widget
        cast_group: Die CastGroup des Events
        location_plan_period: LocationPlanPeriod für Fixed Cast Builder (optional)
        appointment: Das aktuelle Appointment für AvailDay-Cleanup (optional)
        defer_execution: Wenn True, werden Commands gesammelt statt sofort ausgeführt.
                        Bei reject() werden sie rückgängig gemacht.
                        Der Aufrufer kann sie über get_pending_commands() abrufen.
    """

    def __init__(self, parent: QWidget,
                 cast_group: schemas.CastGroupShow,
                 location_plan_period: schemas.LocationPlanPeriodShow | None = None,
                 appointment: schemas.Appointment | None = None,
                 defer_execution: bool = False):
        super().__init__(parent=parent)

        # Validierung: Dialog nur für Events verwenden
        if not cast_group.event:
            raise ValueError("DlgEventProperties kann nur für CastGroups mit Event verwendet werden.")

        self.cast_group = cast_group.model_copy()
        self.location_plan_period = location_plan_period
        self.appointment = appointment

        # Deferred Execution Mode
        self._defer_execution = defer_execution
        self._pending_commands: list[command_base_classes.Command] = []

        if defer_execution:
            # Im deferred Mode: Kein Controller nötig (Commands werden gesammelt)
            self.controller = None
        else:
            # Bisheriges Verhalten für Standalone-Nutzung (z.B. FrmCastGroup)
            self.controller = command_base_classes.ContrExecUndoRedo()

        # Initialer nr_actors Wert für Vergleich
        self._initial_nr_actors = self.cast_group.nr_actors

        self._setup_ui()
        self._setup_widgets()

        # Help-Integration
        setup_form_help(self, "event_properties", add_help_button=True)

    def _setup_ui(self):
        """Erstellt die UI-Struktur."""
        self.setWindowTitle(self.tr("Event Properties"))
        self.setStyleSheet("background-color: none;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(15)

        # Header
        self.layout_head = QVBoxLayout()
        self.main_layout.addLayout(self.layout_head)

        # Info-Label
        info_text = self.tr(
            "Event: {location}\n"
            "{date}, {time_of_day}"
        ).format(
            location=(self.location_plan_period or self.cast_group.event.location_plan_period).location_of_work.name_an_city,
            date=date_to_string(self.cast_group.event.date),
            time_of_day=self.cast_group.event.time_of_day.name
        )
        self.lb_info = QLabel(info_text)
        self.lb_info.setStyleSheet("font-weight: bold;")
        self.layout_head.addWidget(self.lb_info)

        # Body mit Grid Layout
        self.layout_body = QGridLayout()
        self.layout_body.setSpacing(10)
        self.main_layout.addLayout(self.layout_body)

        # --- Fixed Cast ---
        self.lb_fixed_cast = QLabel(self.tr("Fixed Cast:"))
        self.bt_fixed_cast = QPushButton(self.tr("Edit..."))
        self.bt_fixed_cast.setFixedWidth(100)
        self.lb_fixed_cast_value = QLabel()
        self.lb_fixed_cast_value.setWordWrap(True)

        self.layout_body.addWidget(self.lb_fixed_cast, 0, 0)
        self.layout_body.addWidget(self.bt_fixed_cast, 0, 1)
        self.layout_body.addWidget(self.lb_fixed_cast_value, 0, 2)

        # --- Prefer Fixed Cast Events ---
        self.cb_prefer_fixed_cast_events = QCheckBox(self.tr("Prefer Events with Fixed Cast"))
        self.cb_prefer_fixed_cast_events.setToolTip(
            self.tr("If checked, events with a fixed cast are preferred over other events.\n"
                    "Works best with non-nested casts.")
        )
        self.layout_body.addWidget(self.cb_prefer_fixed_cast_events, 1, 0, 1, 3)

        # --- Number of Staff ---
        self.lb_nr_actors = QLabel(self.tr("Number of Staff:"))
        self.spin_nr_actors = QSpinBox()
        self.spin_nr_actors.setMinimum(0)
        self.spin_nr_actors.setMaximum(99)
        self.spin_nr_actors.setFixedWidth(80)
        self.lb_nr_actors_info = QLabel()

        self.layout_body.addWidget(self.lb_nr_actors, 2, 0)
        self.layout_body.addWidget(self.spin_nr_actors, 2, 1)
        self.layout_body.addWidget(self.lb_nr_actors_info, 2, 2)

        # Stretch
        self.main_layout.addStretch()

        # Footer mit Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.main_layout.addWidget(self.button_box)

    def _setup_widgets(self):
        """Initialisiert Widget-Werte und Verbindungen."""
        # Fixed Cast
        self.bt_fixed_cast.clicked.connect(self.edit_fixed_cast)
        self._update_fixed_cast_display()

        # Prefer Fixed Cast Events
        self.cb_prefer_fixed_cast_events.setChecked(self.cast_group.prefer_fixed_cast_events)
        self.cb_prefer_fixed_cast_events.stateChanged.connect(self._prefer_fixed_cast_events_changed)
        self._update_prefer_fixed_cast_checkbox_state()

        # Number of Staff
        self.spin_nr_actors.setValue(self.cast_group.nr_actors)
        self.spin_nr_actors.valueChanged.connect(self._nr_actors_changed)
        self._update_nr_actors_info()

    # -------------------------------------------------------------------------
    # Command Execution (Deferred Mode Support)
    # -------------------------------------------------------------------------

    def _execute_or_defer(self, cmd: command_base_classes.Command):
        """
        Führt Command aus oder sammelt ihn für spätere Ausführung.

        Im deferred Mode wird der Command ausgeführt (für sofortige UI-Änderung),
        aber in _pending_commands gesammelt, damit er bei reject() rückgängig
        gemacht werden kann und bei accept() an den Aufrufer übergeben wird.
        """
        if self._defer_execution:
            cmd.execute()
            self._pending_commands.append(cmd)
        else:
            self.controller.execute(cmd)

    def _add_commands_to_pending(self, commands: list[command_base_classes.Command]):
        """
        Fügt bereits ausgeführte Commands zur pending-Liste hinzu (deferred Mode)
        oder zum Controller (immediate Mode).
        """
        if self._defer_execution:
            self._pending_commands.extend(commands)
        else:
            self.controller.add_to_undo_stack(commands)

    def get_pending_commands(self) -> list[command_base_classes.Command]:
        """
        Gibt die gesammelten Commands zurück (nur im deferred Mode relevant).

        Returns:
            Kopie der pending Commands Liste
        """
        return self._pending_commands.copy()

    def has_pending_commands(self) -> bool:
        """Prüft ob es ausstehende Commands gibt."""
        return bool(self._pending_commands)

    # -------------------------------------------------------------------------
    # Fixed Cast
    # -------------------------------------------------------------------------

    def edit_fixed_cast(self):
        """Öffnet den DlgFixedCast Dialog zur Bearbeitung."""
        location_plan_period = self.location_plan_period
        if location_plan_period is None and self.cast_group.event:
            location_plan_period = db_services.LocationPlanPeriod.get(
                self.cast_group.event.location_plan_period.id
            )
        dlg = DlgFixedCastBuilderCastGroup(
            self, self.cast_group, location_plan_period
        ).build()

        if dlg.exec():
            # Commands übernehmen (DlgFixedCast führt sie bereits aus)
            self._add_commands_to_pending(list(dlg.controller.get_undo_stack()))

            # Daten neu laden
            self.cast_group = db_services.CastGroup.get(self.cast_group.id)

            # UI aktualisieren
            self._update_fixed_cast_display()
            self._update_prefer_fixed_cast_checkbox_state()

            # Konsistenzprüfung: nr_actors >= min_nr_actors aus Fixed Cast
            self._check_fixed_cast_consistency()

    def _update_fixed_cast_display(self):
        """Aktualisiert die Fixed Cast Anzeige."""
        text = generate_fixed_cast_clear_text(
            self.cast_group.fixed_cast,
            self.cast_group.fixed_cast_only_if_available,
            self.cast_group.prefer_fixed_cast_events
        )
        self.lb_fixed_cast_value.setText(text or self.tr("(not set)"))

    def _update_prefer_fixed_cast_checkbox_state(self):
        """
        Aktiviert die Checkbox nur wenn:
        1. fixed_cast gesetzt ist
        2. Die übergeordnete EventGroup weniger aktive Events hat als Child-Groups
        """
        has_fixed_cast = bool(self.cast_group.fixed_cast and self.cast_group.fixed_cast.strip())

        # Prüfen ob prefer_fixed_cast_events sinnvoll ist
        fewer_active_children_than_events = False
        if self.cast_group.event.event_group_id:
            fewer_active_children_than_events = db_services.EventGroup.get_fewer_children_than_events(
                self.cast_group.event.event_group_id
            )

        self.cb_prefer_fixed_cast_events.setEnabled(has_fixed_cast and fewer_active_children_than_events)

        # Auto-Deaktivierung wenn kein fixed_cast
        if not has_fixed_cast and self.cast_group.prefer_fixed_cast_events:
            cmd = cast_group_commands.UpdatePreferFixedCastEvents(self.cast_group.id, False)
            self._execute_or_defer(cmd)
            self.cast_group = cmd.result
            self.cb_prefer_fixed_cast_events.setChecked(False)

    def _prefer_fixed_cast_events_changed(self):
        """Handler für Änderungen an der Prefer-Checkbox."""
        new_value = self.cb_prefer_fixed_cast_events.isChecked()
        cmd = cast_group_commands.UpdatePreferFixedCastEvents(self.cast_group.id, new_value)
        self._execute_or_defer(cmd)
        self.cast_group = cmd.result

    def _check_fixed_cast_consistency(self):
        """Prüft ob nr_actors mit Fixed Cast konsistent ist."""
        if not self.cast_group.fixed_cast:
            return

        try:
            info = SimplifyFixedCastAndInfo(self.cast_group.fixed_cast)
            if self.cast_group.nr_actors < info.min_nr_actors:
                # Automatisch erhöhen
                QMessageBox.information(
                    self,
                    self.tr("Number of Staff"),
                    self.tr("Fixed Cast requires at least {n} employees.\n"
                            "Number of Staff will be adjusted.").format(n=info.min_nr_actors)
                )
                self.spin_nr_actors.setValue(info.min_nr_actors)
        except Exception:
            # Bei Fehler in der Analyse ignorieren
            pass

    # -------------------------------------------------------------------------
    # Number of Staff
    # -------------------------------------------------------------------------

    def _nr_actors_changed(self):
        """Handler für Änderungen an Number of Staff."""
        new_nr_actors = self.spin_nr_actors.value()
        old_nr_actors = self.cast_group.nr_actors

        # Prüfung gegen Fixed Cast
        if self.cast_group.fixed_cast:
            try:
                info = SimplifyFixedCastAndInfo(self.cast_group.fixed_cast)
                if new_nr_actors < info.min_nr_actors:
                    QMessageBox.warning(
                        self,
                        self.tr("Number of Staff"),
                        self.tr("Fixed Cast requires at least {n} employees.").format(n=info.min_nr_actors)
                    )
                    self.spin_nr_actors.blockSignals(True)
                    self.spin_nr_actors.setValue(old_nr_actors)
                    self.spin_nr_actors.blockSignals(False)
                    return
            except Exception:
                pass

        # AvailDay Overflow Check
        if new_nr_actors < old_nr_actors and self.appointment:
            if self._check_avail_day_overflow(new_nr_actors):
                if not self._cleanup_excess_avail_days(new_nr_actors):
                    # Benutzer hat abgebrochen - zurücksetzen
                    self.spin_nr_actors.blockSignals(True)
                    self.spin_nr_actors.setValue(old_nr_actors)
                    self.spin_nr_actors.blockSignals(False)
                    return

        # Update ausführen
        cmd = cast_group_commands.UpdateNrActors(self.cast_group.id, new_nr_actors)
        self._execute_or_defer(cmd)
        self.cast_group = db_services.CastGroup.get(self.cast_group.id)
        self._update_nr_actors_info()

    def _update_nr_actors_info(self):
        """Aktualisiert die Info-Anzeige für Number of Staff."""
        if self.appointment:
            current_count = len(self.appointment.avail_days) + len(self.appointment.guests)
            nr_actors = self.spin_nr_actors.value()

            if current_count > nr_actors:
                self.lb_nr_actors_info.setText(
                    self.tr("{count} assigned (overflow!)").format(count=current_count)
                )
                self.lb_nr_actors_info.setStyleSheet("color: orangered;")
            elif current_count == nr_actors:
                self.lb_nr_actors_info.setText(
                    self.tr("{count} assigned (complete)").format(count=current_count)
                )
                self.lb_nr_actors_info.setStyleSheet("color: green;")
            else:
                self.lb_nr_actors_info.setText(
                    self.tr("{count} of {total} assigned").format(count=current_count, total=nr_actors)
                )
                self.lb_nr_actors_info.setStyleSheet("color: white;")
        else:
            self.lb_nr_actors_info.setText("")

    def _check_avail_day_overflow(self, new_nr_actors: int) -> bool:
        """
        Prüft ob das Appointment mehr Zuweisungen hat als new_nr_actors erlaubt.

        Returns:
            True wenn Overflow vorhanden, False sonst
        """
        if not self.appointment:
            return False

        current_count = len(self.appointment.avail_days) + len(self.appointment.guests)
        return current_count > new_nr_actors

    def _cleanup_excess_avail_days(self, new_nr_actors: int) -> bool:
        """
        Bereinigt überzählige AvailDays wenn nr_actors reduziert wird.

        Returns:
            True wenn Cleanup erfolgreich oder nicht nötig, False bei Abbruch
        """
        if not self.appointment:
            return True

        current_avail_days = list(self.appointment.avail_days)
        current_guests = list(self.appointment.guests)
        current_count = len(current_avail_days) + len(current_guests)

        if current_count <= new_nr_actors:
            return True

        excess = current_count - new_nr_actors

        # Cleanup-Dialog öffnen
        dlg = DlgAvailDayCleanup(self, self.appointment, new_nr_actors, excess)

        if dlg.exec():
            # Commands aus dem Dialog übernehmen (DlgAvailDayCleanup führt sie bereits aus)
            self._add_commands_to_pending(list(dlg.controller.get_undo_stack()))

            # Appointment neu laden
            self.appointment = db_services.Appointment.get(self.appointment.id)
            self._update_nr_actors_info()
            return True

        return False

    # -------------------------------------------------------------------------
    # Dialog Lifecycle
    # -------------------------------------------------------------------------

    def accept(self):
        """Speichern und schließen."""
        super().accept()

    def reject(self):
        """Alle Änderungen rückgängig machen und schließen."""
        if self._defer_execution:
            # Im deferred Mode: Pending Commands rückgängig machen
            for cmd in reversed(self._pending_commands):
                cmd._undo()
            self._pending_commands.clear()
        else:
            # Bisheriges Verhalten
            self.controller.undo_all()
        super().reject()


class DlgAvailDayCleanup(QDialog):
    """
    Dialog zur Auswahl der zu entfernenden Zuweisungen bei Reduzierung von nr_actors.

    Dieser Dialog wird angezeigt, wenn die Anzahl der benötigten Mitarbeiter (nr_actors)
    eines Events reduziert wird und das zugehörige Appointment bereits mehr Zuweisungen
    (AvailDays und/oder Guests) hat als die neue Anzahl erlaubt.

    Anwendungsfälle:
        1. In DlgEventProperties: Wenn der Benutzer die SpinBox "Anzahl Mitarbeiter"
           reduziert und bereits mehr Personen zugewiesen sind.
        2. In DlgEditAppointment: Wenn das Appointment beim Öffnen bereits mehr
           Zuweisungen hat als nr_actors (z.B. nach externer Änderung der
           Besetzungsstärke in der Location-Planungsmaske).

    Funktionsweise:
        - Zeigt eine Liste aller aktuellen Zuweisungen (Mitarbeiter und Gäste)
        - Der Benutzer muss exakt so viele Einträge auswählen, wie entfernt werden müssen
        - Bei Bestätigung werden die entsprechenden UpdateAvailDays/UpdateGuests Commands
          ausgeführt und im internen Controller gespeichert
        - Der aufrufende Dialog kann die Commands über controller.get_undo_stack()
          in seinen eigenen Undo-Stack übernehmen

    Beispiel:
        Ein Event hat nr_actors=3 und das Appointment hat 5 Zuweisungen.
        Der Dialog zeigt alle 5 Zuweisungen an und fordert den Benutzer auf,
        genau 2 davon zur Entfernung auszuwählen.

    Args:
        parent: Übergeordnetes Widget (typischerweise DlgEventProperties oder
                DlgEditAppointment)
        appointment: Das Appointment mit den zu bereinigenden Zuweisungen
        new_nr_actors: Die neue (reduzierte) Anzahl der benötigten Mitarbeiter
        excess: Anzahl der zu entfernenden Zuweisungen
                (= aktuelle Zuweisungen - new_nr_actors)

    Attributes:
        controller: ContrExecUndoRedo-Instanz für die ausgeführten Commands.
                   Nach erfolgreicher Bestätigung enthält dieser die
                   UpdateAvailDays und/oder UpdateGuests Commands.

    Returns (via exec()):
        QDialog.DialogCode.Accepted: Cleanup wurde durchgeführt, Commands sind
                                     im controller verfügbar
        QDialog.DialogCode.Rejected: Benutzer hat abgebrochen, keine Änderungen

    See Also:
        - DlgEventProperties._cleanup_excess_avail_days()
        - DlgEditAppointment._check_and_fix_avail_day_overflow()
        - appointment_commands.UpdateAvailDays
        - appointment_commands.UpdateGuests
    """

    def __init__(self, parent: QWidget, appointment: schemas.Appointment,
                 new_nr_actors: int, excess: int):
        super().__init__(parent=parent)

        self.appointment = appointment
        self.new_nr_actors = new_nr_actors
        self.excess = excess
        self.controller = command_base_classes.ContrExecUndoRedo()

        self._setup_ui()

    def _setup_ui(self):
        """Erstellt die UI."""
        self.setWindowTitle(self.tr("Remove Assignments"))
        self.setStyleSheet("background-color: none;")

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Erklärung
        warning_text = self.tr(
            "Reducing the number of staff to {nr} requires removing {excess} assignment(s).\n\n"
            "Please select which assignments should be removed:"
        ).format(nr=self.new_nr_actors, excess=self.excess)

        lb_warning = QLabel(warning_text)
        lb_warning.setWordWrap(True)
        layout.addWidget(lb_warning)

        # Liste der Zuweisungen
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)

        # AvailDays hinzufügen
        for avd in self.appointment.avail_days:
            item = QListWidgetItem(
                f"{avd.actor_plan_period.person.f_name} {avd.actor_plan_period.person.l_name}"
            )
            item.setData(Qt.ItemDataRole.UserRole, ("avail_day", avd.id))
            self.list_widget.addItem(item)

        # Guests hinzufügen
        for guest in self.appointment.guests:
            item = QListWidgetItem(f"{guest} (Guest)")
            item.setData(Qt.ItemDataRole.UserRole, ("guest", guest))
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        # Hinweis zur Auswahl
        lb_hint = QLabel(
            self.tr("Select exactly {n} assignment(s) to remove.").format(n=self.excess)
        )
        lb_hint.setStyleSheet("font-style: italic;")
        layout.addWidget(lb_hint)

        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _validate_and_accept(self):
        """Validiert die Auswahl und führt die Entfernung durch."""
        selected = self.list_widget.selectedItems()

        if len(selected) != self.excess:
            QMessageBox.warning(
                self,
                self.tr("Selection"),
                self.tr("Please select exactly {n} assignment(s) to remove.").format(n=self.excess)
            )
            return

        # Zuweisungen nach Typ trennen
        avail_days_to_remove: set[UUID] = set()
        guests_to_remove: set[str] = set()

        for item in selected:
            item_type, item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_type == "avail_day":
                avail_days_to_remove.add(item_data)
            else:
                guests_to_remove.add(item_data)

        # Neue Listen erstellen
        new_avail_day_ids = [
            avd.id for avd in self.appointment.avail_days
            if avd.id not in avail_days_to_remove
        ]
        new_guests = [
            g for g in self.appointment.guests
            if g not in guests_to_remove
        ]

        # Commands ausführen
        if set(avd.id for avd in self.appointment.avail_days) != set(new_avail_day_ids):
            cmd_avail = appointment_commands.UpdateAvailDays(self.appointment.id, new_avail_day_ids)
            self.controller.execute(cmd_avail)

        if set(self.appointment.guests) != set(new_guests):
            cmd_guests = appointment_commands.UpdateGuests(self.appointment.id, list(new_guests))
            self.controller.execute(cmd_guests)

        self.accept()
