# Threading-Crash Qt-Warning Analysis - September 2025

## Problem: Qt WARNING QWindowsContext::windowsProc

**Symptom:**
```
WARNING:root:Qt WARNING: QWindowsContext::windowsProc: No Qt Window found for event 0x219 (Unknown), hwnd=0x0x1f80920.
WARNING:root:Qt WARNING: QWindowsContext::windowsProc: No Qt Window found for event 0x1c (WM_ACTIVATEAPP), hwnd=0x0x2710626.
```

## Auslöse-Szenario (exakt reproduzierbar):
1. Neuen Plan erstellen mit `gui\main_window.MainWindow.calculate_plans`
2. `frm_calculate_plan.DlgCalculate` öffnen und mit OK-Button bestätigen
3. Progressbar-Fenster erscheint und schließt nach Berechnung (schließt automatisch DlgCalculate)
4. MessageBox "Pläne anzeigen" mit Yes/No-Button bestätigen
5. **DANACH**: Bei JEDER Ausführung von `gui\frm_plan.FrmTabPlan._check_plan` → Qt-Warnings wiederholen sich automatisch

## Wichtige Erkenntnisse:
- **Instanzen von `FrmLocationPlanPeriod` sind NICHT geöffnet** - Problem liegt woanders
- **Wiederholte `_check_plan` Ausführung OHNE vorherige Plan-Berechnung**: KEINE Warnings
- **Problem ist SPEZIFISCH für Post-Plan-Calculation-State**
- **Etwas aus Plan-Berechnung hinterlässt persistenten korrupten Zustand**

## Systematisch getestete und FEHLGESCHLAGENE Lösungsansätze:

### 1. Thread-Pool-Reset ❌
```python
# In FrmTabPlan._check_plan vor Worker-Start:
self.thread_pool.clear()
self.thread_pool = QThreadPool()
```
**Ergebnis:** Keine Verbesserung

### 2. Thread-Cleanup in DlgCalculate ❌
```python
# In _collect_plan_ids:
if hasattr(self, 'solver_thread') and self.solver_thread:
    self.solver_thread.quit()
    self.solver_thread.wait()
if hasattr(self, 'save_thread') and self.save_thread:
    self.save_thread.quit() 
    self.save_thread.wait()
QCoreApplication.processEvents()
```
**Ergebnis:** Keine Verbesserung

### 3. Widget-Cleanup in FrmTabPlan ❌
```python
# In _check_finished:
self.progress_bar.close()
self.progress_bar.deleteLater()
self.progress_bar = None
QCoreApplication.processEvents()

# In _check_plan (defensive Programmierung):
if hasattr(self, 'progress_bar') and self.progress_bar:
    self.progress_bar.close()
    self.progress_bar.deleteLater()
    self.progress_bar = None
    QCoreApplication.processEvents()
```
**Ergebnis:** Keine Verbesserung

### 4. Signal-Disconnect in DlgCalculate ❌
```python
# Signal-Connection-Referenz speichern:
self.solver_signal_connection = signal_handling.handler_solver.signal_cancel_solving.connect(
    solver_main.solver_quit, Qt.ConnectionType.QueuedConnection)

# closeEvent-Override:
def closeEvent(self, event: QCloseEvent):
    if hasattr(self, 'solver_signal_connection') and self.solver_signal_connection:
        signal_handling.handler_solver.signal_cancel_solving.disconnect(self.solver_signal_connection)
    super().closeEvent(event)
```
**Ergebnis:** Keine Verbesserung

### 5. processEvents() Entfernung ❌
```python
# In MainWindow.calculate_plans - ENTFERNT:
for plan_id in dlg.get_created_plan_ids():
    self.tab_manager.open_plan_tab(plan_id)
    # QCoreApplication.processEvents()  # ← ENTFERNT
```
**Ergebnis:** Keine Verbesserung

## Threading-Architektur-Analyse:

### Plan-Berechnung-Thread-Chain:
1. `MainWindow.calculate_plans()` 
2. `DlgCalculate` → `SolverThread` (QThread-Subklasse)
3. `SolverThread.finished` → `SaveThread` (QThread-Subklasse) + `DlgProgressInfinite`
4. `SaveThread.finished` → Dialog schließen + MessageBox
5. MessageBox bestätigen → `TabManager.open_plan_tab()` → `FrmTabPlan` erstellen

### Plan-Check-Architecture:
- `FrmTabPlan._check_plan()` → `WorkerCheckPlan` (QRunnable) über `QThreadPool`
- **MISCHUNG von QThread-Subklassen und QRunnable/QThreadPool** → Potentielle Threading-Konflikte

### Qt-Warning-Details:
- `0x219` (Unknown Windows Event)
- `0x1c` (WM_ACTIVATEAPP - Application Activation)
- **Window-Handle-Korruption**: Windows-Events werden an nicht-existente Qt-Windows gesendet

## Nächste Analyserichtungen für neue Session:

### 1. Solver-Thread-Architektur genauer analysieren:
- `sat_solver/solver_main.py` - Globale Solver-Instanz
- Mögliche Thread-lokale Storage-Probleme
- CPython GIL-Interaktionen

### 2. TabManager und FrmTabPlan-Lifecycle:
- `gui/tab_manager.py` - `open_plan_tab()` Methode
- `gui/frm_plan.py` - `FrmTabPlan` Constructor und Threading-Setup
- Mögliche Widget-Parent-Child-Hierarchie-Probleme

### 3. Progress-Dialog-System:
- `gui/custom_widgets/progress_bars.py`
- Constructor `self.close()` Problematik
- Signal-Connection-Leaks bei `signal_for_label_text_update`

### 4. Global Signal-Handler-System:
- `gui/observer/signal_handling.py` - `handler_solver` globale Instanz
- Mögliche Signal-Connection-Accumulation
- Thread-sichere Signal-Emission

### 5. Deep Windows-System-Integration:
- Qt's Windows Event-Processing-Hooks
- Mögliche DLL/Native-Code-Interferenz in Solver
- Window-Handle-Lifecycle bei modalen Dialogen

## Status: PROBLEM WEITERHIN AKTIV
**Root Cause noch nicht identifiziert trotz systematischer Threading-Cleanup-Maßnahmen**

## Empfohlener nächster Ansatz:
**Option: Solver-Thread-Architektur komplett auf QRunnable/QThreadPool umstellen**
- Einheitliche Threading-Architektur statt Mixed QThread/QRunnable
- Eliminiert komplexe Thread-Lifecycle-Interaktionen
- Konsistente Thread-Pool-Verwaltung