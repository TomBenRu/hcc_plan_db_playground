"""Symmetrische Verschlüsselung für SMTP-Geheimnisse.

Master-Key liegt in der Env-Var EMAIL_ENCRYPTION_KEY (44 Zeichen, URL-safe Base64,
generiert via `Fernet.generate_key()`). Alle Passwort-Werte in der DB sind
Fernet-Token (AES-128-CBC + HMAC-SHA256 + Timestamp).

Rotation des Master-Keys ist heute nicht implementiert — bei Bedarf ist
`MultiFernet` der Migrationspfad: alte und neue Keys parallel bereitstellen,
re-encrypt im Hintergrund, alten Key entfernen.
"""

import os

from cryptography.fernet import Fernet, InvalidToken


class EmailEncryptionKeyMissingError(RuntimeError):
    """EMAIL_ENCRYPTION_KEY ist nicht gesetzt — Versand ist nicht möglich."""


class EmailDecryptionError(RuntimeError):
    """Ciphertext konnte nicht entschlüsselt werden — Key passt nicht zum Token."""


def _load_fernet() -> Fernet:
    key = os.environ.get("EMAIL_ENCRYPTION_KEY", "").strip()
    if not key:
        raise EmailEncryptionKeyMissingError(
            "EMAIL_ENCRYPTION_KEY ist nicht gesetzt. Generiere einen Key mit "
            '`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` '
            "und trage ihn in die .env (lokal) bzw. ins Render-Dashboard (Production) ein."
        )
    return Fernet(key.encode("ascii"))


def encrypt(plaintext: str) -> str:
    """Verschlüsselt einen Klartext-String. Leere Strings werden 1:1 durchgereicht."""
    if plaintext == "":
        return ""
    return _load_fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    """Entschlüsselt einen Fernet-Token. Leere Strings werden 1:1 durchgereicht."""
    if ciphertext == "":
        return ""
    try:
        return _load_fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise EmailDecryptionError(
            "SMTP-Passwort konnte nicht entschlüsselt werden. Wurde der "
            "EMAIL_ENCRYPTION_KEY rotiert, ohne die DB-Werte neu zu verschlüsseln?"
        ) from exc