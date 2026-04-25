"""Account-Service: lädt und schreibt Profildaten (Person + Address) für den eingeloggten WebUser."""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from database.models import Address, Person
from web_api.models.web_models import WebUser


@dataclass
class ProfileData:
    f_name: str
    l_name: str
    email: str
    phone_nr: str | None
    street: str | None
    postal_code: str | None
    city: str | None


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
        street=addr.street if addr else None,
        postal_code=addr.postal_code if addr else None,
        city=addr.city if addr else None,
    )


def update_profile(
    session: Session,
    web_user: WebUser,
    *,
    email: str,
    phone_nr: str | None,
    street: str | None,
    postal_code: str | None,
    city: str | None,
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
        street=addr_after.street if addr_after else None,
        postal_code=addr_after.postal_code if addr_after else None,
        city=addr_after.city if addr_after else None,
    )
