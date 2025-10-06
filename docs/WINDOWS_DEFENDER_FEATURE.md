# Windows Defender Ausschluss-Feature

## 📋 Übersicht

Dieses Feature ermöglicht es Benutzern, die Anwendung vom Windows Defender-Scan auszuschließen, um den Programmstart zu beschleunigen. Der Windows Defender kann insbesondere bei kompilierten Anwendungen (PyInstaller) den Start deutlich verzögern.

**Hauptmerkmale:**
- ✅ Automatischer Dialog beim ersten Start
- ✅ UAC-Integration ohne App-Neustart
- ✅ Manuelle Steuerung über Settings
- ✅ Intelligente Status-Anzeige
- ✅ Vollständige Benutzer-Kontrolle

**Version:** 1.0  
**Datum:** Oktober 2025  
**Status:** Produktionsbereit

---

## 🎯 Motivation

### Problem
Windows Defender scannt beim Start der Anwendung die ausführbare Datei, was zu spürbaren Verzögerungen führen kann:
- ⏱️ Startverzögerung: 2-10 Sekunden (typisch)
- 📊 CPU-Last während des Scans
- 🔄 Scan bei jedem Start

### Lösung
Durch das Hinzufügen der Anwendung zur Defender-Ausnahmeliste:
- ✅ Schnellerer Programmstart
- ✅ Reduzierte CPU-Last
- ✅ Bessere Benutzererfahrung

### Sicherheitsüberlegungen
- ⚠️ Das Ausschließen reduziert den Schutz für **diese spezifische Anwendung**
- ✅ Die allgemeine Systemsicherheit bleibt unberührt
- ℹ️ Nur für vertrauenswürdige, selbst-entwickelte Anwendungen empfohlen

---

## 🏗️ Architektur

### Komponenten-Übersicht

```
┌─────────────────────────────────────────────────────────┐
│                   App-Start (gui/app.py)                │
│                 gui/app_initialization.py               │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│         check_and_show_defender_dialog()                │
│         (tools/windows_defender_utils.py)               │
└──────┬──────────────────────────────────┬───────────────┘
       │                                  │
       ▼                                  ▼
┌─────────────────┐            ┌─────────────────────────┐
│  DlgDefender    │            │  add_defender_          │
│  Exclusion      │            │  exclusion()            │
│  (Dialog)       │            │  (Core Logic)           │
└─────────────────┘            └─────────────────────────┘
       │                                  │
       ▼                                  ▼
┌─────────────────────────────────────────────────────────┐
│              DefenderSettings (Config)                  │
│         (configuration/general_settings.py)             │
└─────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│         DlgGeneralSettings (Settings UI)                │
│           (gui/frm_general_settings.py)                 │
└─────────────────────────────────────────────────────────┘
```

### Dateien und Verantwortlichkeiten

| Datei | Verantwortlichkeit |
|-------|-------------------|
| `tools/windows_defender_utils.py` | Core-Funktionalität, PowerShell-Integration |
| `configuration/general_settings.py` | Persistierung der User-Präferenzen |
| `gui/custom_widgets/dlg_defender_exclusion.py` | Dialog beim ersten Start |
| `gui/frm_general_settings.py` | Settings-Integration |
| `gui/app_initialization.py` | Integration in Startup-Flow |

---

## 🔧 Technische Details

### 1. Core-Funktionalität (`windows_defender_utils.py`)

#### Hauptfunktionen

##### `is_admin() -> bool`
Prüft, ob die Anwendung mit Administrator-Rechten läuft.

**Verwendung:**
```python
from tools.windows_defender_utils import is_admin

if is_admin():
    print("Admin-Rechte vorhanden")
```

##### `get_executable_path() -> str`
Ermittelt den Pfad zur ausführbaren Datei.

**Logik:**
- PyInstaller-Executable: `sys.executable`
- Entwicklungsumgebung: `sys.argv[0]`

##### `check_defender_exclusion(exe_path: str = None) -> bool`
Prüft, ob ein Pfad bereits in der Defender-Ausnahmeliste ist.

**Wichtig:** Benötigt Administrator-Rechte!

**Fehlerbehandlung:**
```python
try:
    is_excluded = check_defender_exclusion()
except Exception:
    # Ohne Admin-Rechte oder bei Fehler
    is_excluded = False
```

##### `add_defender_exclusion(exe_path: str = None) -> tuple[bool, str]`
Fügt die Anwendung zur Defender-Ausnahmeliste hinzu.

**Rückgabewert:**
- `(True, "Erfolgsnachricht")` bei Erfolg
- `(False, "Fehlernachricht")` bei Fehler

**UAC-Integration:**
- ✅ Ohne Admin-Rechte: Triggert UAC-Dialog automatisch
- ✅ Mit Admin-Rechten: Direkte Ausführung
- ✅ Kein App-Neustart erforderlich

