"""
E-Mail-Sender-Modul für den Versand von E-Mails an Benutzer.

Dieses Modul enthält die Hauptklasse für den E-Mail-Versand via SMTP
und bietet Methoden für Einzel- und Massen-E-Mails.
"""

import smtplib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional, Union, Literal
from email.mime.multipart import MIMEMultipart

from database import schemas

from .config import get_email_config
from .utils import create_multipart_message

logger = logging.getLogger(__name__)


@dataclass
class EmailSendSuccess:
    successfully_sent: list[str]
    failed_to_send: list[str]
    error_message: Optional[str] = None


class EmailSender:
    """Hauptklasse für den Versand von E-Mails via SMTP."""
    
    def __init__(self, config=None):
        """
        Initialisiert den EmailSender.
        
        Args:
            config: Optional, eine EmailConfig-Instanz. Wenn nicht angegeben,
                   wird die globale email_config verwendet.
        """
        self.config = config or get_email_config()
        self._sent_count = 0
        self._last_reset = datetime.now()
        self._rate_limit_reached = False
        
    def _check_rate_limit(self) -> bool:
        """
        Überprüft, ob das Rate-Limit erreicht wurde.
        
        Returns:
            True, wenn das Senden erlaubt ist, False wenn das Rate-Limit erreicht wurde
        """
        # Setze den Zähler zurück, wenn eine Stunde vergangen ist
        now = datetime.now()
        if (now - self._last_reset).total_seconds() > 3600:
            self._sent_count = 0
            self._last_reset = now
            self._rate_limit_reached = False
            
        # Überprüfe das Rate-Limit
        if self._sent_count >= self.config.rate_limit_per_hour:
            if not self._rate_limit_reached:
                logger.warning(
                    f"E-Mail-Rate-Limit erreicht: {self.config.rate_limit_per_hour} pro Stunde"
                )
                self._rate_limit_reached = True
            return False
            
        return True
        
    def _increment_sent_count(self, count=1):
        """Erhöht den Zähler für gesendete E-Mails."""
        self._sent_count += count
        
    def _create_smtp_connection(self) -> smtplib.SMTP:
        """
        Erstellt eine Verbindung zum SMTP-Server.
        
        Returns:
            Eine SMTP-Verbindung
            
        Raises:
            smtplib.SMTPException: Bei Problemen mit der SMTP-Verbindung
        """
        if self.config.use_ssl:
            smtp = smtplib.SMTP_SSL(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=self.config.timeout
            )
        else:
            smtp = smtplib.SMTP(
                self.config.smtp_host,
                self.config.smtp_port,
                timeout=self.config.timeout
            )
            
            if self.config.use_tls:
                smtp.starttls()
                
        # Authentifizierung, falls Benutzername und Passwort vorhanden sind
        if self.config.smtp_username and self.config.smtp_password:
            smtp.login(self.config.smtp_username, self.config.smtp_password)
            
        return smtp
        
    def _send_debug(
        self,
        message: MIMEMultipart,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> None:
        """
        Simuliert das Senden einer E-Mail im Debug-Modus.

        Args:
            message: Die zu sendende MIME-Multipart-Nachricht
            recipients: Liste der Empfänger-E-Mail-Adressen
            cc: Liste der CC-Empfänger (optional)
            bcc: Liste der BCC-Empfänger (optional)
        """
        logger.info("Debug-Modus: E-Mail wird nicht gesendet, sondern nur protokolliert.")
        logger.info(f"Betreff: {message['Subject']}")
        logger.info(f"Empfänger: {', '.join(recipients)}")
        logger.info(f"CC: {', '.join(cc or [])}")
        logger.info(f"BCC: {', '.join(bcc or [])}")
        logger.info(f"Inhalt: {message.as_string()}")

    def _send_via_smtp(
        self,
        message: MIMEMultipart,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> EmailSendSuccess:
        """
        Sendet eine E-Mail über SMTP.
        
        Args:
            message: Die zu sendende MIME-Multipart-Nachricht
            recipients: Liste der Empfänger-E-Mail-Adressen
            cc: Liste der CC-Empfänger (optional)
            bcc: Liste der BCC-Empfänger (optional)
            
        Returns:
            True, wenn die E-Mail erfolgreich gesendet wurde, sonst False
        """
        # Alle Empfänger für SMTP (wird für alle Pfade benötigt)
        all_recipients = recipients.copy()
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)

        # Überprüfe das Rate-Limit
        if not self._check_rate_limit():
            return EmailSendSuccess(successfully_sent=[], failed_to_send=all_recipients,
                                    error_message="rate_limit_exceeded")

        # Überprüfe Debug-Modus
        if self.config.debug_mode:
            self._send_debug(message, recipients, cc, bcc)
            return EmailSendSuccess(successfully_sent=all_recipients, failed_to_send=[])

        email_send_success = EmailSendSuccess(successfully_sent=[], failed_to_send=[])
        
        # Sende die E-Mail
        try:
            with self._create_smtp_connection() as smtp:
                try:
                    # sendmail gibt ein Dictionary mit fehlgeschlagenen Empfängern zurück
                    refused = smtp.sendmail(
                        message['From'],
                        all_recipients,
                        message.as_string()
                    )
                    
                    # Wenn refused leer ist, wurden alle E-Mails akzeptiert
                    if not refused:
                        email_send_success.successfully_sent.extend(all_recipients)
                        logger.info(f"E-Mail vom SMTP-Server akzeptiert für alle Empfänger: {', '.join(all_recipients)}")
                        return email_send_success
                    
                    # Andernfalls wurden einige Empfänger abgelehnt
                    failed_recipients = list(refused.keys())
                    successful_recipients = [r for r in all_recipients if r not in failed_recipients]
                    email_send_success.failed_to_send.extend(failed_recipients)
                    email_send_success.successfully_sent.extend(successful_recipients)
                    
                    logger.error(f"E-Mail konnte nicht an folgende Empfänger gesendet werden: {', '.join(failed_recipients)}")
                    
                    if successful_recipients:
                        logger.info(f"E-Mail vom SMTP-Server akzeptiert für: {', '.join(successful_recipients)}")

                    return email_send_success
                    
                except smtplib.SMTPRecipientsRefused as e:
                    # Dieser Fehler tritt auf, wenn alle Empfänger abgelehnt wurden
                    logger.error(f"Alle Empfänger wurden vom SMTP-Server abgelehnt: {str(e)}")
                    email_send_success.failed_to_send.extend(all_recipients)
                    return email_send_success
                
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP-Authentifizierungsfehler: Anmeldedaten ungültig")
            email_send_success.failed_to_send.extend(all_recipients)
            email_send_success.error_message = "smtp_authentication_error"
            return email_send_success
        except Exception as e:
            logger.error(f"Fehler beim Senden der E-Mail: {str(e)}")
            email_send_success.failed_to_send.extend(all_recipients)
            return email_send_success
        
    def send_email(
        self,
        recipients: list[schemas.Person],
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
        sender: Optional[str] = None,
        cc: Optional[list[schemas.Person]] = None,
        bcc: Optional[list[schemas.Person]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> EmailSendSuccess:
        """
        Sendet eine E-Mail an eine oder mehrere Adressen.
        
        Args:
            recipients: Liste von Empfängern, entweder als Dictionaries mit 'email' und 'name'
                       Keys oder als einfache E-Mail-Adressen
            subject: Betreff der E-Mail
            text_content: Plaintext-Inhalt der E-Mail
            html_content: HTML-Inhalt der E-Mail (optional)
            sender: Absender-Adresse (optional, verwendet den Standard aus der Konfiguration)
            cc: Liste von CC-Empfängern (optional)
            bcc: Liste von BCC-Empfängern (optional)
            reply_to: Reply-To-Adresse (optional)
            attachments: Liste von Anhängen als Dictionaries mit 'path' und optional 'filename'
                        und 'content_type' Keys
                        
        Returns:
            True, wenn die E-Mail erfolgreich gesendet wurde, sonst False
        """
        # Formatiere und validiere die Empfänger
        formatted_recipients = [str(recipient.email) for recipient in recipients if recipient.email]
        if not formatted_recipients:
            logger.error("Keine gültigen Empfänger angegeben")
            return EmailSendSuccess(successfully_sent=[], failed_to_send=[])
            
        # Formatiere CC und BCC, falls vorhanden
        formatted_cc = [str(r.email) for r in cc if r.email] if cc else None
        formatted_bcc = [str(r.email) for r in bcc if r.email] if bcc else None
        
        # Verwende den Standard-Absender, falls keiner angegeben wurde
        sender_address = sender or self.config.sender_formatted
        
        # Erstelle die Nachricht
        message = create_multipart_message(
            sender=sender_address,
            recipients=formatted_recipients,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
            attachments=attachments,
            cc=formatted_cc,
            bcc=formatted_bcc,
            reply_to=reply_to
        )
        
        # Sende die E-Mail
        return self._send_via_smtp(
            message=message,
            recipients=formatted_recipients,
            cc=formatted_cc,
            bcc=formatted_bcc
        )
        
    def send_bulk_email(
        self,
        all_recipients: dict[Literal['recipients', 'cc', 'bcc'], list[schemas.Person]],
        subject: str,
        text_template: str,
        html_template: Optional[str] = None,
        sender: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        template_params: Optional[Dict[str, Any]] = None,
        delay: float = 0.0
    ) -> Dict[str, Any]:
        """
        Sendet personalisierte E-Mails an mehrere Empfänger.
        
        Args:
            all_recipients: Dictionary mit den Empfängern, CC und BCC als Listen von Person-Objekten
            subject: Betreff der E-Mail
            text_template: Plaintext-Template mit Platzhaltern für die Personalisierung
            html_template: HTML-Template mit Platzhaltern für die Personalisierung (optional)
            sender: Absender-Adresse (optional, verwendet den Standard aus der Konfiguration)
            reply_to: Reply-To-Adresse (optional)
            attachments: Liste von Anhängen als Dictionaries (optional)
            template_params: Dictionary mit globalen Parametern für alle E-Mails (optional)
            delay: Verzögerung zwischen dem Senden von E-Mails in Sekunden (optional)
                  
        Returns:
            Dictionary mit Statistiken: Anzahl erfolgreicher und fehlgeschlagener E-Mails
        """

        # Validiere die Eingabedaten
        if not all_recipients['recipients']:
            logger.error("Keine Empfänger angegeben")
            return {'success': 0, 'failed': 0}
            
        # Initialisiere Statistiken
        stats = {'success': 0, 'failed': 0}
        template_params = template_params or {}

        # Sende personalisierte E-Mails an jeden Empfänger
        for i, recipient in enumerate(all_recipients['recipients']):
            # Überprüfe, ob es eine gültige E-Mail-Adresse ist
            if not recipient.email:
                stats['failed'] += 1
                continue
                
            # Erstelle individuelle Template-Parameter
            params = template_params.copy()
            
            # Füge Empfänger-spezifische Parameter hinzu
            params['full_name'] = recipient.full_name
            params['f_name'] = recipient.f_name
            params['l_name'] = recipient.l_name
            params['email'] = recipient.email

            # Personalisiere die Templates
            personalized_text = self._personalize_template(text_template, params)
            personalized_html = None
            if html_template:
                personalized_html = self._personalize_template(html_template, params)

            # Sende die E-Mail
            success = self.send_email(
                recipients=[recipient],
                subject=subject,
                text_content=personalized_text,
                html_content=personalized_html,
                sender=sender,
                reply_to=reply_to,
                attachments=attachments
            )
            
            # Aktualisiere Statistiken
            if success.successfully_sent:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                if success.error_message and 'error' not in stats:
                    stats['error'] = success.error_message
                
            # Verzögerung, um den Server nicht zu überlasten
            if delay > 0 and i < len(all_recipients['recipients']) - 1:
                time.sleep(delay)
                
        return stats
        
    def _personalize_template(self, template: str, params: Dict[str, Any]) -> str:
        """
        Personalisiert ein Template mit den angegebenen Parametern.
        
        Args:
            template: Das Template mit Platzhaltern
            params: Dictionary mit Parametern für die Personalisierung
            
        Returns:
            Das personalisierte Template
        """
        try:
            # Verwende Jinja2 für die Template-Personalisierung
            from jinja2 import Template
            jinja_template = Template(template)
            return jinja_template.render(**params)
        except ImportError:
            logger.warning("Jinja2 ist nicht installiert. Verwende einfache Formatstring-Implementierung.")
            try:
                return template.format(**params)
            except KeyError as e:
                logger.warning(f"Fehlender Template-Parameter: {str(e)}")
                return template
            except Exception as e:
                logger.error(f"Fehler bei der Template-Personalisierung: {str(e)}")
                return template
        except Exception as e:
            logger.error(f"Fehler bei der Jinja2-Template-Personalisierung: {str(e)}")
            # Fallback zur einfachen Formatstring-Implementierung
            try:
                return template.format(**params)
            except Exception:
                return template
