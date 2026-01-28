"""
BaseConfigButton - Basisklasse für Konfigurations-Buttons im AvailDay-Grid

Diese Klasse implementiert das Template Method Pattern für die 4 Config-Button-Typen
in frm_actor_plan_period.py:
- ButtonLocationCombinations (ehem. ButtonCombLocPossible)
- ButtonLocationPreferences (ehem. ButtonActorLocationPref)
- ButtonPartnerPreferences (ehem. ButtonActorPartnerLocationPref)
- ButtonSkills

Die Klasse kapselt gemeinsame Funktionalität:
- Einheitliche Größen-Konfiguration
- 3-Zustands-Stylesheet-Logik (standard/default/different)
- Gemeinsame reload_actor_plan_period() Implementierung
- Gemeinsame avail_days_at_date() Query

Erstellt: Januar 2026
"""

import datetime
from abc import abstractmethod

from PySide6 import QtCore
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QPushButton, QWidget

from commands import command_base_classes
from database import schemas, db_services
from gui import widget_styles
from gui.observer import signal_handling


class BaseConfigButton(QPushButton):
    """Basisklasse für Konfigurations-Buttons im AvailDay-Grid.

    Implementiert das Template Method Pattern für einheitliches Stylesheet-Management
    mit 3-Zustands-Logik:
    - None: Keine Daten vorhanden (standard_colors - gelb)
    - True: Alle Werte entsprechen Defaults (all_properties_are_default - grün)
    - False: Abweichungen von Defaults (any_properties_are_different - rot)

    Unterklassen MÜSSEN implementieren:
    - _check_matches_defaults() -> bool | None

    Unterklassen KÖNNEN überschreiben:
    - _connect_signals(): Für klassenspezifische Signal-Verbindungen
    - _setup_tooltip(): Für klassenspezifischen Tooltip
    - _on_stylesheet_updated(): Hook nach Stylesheet-Aktualisierung (z.B. für Tooltip)
    - _ensure_consistency(): Hook für Datenkonsistenz vor dem Check
    """

    def __init__(
        self,
        parent: QWidget,
        date: datetime.date,
        width_height: int,
        actor_plan_period: schemas.ActorPlanPeriodShow,
        connect_to_avail_configs_signal: bool = True
    ):
        """Initialisiert den Config-Button.

        Args:
            parent: Parent-Widget
            date: Datum für diesen Button
            width_height: Größe des quadratischen Buttons in Pixeln
            actor_plan_period: ActorPlanPeriod-Daten
            connect_to_avail_configs_signal: Ob signal_reload_actor_pp__avail_configs
                                             verbunden werden soll (default: True)
        """
        super().__init__(parent)

        # Widget-Attribute für sauberes Cleanup
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)

        # Gemeinsame Attribute
        self.date = date
        self.actor_plan_period = actor_plan_period

        # Größen-Konfiguration (ersetzt 4 einzelne Zeilen)
        self._setup_size(width_height)

        self.controller = command_base_classes.ContrExecUndoRedo()

        # Signal-Verbindungen
        if connect_to_avail_configs_signal:
            signal_handling.handler_actor_plan_period.signal_reload_actor_pp__avail_configs.connect(
                self.refresh
            )

        # Hook für klassenspezifische Signal-Verbindungen
        self._connect_signals()

        # Tooltip und Stylesheet initialisieren
        self._setup_tooltip()
        self.set_stylesheet()

    def _setup_size(self, width_height: int) -> None:
        """Setzt die Größe des quadratischen Buttons.

        Ersetzt die 4 einzelnen setMaximum/setMinimum-Aufrufe.
        """
        self.setMaximumWidth(width_height)
        self.setMinimumWidth(width_height)
        self.setMaximumHeight(width_height)
        self.setMinimumHeight(width_height)

    # === Template Methods (MÜSSEN von Unterklassen implementiert werden) ===

    @abstractmethod
    def _check_matches_defaults(self) -> bool | None:
        """Prüft den Zustand für die Stylesheet-Bestimmung (reine Query).

        Diese Methode darf KEINE Seiteneffekte haben (CQS-Prinzip).
        Für Seiteneffekte wie Auto-Reset bei Inkonsistenzen
        sollte _ensure_consistency() verwendet werden.

        Returns:
            None: Keine Daten vorhanden -> standard_colors (gelb)
            True: Alle Werte entsprechen Defaults -> all_properties_are_default (grün)
            False: Abweichungen von Defaults -> any_properties_are_different (rot)
        """
        pass

    # === Optionale Hooks (können von Unterklassen überschrieben werden) ===

    def _connect_signals(self) -> None:
        """Hook für klassenspezifische Signal-Verbindungen.

        Wird nach der Standard-Signal-Verbindung aufgerufen.
        Unterklassen können hier zusätzliche Signals verbinden.
        """
        pass

    def _setup_tooltip(self) -> None:
        """Hook für klassenspezifischen Tooltip.

        Wird im Konstruktor aufgerufen.
        Unterklassen sollten hier setToolTip() aufrufen.
        """
        pass

    def _on_stylesheet_updated(self) -> None:
        """Hook der nach set_stylesheet() aufgerufen wird.

        Nützlich für Klassen die nach Stylesheet-Änderung weitere
        Updates benötigen (z.B. Tooltip-Aktualisierung bei ButtonSkills).
        """
        pass

    def _ensure_consistency(self) -> None:
        """Hook: Stellt Datenkonsistenz her bevor der Check läuft.

        Unterklassen können hier Inkonsistenzen zwischen AvailDays erkennen
        und beheben (z.B. unterschiedliche Präferenzen am selben Tag).
        Dies trennt die Konsistenz-Herstellung (Command) von der
        Stylesheet-Bestimmung (Query) gemäß CQS-Prinzip.

        Default: Keine Aktion.
        """
        pass

    # === Gemeinsame Implementierungen ===

    def set_stylesheet(self) -> None:
        """Template Method: Setzt das Stylesheet basierend auf _check_matches_defaults().

        Implementiert die 3-Zustands-Logik:
        - None -> standard_colors (gelb) - keine Daten
        - True -> all_properties_are_default (grün) - Defaults
        - False -> any_properties_are_different (rot) - Abweichungen
        """
        # Erst Konsistenz sicherstellen (Hook für Unterklassen)
        self._ensure_consistency()

        # Dann den Check für Stylesheet-Farbe (reine Query)
        check_result = self._check_matches_defaults()
        # Automatischer Klassenname - keine manuelle Überschreibung nötig
        class_name = self.__class__.__name__
        colors = widget_styles.buttons.ConfigButtonsInCheckFields

        if check_result is None:
            color = colors.standard_colors
            disabled_color = colors.standard_colors_disabled
        elif check_result:
            color = colors.all_properties_are_default
            disabled_color = colors.all_properties_are_default_disabled
        else:
            color = colors.any_properties_are_different
            disabled_color = colors.any_properties_are_different_disabled

        self.setStyleSheet(
            f"{class_name} {{background-color: {color}}}"
            f"{class_name}::disabled {{background-color: {disabled_color};}}"
        )

        # Hook für zusätzliche Updates nach Stylesheet-Änderung
        self._on_stylesheet_updated()

    def avail_days_at_date(self) -> list[schemas.AvailDay]:
        """Gibt alle AvailDays am Button-Datum zurück.

        Filtert gelöschte (prep_delete) AvailDays aus.

        Returns:
            Liste der AvailDays am Datum dieses Buttons
        """
        return [
            avd for avd in self.actor_plan_period.avail_days
            if not avd.prep_delete and avd.date == self.date
        ]

    @Slot(signal_handling.DataActorPPWithDate)
    def refresh(self, data: signal_handling.DataActorPPWithDate | None = None) -> None:
        """Lädt die ActorPlanPeriod-Daten neu und aktualisiert das Stylesheet.

        Diese Methode ersetzt reload_actor_plan_period() mit einem klareren Namen,
        der die vollständige Aktualisierung (Daten + Stylesheet) besser beschreibt.

        Wird aufgerufen wenn:
        - data is None: Direkter Aufruf ohne Signal-Daten
        - data enthält passende actor_plan_period.id und optionales Datum

        Args:
            data: Signal-Daten mit ActorPlanPeriod und optionalem Datum.
                  Bei None wird direkt aus DB geladen.
        """
        if data is None:
            # Direkter Aufruf: Lade aus DB
            self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period.id)
            self.set_stylesheet()
        elif data.actor_plan_period.id == self.actor_plan_period.id:
            # Signal mit passender ActorPlanPeriod
            if data.date is None or data.date == self.date:
                self.actor_plan_period = data.actor_plan_period
                self.set_stylesheet()

    # Alias für Abwärtskompatibilität
    def reload_actor_plan_period(self, data: signal_handling.DataActorPPWithDate | None = None) -> None:
        """Alias für refresh() - für Abwärtskompatibilität."""
        self.refresh(data)