**Implementierung:**
```python
# PowerShell-Script mit erhöhten Rechten ausführen
Start-Process powershell -Verb RunAs -Wait
```

##### `check_and_show_defender_dialog(parent_widget=None) -> None`
High-Level-Funktion für den Startup-Flow.

**Logik:**
1. Prüft `defender_settings.exclusion_asked`
2. Zeigt Dialog wenn noch nicht gefragt
3. Verarbeitet User-Entscheidung
4. Speichert Settings

---

### 2. Configuration (`general_settings.py`)

#### DefenderSettings

```python
class DefenderSettings(BaseModel):
    """
    Windows Defender exclusion settings.
    """
    exclusion_asked: bool = False
```

**Bedeutung:**
- `False`: Dialog wird beim nächsten Start angezeigt
- `True`: Dialog wird nicht mehr angezeigt

**Speicherort:**
```
<user_config_path>/general_settings/general_settings.toml
```

**Beispiel TOML:**
```toml
[defender_settings]
exclusion_asked = true
```

---

### 3. UI-Komponenten

#### Startup-Dialog (`dlg_defender_exclusion.py`)

**Design:**
- Informationstext über Funktion
- Hinweis auf Sicherheitsimplikationen
- Drei Optionen als Buttons

**Button-Logik:**

| Button | Aktion | `exclusion_asked` |
|--------|--------|-------------------|
| "Jetzt ausschließen" | UAC → Ausnahme hinzufügen | `True` |
| "Später" | Dialog schließen | `False` |
| "Nie wieder fragen" | Dialog schließen | `True` |

**Enum-Rückgabewerte:**
```python
class DefenderExclusionResult(Enum):
    ADD_NOW = "add_now"
    LATER = "later"
    NEVER_ASK = "never_ask"
```

#### Settings-Integration (`frm_general_settings.py`)

**GroupBox: "Performance"**

Komponenten:
1. Beschreibungstext
2. Status-Label (farbcodiert)
3. Button "Vom Virenscan ausschließen"

**Status-Anzeige:**

| Zustand | Text | Farbe | Button |
|---------|------|-------|--------|
| Ausgeschlossen | "✓ Vom Virenscan ausgeschlossen" | Grün | Disabled |
| Nicht ausgeschlossen | "Nicht ausgeschlossen" | Orange | Enabled |
| Status unbekannt | "Status unbekannt (Admin-Rechte erforderlich)" | Grau | Enabled |
| Fehler | "Fehler beim Prüfen des Status" | Rot | Enabled |

**Wichtig:** Status kann nur mit Admin-Rechten geprüft werden!

---

## 📖 Benutzer-Dokumentation

### Für End-User

#### Beim ersten Start

**Was passiert:**
Nach dem Start der Anwendung erscheint ein Dialog mit der Frage, ob Sie die Anwendung vom Windows Defender-Scan ausschließen möchten.

**Ihre Optionen:**

**1. "Jetzt ausschließen"**
- Es erscheint ein Windows-Sicherheitsdialog (UAC)
- Geben Sie Ihr Administrator-Passwort ein
- Die Anwendung wird ausgeschlossen
- Der Programmstart wird zukünftig schneller

**2. "Später"**
- Der Dialog wird beim nächsten Start erneut angezeigt
- Keine Änderungen werden vorgenommen

**3. "Nie wieder fragen"**
- Der Dialog wird nicht mehr angezeigt
- Sie können die Funktion jederzeit in den Einstellungen nutzen

#### In den Einstellungen

**Wo finden:**
Menü → Einstellungen → "Performance"-Bereich

**Was Sie sehen:**
- Status: Ob die Anwendung ausgeschlossen ist
- Button: "Vom Virenscan ausschließen"

**So verwenden:**
1. Klicken Sie auf den Button
2. Bestätigen Sie den Sicherheitsdialog
3. Geben Sie Ihr Administrator-Passwort ein (UAC)
4. Die Ausnahme wird hinzugefügt

**Status ohne Admin-Rechte:**
Wenn Sie die Einstellungen ohne Admin-Rechte öffnen, wird "Status unbekannt" angezeigt. Der Button funktioniert trotzdem - Sie müssen nur beim Klick das Admin-Passwort eingeben.

#### Ausnahme wieder entfernen

**Manuell über Windows:**
1. Öffnen Sie "Windows-Sicherheit"
2. Gehen Sie zu "Viren- & Bedrohungsschutz"
3. Klicken Sie auf "Einstellungen verwalten"
4. Scrollen Sie zu "Ausschlüsse"
5. Entfernen Sie die Anwendung aus der Liste

