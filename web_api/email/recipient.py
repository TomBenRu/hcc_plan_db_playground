"""Helper: Privat-Email mit Login-Email als Fallback.

`Person.email` ist die Stammdaten-/Privat-Adresse aus dem Account-Profil
(`/account/profile`). `WebUser.email` ist der Login-Identifier — der
muss eindeutig sein und passt fuer Auth-/Account-Management-Mails (z. B.
Passwort-Reset, Email-Change-Bestaetigung), aber NICHT fuer
Notifications, weil der User die Privat-Email getrennt pflegen kann.

Variante A aus dem Mail-Recipient-Bug-Fix (2026-05-03):
    Person.email bevorzugt, WebUser.email als Fallback. Service-Accounts
    ohne Person-Verknuepfung (web_user.person_id IS NULL) bekommen
    weiterhin an WebUser.email.

Verwendung:

    from web_api.email.recipient import recipient_email_for_web_user

    to = recipient_email_for_web_user(session, dispatcher_user)
    schedule_emails(..., [EmailPayload(to=[to], ...)])

Fuer Bulk-Querys, die ohnehin auf Person joinen, das SQL-Pendant nutzen:

    from sqlalchemy import func
    from web_api.email.recipient import sql_recipient_email
    sa_select(..., sql_recipient_email().label("email"))
"""

from typing import Optional

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import Person
from web_api.models.web_models import WebUser


def recipient_email_for_web_user(session: Session, web_user: WebUser) -> str:
    """Liefert die Privat-Email der zugeordneten Person, sonst die Login-Email.

    Performance: ein zusaetzlicher Single-Column-Select pro Aufruf.
    Akzeptabel fuer Mail-Recipient-Auswahl (1–2 Aufrufe pro Request).
    Bulk-Pfade sollten stattdessen `sql_recipient_email()` direkt im
    SELECT verwenden, um N+1 zu vermeiden.
    """
    if web_user.person_id is None:
        return web_user.email
    person_email: Optional[str] = session.execute(
        sa_select(Person.email).where(Person.id == web_user.person_id)
    ).scalar_one_or_none()
    return person_email or web_user.email


def first_name_for_web_user(session: Session, web_user: WebUser) -> str:
    """Liefert Person.f_name fuer die Anrede in Mails, sonst leeren String.

    Service-Accounts ohne Person-Verknuepfung oder Personen mit leerem
    f_name liefern "" zurueck — die Templates lassen die Anrede dann
    ueber `{% if recipient_first_name %}` weg.
    """
    if web_user.person_id is None:
        return ""
    f_name: Optional[str] = session.execute(
        sa_select(Person.f_name).where(Person.id == web_user.person_id)
    ).scalar_one_or_none()
    return f_name or ""


def sql_recipient_email():
    """SQLAlchemy-Expression fuer COALESCE(Person.email, WebUser.email).

    Erfordert, dass Person und WebUser bereits Bestandteil der Query
    (FROM/JOIN) sind. Liefert die Spalte als Expression — der Aufrufer
    kann mit `.label("...")` ein Alias setzen.
    """
    return func.coalesce(Person.email, WebUser.email)
