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


def format_recipients(recipients: List[Dict[str, str]]) -> List[str]:
    """
    Formatiert eine Liste von Empfänger-Dictionaries in eine Liste von formatierten Strings.
    
    Args:
        recipients: Liste von Dictionaries mit 'email' und optional 'name' Keys
        
    Returns:
        Liste von formatierten Empfänger-Strings ("Name <email@example.com>")
    """
    formatted = []
    for recipient in recipients:
        email = recipient.get('email', '')
        name = recipient.get('name', '')

        if not email or not validate_email_str(email):
            print(f"Ungültige E-Mail-Adresse übersprungen: {email}")
            logger.warning(f"Ungültige E-Mail-Adresse übersprungen: {email}")
            continue
            
        if name:
            formatted.append(f"{name} <{email}>")
        else:
            formatted.append(email)
            
    return formatted


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
    # Erstelle die Basis-Nachricht
    if html_content:
        message = MIMEMultipart('alternative')
    else:
        message = MIMEMultipart()
        
    # Füge Metadaten hinzu
    message['From'] = sender
    message['To'] = ', '.join(recipients)
    message['Date'] = formatdate(localtime=True)
    message['Subject'] = subject
    
    if cc:
        message['Cc'] = ', '.join(cc)
    if reply_to:
        message['Reply-To'] = reply_to
        
    # Füge Plaintext-Inhalt hinzu
    message.attach(MIMEText(text_content, 'plain', 'utf-8'))
    
    # Füge HTML-Inhalt hinzu, wenn vorhanden
    if html_content:
        message.attach(MIMEText(html_content, 'html', 'utf-8'))
    
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
                
            part.add_header('Content-Disposition', 'attachment', filename=filename)
            if content_type:
                part.add_header('Content-Type', content_type)
                
            message.attach(part)
    
    return message


def extract_emails_from_persons(persons, attr_name='email'):
    """
    Extrahiert E-Mail-Adressen aus einer Liste von Person-Objekten.
    
    Args:
        persons: Liste von Person-Objekten
        attr_name: Name des Attributs, das die E-Mail-Adresse enthält (Standard: 'email')
        
    Returns:
        Liste von Dictionaries mit 'email' und 'name' Keys
    """
    recipients = []
    for person in persons:
        if hasattr(person, attr_name) and getattr(person, attr_name):
            email = getattr(person, attr_name)
            if validate_email_str(email):
                recipients.append({
                    'email': email,
                    'name': getattr(person, 'full_name', f"{getattr(person, 'f_name', '')} {getattr(person, 'l_name', '')}")
                })
    return recipients
