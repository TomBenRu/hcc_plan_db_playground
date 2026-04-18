"""Persistente Ablage des Refresh-Tokens im OS-Keyring.

Die "Angemeldet bleiben"-Funktion speichert das Refresh-Token des angemeldeten
Users im Betriebssystem-Keyring (Windows Credential Manager, macOS Keychain,
Linux Secret Service). Dort ist es vom User-Login des Betriebssystems
verschluesselt.

Das Access-Token wird **nicht** persistiert — es laeuft zu schnell ab
(Minuten), der Gewinn lohnt das Risiko nicht. Nur der Refresh-Token landet
im Keyring.

Ein einziger Slot pro Geraet: der zuletzt "angemeldet gebliebene" User
ueberschreibt den vorigen. Das entspricht einer Single-User-Desktop-Annahme;
wer mehrere Profile auf demselben Geraet pflegen will, kann "Angemeldet
bleiben" abwaehlen und sich jedes Mal frisch einloggen.
"""

from __future__ import annotations

import keyring
import keyring.errors

# Service-Name identifiziert uns eindeutig im Keyring (Windows: zeigt als
# "Service" in Credential Manager). Nicht aendern ohne Migration, sonst
# finden alte Installationen ihren gespeicherten Token nicht mehr.
_SERVICE_NAME = "hcc-plan-desktop"

# Fixer "Username"-Slot — wir speichern den Token unter einem bekannten Key,
# nicht unter der E-Mail des Users. Grund: beim App-Start wissen wir noch
# nicht, wer gleich eingeloggt ist.
_TOKEN_SLOT = "refresh_token"


class TokenStoreError(Exception):
    """Keyring ist nicht verfuegbar (z. B. headless Linux ohne Secret Service)
    oder der Zugriff scheiterte anderweitig. Aufrufer sollte daraufhin in
    Nicht-Persistenz-Modus fallen (kein 'Angemeldet bleiben')."""


def save_refresh_token(token: str) -> None:
    """Speichert das Refresh-Token im Keyring. Ueberschreibt vorhandene Werte."""
    try:
        keyring.set_password(_SERVICE_NAME, _TOKEN_SLOT, token)
    except keyring.errors.KeyringError as exc:
        raise TokenStoreError(f"Konnte Token nicht speichern: {exc}") from exc


def load_refresh_token() -> str | None:
    """Liest das gespeicherte Refresh-Token, oder None falls keiner vorhanden.

    Gibt None auch zurueck, wenn der Keyring nicht verfuegbar ist — dann
    gilt: es ist halt kein Token gespeichert.
    """
    try:
        return keyring.get_password(_SERVICE_NAME, _TOKEN_SLOT)
    except keyring.errors.KeyringError:
        return None


def clear_refresh_token() -> None:
    """Loescht das gespeicherte Refresh-Token. Idempotent — keine Exception,
    wenn nichts gespeichert war."""
    try:
        keyring.delete_password(_SERVICE_NAME, _TOKEN_SLOT)
    except keyring.errors.PasswordDeleteError:
        # Nichts gespeichert — in Ordnung.
        pass
    except keyring.errors.KeyringError:
        # Keyring nicht verfuegbar — auch in Ordnung, nichts zu loeschen.
        pass