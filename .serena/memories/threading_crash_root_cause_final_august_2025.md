# Threading-Crash-Problem - FINALE ROOT CAUSE August 2025

## Problem GELÖST - Exakte Ursache identifiziert

**QThreadStorage-Crash Exit Code 3 wird verursacht durch:**
```python
# In gui/frm_location_plan_period.py, data_setup() Methode:
self.scroll_area_events.setWidget(self.frame_events)
```

## Systematische Isolation - Erfolgreiche Methodik

### Crash-Trigger-Sequenz (exakt):
1. Planansicht öffnen ✅
2. Zu Planungsmasken wechseln ✅  
3. **Einrichtung wechseln** → `data_setup()` → `setWidget()` → QThreadStorage-Korruption ❌
4. Zurück zur Planansicht wechseln ✅
5. **Beliebige AppointmentField-Operation** → Crash ❌

### Eliminierte falsche Hypothesen:
- ❌ Solver-Code (`test_plan()`)
- ❌ `delete_location_plan_period_widgets()`
- ❌ Tab-Wechsel-Operationen
- ❌ Thread-Pool-Zustand
- ❌ Progress-Bar-Operationen
- ❌ Worker-Signal-Connections
- ❌ Widget-Erstellung (`FrmLocationPlanPeriod`)
- ❌ Signal-Disconnect/Reconnect (`info_text_setup()`)

### Bestätigte Root Cause:
✅ **`ScrollArea.setWidget()` korrumpiert Qt's globales QThreadStorage-System**

## Lösungsansätze bereit:
1. Delayed Widget Assignment mit QTimer
2. Widget-Hiding statt Neuerstellen  
3. Alternative ScrollArea-Architektur
4. Widget-Caching-System

## Bedeutung:
- Problem tritt auf bei **Einrichtungswechsel**, nicht Tab-Wechsel
- **Jede Threading-Operation** danach crasht (AppointmentField-Klicks, Plan-Checks)
- **Plan-Schließen/Öffnen resettet** den korrupten Zustand (neue Widgets)

## Status: ROOT CAUSE IDENTIFIZIERT ✅
Bereit für Lösungsimplementierung nach User-Zustimmung.