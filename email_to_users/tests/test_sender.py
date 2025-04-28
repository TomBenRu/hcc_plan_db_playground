"""
Tests für die EmailSender-Klasse.
"""

import unittest
from unittest.mock import patch, MagicMock
from io import StringIO
import sys

from email_to_users.config import EmailConfig
from email_to_users.sender import EmailSender


class TestEmailSender(unittest.TestCase):
    """Testfälle für die EmailSender-Klasse."""
    
    def setUp(self):
        """Setup für die Tests."""
        # Erstelle eine Testkonfiguration mit Debug-Modus
        self.config = EmailConfig(
            smtp_host="test.example.com",
            smtp_port=587,
            smtp_username="test",
            smtp_password="password",
            use_tls=True,
            debug_mode=True,
            default_sender_email="sender@example.com",
            default_sender_name="Test Sender"
        )
        
        self.sender = EmailSender(config=self.config)
        
    def test_format_recipients_input(self):
        """Test der Funktion zum Formatieren der Empfängereingabe."""
        # Test mit Liste von Strings
        recipients = ["test1@example.com", "invalid@", "test2@example.com"]
        expected = ["test1@example.com", "test2@example.com"]
        self.assertEqual(self.sender._format_recipients_input(recipients), expected)
        
        # Test mit Liste von Dictionaries
        recipients = [
            {"email": "test1@example.com", "name": "Test User 1"},
            {"email": "invalid@", "name": "Invalid User"},
            {"email": "test2@example.com", "name": "Test User 2"}
        ]
        expected = ["Test User 1 <test1@example.com>", "Test User 2 <test2@example.com>"]
        self.assertEqual(self.sender._format_recipients_input(recipients), expected)
        
        # Test mit leerer Liste
        self.assertEqual(self.sender._format_recipients_input([]), [])
        
        # Test mit None
        self.assertEqual(self.sender._format_recipients_input(None), [])
    
    @patch('email_to_users.sender.smtplib.SMTP')
    def test_create_smtp_connection(self, mock_smtp):
        """Test der SMTP-Verbindungserstellung."""
        # Teste TLS-Verbindung
        config = EmailConfig(
            smtp_host="test.example.com",
            smtp_port=587,
            smtp_username="test",
            smtp_password="password",
            use_tls=True,
            use_ssl=False
        )
        sender = EmailSender(config=config)
        
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value = mock_smtp_instance
        
        sender._create_smtp_connection()
        
        mock_smtp.assert_called_once_with(
            "test.example.com", 587, timeout=30
        )
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("test", "password")
        
    @patch('email_to_users.sender.smtplib.SMTP_SSL')
    def test_create_smtp_connection_ssl(self, mock_smtp_ssl):
        """Test der SMTP-Verbindungserstellung mit SSL."""
        # Teste SSL-Verbindung
        config = EmailConfig(
            smtp_host="test.example.com",
            smtp_port=465,
            smtp_username="test",
            smtp_password="password",
            use_tls=False,
            use_ssl=True
        )
        sender = EmailSender(config=config)
        
        mock_smtp_instance = MagicMock()
        mock_smtp_ssl.return_value = mock_smtp_instance
        
        sender._create_smtp_connection()
        
        mock_smtp_ssl.assert_called_once_with(
            "test.example.com", 465, timeout=30
        )
        mock_smtp_instance.login.assert_called_once_with("test", "password")
    
    def test_send_debug_output(self):
        """Test der Debug-Ausgabe beim E-Mail-Versand."""
        # Fange die Ausgabe ab
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        
        message = MagicMock()
        message.__getitem__ = lambda self, key: {
            'From': 'Test Sender <sender@example.com>',
            'To': 'recipient@example.com',
            'Subject': 'Test Subject',
            'Date': 'Mon, 28 Apr 2025 12:00:00 +0200'
        }.get(key)
        
        message.walk.return_value = [MagicMock(get_content_type=lambda: 'text/plain', 
                                               get_payload=lambda decode: b'Test content')]
        
        self.sender._send_debug(
            message=message,
            recipients=["recipient@example.com"],
            cc=["cc@example.com"],
            bcc=["bcc@example.com"]
        )
        
        sys.stdout = old_stdout
        output = mystdout.getvalue()
        
        # Überprüfe, ob die wichtigsten Informationen in der Ausgabe enthalten sind
        self.assertIn("[DEBUG EMAIL]", output)
        self.assertIn("Von: Test Sender <sender@example.com>", output)
        self.assertIn("An: recipient@example.com", output)
        self.assertIn("CC: cc@example.com", output)
        self.assertIn("BCC: bcc@example.com", output)
        self.assertIn("Betreff: Test Subject", output)


if __name__ == "__main__":
    unittest.main()
