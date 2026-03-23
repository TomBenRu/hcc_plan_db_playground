"""App-weite Exception-Klassen."""


class LoginRequired(Exception):
    """Wird geworfen wenn eine geschützte Route ohne gültigen Token aufgerufen wird.

    main.py registriert einen Handler, der zur Login-Seite mit ?next= weiterleitet.
    """

    def __init__(self, next_url: str = "/") -> None:
        self.next_url = next_url
