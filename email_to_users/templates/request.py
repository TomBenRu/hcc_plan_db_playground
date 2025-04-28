"""
Template für Verfügbarkeitsanfragen.

Dieses Modul enthält das Template für E-Mails, die Verfügbarkeiten
von Mitarbeitern abfragen.
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, date

from .base import EmailTemplate


class AvailabilityRequestTemplate(EmailTemplate):
    """Template für Verfügbarkeitsanfragen."""
    
    def __init__(self):
        """Initialisiert das Template mit Standard-Betreff."""
        super().__init__(subject_template="Verfügbarkeitsabfrage: {plan_period}")
        
    def render(
        self, 
        recipient_name: str,
        plan_period: str,
        team_name: str,
        deadline: date,
        period_start: date,
        period_end: date,
        url: Optional[str] = None,
        notes: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, str, str]:
        """
        Rendert das Template für eine Verfügbarkeitsanfrage.
        
        Args:
            recipient_name: Name des Empfängers
            plan_period: Bezeichnung des Planungszeitraums (z.B. "Mai 2025")
            team_name: Name des Teams
            deadline: Deadline für die Eingabe der Verfügbarkeiten
            period_start: Startdatum des Planungszeitraums
            period_end: Enddatum des Planungszeitraums
            url: Optionale URL zur Eingabe der Verfügbarkeiten
            notes: Optionale Notizen zur Anfrage
            **kwargs: Weitere Parameter für das Template
            
        Returns:
            Ein Tupel mit (Betreff, Plaintext-Inhalt, HTML-Inhalt)
        """
        # Formatiere Datumsangaben
        deadline_str = deadline.strftime("%d.%m.%Y")
        period_start_str = period_start.strftime("%d.%m.%Y")
        period_end_str = period_end.strftime("%d.%m.%Y")
        
        # Parameter für das Template
        params = {
            'recipient_name': recipient_name,
            'plan_period': plan_period,
            'team_name': team_name,
            'deadline': deadline_str,
            'period_start': period_start_str,
            'period_end': period_end_str,
            'url': url or "",
            'notes': notes or "",
            **kwargs
        }
        
        # Betreff
        subject = self._render_subject(params)
        
        # Plaintext-Inhalt
        text_content = self._generate_text_content(params)
        
        # HTML-Inhalt
        html_content = self._generate_html_content(params)
        
        return subject, text_content, html_content
        
    def _generate_text_content(self, params: Dict[str, Any]) -> str:
        """
        Generiert den Plaintext-Inhalt der E-Mail.
        
        Args:
            params: Parameter für das Template
            
        Returns:
            Der generierte Plaintext-Inhalt
        """
        text_template = """Hallo {recipient_name},

bitte gib deine Verfügbarkeiten für den Zeitraum {period_start} bis {period_end} ({plan_period}) an.

Team: {team_name}

Bitte trage deine Verfügbarkeiten bis spätestens {deadline} ein.
{url_section}
{notes_section}

Bei Fragen wende dich bitte an deinen Team-Dispatcher.

Mit freundlichen Grüßen
Das HCC-Plan-Team
"""
        
        # Füge URL hinzu, falls vorhanden
        url_section = ""
        if params['url']:
            url_section = f"Hier kannst du deine Verfügbarkeiten eingeben: {params['url']}\n"
            
        # Füge Notizen hinzu, falls vorhanden
        notes_section = ""
        if params['notes']:
            notes_section = f"Hinweise:\n{params['notes']}\n"
            
        params_with_sections = {
            **params,
            'url_section': url_section,
            'notes_section': notes_section
        }
        
        return self._format_template(text_template, params_with_sections)
        
    def _generate_html_content(self, params: Dict[str, Any]) -> str:
        """
        Generiert den HTML-Inhalt der E-Mail.
        
        Args:
            params: Parameter für das Template
            
        Returns:
            Der generierte HTML-Inhalt
        """
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            border: 1px solid #ddd;
            border-radius: 5px;
            overflow: hidden;
        }
        .header {
            background-color: #4a86e8;
            color: white;
            padding: 15px;
            text-align: center;
        }
        .content {
            padding: 20px;
        }
        .footer {
            background-color: #f5f5f5;
            padding: 15px;
            text-align: center;
            font-size: 0.8em;
            color: #777;
        }
        .button {
            display: inline-block;
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            text-align: center;
            text-decoration: none;
            font-size: 16px;
            margin: 15px 0;
            border-radius: 4px;
        }
        .highlight {
            font-weight: bold;
            color: #d9534f;
        }
        .notes {
            background-color: #fff8dc;
            padding: 10px;
            border-left: 3px solid #ffeb3b;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Verfügbarkeitsabfrage</h2>
        </div>
        <div class="content">
            <p>Hallo {recipient_name},</p>
            
            <p>bitte gib deine Verfügbarkeiten für den Zeitraum <strong>{period_start} bis {period_end}</strong> (<strong>{plan_period}</strong>) an.</p>
            
            <p><strong>Team:</strong> {team_name}</p>
            
            <p>Bitte trage deine Verfügbarkeiten bis spätestens <span class="highlight">{deadline}</span> ein.</p>
            
            {url_html}
            
            {notes_html}
            
            <p>Bei Fragen wende dich bitte an deinen Team-Dispatcher.</p>
        </div>
        <div class="footer">
            <p>Mit freundlichen Grüßen<br>Das HCC-Plan-Team</p>
        </div>
    </div>
</body>
</html>
"""
        
        # Füge URL-Button hinzu, falls vorhanden
        url_html = ""
        if params['url']:
            url_html = f"""
            <p>
                <a href="{params['url']}" class="button">Verfügbarkeiten jetzt eingeben</a>
            </p>"""
            
        # Füge Notizen hinzu, falls vorhanden
        notes_html = ""
        if params['notes']:
            notes_html = f"""
            <div class="notes">
                <h3>Hinweise:</h3>
                <p>{params['notes']}</p>
            </div>"""
            
        params_with_html = {
            **params,
            'url_html': url_html,
            'notes_html': notes_html
        }
        
        return self._format_template(html_template, params_with_html)