**Nach dem Entfernen:**
Die Anwendung wird beim nächsten Start wieder gescannt. Sie können in den Einstellungen erneut ausschließen.

---

## 👨‍💻 Entwickler-Dokumentation

### Integration in neue Projekte

#### Voraussetzungen
- Python 3.12+
- PySide6
- Windows (Feature ist Windows-spezifisch)
- Pydantic für Settings

#### Schritt 1: Core-Funktionalität kopieren

Kopieren Sie `tools/windows_defender_utils.py` in Ihr Projekt.

#### Schritt 2: Settings erweitern

```python
from pydantic import BaseModel

class DefenderSettings(BaseModel):
    exclusion_asked: bool = False

class GeneralSettings(BaseModel):
    # ... andere Settings
    defender_settings: DefenderSettings = DefenderSettings()
```

#### Schritt 3: Dialog integrieren

Kopieren Sie `gui/custom_widgets/dlg_defender_exclusion.py`.

#### Schritt 4: Startup-Integration

```python
# Nach MainWindow-Initialisierung, vor app.exec()
import platform
if platform.system() == "Windows":
    from tools.windows_defender_utils import check_and_show_defender_dialog
    check_and_show_defender_dialog(main_window)
```

#### Schritt 5: Settings-Integration (optional)

Fügen Sie in Ihrem Settings-Dialog hinzu:
```python
from tools.windows_defender_utils import add_defender_exclusion

# Button-Handler
def on_add_exclusion():
    success, message = add_defender_exclusion()
    # ... Erfolg/Fehler anzeigen
```

### API-Referenz

#### Wichtigste Funktionen

```python
# Status prüfen (benötigt Admin-Rechte)
from tools.windows_defender_utils import check_defender_exclusion
is_excluded = check_defender_exclusion()

# Ausnahme hinzufügen (triggert UAC wenn nötig)
from tools.windows_defender_utils import add_defender_exclusion
success, message = add_defender_exclusion()

# Kompletter Startup-Flow
from tools.windows_defender_utils import check_and_show_defender_dialog
check_and_show_defender_dialog(parent_widget)
```

### Fehlerbehandlung

**Alle Funktionen haben robuste Fehlerbehandlung:**
- ✅ Timeouts bei PowerShell-Befehlen
- ✅ Graceful degradation bei Fehlern
- ✅ Logging aller Aktionen
- ✅ Benutzerfreundliche Fehlermeldungen

**Best Practice:**
```python
try:
    success, message = add_defender_exclusion()
    if success:
        QMessageBox.information(None, "Erfolg", message)
    else:
        QMessageBox.warning(None, "Fehler", message)
except Exception as e:
    logging.error(f"Defender exclusion failed: {e}")
    # App läuft trotzdem weiter
```

---

## 🐛 Troubleshooting

### Problem: UAC-Dialog erscheint nicht

**Ursache:** PowerShell-Script-Ausführung blockiert

**Lösung:**
1. Öffnen Sie PowerShell als Administrator
2. Führen Sie aus: `Set-ExecutionPolicy RemoteSigned`
3. Bestätigen Sie mit "Y"

### Problem: "Status unbekannt" in Settings

**Ursache:** Keine Administrator-Rechte

**Lösung:**
- Dies ist normales Verhalten ohne Admin-Rechte
- Der Button funktioniert trotzdem
- Beim Klick erscheint der UAC-Dialog

### Problem: Ausnahme wird nicht hinzugefügt

**Mögliche Ursachen:**
1. UAC-Dialog wurde abgebrochen
2. Windows Defender ist deaktiviert
3. Unternehmens-Policy verhindert Änderungen

**Diagnose:**
```powershell
# Als Administrator in PowerShell:
Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
```

### Problem: Dialog erscheint immer wieder

**Ursache:** `exclusion_asked` wird nicht gespeichert

**Lösung:**
1. Prüfen Sie, ob Settings-Datei beschreibbar ist
2. Prüfen Sie Log-Dateien auf Fehler
3. Löschen Sie `general_settings.toml` und versuchen Sie erneut

### Problem: Nach manueller Löschung kein Dialog

**Ursache:** `exclusion_asked = True` ist noch gespeichert

**Lösung:**
- Nutzen Sie den Button in den Settings
- Oder: Setzen Sie `exclusion_asked = false` in der TOML-Datei
- Oder: Löschen Sie die TOML-Datei komplett

---

## 🔍 Testing

### Manuelle Tests

#### Test 1: Erster Start
1. Löschen Sie `general_settings.toml`
2. Starten Sie die App
3. **Erwartung:** Dialog erscheint
4. Klicken Sie "Jetzt ausschließen"
5. **Erwartung:** UAC-Dialog → Erfolgsmeldung

