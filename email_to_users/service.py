"""
Service-Modul für E-Mail-Funktionalitäten.

Dieses Modul bietet High-Level-Funktionen für den E-Mail-Versand an Mitarbeiter,
Integration mit dem Datenmodell und kontextbezogene E-Mail-Aktionen.
"""

import logging
from typing import List, Dict, Any, Optional, Union
from datetime import date, datetime
from pathlib import Path
import os
from uuid import UUID

from pony.orm import db_session, select

from database.models import Person, Team, Plan, PlanPeriod, Project

try:
    from .sender import EmailSender
    from .templates import PlanNotificationTemplate, AvailabilityRequestTemplate
    from .utils import extract_emails_from_persons
except ImportError:
    from sender import EmailSender
    from templates import PlanNotificationTemplate, AvailabilityRequestTemplate
    from utils import extract_emails_from_persons

logger = logging.getLogger(__name__)


class EmailService:
    """Service-Klasse für E-Mail-Funktionalitäten."""
    
    def __init__(self):
        """Initialisiert den EmailService mit einem EmailSender."""
        self.sender = EmailSender()
        self.plan_template = PlanNotificationTemplate()
        self.request_template = AvailabilityRequestTemplate()
        
    @db_session
    def send_plan_notification(
        self,
        plan_id: str,
        recipient_ids: Optional[List[str]] = None,
        include_attachments: bool = True
    ) -> Dict[str, int]:
        """
        Sendet Benachrichtigungen über einen neuen oder aktualisierten Einsatzplan.
        
        Args:
            plan_id: ID des Plans
            recipient_ids: Optional, Liste von Empfänger-IDs. Wenn nicht angegeben,
                          werden alle in dem Plan eingetragenen Mitarbeiter benachrichtigt
            include_attachments: Ob der Plan als Anhang mitgeschickt werden soll
            
        Returns:
            Dictionary mit Statistiken: Anzahl erfolgreicher und fehlgeschlagener E-Mails
        """
        try:
            # Hole den Plan aus der Datenbank
            plan = Plan[plan_id]
            plan_period = plan.plan_period
            team = plan_period.team
            
            # Bestimme die Empfänger
            if recipient_ids:
                recipients = [Person[id] for id in recipient_ids if Person.exists(id=id)]
            else:
                # Sammle alle Personen, die in dem Plan eingetragen sind
                recipients = []
                for appointment in plan.appointments:
                    for avail_day in appointment.avail_days:
                        if avail_day.actor_plan_period.person not in recipients:
                            recipients.append(avail_day.actor_plan_period.person)
            
            if not recipients:
                logger.warning(f"Keine Empfänger für Plan {plan.name} gefunden")
                return {'success': 0, 'failed': 0}
                
            # Formatiere den Zeitraum
            period_str = f"{plan_period.start.strftime('%d.%m.%Y')} - {plan_period.end.strftime('%d.%m.%Y')}"
            
            # Bereite Anhänge vor, falls gewünscht
            attachments = None
            if include_attachments:
                # TODO: Implementiere Generierung von Excel/PDF-Anhängen
                pass
            
            # Sende E-Mails an alle Empfänger
            stats = {'success': 0, 'failed': 0}
            for person in recipients:
                # Sammle die Einsätze dieser Person
                assignments = []
                for appointment in plan.appointments:
                    for avail_day in appointment.avail_days:
                        if avail_day.actor_plan_period.person.id == person.id:
                            event = appointment.event
                            location = event.location_plan_period.location_of_work
                            
                            assignments.append({
                                'date': event.date.strftime('%d.%m.%Y'),
                                'time': event.time_of_day.name,
                                'location': location.name
                            })
                
                if not assignments:
                    logger.debug(f"Keine Einsätze für {person.full_name} in Plan {plan.name} gefunden")
                    continue
                
                # Rendere das Template
                subject, text, html = self.plan_template.render(
                    recipient_name=person.full_name,
                    plan_name=plan.name,
                    plan_period=period_str,
                    team_name=team.name,
                    assignments=assignments,
                    notes=plan.notes
                )
                
                # Sende die E-Mail
                success = self.sender.send_email(
                    recipients=[{'email': person.email, 'name': person.full_name}],
                    subject=subject,
                    text_content=text,
                    html_content=html,
                    attachments=attachments
                )
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Fehler beim Senden der Plan-Benachrichtigung: {str(e)}")
            return {'success': 0, 'failed': 0}
    
    @db_session
    def send_availability_request(
        self,
        plan_period_id: str,
        recipient_ids: Optional[List[str]] = None,
        url_base: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Sendet Verfügbarkeitsanfragen an Mitarbeiter für einen Planungszeitraum.
        
        Args:
            plan_period_id: ID des Planungszeitraums
            recipient_ids: Optional, Liste von Empfänger-IDs. Wenn nicht angegeben,
                          werden alle Mitarbeiter des Teams benachrichtigt
            url_base: Basis-URL für die Verfügbarkeitseingabe, z.B. "http://example.com/availability/"
            notes: Optionale Notizen zur Anfrage
            
        Returns:
            Dictionary mit Statistiken: Anzahl erfolgreicher und fehlgeschlagener E-Mails
        """
        try:
            # Hole den Planungszeitraum aus der Datenbank
            plan_period = PlanPeriod[plan_period_id]
            team = plan_period.team
            
            # Bestimme die Empfänger
            if recipient_ids:
                recipients = [Person[id] for id in recipient_ids if Person.exists(id=id)]
            else:
                # Sammle alle Personen des Teams
                recipients = []
                for taa in team.team_actor_assigns:
                    if (not taa.end or taa.end >= plan_period.start) and taa.start <= plan_period.end:
                        if taa.person not in recipients:
                            recipients.append(taa.person)
            
            if not recipients:
                logger.warning(f"Keine Empfänger für Planungszeitraum {plan_period.id} gefunden")
                return {'success': 0, 'failed': 0}
                
            # Formatiere den Zeitraum für den Betreff
            month_names = [
                "Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"
            ]
            start_month = plan_period.start.month - 1  # 0-based index
            start_year = plan_period.start.year
            period_name = f"{month_names[start_month]} {start_year}"
            
            # Sende E-Mails an alle Empfänger
            stats = {'success': 0, 'failed': 0}
            for person in recipients:
                # Erstelle URL für die Verfügbarkeitseingabe, falls eine Basis-URL angegeben wurde
                url = None
                if url_base:
                    url = f"{url_base.rstrip('/')}/{plan_period.id}/{person.id}"
                
                # Rendere das Template
                subject, text, html = self.request_template.render(
                    recipient_name=person.full_name,
                    plan_period=period_name,
                    team_name=team.name,
                    deadline=plan_period.deadline,
                    period_start=plan_period.start,
                    period_end=plan_period.end,
                    url=url,
                    notes=notes or plan_period.notes_for_employees
                )
                
                # Sende die E-Mail
                success = self.sender.send_email(
                    recipients=[{'email': person.email, 'name': person.full_name}],
                    subject=subject,
                    text_content=text,
                    html_content=html
                )
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Fehler beim Senden der Verfügbarkeitsanfrage: {str(e)}")
            return {'success': 0, 'failed': 0}
    
    @db_session
    def send_custom_email(
        self,
        subject: str,
        text_content: str,
        html_content: Optional[str] = None,
        recipient_ids: Optional[List[UUID]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, int]:
        """
        Sendet eine benutzerdefinierte E-Mail an ausgewählte Mitarbeiter.
        
        Args:
            subject: Betreff der E-Mail
            text_content: Plaintext-Inhalt der E-Mail
            html_content: HTML-Inhalt der E-Mail (optional)
            recipient_ids: Liste von Empfänger-IDs (optional)
            team_id: ID eines Teams, dessen Mitglieder benachrichtigt werden sollen (optional)
            project_id: ID eines Projekts, dessen Mitglieder benachrichtigt werden sollen (optional)
            attachments: Liste von Anhängen als Dictionaries (optional)
            
        Returns:
            Dictionary mit Statistiken: Anzahl erfolgreicher und fehlgeschlagener E-Mails
            
        Note:
            Mindestens eines der Argumente recipient_ids, team_id oder project_id muss angegeben werden.
        """
        try:
            # Bestimme die Empfänger
            recipients = []

            if recipient_ids:
                for id in recipient_ids:
                    if Person.exists(id=id):
                        person = Person[id]
                        if person not in recipients:
                            recipients.append(person)
            
            if not recipients:
                logger.warning("Keine Empfänger für benutzerdefinierte E-Mail gefunden")
                return {'success': 0, 'failed': 0}
            
            # Extrahiere E-Mail-Adressen aus Personen
            recipient_dicts = extract_emails_from_persons(recipients)
            
            # Sende die E-Mail an alle Empfänger
            stats = self.sender.send_bulk_email(
                recipients=recipient_dicts,
                subject=subject,
                text_template=text_content,
                html_template=html_content,
                attachments=attachments,
                delay=0.2  # Kurze Verzögerung zwischen E-Mails
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"Fehler beim Senden der benutzerdefinierten E-Mail: {str(e)}")
            return {'success': 0, 'failed': 0}


# Globale Service-Instanz
email_service = EmailService()
