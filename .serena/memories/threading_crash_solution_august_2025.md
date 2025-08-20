# Threading-Crash-Problem - Lösung August 2025

## Gelöstes Problem
Der intermittierende Crash mit Exit Code `-1073740791 (0xC0000409)` beim Plan-Check nach Ansichtswechsel wurde behoben.

## Root Cause
Die bereits implementierten `cleanup()` Methoden in `FrmTabPlan` und `AppointmentField` wurden bei kritischen Tab-Wechseln nicht aufgerufen, was zu Race Conditions zwischen alten und neuen Worker-Threads führte.

## Implementierte Lösung

### 1. gui/tab_manager.py - _on_left_tabs_changed()
- Cleanup wird jetzt sowohl beim Wechsel zu Masken ALS AUCH beim Zurückwechseln zu Plans aufgerufen
- Dies verhindert Race Conditions nach Änderungen in den Planungsmasken

### 2. gui/tab_manager.py - _close_all_visible_tabs()
- Cleanup wird jetzt VOR dem Trennen der Widgets vom TabBar aufgerufen
- Wichtig für Tab-Caching-Szenarien

### 3. Bereits vorhandene cleanup() Methoden
Die folgenden Methoden waren bereits implementiert und werden jetzt korrekt aufgerufen:
- `FrmTabPlan.cleanup()`: Stoppt Worker, schließt Progress-Bar, wartet auf Thread-Pool
- `AppointmentField.cleanup()`: Stoppt Worker, Timer und Progress-Bar
- `FrmTabPlan._check_plan()`: Speichert Worker als Instanzvariable
- `FrmTabPlan._check_finished()`: Cleared Worker-Referenz und Progress-Bar

## Test-Szenario
1. Planansicht öffnen
2. Zu Planungsmasken wechseln
3. Neue LocationPlanPeriod auswählen
4. Zurück zur Planansicht wechseln
5. Plan überprüfen → Kein Crash mehr

## Wichtige Erkenntnisse
- Das Problem lag nicht im fehlenden Cleanup-Code, sondern darin, dass er nicht aufgerufen wurde
- Tab-Wechsel sind kritische Punkte für Thread-Management
- Qt's `deleteLater()` und Thread-Pool `waitForDone()` sind essentiell für sauberes Cleanup

## Status: GELÖST
Die Lösung ist minimal-invasiv und nutzt die vorhandene Infrastruktur optimal.