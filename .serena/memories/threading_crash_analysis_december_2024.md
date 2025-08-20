# Threading-Crash-Problem - Status Dezember 2024

## Problem-Beschreibung
- **Symptom:** Intermittierender Programmabsturz mit Exit Code `-1073740791 (0xC0000409)`
- **Häufigkeit:** Geschätzt jedes 10. Mal
- **Trigger-Sequenz:**
  1. Notes-Änderung in Planungsmaske (frm_location_plan_period.py)
  2. Signal `_event_changed` erreicht AppointmentField
  3. Sofort danach Besetzungsänderung im gleichen AppointmentField
  4. Automatische Validierung startet (`_start_plan_check`)
  5. Progress-Bar erscheint, friert nach Sekunden ein → Crash

## Konsolen-Output beim Crash
```
INFO:gui.frm_plan:Signal received - _event_changed in AppointmentField d6c4e354-c281-4e98-8ca5-e4c11f9c8b92
INFO:gui.frm_plan:State cleanup completed for AppointmentField fe524fda-d979-48df-94b5-f2c3372c124c  
INFO:gui.frm_plan:Plan check started for AppointmentField fe524fda-d979-48df-94b5-f2c3372c124c
########################### OPTIMAL ############################################
Process finished with exit code -1073740791 (0xC0000409)
```

## Root Cause Analyse
- **Zunächst vermutet:** Signal-Broadcasting zwischen AppointmentFields
- **Tatsächlich:** Widget-Lifecycle-Problem bei `refresh_plan()`
- **Erklärung:** Verschiedene AppointmentField-IDs entstehen durch zwischenzeitlichen `refresh_plan()` Aufruf
- **Qt-Verhalten:** `deleteLater()` ist asynchron - alte Widgets laufen parallel zu neuen

## Durchgeführte Änderungen in gui/frm_plan.py

### 1. AppointmentField._start_plan_check()
- Worker als Instanzvariable gespeichert: `self.check_plan_worker`
- Defensive Programmierung: Prüfung auf bereits laufende Worker
- Logging verbessert

### 2. AppointmentField.check_finished()
- `progress_bar.deleteLater()` statt nur `close()`
- Worker-Referenz cleanup: `self.check_plan_worker = None`
- Defensive Programmierung mit `hasattr()` Prüfungen

### 3. FrmTabPlan._check_plan() und _check_finished()
- Identische Verbesserungen wie bei AppointmentField
- Worker-Instanzvariable: `self.check_plan_worker`
- Ordnungsgemäße Progress-Bar-Cleanup

### 4. Widget-Lifecycle-Cleanup (MÖGLICHERWEISE ÜBERFLÜSSIG)
- `AppointmentField._cleanup_on_destruction()` implementiert
- `FrmTabPlan._cleanup_all_appointment_fields()` implementiert
- Signal-Disconnect in Widget-Destruktor
- **HINWEIS:** Qt sollte Child-Widgets automatisch cleanup - diese Änderungen könnten unnötig sein

## Aktuelle Hypothese
Das Problem liegt **NICHT** in Widget-Management, sondern im Threading zwischen:
- Worker-Threads (WorkerCheckPlan)
- Qt Main Thread
- Progress-Bar Management
- Signal-Verarbeitung

## Nächste Schritte für neue Konversation
1. **Widget-Cleanup entfernen** - Qt's Parent-Child-System vertrauen
2. **Focus auf Threading-Synchronisation:**
   - QueuedConnection vs DirectConnection
   - Worker-Thread-Pool Management
   - Progress-Bar Threading-Safety
3. **Solver-Main-Integration prüfen:** `solver_main.test_plan()` könnte Threading-Probleme haben
4. **Memory-Access-Pattern analysieren:** Exit Code 0xC0000409 = Stack Buffer Overrun

## Relevante Dateien
- `gui/frm_plan.py` - AppointmentField und FrmTabPlan Klassen  
- `gui/concurrency/general_worker.py` - WorkerCheckPlan
- `gui/custom_widgets/progress_bars.py` - DlgProgressInfinite
- `sat_solver/solver_main.py` - test_plan() Funktion
- `gui/frm_location_plan_period.py` - ButtonNotes (löst event_changed aus)

## Threading-Best-Practices bereits implementiert
- Worker als Instanzvariablen (verhindert Garbage Collection)
- Qt.ConnectionType.QueuedConnection für Thread-sichere Signale
- Defensive Programmierung mit hasattr() Prüfungen
- Progress-Bar deleteLater() cleanup

## Problem bleibt bestehen
Trotz aller Änderungen tritt der Crash weiterhin auf. Das deutet auf ein tieferliegendes Threading-Problem hin, möglicherweise in:
- Solver-Implementierung
- Qt-Threading-Architektur  
- Memory-Management bei parallel laufenden Workern