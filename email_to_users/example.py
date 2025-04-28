"""
Beispielskript zur Demonstration der E-Mail-Funktionalität.

Dieses Skript zeigt, wie die verschiedenen E-Mail-Funktionen verwendet werden können.
"""

import os
import sys
from datetime import date, timedelta

# Deaktiviere das Senden tatsächlicher E-Mails während der Demonstration
os.environ["EMAIL_DEBUG_MODE"] = "True"

# Importiere nach dem Setzen der Umgebungsvariablen
from email_to_users import email_service, EmailSender
from email_to_users.templates import PlanNotificationTemplate, AvailabilityRequestTemplate


def demo_direct_email():
    """Demonstriert den direkten E-Mail-Versand ohne Datenbank."""
    print("\n=== Direkter E-Mail-Versand ===")
    
    sender = EmailSender()
    
    # Beispiel für einfachen E-Mail-Versand
    print("\n1. Einfache E-Mail:")
    sender.send_email(
        recipients=[{"email": "mail@thomas-ruff.de", "name": "Thomas Ruff"}],
        subject="Test-E-Mail",
        text_content="Dies ist eine Test-E-Mail.\n\nMit freundlichen Grüßen\nDas HCC-Plan-Team"
    )
    
    # Beispiel für HTML-E-Mail
    print("\n2. HTML-E-Mail:")
    sender.send_email(
        recipients=[{"email": "mail@thomas-ruff.de", "name": "Thomas Ruff"}],
        subject="HTML Test-E-Mail",
        text_content="Dies ist eine Test-E-Mail mit HTML-Inhalt.",
        html_content="""
        <html>
        <body>
            <h1>Test-E-Mail</h1>
            <p>Dies ist eine <strong>HTML-formatierte</strong> Test-E-Mail.</p>
            <p>Mit freundlichen Grüßen<br>Das HCC-Plan-Team</p>
        </body>
        </html>
        """
    )
    
    # Beispiel für Massen-E-Mail mit Personalisierung
    print("\n3. Personalisierte Massen-E-Mail:")
    sender.send_bulk_email(
        recipients=[
            {"email": "mail@thomas-ruff.de", "name": "mail@thomas-ruff.de"},
            {"email": "werbe@thomas-ruff.de", "name": "Thomas Ruff"}
        ],
        subject="Personalisierte E-Mail für {name}",
        text_template="Hallo {name},\n\nDies ist eine personalisierte E-Mail für Sie.\n\nMit freundlichen Grüßen\nDas HCC-Plan-Team",
        delay=1.0  # 1 Sekunde Verzögerung zwischen E-Mails
    )


def demo_templates():
    """Demonstriert die Verwendung der E-Mail-Templates."""
    print("\n=== Template-Verwendung ===")
    
    sender = EmailSender()
    
    # Beispiel für Plan-Benachrichtigung
    print("\n1. Einsatzplan-Benachrichtigung:")
    plan_template = PlanNotificationTemplate()
    subject, text, html = plan_template.render(
        recipient_name="Max Mustermann",
        plan_name="Einsatzplan Mai 2025",
        plan_period="01.05.2025 - 31.05.2025",
        team_name="Team Nord",
        assignments=[
            {"date": "03.05.2025", "time": "Vormittag", "location": "Klinik A"},
            {"date": "10.05.2025", "time": "Nachmittag", "location": "Klinik B"},
            {"date": "17.05.2025", "time": "Vormittag", "location": "Klinik A"}
        ],
        notes="Bitte beachten Sie die geänderten Öffnungszeiten in Klinik B."
    )
    
    sender.send_email(
        recipients=[{"email": "mail@thomas-ruff.de", "name": "Max Mustermann"}],
        subject=subject,
        text_content=text,
        html_content=html
    )
    
    # Beispiel für Verfügbarkeitsanfrage
    print("\n2. Verfügbarkeitsanfrage:")
    request_template = AvailabilityRequestTemplate()
    today = date.today()
    subject, text, html = request_template.render(
        recipient_name="Erika Musterfrau",
        plan_period="Juni 2025",
        team_name="Team Süd",
        deadline=today + timedelta(days=14),
        period_start=date(2025, 6, 1),
        period_end=date(2025, 6, 30),
        url="https://example.com/availability/12345",
        notes="Bitte beachten Sie, dass im Juni vermehrt Einsätze am Wochenende geplant sind."
    )
    
    sender.send_email(
        recipients=[{"email": "mail@thomas-ruff.de", "name": "Erika Musterfrau"}],
        subject=subject,
        text_content=text,
        html_content=html
    )


def demo_service_api():
    """
    Demonstriert die Verwendung der Service-API.
    
    Hinweis: Diese Funktionen erfordern eine Datenbankverbindung und können
    daher nicht direkt ausgeführt werden. Der Code wird nur zur Demonstration gezeigt.
    """
    print("\n=== Service-API (Beispielcode) ===")
    print("Hinweis: Diese Funktionen erfordern eine Datenbankverbindung und werden nicht ausgeführt.")
    
    print("""
# Beispiel für das Senden einer Plan-Benachrichtigung:
stats = email_service.send_plan_notification(
    plan_id="12345",
    include_attachments=True
)
print(f"Erfolgreiche E-Mails: {stats['success']}")
print(f"Fehlgeschlagene E-Mails: {stats['failed']}")

# Beispiel für das Senden einer Verfügbarkeitsanfrage:
stats = email_service.send_availability_request(
    plan_period_id="67890",
    url_base="https://example.com/availability"
)
print(f"Erfolgreiche E-Mails: {stats['success']}")
print(f"Fehlgeschlagene E-Mails: {stats['failed']}")

# Beispiel für das Senden einer benutzerdefinierten E-Mail:
stats = email_service.send_custom_email(
    subject="Wichtige Mitteilung",
    text_content="Hallo {name},\\n\\nDies ist eine wichtige Mitteilung.\\n\\nMit freundlichen Grüßen\\nDas HCC-Plan-Team",
    team_id="12345"
)
print(f"Erfolgreiche E-Mails: {stats['success']}")
print(f"Fehlgeschlagene E-Mails: {stats['failed']}")
""")


if __name__ == "__main__":
    print("=== E-Mail-Funktionalität Demonstration ===")
    print("Hinweis: Alle E-Mails werden im Debug-Modus gesendet und nicht tatsächlich verschickt.")
    
    demo_direct_email()
    demo_templates()
    demo_service_api()
    
    print("\nDemonstration abgeschlossen.")
