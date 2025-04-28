# GUI-Integration für E-Mail-Funktionalität

Dieses Modul bietet die Integration der E-Mail-Funktionalität in die Qt-basierte GUI des HCC Plan DB Playground-Projekts.

## Überblick

Die GUI-Integration besteht aus vier verschiedenen Dialogklassen, die in separaten Dateien implementiert sind, sowie einer Hauptdatei, die diese zusammenführt und einfache Funktionen zum Öffnen der Dialoge bereitstellt.

## Dialoge

### 1. E-Mail-Konfigurationsdialog

Dieser Dialog ermöglicht die Konfiguration der SMTP-Servereinstellungen, Absenderinformationen und weiterer Optionen.

![Konfigurationsdialog](config_dialog.png)

### 2. Einsatzplan-Benachrichtigungsdialog

Mit diesem Dialog können Benachrichtigungen über einen neuen oder aktualisierten Einsatzplan an die betroffenen Mitarbeiter gesendet werden.

![Einsatzplan-Benachrichtigungsdialog](plan_dialog.png)

### 3. Verfügbarkeitsanfrage-Dialog

Dieser Dialog ermöglicht das Senden von Anfragen zur Eingabe von Verfügbarkeiten an Teammitglieder.

![Verfügbarkeitsanfrage-Dialog](availability_dialog.png)

### 4. Benutzerdefinierter E-Mail-Dialog

Mit diesem Dialog können benutzerdefinierte E-Mails an einzelne Personen, ein ganzes Team oder ein Projekt gesendet werden.

![Benutzerdefinierter E-Mail-Dialog](custom_dialog.png)

## Verwendung

### Konfiguration

```python
from email_to_users.gui_integration_main import show_config_dialog

# Zeigt den Konfigurationsdialog an
if show_config_dialog(parent_widget):
    print("Konfiguration gespeichert")
else:
    print("Konfiguration abgebrochen")
```

### Einsatzplan-Benachrichtigung

```python
from email_to_users.gui_integration_main import show_plan_notification_dialog

# Zeigt den Dialog zum Senden von Einsatzplan-Benachrichtigungen an
plan_id = "12345"  # UUID des Plans
if show_plan_notification_dialog(plan_id, parent_widget):
    print("E-Mails gesendet")
else:
    print("Abgebrochen")
```

### Verfügbarkeitsanfrage

```python
from email_to_users.gui_integration_main import show_availability_request_dialog

# Zeigt den Dialog zum Senden von Verfügbarkeitsanfragen an
plan_period_id = "67890"  # UUID des Planungszeitraums
if show_availability_request_dialog(plan_period_id, parent_widget):
    print("E-Mails gesendet")
else:
    print("Abgebrochen")
```

### Benutzerdefinierte E-Mail

```python
from email_to_users.gui_integration_main import show_custom_email_dialog

# Zeigt den Dialog zum Senden von benutzerdefinierten E-Mails an
if show_custom_email_dialog(parent_widget):
    print("E-Mails gesendet")
else:
    print("Abgebrochen")
```

## Integration in die Hauptanwendung

Die am besten geeigneten Stellen für die Integration in die Hauptanwendung sind:

1. **Menü**: Fügen Sie Menüpunkte für E-Mail-Funktionen hinzu, z.B. unter "Extras" oder "Kommunikation".

2. **Symbolleiste**: Fügen Sie Schaltflächen für häufig verwendete E-Mail-Funktionen hinzu.

3. **Kontextmenüs**: Fügen Sie E-Mail-Optionen zu relevanten Kontextmenüs hinzu, z.B. im Plan-Viewer oder Mitarbeiter-Verwaltung.

4. **Einstellungen**: Integrieren Sie den Konfigurationsdialog in die allgemeinen Einstellungen der Anwendung.

### Beispiel für die Integration in ein Menü:

```python
from PySide6.QtWidgets import QAction, QMenu

# E-Mail-Menü erstellen
email_menu = QMenu("E-Mail", main_window)

# Aktionen hinzufügen
config_action = QAction("Konfiguration...", main_window)
config_action.triggered.connect(lambda: show_config_dialog(main_window))

custom_email_action = QAction("Benutzerdefinierte E-Mail...", main_window)
custom_email_action.triggered.connect(lambda: show_custom_email_dialog(main_window))

email_menu.addAction(config_action)
email_menu.addAction(custom_email_action)

# Zum Hauptmenü hinzufügen
main_menu_bar.addMenu(email_menu)
```

### Beispiel für die Integration in ein Kontextmenü:

```python
# Kontextmenü für Plan-Ansicht
from PySide6.QtWidgets import QMenu, QAction

def on_plan_context_menu(position):
    context_menu = QMenu()
    
    # Plan-ID des ausgewählten Plans ermitteln
    selected_plan_id = get_selected_plan_id()
    
    # Aktion hinzufügen
    notify_action = QAction("Benachrichtigung senden...", main_window)
    notify_action.triggered.connect(lambda: show_plan_notification_dialog(selected_plan_id, main_window))
    
    context_menu.addAction(notify_action)
    context_menu.exec_(plan_view.mapToGlobal(position))

# Kontextmenü-Handler installieren
plan_view.customContextMenuRequested.connect(on_plan_context_menu)
```
