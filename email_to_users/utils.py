"""
Hilfsfunktionen für E-Mail-Erstellung und -Verwaltung.

Dieses Modul enthält Utility-Funktionen, die für die E-Mail-Funktionalität
im gesamten email_to_users-Paket verwendet werden.
"""
from email_validator import validate_email, EmailNotValidError
import re
import logging
from typing import List, Union, Dict, Any, Optional
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
import os.path

from pydantic import EmailStr, ValidationError

logger = logging.getLogger(__name__)


def validate_email_str(email: str) -> bool:
    """
    Validiert eine E-Mail-Adresse.

    Args:
        email: Die zu validierende E-Mail-Adresse

    Returns:
        True, wenn die E-Mail-Adresse gültig ist, sonst False
    """

    try:
        validate_email(email)
        return True
    except ValidationError:
        return False


def create_multipart_message(
    sender: str,
    recipients: List[str],
    subject: str,
    text_content: str,
    html_content: Optional[str] = None,
    attachments: Optional[List[Dict[str, Any]]] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
    reply_to: Optional[str] = None,
) -> MIMEMultipart:
    """
    Erstellt eine MIME-Multipart-Nachricht für den E-Mail-Versand.
    
    Args:
        sender: Absender-E-Mail-Adresse
        recipients: Liste der Empfänger-E-Mail-Adressen
        subject: Betreff der E-Mail
        text_content: Plaintext-Inhalt der E-Mail
        html_content: HTML-Inhalt der E-Mail (optional)
        attachments: Liste von Anhängen als Dictionaries mit 'path' und optionalen 'filename' Keys
        cc: Liste der CC-Empfänger (optional)
        bcc: Liste der BCC-Empfänger (optional)
        reply_to: Reply-To-Adresse (optional)
        
    Returns:
        Eine MIME-Multipart-Nachricht für den E-Mail-Versand
    """
    # Erstelle die Hauptnachricht als mixed (für Anhänge)
    message = MIMEMultipart('mixed')
        
    # Füge Metadaten hinzu
    message['From'] = sender
    message['To'] = ', '.join(recipients)
    message['Date'] = formatdate(localtime=True)
    message['Subject'] = subject
    
    if cc:
        message['Cc'] = ', '.join(cc)
    if reply_to:
        message['Reply-To'] = reply_to
    
    # Wenn sowohl Text als auch HTML vorhanden sind, erstelle einen 'alternative' Teil
    if html_content:
        # Erstelle einen 'alternative' Teil für Text und HTML
        alt_part = MIMEMultipart('alternative')
        # Füge Plaintext-Inhalt zum alternative Teil hinzu
        alt_part.attach(MIMEText(text_content, 'plain', 'utf-8'))
        # Füge HTML-Inhalt zum alternative Teil hinzu
        alt_part.attach(MIMEText(html_content, 'html', 'utf-8'))
        # Füge den alternativen Teil zur Hauptnachricht hinzu
        message.attach(alt_part)
    else:
        # Nur Plaintext - direkt zur Hauptnachricht hinzufügen
        message.attach(MIMEText(text_content, 'plain', 'utf-8'))
    
    # Füge Anhänge hinzu, wenn vorhanden
    if attachments:
        for attachment in attachments:
            path = attachment.get('path', '')
            if not path or not os.path.isfile(path):
                logger.warning(f"Anhang nicht gefunden: {path}")
                continue
                
            filename = attachment.get('filename', os.path.basename(path))
            content_type = attachment.get('content_type', '')
            
            with open(path, 'rb') as file:
                part = MIMEApplication(file.read())
                
            # Setze die Header für korrekte Anzeige in verschiedenen Clients
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            if content_type:
                part.add_header('Content-Type', content_type)
            else:
                # Wenn kein Content-Type angegeben ist, versuchen wir die Dateiendung zu erkennen
                ext = os.path.splitext(filename)[1].lower()
                if ext in ['.pdf']:
                    part.add_header('Content-Type', 'application/pdf')
                elif ext in ['.jpg', '.jpeg']:
                    part.add_header('Content-Type', 'image/jpeg')
                elif ext in ['.png']:
                    part.add_header('Content-Type', 'image/png')
                elif ext in ['.txt']:
                    part.add_header('Content-Type', 'text/plain')
                # Weitere Content-Types könnten hier hinzugefügt werden
                
            message.attach(part)
    
    return message
