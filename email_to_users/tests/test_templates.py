"""
Tests für die E-Mail-Templates.
"""

import unittest
from datetime import date

from email_to_users.templates import PlanNotificationTemplate, AvailabilityRequestTemplate


class TestPlanNotificationTemplate(unittest.TestCase):
    """Testfälle für das Plan-Benachrichtigungstemplate."""
    
    def setUp(self):
        """Setup für die Tests."""
        self.template = PlanNotificationTemplate()
        
    def test_render(self):
        """Test des Renderings des Templates."""
        # Testdaten
        recipient_name = "Max Mustermann"
        plan_name = "Einsatzplan Mai 2025"
        plan_period = "01.05.2025 - 31.05.2025"
        team_name = "Team Nord"
        assignments = [
            {"date": "03.05.2025", "time": "Vormittag", "location": "Klinik A"},
            {"date": "10.05.2025", "time": "Nachmittag", "location": "Klinik B"}
        ]
        notes = "Testnotizen"
        
        # Rendere das Template
        subject, text, html = self.template.render(
            recipient_name=recipient_name,
            plan_name=plan_name,
            plan_period=plan_period,
            team_name=team_name,
            assignments=assignments,
            notes=notes
        )
        
        # Überprüfe den Betreff
        self.assertEqual(subject, f"Neuer Einsatzplan verfügbar: {plan_name}")
        
        # Überprüfe den Textinhalt
        self.assertIn(recipient_name, text)
        self.assertIn(plan_name, text)
        self.assertIn(plan_period, text)
        self.assertIn(team_name, text)
        self.assertIn("03.05.2025", text)
        self.assertIn("Vormittag", text)
        self.assertIn("Klinik A", text)
        self.assertIn("10.05.2025", text)
        self.assertIn("Nachmittag", text)
        self.assertIn("Klinik B", text)
        self.assertIn(notes, text)
        
        # Überprüfe den HTML-Inhalt
        self.assertIn(recipient_name, html)
        self.assertIn(plan_name, html)
        self.assertIn(plan_period, html)
        self.assertIn(team_name, html)
        self.assertIn("03.05.2025", html)
        self.assertIn("Vormittag", html)
        self.assertIn("Klinik A", html)
        self.assertIn("10.05.2025", html)
        self.assertIn("Nachmittag", html)
        self.assertIn("Klinik B", html)
        self.assertIn(notes, html)
        self.assertIn("<html", html)
        self.assertIn("<table", html)
        
    def test_render_without_notes(self):
        """Test des Renderings des Templates ohne Notizen."""
        # Testdaten
        recipient_name = "Max Mustermann"
        plan_name = "Einsatzplan Mai 2025"
        plan_period = "01.05.2025 - 31.05.2025"
        team_name = "Team Nord"
        assignments = [
            {"date": "03.05.2025", "time": "Vormittag", "location": "Klinik A"}
        ]
        
        # Rendere das Template ohne Notizen
        subject, text, html = self.template.render(
            recipient_name=recipient_name,
            plan_name=plan_name,
            plan_period=plan_period,
            team_name=team_name,
            assignments=assignments
        )
        
        # Überprüfe den Betreff
        self.assertEqual(subject, f"Neuer Einsatzplan verfügbar: {plan_name}")
        
        # Überprüfe den Textinhalt
        self.assertIn(recipient_name, text)
        self.assertIn(plan_name, text)
        self.assertNotIn("Hinweise:", text)  # Keine Notizen
        
        # Überprüfe den HTML-Inhalt
        self.assertIn(recipient_name, html)
        self.assertIn(plan_name, html)
        self.assertNotIn("class=\"notes\"", html)  # Keine Notizen


class TestAvailabilityRequestTemplate(unittest.TestCase):
    """Testfälle für das Verfügbarkeitsanfragetemplate."""
    
    def setUp(self):
        """Setup für die Tests."""
        self.template = AvailabilityRequestTemplate()
        
    def test_render(self):
        """Test des Renderings des Templates."""
        # Testdaten
        recipient_name = "Erika Musterfrau"
        plan_period = "Juni 2025"
        team_name = "Team Süd"
        deadline = date(2025, 5, 15)
        period_start = date(2025, 6, 1)
        period_end = date(2025, 6, 30)
        url = "https://example.com/availability/12345"
        notes = "Wichtige Hinweise"
        
        # Rendere das Template
        subject, text, html = self.template.render(
            recipient_name=recipient_name,
            plan_period=plan_period,
            team_name=team_name,
            deadline=deadline,
            period_start=period_start,
            period_end=period_end,
            url=url,
            notes=notes
        )
        
        # Überprüfe den Betreff
        self.assertEqual(subject, f"Verfügbarkeitsabfrage: {plan_period}")
        
        # Überprüfe den Textinhalt
        self.assertIn(recipient_name, text)
        self.assertIn(plan_period, text)
        self.assertIn(team_name, text)
        self.assertIn("15.05.2025", text)  # Deadline
        self.assertIn("01.06.2025", text)  # Startdatum
        self.assertIn("30.06.2025", text)  # Enddatum
        self.assertIn(url, text)
        self.assertIn(notes, text)
        
        # Überprüfe den HTML-Inhalt
        self.assertIn(recipient_name, html)
        self.assertIn(plan_period, html)
        self.assertIn(team_name, html)
        self.assertIn("15.05.2025", html)  # Deadline
        self.assertIn("01.06.2025", html)  # Startdatum
        self.assertIn("30.06.2025", html)  # Enddatum
        self.assertIn(url, html)
        self.assertIn(notes, html)
        self.assertIn("<html", html)
        self.assertIn("class=\"button\"", html)  # Button für URL
        
    def test_render_without_url_and_notes(self):
        """Test des Renderings des Templates ohne URL und Notizen."""
        # Testdaten
        recipient_name = "Erika Musterfrau"
        plan_period = "Juni 2025"
        team_name = "Team Süd"
        deadline = date(2025, 5, 15)
        period_start = date(2025, 6, 1)
        period_end = date(2025, 6, 30)
        
        # Rendere das Template ohne URL und Notizen
        subject, text, html = self.template.render(
            recipient_name=recipient_name,
            plan_period=plan_period,
            team_name=team_name,
            deadline=deadline,
            period_start=period_start,
            period_end=period_end
        )
        
        # Überprüfe den Betreff
        self.assertEqual(subject, f"Verfügbarkeitsabfrage: {plan_period}")
        
        # Überprüfe den Textinhalt
        self.assertIn(recipient_name, text)
        self.assertIn(plan_period, text)
        self.assertNotIn("Hier kannst du deine Verfügbarkeiten eingeben:", text)  # Keine URL
        self.assertNotIn("Hinweise:", text)  # Keine Notizen
        
        # Überprüfe den HTML-Inhalt
        self.assertIn(recipient_name, html)
        self.assertIn(plan_period, html)
        self.assertNotIn("class=\"button\"", html)  # Kein Button für URL
        self.assertNotIn("class=\"notes\"", html)  # Keine Notizen


if __name__ == "__main__":
    unittest.main()
