"""Email-Domain-Validation für Eingabe-Pfade.

Prueft beim Eintragen einer Email-Adresse, ob die Domain technisch Mail
empfangen kann. Faengt komplett nicht-existierende Domains (NXDOMAIN),
RFC-7505 Null-MX (z.B. ``example.com``) und Syntax-Fehler.

Faengt NICHT (Phase-2-Thema "Bounce-Webhook"):
  - Existierende Domain mit nicht-existierender Mailbox.
  - Squatter-Tippfehler-Domains (``gnail.com``, registriert mit eigenem MX).
  - Spamfilter-Reject, volle Mailboxes.

DNS-Hiccups (Timeout, Netzwerkfehler) werden defensiv akzeptiert — sonst
koennte ein temporaeres DNS-Problem alle Form-Submissions blocken.

Oeffentliche API:
    validate_deliverable_email(email, *, timeout=3) -> str
    EmailDomainInvalid (Exception, Subclass von ValueError)
"""

import logging

from email_validator import EmailNotValidError, validate_email

logger = logging.getLogger(__name__)

_DNS_TIMEOUT_SECONDS = 3
# Heuristische Stichworte fuer "DNS-Server nicht erreichbar" — abgegrenzt von
# "Domain hat eindeutig kein MX". email-validator unterscheidet beides nicht
# in der Exception-Klasse, sondern nur in der Message.
_DNS_HICCUP_HINTS = ("timeout", "no nameservers", "name service")


class EmailDomainInvalid(ValueError):
    """Email ist syntaktisch falsch oder Domain kann keine Mail empfangen.

    Aufrufer fangen das und zeigen ``str(exc)`` im UI als Fehlermeldung
    (oder uebersetzen kontextabhaengig).
    """


def validate_deliverable_email(
    email: str, *, timeout: int = _DNS_TIMEOUT_SECONDS
) -> str:
    """Validiert Email-Syntax + Domain-Zustellbarkeit.

    Returns:
        Normalisierte Email-Adresse (Domain lowercased, IDN-codiert).

    Raises:
        EmailDomainInvalid: bei Syntax-Fehler oder eindeutig
            nicht-zustellbarer Domain. Bei DNS-Hiccups wird die Adresse
            defensiv akzeptiert und nur eine Warnung geloggt.
    """
    if not email or not email.strip():
        raise EmailDomainInvalid("Email-Adresse darf nicht leer sein")

    try:
        info = validate_email(
            email.strip(), check_deliverability=True, timeout=timeout,
        )
        return info.normalized
    except EmailNotValidError as exc:
        msg_lower = str(exc).lower()
        if any(hint in msg_lower for hint in _DNS_HICCUP_HINTS):
            logger.warning(
                "DNS-Hiccup bei Validation '%s' — Adresse defensiv akzeptiert: %s",
                email, exc,
            )
            return email.strip()
        raise EmailDomainInvalid(str(exc)) from exc