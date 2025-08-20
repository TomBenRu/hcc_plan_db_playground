# Status für nächste Konversation - Threading-Crash-Problem

## Problem-Kontext
- **Symptom:** Intermittierender QThreadStorage-Crash mit Exit Code 3
- **Trigger-Sequenz:** `delete_location_plan_period_widgets()` → (1 Minute warten) → Planvalidierung → Crash
- **Häufigkeit:** Reproduzierbar nach Widget-Deletion

## Wichtiger Durchbruch in dieser Session
✅ **Root Cause identifiziert:** `delete_location_plan_period_widgets()` korrumpiert Qt's globales QThreadStorage-System

### Systematische Isolation durchgeführt:
1. **Progress Bar entfernt** → Crash weiterhin, aber an anderer Stelle
2. **Signal-Connections entfernt** → Crash weiterhin
3. **Worker-Thread isoliert** → Crash-Location ändert sich zu `side_menu.py:243 enterEvent`
4. **Conclusion:** Problem liegt bei Widget-Deletion, nicht bei Threading-Code

## Aktuelle Code-Änderungen
- **Progress Bar Code:** Auskommentiert in `frm_plan.py`
- **Signal-Cleanup:** Implementiert in `frm_location_plan_period.py` (disconnect_global_signals Methoden)
- **Worker-Thread Callbacks:** Auskommentiert für Testing

## Nächste Schritte (BEREIT ZUM UMSETZEN)
1. **Sofort testbare Lösungsansätze:**
   - Option A: Widgets verstecken statt löschen (`setVisible(False)`)
   - Option B: Delayed deletion mit QTimer
   - Option C: `delete_location_plan_period_widgets()` Aufruf komplett vermeiden

2. **Investigate:** Warum wird `delete_location_plan_period_widgets()` überhaupt aufgerufen?

## Relevante Dateien
- `gui/frm_location_plan_period.py` (delete_location_plan_period_widgets Methode)
- `gui/frm_plan.py` (Progress Bar Code auskommentiert)
- `gui/custom_widgets/side_menu.py` (aktueller Crash-Location)

## Problem ist FAST gelöst - nur noch Widget-Deletion-Strategie ändern!