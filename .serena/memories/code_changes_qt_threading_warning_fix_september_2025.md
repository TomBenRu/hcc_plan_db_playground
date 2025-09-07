# Code-Änderungen: Qt Threading Warning Fix - September 2025

## BEREITS IMPLEMENTIERTE ÄNDERUNGEN:

### 1. gui/frm_plan.py - Widget-Cleanup (IMPLEMENTIERT)

**_check_finished Methode erweitert:**
```python
@Slot(bool, list)
def _check_finished(self, success: bool, problems: list[str]):
    self.progress_bar.close()
    
    # Widget-Cleanup hinzufügen:
    self.progress_bar.deleteLater()  # Qt-konforme Widget-Zerstörung
    self.progress_bar = None         # Referenz-Reset
    QCoreApplication.processEvents() # Event-Queue verarbeiten
    
    if success:
        # ... rest unchanged
```

**_check_plan Methode erweitert:**
```python
def _check_plan(self):
    # Alte Progress-Bar aufräumen falls vorhanden
    if hasattr(self, 'progress_bar') and self.progress_bar:
        self.progress_bar.close()
        self.progress_bar.deleteLater()
        self.progress_bar = None
        QCoreApplication.processEvents()
    
    self.progress_bar = DlgProgressInfinite(...)
    # ... rest unchanged
```

### 2. gui/frm_calculate_plan.py - Signal-Cleanup (IMPLEMENTIERT)

**Import hinzugefügt:**
```python
from PySide6.QtGui import QCloseEvent
```

**Signal-Connection-Speicherung:**
```python
# Signal-Connection für späteren Disconnect speichern
self.solver_signal_connection = signal_handling.handler_solver.signal_cancel_solving.connect(
    solver_main.solver_quit, Qt.ConnectionType.QueuedConnection)
```

**Save-Thread als Instanzvariable:**
```python
# Geändert von: save_thread = SaveThread(...)
# Zu: self.save_thread = SaveThread(...)
```

**Thread-Cleanup in _collect_plan_ids:**
```python
@Slot(list)
def _collect_plan_ids(self, plan_ids: list[UUID]):
    self._created_plan_ids = plan_ids
    self.plans_save_progress_bar.close()
    
    # Threading-Cleanup hinzufügen:
    if hasattr(self, 'solver_thread') and self.solver_thread:
        self.solver_thread.quit()
        self.solver_thread.wait()
    
    if hasattr(self, 'save_thread') and self.save_thread:
        self.save_thread.quit() 
        self.save_thread.wait()
    
    QCoreApplication.processEvents()  # Event-Queue leeren
    
    self.accept()
```

**closeEvent-Override:**
```python
def closeEvent(self, event: QCloseEvent):
    """Signal-Cleanup beim Schließen des Dialogs"""
    # Signal-Connection disconnecten um Threading-Probleme zu vermeiden
    if hasattr(self, 'solver_signal_connection') and self.solver_signal_connection:
        signal_handling.handler_solver.signal_cancel_solving.disconnect(self.solver_signal_connection)
    
    # Standard closeEvent aufrufen
    super().closeEvent(event)
```

### 3. gui/main_window.py - processEvents() Entfernung (IMPLEMENTIERT)

**calculate_plans Methode geändert:**
```python
# ENTFERNT: QCoreApplication.processEvents() aus der Loop
for plan_id in dlg.get_created_plan_ids():
    self.tab_manager.open_plan_tab(plan_id)
    # QCoreApplication.processEvents()  # ← ENTFERNT
```

## ALLE ÄNDERUNGEN OHNE WIRKUNG:
Trotz aller implementierten Threading-Cleanup-Maßnahmen bleibt das Qt-WARNING-Problem bestehen.

## NEXT SESSION TASK:
**Root Cause liegt tiefer** - wahrscheinlich in der fundamentalen Threading-Architektur oder im Solver-System. Mixed QThread/QRunnable-Architektur muss vereinheitlicht werden.

## WICHTIG:
Die obigen Code-Änderungen sind BEREITS IMPLEMENTIERT und müssen in neuer Session NICHT wiederholt werden. Focus auf neue Ansätze legen!