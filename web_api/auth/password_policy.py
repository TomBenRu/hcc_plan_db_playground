"""Passwort-Policy: Längen- und Inhalts-Prüfung für neue Passwörter.

Defaults nach OWASP: Länge schlägt Komplexität. Keine Pflicht-Sonderzeichen
oder Groß-/Kleinbuchstaben-Vorgaben. Oberes Limit orientiert sich am
bcrypt-72-Byte-Cap (pragmatisch auf 72 Zeichen festgelegt — wer längere
Passphrasen will, soll sie vorher hashen).
"""

MIN_LENGTH = 12
MAX_LENGTH = 72


def validate_password(password: str, email: str) -> list[str]:
    """Liefert eine Liste von Fehlermeldungen; leere Liste = OK."""
    errors: list[str] = []
    if len(password) < MIN_LENGTH:
        errors.append(
            f"Das Passwort muss mindestens {MIN_LENGTH} Zeichen lang sein."
        )
    if len(password) > MAX_LENGTH:
        errors.append(
            f"Das Passwort darf höchstens {MAX_LENGTH} Zeichen lang sein."
        )
    if password.strip().lower() == email.strip().lower():
        errors.append("Das Passwort darf nicht deiner E-Mail-Adresse entsprechen.")
    return errors