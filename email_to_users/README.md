# E-Mail-Funktionalität für HCC Plan DB

Dieses Paket implementiert die E-Mail-Versand-Funktionalität für das HCC Plan DB Playground-Projekt.

## Überblick

Die E-Mail-Funktionalität ermöglicht das Versenden von Benachrichtigungen und Informationen an Mitarbeiter. Folgende Hauptfunktionen werden bereitgestellt:

- Senden von Einsatzplan-Benachrichtigungen
- Senden von Verfügbarkeitsanfragen
- Senden von benutzerdefinierten E-Mails an einzelne Mitarbeiter oder Gruppen
- HTML- und Plaintext-E-Mails
- Unterstützung für Anhänge
- Konfigurierbare SMTP-Einstellungen

## Paket-Struktur

```
email_to_users/
├── __init__.py            # Paket-Exporte
├── config.py              # Konfigurationseinstellungen
├── sender.py              # E-Mail-Sender-Klasse
├── service.py             # Service-Schicht für Integration mit dem Datenmodell
├── utils.py               # Hilfsfunktionen
├── example.py             # Beispiele für die Verwendung
├── README.md              # Diese Datei
├── tests/                 # Testfälle
│   ├── __init__.py
│   ├── test_utils.py
│   ├── test_sender.py
│   └── test_templates.py
└── templates/             # E-Mail-Templates
    ├── __init__.py
    ├── base.py            # Basis-Template-Klasse
    ├── plan_notify.py     # Template für Einsatzplan-Benachrichtigungen
    └── request.py         # Template für Verfügbarkeitsanfragen
```

## Konfiguration

Die E-Mail-Einstellungen können auf folgende Arten konfiguriert werden:

1. Umgebungsvariablen:
   ```
   SMTP_HOST=smtp.example.com
   SMTP_PORT=587
   SMTP_USERNAME=username
   SMTP_PASSWORD=password
   SMTP_USE_TLS=True
   SMTP_USE_SSL=False
   DEFAULT_SENDER_EMAIL=noreply@example.com
   DEFAULT_SENDER_NAME=HCC Plan
   ```

2. Programmatisch:
   ```python
   from email_to_users.config import email_config
   
   email_config.smtp_host = "smtp.example.com"
   email_config.smtp_port = 587
   email_config.smtp_username = "username"
   email_config.smtp_password = "password"
   ```

3. Aus einer Konfigurationsdatei:
   ```python
   from email_to_users.config import load_config_from_file
   
   load_config_from_file("config.toml")
   ```

## Verwendung

### Direkte Verwendung des E-Mail-Senders

```python
from email_to_users import EmailSender

sender = EmailSender()

# Einfache E-Mail senden
sender.send_email(
    recipients=[{"email": "mitarbeiter@example.com", "name": "Max Mustermann"}],
    subject="Wichtige Mitteilung",
    text_content="Dies ist eine wichtige Mitteilung.\n\nMit freundlichen Grüßen\nDas HCC-Plan-Team"
)

# HTML-E-Mail senden
sender.send_email(
    recipients=[{"email": "mitarbeiter@example.com", "name": "Max Mustermann"}],
    subject="Wichtige Mitteilung",
    text_content="Dies ist eine wichtige Mitteilung.",
    html_content="<html><body><h1>Wichtige Mitteilung</h1><p>Dies ist eine wichtige Mitteilung.</p></body></html>"
)

# Personalisierte Massen-E-Mail senden
sender.send_bulk_email(
    recipients=[
        {"email": "mitarbeiter1@example.com", "name": "Max Mustermann"},
        {"email": "mitarbeiter2@example.com", "name": "Erika Musterfrau"}
    ],
    subject="Personalisierte Mitteilung für {name}",
    text_template="Hallo {name},\n\nDies ist eine personalisierte Mitteilung für Sie."
)
```

### Verwendung der Service-Schicht

```python
from email_to_users import email_service

# Einsatzplan-Benachrichtigung senden
stats = email_service.send_plan_notification(
    plan_id="12345",
    include_attachments=True
)

# Verfügbarkeitsanfrage senden
stats = email_service.send_availability_request(
    plan_period_id="67890",
    url_base="https://example.com/availability"
)

# Benutzerdefinierte E-Mail an ein Team senden
stats = email_service.send_custom_email(
    subject="Wichtige Mitteilung",
    text_content="Hallo {name},\n\nDies ist eine wichtige Mitteilung.",
    team_id="12345"
)
```

### Verwendung der Templates

```python
from email_to_users.templates import PlanNotificationTemplate

template = PlanNotificationTemplate()
subject, text, html = template.render(
    recipient_name="Max Mustermann",
    plan_name="Einsatzplan Mai 2025",
    plan_period="01.05.2025 - 31.05.2025",
    team_name="Team Nord",
    assignments=[
        {"date": "03.05.2025", "time": "Vormittag", "location": "Klinik A"},
        {"date": "10.05.2025", "time": "Nachmittag", "location": "Klinik B"}
    ],
    notes="Wichtige Informationen zum Einsatzplan."
)
```

## Debug-Modus

Für Testzwecke kann der Debug-Modus aktiviert werden, der E-Mails nicht wirklich versendet, sondern auf der Konsole ausgibt:

```python
import os
os.environ["EMAIL_DEBUG_MODE"] = "True"

# Oder programmatisch:
from email_to_users.config import email_config
email_config.debug_mode = True
```

## Tests

Die Tests können mit dem Standard-Unittest-Framework ausgeführt werden:

```bash
python -m unittest discover -s email_to_users/tests
```

## Beispiele

Weitere Beispiele zur Verwendung der E-Mail-Funktionalität finden sich in der Datei `example.py`.
