"""Account-Service: lädt und schreibt Profildaten (Person + Address) für den eingeloggten WebUser."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database.enums import Gender
from database.models import Address, Person
from web_api.auth.password_policy import validate_password
from web_api.auth.service import hash_password, verify_password
from web_api.models.web_models import WebUser


@dataclass
class ProfileData:
    f_name: str
    l_name: str
    email: str
    phone_nr: str | None
    gender: Gender | None
    street: str | None
    postal_code: str | None
    city: str | None
    share_phone_in_emergency: bool = True


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_profile(session: Session, web_user: WebUser) -> ProfileData | None:
    """Liefert die Person+Address-Daten oder None, wenn der WebUser keine Person hat."""
    if web_user.person_id is None:
        return None

    person = session.exec(
        select(Person)
        .where(Person.id == web_user.person_id)
        .options(selectinload(Person.address))  # type: ignore[arg-type]
    ).first()
    if person is None:
        return None

    addr = person.address
    return ProfileData(
        f_name=person.f_name,
        l_name=person.l_name,
        email=person.email,
        phone_nr=person.phone_nr,
        gender=person.gender,
        street=addr.street if addr else None,
        postal_code=addr.postal_code if addr else None,
        city=addr.city if addr else None,
        share_phone_in_emergency=person.share_phone_in_emergency,
    )


def update_profile(
    session: Session,
    web_user: WebUser,
    *,
    email: str,
    phone_nr: str | None,
    gender: Gender | None,
    street: str | None,
    postal_code: str | None,
    city: str | None,
    share_phone_in_emergency: bool = True,
) -> ProfileData:
    """Updated Email/Telefon auf Person und Adresse via Copy-on-Write.

    Copy-on-Write: wenn die aktuelle Adresse von mehreren Persons benutzt wird,
    bekommt diese Person eine eigene Address-Kopie — sonst würde der Edit
    bei den anderen Persons mit-erscheinen.
    """
    if web_user.person_id is None:
        raise ValueError("Kein Personenprofil mit diesem Konto verknüpft.")

    person = session.exec(
        select(Person)
        .where(Person.id == web_user.person_id)
        .options(selectinload(Person.address).selectinload(Address.persons))  # type: ignore[arg-type]
    ).first()
    if person is None:
        raise ValueError("Personenprofil nicht gefunden.")

    person.email = email.strip()
    person.phone_nr = (phone_nr or "").strip() or None
    person.gender = gender
    person.share_phone_in_emergency = share_phone_in_emergency

    has_addr_input = any(v and v.strip() for v in (street, postal_code, city))
    addr = person.address

    if has_addr_input:
        if addr is None:
            addr = Address(project_id=person.project_id)
            session.add(addr)
            session.flush()
            person.address_id = addr.id
        elif len(addr.persons) > 1:
            # Copy-on-Write: andere Persons hängen an dieser Adresse → eigene anlegen
            new_addr = Address(
                project_id=addr.project_id,
                name=addr.name,
                street=addr.street,
                postal_code=addr.postal_code,
                city=addr.city,
            )
            session.add(new_addr)
            session.flush()
            person.address_id = new_addr.id
            addr = new_addr

        addr.street = (street or "").strip() or None
        addr.postal_code = (postal_code or "").strip() or None
        addr.city = (city or "").strip() or None
        addr.last_modified = _utcnow()

    person.last_modified = _utcnow()
    session.add(person)
    session.flush()
    session.refresh(person)

    addr_after = person.address
    return ProfileData(
        f_name=person.f_name,
        l_name=person.l_name,
        email=person.email,
        phone_nr=person.phone_nr,
        gender=person.gender,
        street=addr_after.street if addr_after else None,
        postal_code=addr_after.postal_code if addr_after else None,
        city=addr_after.city if addr_after else None,
        share_phone_in_emergency=person.share_phone_in_emergency,
    )


def change_password(
    session: Session,
    web_user: WebUser,
    *,
    current_password: str,
    new_password: str,
    new_password_confirm: str,
) -> list[str]:
    """Validiert + setzt ein neues Passwort. Gibt Fehlerliste zurück (leer = OK).

    Bei Erfolg wird password_changed_at aktualisiert — das macht alle vorher
    ausgestellten Refresh-Tokens via iat-Check ungültig (Phase 1).
    """
    errors: list[str] = []

    if not verify_password(current_password, web_user.hashed_password):
        errors.append("Das aktuelle Passwort ist falsch.")

    if new_password != new_password_confirm:
        errors.append("Die beiden neuen Passwort-Eingaben stimmen nicht überein.")

    errors.extend(validate_password(new_password, web_user.email))

    if not errors and new_password == current_password:
        errors.append("Das neue Passwort darf nicht mit dem alten übereinstimmen.")

    if errors:
        return errors

    now = datetime.now(timezone.utc)
    web_user.hashed_password = hash_password(new_password)
    web_user.password_changed_at = now
    web_user.last_modified = now
    session.add(web_user)
    session.flush()
    return []
