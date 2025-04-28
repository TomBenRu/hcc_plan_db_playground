"""
Template für Einsatzplan-Benachrichtigungen.

Dieses Modul enthält das Template für E-Mails, die Mitarbeiter über neue
oder aktualisierte Einsatzpläne informieren.
"""

from typing import Dict, Any, Tuple, Optional, List

from .base import EmailTemplate


class PlanNotificationTemplate(EmailTemplate):
    """Template für Einsatzplan-Benachrichtigungen."""
    
    def __init__(self):
        """Initialisiert das Template mit Standard-Betreff."""
        super().__init__(subject_template="Neuer Einsatzplan verfügbar: {plan_name}")
        
    def render(
        self, 
        recipient_name: str,
        plan_name: str,
        plan_period: str,
        team_name: str,
        assignments: List[Dict[str, Any]],
        notes: Optional[str] = None,
        **kwargs
    ) -> Tuple[str, str, str]:
        """
        Rendert das Template für eine Einsatzplan-Benachrichtigung.
        
        Args:
            recipient_name: Name des Empfängers
            plan_name: Name des Einsatzplans
            plan_period: Zeitraum des Plans (z.B. "01.05.2025 - 31.05.2025")
            team_name: Name des Teams
            assignments: Liste der Einsätze als Dictionaries mit 'date', 'time', 'location' Keys
            notes: Optionale Notizen zum Plan
            **kwargs: Weitere Parameter für das Template
            
        Returns:
            Ein Tupel mit (Betreff, Plaintext-Inhalt, HTML-Inhalt)
        """
        # Parameter für das Template
        params = {
            'recipient_name': recipient_name,
            'plan_name': plan_name,
            'plan_period': plan_period,
            'team_name': team_name,
            'notes': notes or "",
            **kwargs
        }
        
        # Betreff
        subject = self._render_subject(params)
        
        # Plaintext-Inhalt
        text_content = self._generate_text_content(params, assignments)
        
        # HTML-Inhalt
        html_content = self._generate_html_content(params, assignments)
        
        return subject, text_content, html_content
        
    def _generate_text_content(
        self, 
        params: Dict[str, Any],
        assignments: List[Dict[str, Any]]
    ) -> str:
        """
        Generiert den Plaintext-Inhalt der E-Mail.
        
        Args:
            params: Parameter für das Template
            assignments: Liste der Einsätze
            
        Returns:
            Der generierte Plaintext-Inhalt
        """
        text_template = """Hallo {recipient_name},

ein neuer Einsatzplan "{plan_name}" für den Zeitraum {plan_period} ist verfügbar.

Team: {team_name}

Deine geplanten Einsätze:
{assignments}

{notes_section}

Bei Fragen wende dich bitte an deinen Team-Dispatcher.

Mit freundlichen Grüßen
Das HCC-Plan-Team
"""
        
        # Formatiere die Einsätze
        assignments_text = ""
        for assignment in assignments:
            assignments_text += f"- {assignment['date']}, {assignment['time']}: {assignment['location']}\n"
            
        # Füge Notizen hinzu, falls vorhanden
        notes_section = ""
        if params['notes']:
            notes_section = f"Hinweise:\n{params['notes']}\n"
            
        params_with_assignments = {
            **params,
            'assignments': assignments_text,
            'notes_section': notes_section
        }
        
        return self._format_template(text_template, params_with_assignments)
        
    def _generate_html_content(
        self, 
        params: Dict[str, Any],
        assignments: List[Dict[str, Any]]
    ) -> str:
        """
        Generiert den HTML-Inhalt der E-Mail.
        
        Args:
            params: Parameter für das Template
            assignments: Liste der Einsätze
            
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
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        th, td {
            padding: 10px;
            border: 1px solid #ddd;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
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
            <h2>Neuer Einsatzplan</h2>
        </div>
        <div class="content">
            <p>Hallo {recipient_name},</p>
            
            <p>ein neuer Einsatzplan <strong>"{plan_name}"</strong> für den Zeitraum <strong>{plan_period}</strong> ist verfügbar.</p>
            
            <p><strong>Team:</strong> {team_name}</p>
            
            <h3>Deine geplanten Einsätze:</h3>
            
            <table>
                <tr>
                    <th>Datum</th>
                    <th>Uhrzeit</th>
                    <th>Einsatzort</th>
                </tr>
                {assignment_rows}
            </table>
            
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
        
        # Formatiere die Einsätze als HTML-Tabellenzeilen
        assignment_rows = ""
        for assignment in assignments:
            assignment_rows += f"""
                <tr>
                    <td>{assignment['date']}</td>
                    <td>{assignment['time']}</td>
                    <td>{assignment['location']}</td>
                </tr>"""
            
        # Füge Notizen hinzu, falls vorhanden
        notes_html = ""
        if params['notes']:
            notes_html = f"""
            <div class="notes">
                <h3>Hinweise:</h3>
                <p>{params['notes']}</p>
            </div>"""
            
        params_with_assignments = {
            **params,
            'assignment_rows': assignment_rows,
            'notes_html': notes_html
        }
        
        return self._format_template(html_template, params_with_assignments)
