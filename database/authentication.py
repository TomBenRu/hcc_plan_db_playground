"""
Password Authentication Module

Verwendet direkt bcrypt (ohne passlib) für Password-Hashing.
Kompatibel mit bestehenden passlib-bcrypt Hashes.
"""

import bcrypt


def hash_psw(password: str) -> str:
    """
    Hasht ein Passwort mit bcrypt.
    
    Args:
        password: Das zu hashende Passwort
        
    Returns:
        Der bcrypt-Hash des Passworts (als String)
        
    Raises:
        ValueError: Wenn das Passwort länger als 72 Bytes ist
    """
    # Sicherheitsprüfung: bcrypt limitiert auf 72 Bytes
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        raise ValueError("Passwort darf maximal 72 Bytes lang sein")
    
    # bcrypt.hashpw benötigt bytes und gibt bytes zurück
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Als String zurückgeben (für DB-Speicherung)
    return hashed.decode('utf-8')


def verify(plain_password: str, hashed_password: str) -> bool:
    """
    Verifiziert ein Passwort gegen einen Hash.
    
    Args:
        plain_password: Das Klartext-Passwort
        hashed_password: Der bcrypt-Hash zum Vergleich
        
    Returns:
        True wenn das Passwort korrekt ist, sonst False
    """
    try:
        # Beide Parameter müssen bytes sein
        password_bytes = plain_password.encode('utf-8')
        hash_bytes = hashed_password.encode('utf-8')
        
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        # Bei ungültigen Hashes oder anderen Fehlern
        return False
