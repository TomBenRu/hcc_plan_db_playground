"""
Tests für Hilfsfunktionen im E-Mail-Modul.
"""

import unittest
from email.mime.multipart import MIMEMultipart

from email_to_users.utils import validate_email, format_recipients, extract_emails_from_persons


class TestUtils(unittest.TestCase):
    """Testfälle für die Utility-Funktionen."""
    
    def test_validate_email(self):
        """Test der E-Mail-Validierungsfunktion."""
        # Gültige E-Mail-Adressen
        self.assertTrue(validate_email("test@example.com"))
        self.assertTrue(validate_email("user.name+tag@example.co.uk"))
        
        # Ungültige E-Mail-Adressen
        self.assertFalse(validate_email("not_an_email"))
        self.assertFalse(validate_email("missing@tld"))
        self.assertFalse(validate_email("@missing_username.com"))
        self.assertFalse(validate_email(""))
        
    def test_format_recipients(self):
        """Test der Empfängerformatierungsfunktion."""
        recipients = [
            {"email": "test1@example.com", "name": "Test User 1"},
            {"email": "test2@example.com", "name": ""},
            {"email": "invalid@", "name": "Invalid User"},
            {"email": "test3@example.com"}
        ]
        
        expected = [
            "Test User 1 <test1@example.com>",
            "test2@example.com",
            "test3@example.com"
        ]
        
        self.assertEqual(format_recipients(recipients), expected)
        
    def test_extract_emails_from_persons(self):
        """Test der Funktion zum Extrahieren von E-Mails aus Personen-Objekten."""
        # Erstelle Mock-Personen-Objekte
        class MockPerson:
            def __init__(self, email, f_name, l_name):
                self.email = email
                self.f_name = f_name
                self.l_name = l_name
                
            @property
            def full_name(self):
                return f"{self.f_name} {self.l_name}"
                
        persons = [
            MockPerson("valid@example.com", "John", "Doe"),
            MockPerson("", "Jane", "Smith"),  # Leere E-Mail
            MockPerson("invalid@", "Invalid", "User"),  # Ungültige E-Mail
            MockPerson("test@example.com", "Test", "User")
        ]
        
        expected = [
            {"email": "valid@example.com", "name": "John Doe"},
            {"email": "test@example.com", "name": "Test User"}
        ]
        
        self.assertEqual(extract_emails_from_persons(persons), expected)


if __name__ == "__main__":
    unittest.main()
