import smtplib
from email.message import EmailMessage
from typing import Optional
import os


def send_emails(sender: str, password: str, recipients: list[str], subject: str, body: str, files: list[str],
                cc_list: Optional[list[str]] = None):
    if cc_list is None:
        cc_list = []

    try:
        # SMTP-Verbindung öffnen und einmalig einloggen
        with smtplib.SMTP('smtp.example.com', 587) as server:
            try:
                server.starttls()
                server.login(sender, password)
                print("Erfolgreich beim SMTP-Server eingeloggt.")
            except smtplib.SMTPAuthenticationError:
                print("Fehler: Login fehlgeschlagen. Überprüfe Benutzername und Passwort.")
                return
            except smtplib.SMTPException as e:
                print(f"SMTP-Fehler beim Login: {e}")
                return

            # Schleife durch die Empfänger
            for recipient in recipients:
                try:
                    # Erstellen einer neuen Nachricht für jeden Empfänger
                    msg = EmailMessage()
                    msg['From'] = sender
                    msg['To'] = recipient
                    msg['Cc'] = ', '.join(cc_list)
                    msg['Subject'] = subject
                    msg.set_content(body)

                    # Dateien anhängen
                    for file in files:
                        try:
                            with open(file, 'rb') as f:
                                file_data = f.read()
                                file_name = os.path.basename(file)
                            msg.add_attachment(file_data, maintype='application', subtype='octet-stream',
                                               filename=file_name)
                        except FileNotFoundError:
                            print(f"Fehler: Datei '{file}' wurde nicht gefunden.")
                            continue
                        except IOError as e:
                            print(f"Fehler beim Öffnen der Datei '{file}': {e}")
                            continue

                    # Nachricht an den Empfänger senden
                    server.send_message(msg)
                    print(f"E-Mail erfolgreich an {recipient} gesendet.")

                except smtplib.SMTPRecipientsRefused:
                    print(f"Fehler: Empfänger {recipient} wurde vom Server abgelehnt.")
                except smtplib.SMTPException as e:
                    print(f"SMTP-Fehler beim Senden an {recipient}: {e}")

    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:
        print(f"Fehler: Keine Verbindung zum SMTP-Server möglich: {e}")
    except smtplib.SMTPException as e:
        print(f"Allgemeiner SMTP-Fehler: {e}")
    except Exception as e:
        print(f"Ein unerwarteter Fehler ist aufgetreten: {e}")


if __name__ == '__main__':
    # Beispielaufruf
    send_emails(
        sender='your_email@example.com',
        password='your_password',
        recipients=['recipient1@example.com', 'recipient2@example.com', 'recipient3@example.com'],
        subject='Test Email an mehrere Empfänger',
        body='Dies ist eine Test-E-Mail mit einem Anhang.',
        files=['/path/to/file.pdf'],
        cc_list=['cc_recipient@example.com']
    )
