"""
E-Mail-Sender-Modul für den Versand von E-Mails an Benutzer.

Dieses Modul enthält die Hauptklasse für den E-Mail-Versand via SMTP
und bietet Methoden für Einzel- und Massen-E-Mails.
"""

import smtplib
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Union
from email.mime.multipart import MIMEMultipart

try:
    from .config import email_config
    from .utils import (
        validate_email,
        format_recipients,
        create_multipart_message,
        extract_emails_from_persons
    )
except ImportError:
    from config import email_config
    from utils import (
        validate_email,
        format_recipients,
        create_multipart_message,
        extract_emails_from_persons
    )

logger = logging.getLogger(__name__)


class EmailSender:
    """Hauptklasse für den Versand von E-Mails via SMTP."""
    
    def __init__(self, config=None):
        """
        Initialisiert den EmailSender.
        
        Args:
            config: Optional, eine EmailConfig-Instanz. Wenn nicht angegeben,
                   wird die globale email_config verwendet.
        """
        self.config = config or email_config
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
        
    def _increment_sent_count(self):
        """Erhöht den Zähler für gesendete E-Mails."""
        self._sent_count += 1
        
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
        
    def _send_via_smtp(
        self,
        message: MIMEMultipart,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> bool:
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
        # Überprüfe das Rate-Limit
        if not self._check_rate_limit():
            return False
            
        # Überprüfe Debug-Modus
        if self.config.debug_mode:
            self._send_debug(message, recipients, cc, bcc)
            self._increment_sent_count()
            return True
            
        # Alle Empfänger für SMTP
        all_recipients = recipients.copy()
        if cc:
            all_recipients.extend(cc)
        if bcc:
            all_recipients.extend(bcc)
            
        # Sende die E-Mail
        try:
            with self._create_smtp_connection() as smtp:
                smtp.send_message(
                    message,
                    from_addr=message['From'],
                    to_addrs=all_recipients
                )
                
            self._increment_sent_count()
            logger.info(f"E-Mail erfolgreich gesendet an: {', '.join(recipients)}")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Senden der E-Mail: {str(e)}")
            return False
            
    def _send_debug(
        self,
        message: MIMEMultipart,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ):
        """
        Gibt eine E-Mail im Debug-Modus aus.
        
        Args:
            message: Die zu sendende MIME-Multipart-Nachricht
            recipients: Liste der Empfänger-E-Mail-Adressen
            cc: Liste der CC-Empfänger (optional)
            bcc: Liste der BCC-Empfänger (optional)
        """
        debug_prefix = "[DEBUG EMAIL] "
        print(f"\n{debug_prefix}{'=' * 50}")
        print(f"{debug_prefix}Von: {message['From']}")
        print(f"{debug_prefix}An: {', '.join(recipients)}")
        
        if cc:
            print(f"{debug_prefix}CC: {', '.join(cc)}")
        if bcc:
            print(f"{debug_prefix}BCC: {', '.join(bcc)}")
            
        print(f"{debug_prefix}Betreff: {message['Subject']}")
        print(f"{debug_prefix}Datum: {message['Date']}")
        
        if 'Reply-To' in message:
            print(f"{debug_prefix}Antwort an: {message['Reply-To']}")
            
        print(f"{debug_prefix}{'-' * 50}")
        
        # Zeige den Plaintext-Inhalt an
        for part in message.walk():
            if part.get_content_type() == 'text/plain':
                print(f"{debug_prefix}Plaintext-Inhalt:")
                print(f"{debug_prefix}{part.get_payload(decode=True).decode('utf-8')}")
                break
                
        # Liste Anhänge auf
        attachments = []
        for part in message.walk():
            if part.get_content_disposition() == 'attachment':
                filename = part.get_filename()
                if filename:
                    attachments.append(filename)
                    
        if attachments:
            print(f"{debug_prefix}Anhänge: {', '.join(attachments)}")
            
        print(f"{debug_prefix}{'=' * 50}\n")
    
    def _format_recipients_input(self, recipients):
        """
        Formatiert die Empfänger-Eingabe zu einer Liste von E-Mail-Adressen.
        
        Args:
            recipients: Liste von Empfängern, entweder als Dictionaries mit 'email' und 'name'
                       Keys oder als einfache E-Mail-Adressen oder None
        
        Returns:
            Liste von formatierten E-Mail-Adressen oder leere Liste wenn keine gültigen Empfänger
        """
        if not recipients:
            return []
            
        # Überprüfe, ob es sich um eine Liste von Strings handelt
        if isinstance(recipients[0], str):
            return [r for r in recipients if validate_email(r)]
            
        # Ansonsten handelt es sich um eine Liste von Dictionaries
        return format_recipients(recipients)
        
    def send_email(
        self,
        recipients: Union[List[Dict[str, str]], List[str]],
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
        sender: Optional[str] = None,
        cc: Optional[Union[List[Dict[str, str]], List[str]]] = None,
        bcc: Optional[Union[List[Dict[str, str]], List[str]]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
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
        formatted_recipients = self._format_recipients_input(recipients)
        if not formatted_recipients:
            logger.error("Keine gültigen Empfänger angegeben")
            return False
            
        # Formatiere CC und BCC, falls vorhanden
        formatted_cc = self._format_recipients_input(cc) if cc else None
        formatted_bcc = self._format_recipients_input(bcc) if bcc else None
        
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
        recipients: List[Dict[str, str]],
        subject: str,
        text_template: str,
        html_template: Optional[str] = None,
        sender: Optional[str] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        template_params: Optional[Dict[str, Any]] = None,
        individual_template_params: Optional[List[Dict[str, Any]]] = None,
        delay: float = 0.0
    ) -> Dict[str, int]:
        """
        Sendet personalisierte E-Mails an mehrere Empfänger.
        
        Args:
            recipients: Liste von Empfänger-Dictionaries mit 'email' und 'name' Keys
            subject: Betreff der E-Mail
            text_template: Plaintext-Template mit Platzhaltern für die Personalisierung
            html_template: HTML-Template mit Platzhaltern für die Personalisierung (optional)
            sender: Absender-Adresse (optional, verwendet den Standard aus der Konfiguration)
            reply_to: Reply-To-Adresse (optional)
            attachments: Liste von Anhängen als Dictionaries (optional)
            template_params: Dictionary mit globalen Parametern für alle E-Mails (optional)
            individual_template_params: Liste von Dictionaries mit individuellen Parametern
                                       für jeden Empfänger (optional, muss die gleiche Länge
                                       wie recipients haben)
            delay: Verzögerung zwischen dem Senden von E-Mails in Sekunden (optional)
                  
        Returns:
            Dictionary mit Statistiken: Anzahl erfolgreicher und fehlgeschlagener E-Mails
        """
        # Validiere die Eingabedaten
        if not recipients:
            logger.error("Keine Empfänger angegeben")
            return {'success': 0, 'failed': 0}
            
        if individual_template_params and len(individual_template_params) != len(recipients):
            logger.error(
                f"Die Anzahl der individuellen Template-Parameter ({len(individual_template_params)}) "
                f"stimmt nicht mit der Anzahl der Empfänger ({len(recipients)}) überein"
            )
            return {'success': 0, 'failed': 0}
            
        # Initialisiere Statistiken
        stats = {'success': 0, 'failed': 0}
        template_params = template_params or {}
        
        # Sende personalisierte E-Mails an jeden Empfänger
        for i, recipient in enumerate(recipients):
            # Überprüfe, ob es eine gültige E-Mail-Adresse ist
            if not recipient.get('email') or not validate_email(recipient['email']):
                stats['failed'] += 1
                continue
                
            # Erstelle individuelle Template-Parameter
            params = template_params.copy()
            
            # Füge Empfänger-spezifische Parameter hinzu
            params['name'] = recipient.get('name', '')
            params['email'] = recipient['email']
            
            # Füge individuelle Parameter hinzu, falls vorhanden
            if individual_template_params:
                params.update(individual_template_params[i])
                
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
            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1
                
            # Verzögerung, um den Server nicht zu überlasten
            if delay > 0 and i < len(recipients) - 1:
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
        # Einfache Implementierung mit Formatstring
        try:
            return template.format(**params)
        except KeyError as e:
            logger.warning(f"Fehlender Template-Parameter: {str(e)}")
            return template
        except Exception as e:
            logger.error(f"Fehler bei der Template-Personalisierung: {str(e)}")
            return template