#### Test 2: Zweiter Start
1. Starten Sie die App erneut
2. **Erwartung:** Kein Dialog

#### Test 3: "Später"-Funktion
1. Löschen Sie `general_settings.toml`
2. Starten Sie die App
3. Klicken Sie "Später"
4. Starten Sie die App erneut
5. **Erwartung:** Dialog erscheint wieder

#### Test 4: Settings-Integration
1. Öffnen Sie Settings
2. Finden Sie "Performance"-Bereich
3. **Erwartung:** Status wird angezeigt (mit Admin-Rechten)
4. Klicken Sie Button
5. **Erwartung:** UAC → Ausnahme wird hinzugefügt

#### Test 5: Ohne Admin-Rechte
1. Starten Sie App ohne Admin-Rechte
2. Öffnen Sie Settings
3. **Erwartung:** "Status unbekannt"
4. Klicken Sie Button
5. **Erwartung:** UAC-Dialog erscheint

### PowerShell-Verifizierung

**Ausnahme prüfen:**
```powershell
Get-MpPreference | Select-Object -ExpandProperty ExclusionPath
```

**Ausnahme manuell hinzufügen:**
```powershell
Add-MpPreference -ExclusionPath "C:\Path\To\App.exe"
```

**Ausnahme manuell entfernen:**
```powershell
Remove-MpPreference -ExclusionPath "C:\Path\To\App.exe"
```

---

## 📊 Designentscheidungen

### Warum kein automatisches Hinzufügen?

**Entscheidung:** User muss explizit zustimmen

**Gründe:**
- 🔒 Sicherheit: User soll bewusst entscheiden
- ⚖️ Transparenz: Keine versteckten Änderungen am System
- ✅ Compliance: Unternehmensrichtlinien werden respektiert

### Warum UAC statt App-Neustart?

**Entscheidung:** Nur PowerShell-Befehl mit erhöhten Rechten

**Gründe:**
- ⚡ Performance: Kein App-Neustart = schneller
- 💾 State-Erhaltung: User verliert nicht den aktuellen Zustand
- 🎯 Präzise: Nur die spezifische Operation benötigt Rechte

### Warum Settings-Integration?

**Entscheidung:** Zusätzlicher Button in Settings

**Gründe:**
- 🔄 Flexibilität: User kann jederzeit ausschließen
- 🛠️ Kontrolle: Lösung wenn Ausnahme manuell gelöscht wurde
- 👥 UX: Kein Admin-Check beim Start nötig

### Warum ein Flag statt zwei?

**Entscheidung:** Nur `exclusion_asked` statt auch `never_ask_again`

**Gründe:**
- 🎯 KEEP IT SIMPLE: Weniger Komplexität
- 📝 Semantik: "Dialog wurde gezeigt" ist eine klare Aussage
- 🔄 Settings-Button macht Unterscheidung obsolet

---

## 🚀 Zukünftige Erweiterungen

### Mögliche Verbesserungen

**1. Andere Virenscanner unterstützen**
- Windows Security Essentials
- Avast, AVG, Norton, etc.
- Generischer Ansatz für verschiedene AV-Software

**2. Performance-Messung**
- Startzeit vor/nach Ausschluss messen
- Statistik anzeigen
- User zeigen, wie viel Zeit gespart wird

**3. Intelligentes Timing**
- Nur Dialog zeigen wenn Start > X Sekunden
- Automatische Erkennung von Scan-Verzögerung

**4. Gruppen-Policy**
- Zentrale Konfiguration für Unternehmensumgebungen
- Admin kann Feature deaktivieren/erzwingen

---

## 📝 Changelog

### Version 1.0 (Oktober 2025)
- ✅ Initiales Release
- ✅ Startup-Dialog mit drei Optionen
- ✅ UAC-Integration ohne App-Neustart
- ✅ Settings-Integration
- ✅ Intelligente Status-Anzeige
- ✅ Robuste Fehlerbehandlung
- ✅ Vollständige Dokumentation

---

## 👥 Credits

**Entwicklung:** Claude (Anthropic) + Thomas
**Testing:** Thomas
**Dokumentation:** Claude
**Design-Philosophie:** KEEP IT SIMPLE

---

## 📄 Lizenz

Dieses Feature ist Teil der HCC Plan DB Playground Anwendung und unterliegt deren Lizenz.

---

## 🤝 Support

Bei Fragen oder Problemen:
1. Prüfen Sie die Troubleshooting-Sektion
2. Prüfen Sie die Log-Dateien
3. Kontaktieren Sie den Entwickler

**Log-Dateien finden:**
```
<user_config_path>/logs/hcc-dispo.log
```

---

**Dokumentation Version:** 1.0  
**Stand:** Oktober 2025  
**Status:** ✅ Produktionsbereit
