"""FastAPI-Dependencies für Auth: get_current_user, require_login, require_role."""

from typing import Annotated
from urllib.parse import urlparse

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.auth.service import decode_token
from web_api.config import Settings, get_settings
from web_api.dependencies import get_db_session
from web_api.exceptions import LoginRequired
from web_api.models.web_models import WebUser, WebUserRole, WebUserRoleLink

# auto_error=False → wir kombinieren selbst Bearer + Cookie
_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _load_user_from_token(
    token: str,
    session: Session,
    settings: Settings,
) -> WebUser:
    """Dekodiert Token und lädt User mit eager-geladenen role_links.

    Wirft HTTPException(401) bei ungültigem Token oder inaktivem User.
    """
    try:
        payload = decode_token(token, settings)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token abgelaufen")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Ungültiges Token")

    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falscher Token-Typ")

    user = session.exec(
        select(WebUser)
        .where(WebUser.id == payload["sub"])
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()

    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer nicht gefunden oder inaktiv",
        )
    return user


def get_current_user(
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    bearer_token: str | None = Depends(_oauth2_scheme),
    access_token: str | None = Cookie(default=None),
) -> WebUser:
    """Für API-Endpoints: wirft 401 bei fehlendem/ungültigem Token."""
    token = bearer_token or access_token
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Nicht authentifiziert")
    return _load_user_from_token(token, session, settings)


def _build_next_url(request: Request) -> str:
    """Berechnet das `next`-Ziel für Login-Redirects.

    GET-Routen sind selbst ein gültiges Redirect-Target → Path+Query nehmen.
    Mutations-Routen (POST/PATCH/PUT/DELETE) sind kein gültiges GET-Target →
    Referer-Header heranziehen, sonst Dashboard. Loop-Guard gegen `/auth/`-
    Pfade verhindert Login→Login-Schleifen.
    """
    if request.method == "GET":
        path = request.url.path
        query = request.url.query
        candidate = f"{path}?{query}" if query else path
    else:
        referer = request.headers.get("referer", "")
        try:
            parsed = urlparse(referer)
        except ValueError:
            parsed = None
        if parsed and parsed.path and parsed.path.startswith("/"):
            candidate = f"{parsed.path}?{parsed.query}" if parsed.query else parsed.path
        else:
            return "/dashboard"

    if candidate.startswith("/auth/"):
        return "/dashboard"
    return candidate


def require_login(
    request: Request,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    bearer_token: str | None = Depends(_oauth2_scheme),
    access_token: str | None = Cookie(default=None),
) -> WebUser:
    """Für Browser-Routen: leitet bei fehlendem Token zu /auth/login?next=... weiter."""
    token = bearer_token or access_token
    if not token:
        raise LoginRequired(next_url=_build_next_url(request))
    try:
        return _load_user_from_token(token, session, settings)
    except HTTPException:
        raise LoginRequired(next_url=_build_next_url(request))


CurrentUser = Annotated[WebUser, Depends(get_current_user)]
LoggedInUser = Annotated[WebUser, Depends(require_login)]


def require_role(*roles: WebUserRole):
    """Dependency-Factory: erlaubt nur Benutzer mit mindestens einer der angegebenen Rollen.

    Baut auf `LoggedInUser` (= `require_login`), damit fehlende/abgelaufene Tokens
    LoginRequired werfen (→ Redirect zur Login-Seite, in HTMX-Form via HX-Redirect).
    Würde der Sub-Dep `CurrentUser` verwendet, wäre die Antwort ein nackter 401
    ohne Login-Flow — der ist dem Desktop-API-Pfad (`/api/v1/...`) vorbehalten.
    """

    def _check(current_user: LoggedInUser) -> WebUser:
        if not current_user.has_any_role(*roles):
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Keine Berechtigung")
        return current_user

    return Depends(_check)