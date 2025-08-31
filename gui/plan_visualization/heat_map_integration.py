"""
Heat-Map Integration Interface für bestehende Plan-Views

Einfache Integration von Workload Heat-Maps in bestehende frm_plan.py
ohne strukturelle Änderungen an der Architektur.

Erstellt: 31. August 2025
Teil von: Workload Heat-Maps Feature Implementation - Tag 2
"""

from typing import Optional, Callable
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QTableView, QTreeView, QAbstractItemView,
    QPushButton, QToolButton, QHBoxLayout, QVBoxLayout,
    QLabel, QFrame, QSizePolicy, QCheckBox, QComboBox
)
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor

from gui.custom_widgets.workload_heat_delegate import WorkloadHeatDelegate
from gui.plan_visualization.workload_model_integration import WorkloadDataProvider, add_workload_support_to_model
from database.models import PlanPeriod
import logging

logger = logging.getLogger(__name__)


class HeatMapController(QObject):
    """
    Controller für Heat-Map-Funktionalität in bestehenden Views
    
    Verwaltet Delegate-Switching, Model-Integration und UI-State.
    Kann einfach in bestehende Formulare integriert werden.
    """
    
    # Signals für UI-Updates
    heatMapToggled = Signal(bool)  # enabled
    heatMapConfigChanged = Signal(dict)  # config_dict
    
    def __init__(self, table_view: QAbstractItemView, parent: Optional[QWidget] = None):
        """
        Initialisiert Heat-Map-Controller für gegebene View
        
        Args:
            table_view: QTableView oder QTreeView für Heat-Map-Integration
            parent: Parent Widget
        """
        super().__init__(parent)
        
        self.table_view = table_view
        self.parent_widget = parent
        
        # Heat-Map-Komponenten
        self.heat_delegate: Optional[WorkloadHeatDelegate] = None
        self.workload_provider: Optional[WorkloadDataProvider] = None
        self.original_delegate = table_view.itemDelegate()
        
        # UI-State
        self.is_heat_map_enabled = False
        self.current_plan_period: Optional[PlanPeriod] = None
        
        # Get-Person-Function für Model-Integration
        self.get_person_function: Optional[Callable] = None
        
        logger.debug(f"HeatMapController initialisiert für {type(table_view).__name__}")
    
    def setup_model_integration(self, get_person_func: Callable, plan_period: Optional[PlanPeriod] = None):
        """
        Richtet Model-Integration für Heat-Map-Daten ein
        
        Args:
            get_person_func: Function(QModelIndex) -> Person Entity
            plan_period: Aktuelle Planperiode
        """
        self.get_person_function = get_person_func
        self.current_plan_period = plan_period
        
        # Model mit Workload-Support erweitern
        model = self.table_view.model()
        if model:
            self.workload_provider = add_workload_support_to_model(model, plan_period)
            
            logger.info("Model-Integration für Heat-Map eingerichtet")
    
    def toggle_heat_map(self, enabled: Optional[bool] = None) -> bool:
        """
        Schaltet Heat-Map-Darstellung ein/aus
        
        Args:
            enabled: Optional expliziter State, sonst Toggle
            
        Returns:
            bool: Neuer Heat-Map-Status
        """
        if enabled is None:
            enabled = not self.is_heat_map_enabled
        
        if enabled == self.is_heat_map_enabled:
            return enabled  # Kein Change
        
        try:
            if enabled:
                self._enable_heat_map()
            else:
                self._disable_heat_map()
            
            self.is_heat_map_enabled = enabled
            self.heatMapToggled.emit(enabled)
            
            logger.info(f"Heat-Map {'aktiviert' if enabled else 'deaktiviert'}")
            
        except Exception as e:
            logger.error(f"Fehler beim Heat-Map-Toggle: {e}")
            return self.is_heat_map_enabled
        
        return enabled
    
    def _enable_heat_map(self):
        """Aktiviert Heat-Map-Darstellung"""
        
        # Heat-Map-Delegate erstellen falls noch nicht vorhanden
        if not self.heat_delegate:
            self.heat_delegate = WorkloadHeatDelegate(parent=self.parent_widget)
            
            # Hover-Tracking einrichten
            self.table_view.setMouseTracking(True)
            if hasattr(self.table_view, 'entered'):
                self.table_view.entered.connect(self.heat_delegate.set_hovered_index)
        
        # Delegate setzen
        self.table_view.setItemDelegate(self.heat_delegate)
        
        # Model Heat-Map-Modus aktivieren
        if hasattr(self.table_view.model(), 'set_heat_map_enabled'):
            self.table_view.model().set_heat_map_enabled(True)
        
        # View-Properties für bessere Heat-Map-Darstellung
        self._configure_view_for_heat_map()
        
        # View aktualisieren
        self.table_view.viewport().update()
    
    def _disable_heat_map(self):
        """Deaktiviert Heat-Map-Darstellung"""
        
        # Original-Delegate wiederherstellen
        self.table_view.setItemDelegate(self.original_delegate)
        
        # Model Heat-Map-Modus deaktivieren
        if hasattr(self.table_view.model(), 'set_heat_map_enabled'):
            self.table_view.model().set_heat_map_enabled(False)
        
        # Hover-Effekte zurücksetzen
        if self.heat_delegate:
            self.heat_delegate.clear_hover()
        
        # View aktualisieren
        self.table_view.viewport().update()
    
    def _configure_view_for_heat_map(self):
        """
        Konfiguriert View-Properties für optimale Heat-Map-Darstellung
        """
        # Minimum-Zellgröße für lesbare Heat-Maps
        if hasattr(self.table_view, 'setMinimumSectionSize'):
            header = self.table_view.horizontalHeader()
            if header:
                header.setMinimumSectionSize(120)
        
        # Höhere Zeilen für bessere Lesbarkeit
        if hasattr(self.table_view, 'setDefaultRowHeight'):
            self.table_view.setDefaultRowHeight(60)
        elif hasattr(self.table_view, 'verticalHeader'):
            v_header = self.table_view.verticalHeader()
            if v_header:
                v_header.setDefaultSectionSize(60)
    
    def set_plan_period(self, plan_period: PlanPeriod):
        """
        Setzt neue Planperiode für Workload-Berechnungen
        
        Args:
            plan_period: Neue Planperiode
        """
        self.current_plan_period = plan_period
        
        # Workload-Provider über Änderung informieren
        if self.workload_provider:
            self.workload_provider.set_plan_period(plan_period)
        
        # Model über Änderung informieren
        if hasattr(self.table_view.model(), 'set_plan_period_for_workload'):
            self.table_view.model().set_plan_period_for_workload(plan_period)
        
        logger.debug(f"Planperiode für Heat-Map gewechselt: {plan_period.name}")
    
    def refresh_heat_map_data(self):
        """
        Aktualisiert alle Heat-Map-Daten (manueller Refresh)
        """
        if self.workload_provider:
            self.workload_provider.refresh_data()
        
        if self.is_heat_map_enabled:
            self.table_view.viewport().update()
        
        logger.debug("Heat-Map-Daten aktualisiert")
    
    def invalidate_cache(self):
        """
        Invalidiert Workload-Cache bei Datenänderungen
        """
        if self.workload_provider:
            self.workload_provider.invalidate_cache()
    
    def get_heat_map_delegate(self) -> Optional[WorkloadHeatDelegate]:
        """
        Gibt Heat-Map-Delegate für weitere Konfiguration zurück
        
        Returns:
            Optional[WorkloadHeatDelegate]: Delegate oder None
        """
        return self.heat_delegate
    
    def configure_heat_map_display(self, show_percentage: bool = True, 
                                 show_appointments: bool = True,
                                 use_gradients: bool = True):
        """
        Konfiguriert Heat-Map-Darstellungsoptionen
        
        Args:
            show_percentage: Prozent-Anzeige
            show_appointments: Termin-Anzahl anzeigen
            use_gradients: Gradient-Hintergründe verwenden
        """
        if self.heat_delegate:
            self.heat_delegate.set_show_percentage_text(show_percentage)
            self.heat_delegate.set_show_appointment_count(show_appointments)
            self.heat_delegate.set_use_gradient_backgrounds(use_gradients)
            
            config = {
                'show_percentage': show_percentage,
                'show_appointments': show_appointments,
                'use_gradients': use_gradients
            }
            self.heatMapConfigChanged.emit(config)
            
            if self.is_heat_map_enabled:
                self.table_view.viewport().update()


