"""Desktop-API Auth: JWT-basierter DesktopUser-Dep (kein DB-Hit).

Im Gegensatz zum Web-UI, das `get_current_user` aus web_api.auth.dependencies
nutzt (DB-Fetch fuer WebUser + role_links), vertraut die Desktop-API dem
JWT komplett. Vorteile bei remote DB:

- Kein `SELECT WebUser` pro Request (~200ms RTT).
- Kein `selectinload(role_links)` pro Request (~200ms RTT).
- Zusammen: ~400ms pro Call gespart.

Trade-off: User-Deaktivierung oder Rollen-Widerruf werden erst mit dem
naechsten Token-Refresh wirksam (Access-Token-Lebensdauer, default
kurze Minuten). Fuer Dispatcher-/Admin-Zugriffe typischerweise
akzeptabel.

Die Desktop-Router nutzen das Objekt ausschliesslich als Auth-Guard
(`_: DesktopUser` — discarded). Wer den Auth-Kontext inhaltlich
braucht, bekommt die drei Felder id / email / roles aus dem JWT-Payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from web_api.auth.service import decode_token
from web_api.config import Settings, get_settings
from web_api.models.web_models import WebUserRole


# auto_error=False → wir kombinieren selbst Bearer + Cookie (analog Web-UI-Dep).
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


@dataclass(frozen=True)
class DesktopAuthContext:
    """Leichter Auth-Kontext aus dem JWT-Payload — kein DB-Hit."""

    id: UUID
    email: str
    roles: frozenset[WebUserRole]

    def has_any_role(self, *roles: WebUserRole) -> bool:
        return bool(self.roles & set(roles))


def _roles_from_payload(payload: dict) -> frozenset[WebUserRole]:
    """Wandelt die JWT-`roles`-Liste in WebUserRole-Set um.

    Unbekannte Rollen-Strings werden ignoriert — robust gegen Enum-
    Erweiterungen auf der Server-Seite, die die Client-Sicht ueberholen.
    """
    role_strings = payload.get("roles", []) or []
    valid = WebUserRole._value2member_map_  # type: ignore[attr-defined]
    return frozenset(WebUserRole(r) for r in role_strings if r in valid)


def _require_desktop_user(
    settings: Settings = Depends(get_settings),
    bearer_token: str | None = Depends(_oauth2_scheme),
    access_token: str | None = Cookie(default=None),
) -> DesktopAuthContext:
    token = bearer_token or access_token
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Nicht authentifiziert")

    try:
        payload = decode_token(token, settings)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token abgelaufen")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Ungueltiges Token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falscher Token-Typ")

    ctx = DesktopAuthContext(
        id=UUID(payload["sub"]),
        email=payload.get("email", ""),
        roles=_roles_from_payload(payload),
    )

    if not ctx.has_any_role(WebUserRole.dispatcher, WebUserRole.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung")
    return ctx


DesktopUser = Annotated[DesktopAuthContext, Depends(_require_desktop_user)]