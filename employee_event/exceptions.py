"""
Custom Exception-Klassen für das Employee Event Management System.
"""


class EmployeeEventError(Exception):
    """Basis-Exception für alle Employee Event-bezogenen Fehler."""
    
    def __init__(self, message: str, details: str = None):
        self.message = message
        self.details = details
        super().__init__(self.message)
    
    def __str__(self):
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class EmployeeEventNotFoundError(EmployeeEventError):
    """Exception für nicht gefundene Employee Events."""
    
    def __init__(self, event_id: str = None, event_title: str = None):
        if event_id:
            message = f"Employee Event mit ID '{event_id}' nicht gefunden"
        elif event_title:
            message = f"Employee Event mit Titel '{event_title}' nicht gefunden"
        else:
            message = "Employee Event nicht gefunden"
        super().__init__(message)


class EmployeeEventValidationError(EmployeeEventError):
    """Exception für Validierungsfehler bei Employee Events."""
    
    def __init__(self, field: str, value: str, reason: str):
        message = f"Validierungsfehler im Feld '{field}'"
        details = f"Wert: '{value}', Grund: {reason}"
        super().__init__(message, details)


class EmployeeEventCategoryError(EmployeeEventError):
    """Exception für Employee Event Category-bezogene Fehler."""
    
    def __init__(self, category_name: str = None, message: str = None):
        if not message:
            if category_name:
                message = f"Fehler bei Employee Event Category '{category_name}'"
            else:
                message = "Fehler bei Employee Event Category"
        super().__init__(message)


class EmployeeEventParticipantError(EmployeeEventError):
    """Exception für Teilnehmer-bezogene Fehler."""
    
    def __init__(self, participant_name: str = None, event_title: str = None, message: str = None):
        if not message:
            if participant_name and event_title:
                message = f"Teilnehmer-Fehler: '{participant_name}' bei Event '{event_title}'"
            elif participant_name:
                message = f"Teilnehmer-Fehler: '{participant_name}'"
            else:
                message = "Teilnehmer-Fehler"
        super().__init__(message)


class EmployeeEventTeamError(EmployeeEventError):
    """Exception für Team-bezogene Fehler bei Employee Events."""
    
    def __init__(self, team_name: str = None, event_title: str = None, message: str = None):
        if not message:
            if team_name and event_title:
                message = f"Team-Fehler: '{team_name}' bei Event '{event_title}'"
            elif team_name:
                message = f"Team-Fehler: '{team_name}'"
            else:
                message = "Team-Fehler bei Employee Event"
        super().__init__(message)


class EmployeeEventDateError(EmployeeEventError):
    """Exception für Datum-bezogene Fehler bei Employee Events."""
    
    def __init__(self, date_info: str, reason: str = None):
        message = f"Datum-Fehler: {date_info}"
        super().__init__(message, reason)