class HeatMapControlWidget(QFrame):
    """
    Fertige UI-Kontrolle für Heat-Map-Integration
    
    Kann einfach in bestehende Layouts integriert werden.
    Bietet Toggle-Button und Konfigurationsoptionen.
    """
    
    def __init__(self, heat_map_controller: HeatMapController, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self.controller = heat_map_controller
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Erstellt UI-Layout für Heat-Map-Kontrolle"""
        
        # Haupt-Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        # Heat-Map-Toggle-Button
        self.toggle_button = QPushButton("Heat-Map anzeigen")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setMinimumWidth(140)
        self.toggle_button.setToolTip("Zeigt Mitarbeiter-Auslastung farbkodiert an")
        
        # Icon für Toggle-Button (optional)
        self._create_heat_map_icon()
        
        layout.addWidget(self.toggle_button)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Konfigurationsoptionen (initial versteckt)
        self.config_widget = QWidget()
        config_layout = QHBoxLayout(self.config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        
        # Prozent-Anzeige Toggle
        self.show_percentage_cb = QCheckBox("Prozent")
        self.show_percentage_cb.setChecked(True)
        self.show_percentage_cb.setToolTip("Zeigt Auslastung in Prozent an")
        
        # Termine-Anzeige Toggle
        self.show_appointments_cb = QCheckBox("Termine")
        self.show_appointments_cb.setChecked(True)
        self.show_appointments_cb.setToolTip("Zeigt Anzahl der Termine an")
        
        # Gradient-Hintergrund Toggle
        self.use_gradients_cb = QCheckBox("Verläufe")
        self.use_gradients_cb.setChecked(True)
        self.use_gradients_cb.setToolTip("Verwendet Farbverläufe für Hintergründe")
        
        config_layout.addWidget(QLabel("Anzeige:"))
        config_layout.addWidget(self.show_percentage_cb)
        config_layout.addWidget(self.show_appointments_cb)
        config_layout.addWidget(self.use_gradients_cb)
        config_layout.addStretch()
        
        self.config_widget.setVisible(False)
        layout.addWidget(self.config_widget)
        
        # Refresh-Button
        self.refresh_button = QPushButton("↻")
        self.refresh_button.setMaximumWidth(30)
        self.refresh_button.setToolTip("Aktualisiert Heat-Map-Daten")
        self.refresh_button.setVisible(False)
        layout.addWidget(self.refresh_button)
        
        layout.addStretch()
        
        # Styling
        self.setFrameStyle(QFrame.Shape.StyledPanel)
        self.setLineWidth(1)
    
    def _create_heat_map_icon(self):
        """Erstellt Icon für Heat-Map-Button"""
        try:
            # Einfaches Heat-Map-Icon erstellen
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Kleine Quadrate in Heat-Map-Farben
            colors = [QColor(70, 130, 180), QColor(255, 255, 0), QColor(255, 165, 0), QColor(220, 20, 60)]
            
            for i, color in enumerate(colors):
                x = (i % 2) * 8
                y = (i // 2) * 8
                painter.fillRect(x, y, 7, 7, color)
            
            painter.end()
            
            icon = QIcon(pixmap)
            self.toggle_button.setIcon(icon)
            
        except Exception as e:
            logger.debug(f"Icon-Erstellung fehlgeschlagen: {e}")
    
    def _connect_signals(self):
        """Verbindet UI-Signals mit Controller"""
        
        # Toggle-Button
        self.toggle_button.clicked.connect(self._on_toggle_clicked)
        
        # Konfiguration-Checkboxes
        self.show_percentage_cb.toggled.connect(self._on_config_changed)
        self.show_appointments_cb.toggled.connect(self._on_config_changed)
        self.use_gradients_cb.toggled.connect(self._on_config_changed)
        
        # Refresh-Button
        self.refresh_button.clicked.connect(self.controller.refresh_heat_map_data)
        
        # Controller-Signals
        self.controller.heatMapToggled.connect(self._on_heat_map_toggled)
    
    def _on_toggle_clicked(self):
        """Behandelt Toggle-Button-Klick"""
        enabled = self.toggle_button.isChecked()
        actual_state = self.controller.toggle_heat_map(enabled)
        
        # Button-State mit tatsächlichem State synchronisieren (falls Fehler)
        if actual_state != enabled:
            self.toggle_button.setChecked(actual_state)
    
    def _on_config_changed(self):
        """Behandelt Konfigurationsänderungen"""
        self.controller.configure_heat_map_display(
            show_percentage=self.show_percentage_cb.isChecked(),
            show_appointments=self.show_appointments_cb.isChecked(),
            use_gradients=self.use_gradients_cb.isChecked()
        )
    
    def _on_heat_map_toggled(self, enabled: bool):
        """
        Behandelt Heat-Map-Toggle-Signal vom Controller
        
        Args:
            enabled: Neuer Heat-Map-Status
        """
        # UI-Updates
        if enabled:
            self.toggle_button.setText("Heat-Map ausblenden")
            self.config_widget.setVisible(True)
            self.refresh_button.setVisible(True)
        else:
            self.toggle_button.setText("Heat-Map anzeigen")
            self.config_widget.setVisible(False)
            self.refresh_button.setVisible(False)
        
        # Button-State synchronisieren
        self.toggle_button.setChecked(enabled)


# Convenience-Factory für einfache Integration
def create_heat_map_integration(table_view: QAbstractItemView, 
                               get_person_func: Callable,
                               plan_period: Optional[PlanPeriod] = None,
                               parent: Optional[QWidget] = None) -> tuple[HeatMapController, HeatMapControlWidget]:
    """
    Factory-Funktion für komplette Heat-Map-Integration
    
    Args:
        table_view: QTableView oder QTreeView
        get_person_func: Function(QModelIndex) -> Person Entity
        plan_period: Aktuelle Planperiode
        parent: Parent Widget
        
    Returns:
        tuple: (HeatMapController, HeatMapControlWidget)
    """
    # Controller erstellen
    controller = HeatMapController(table_view, parent)
    controller.setup_model_integration(get_person_func, plan_period)
    
    # Control-Widget erstellen
    control_widget = HeatMapControlWidget(controller, parent)
    
    logger.info(f"Heat-Map-Integration für {type(table_view).__name__} erstellt")
    
    return controller, control_widget


# Integration-Helper für bestehende frm_plan.py
def integrate_heat_map_into_existing_form(form_instance,
                                        table_view_attr: str,
                                        layout_attr: str,
                                        get_person_func: Callable,
                                        plan_period_attr: str = None):
    """
    Helper-Funktion für Integration in bestehende Formulare
    
    Args:
        form_instance: Bestehende Form-Instanz (z.B. FrmPlan)
        table_view_attr: Name des TableView-Attributs (z.B. 'plan_table_view')
        layout_attr: Name des Layout-Attributs für Control-Widget
        get_person_func: Function für Person-Entity-Extraktion
        plan_period_attr: Optional Name des PlanPeriod-Attributs
    """
    try:
        # TableView holen
        table_view = getattr(form_instance, table_view_attr)
        
        # PlanPeriod holen falls angegeben
        plan_period = None
        if plan_period_attr and hasattr(form_instance, plan_period_attr):
            plan_period = getattr(form_instance, plan_period_attr)
        
        # Heat-Map-Integration erstellen
        controller, control_widget = create_heat_map_integration(
            table_view, get_person_func, plan_period, form_instance
        )
        
        # Attribute an Form anhängen
        setattr(form_instance, 'heat_map_controller', controller)
        setattr(form_instance, 'heat_map_control_widget', control_widget)
        
        # Control-Widget in Layout einfügen
        layout = getattr(form_instance, layout_attr)
        if hasattr(layout, 'addWidget'):
            layout.addWidget(control_widget)
        elif hasattr(layout, 'insertWidget'):
            layout.insertWidget(0, control_widget)  # Am Anfang einfügen
        
        logger.info(f"Heat-Map erfolgreich in {type(form_instance).__name__} integriert")
        
        return controller, control_widget
        
    except Exception as e:
        logger.error(f"Heat-Map-Integration fehlgeschlagen: {e}")
        raise
