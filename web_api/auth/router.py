"""Auth-Router: /auth/login, /auth/refresh, /auth/logout, /auth/me."""

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.auth.dependencies import CurrentUser
from web_api.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from web_api.config import Settings, get_settings
from web_api.dependencies import get_db_session
from web_api.models.web_models import WebUser
from web_api.templating import templates

router = APIRouter(prefix="/auth", tags=["auth"])

_ACCESS_COOKIE = "access_token"
_REFRESH_COOKIE = "refresh_token"


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        _ACCESS_COOKIE,
        access_token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        _REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth/refresh",
    )


def _load_user_with_roles(session: Session, email: str) -> WebUser | None:
    return session.exec(
        select(WebUser)
        .where(WebUser.email == email)
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()


def _validate_next_url(next_url: str | None) -> str | None:
    """Verhindert Open-Redirect: nur relative URLs ohne Protokoll erlaubt."""
    if next_url and next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return None


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    error: str | None = Query(default=None),
    prefill_email: str | None = Query(default=None),
    next_url: str | None = Query(default=None, alias="next"),
    access_token: str | None = Cookie(default=None),
    settings: Settings = Depends(get_settings),
):
    """Zeigt die Login-Seite an. Leitet direkt zum Dashboard weiter, wenn bereits eingeloggt."""
    if access_token:
        try:
            payload = decode_token(access_token, settings)
            if payload.get("type") == "access":
                redirect_url = _validate_next_url(next_url) or "/dashboard"
                return RedirectResponse(url=redirect_url, status_code=303)
        except jwt.PyJWTError:
            pass

    return templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "error": error,
            "prefill_email": prefill_email,
            "next_url": _validate_next_url(next_url),
        },
    )


@router.post("/login")
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    next_url: str | None = Query(default=None, alias="next"),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """OAuth2 Password Flow.

    - API-Clients (Accept: application/json) → JSON + httpOnly-Cookies
    - HTMX-Requests (HX-Request: true)       → HX-Redirect-Header
    - Browser-Forms                           → 303 See Other Redirect

    ?next= leitet nach erfolgreichem Login zu einer bestimmten URL weiter.
    """
    user = _load_user_with_roles(session, form.username)

    # ── Fehlerfälle ──
    if not user or not verify_password(form.password, user.hashed_password):
        return _login_failure(request, form.username, "Ungültige E-Mail-Adresse oder Passwort", next_url)
    if not user.is_active:
        return _login_failure(request, form.username, "Dieses Benutzerkonto ist deaktiviert", next_url)

    # ── Tokens erstellen ──
    role_values = [r.value for r in user.roles]
    access_tok = create_access_token(str(user.id), user.email, role_values, settings)
    refresh_tok = create_refresh_token(str(user.id), settings)

    # ?next= hat Vorrang, sonst Dashboard
    redirect_url = _validate_next_url(next_url) or "/dashboard"

    # ── Antwort je nach Client-Typ ──
    accepts_json = "application/json" in request.headers.get("accept", "")
    is_htmx = request.headers.get("HX-Request") == "true"

    if accepts_json:
        _set_auth_cookies(response, access_tok, refresh_tok, settings)
        return {"access_token": access_tok, "token_type": "bearer"}

    if is_htmx:
        htmx_response = Response(status_code=200)
        htmx_response.headers["HX-Redirect"] = redirect_url
        _set_auth_cookies(htmx_response, access_tok, refresh_tok, settings)
        return htmx_response

    # Regulärer Browser-Submit: POST-Redirect-GET (303)
    redirect_response = RedirectResponse(url=redirect_url, status_code=303)
    _set_auth_cookies(redirect_response, access_tok, refresh_tok, settings)
    return redirect_response


def _login_failure(
    request: Request,
    email: str,
    message: str,
    next_url: str | None = None,
) -> Response:
    """Gibt bei fehlerhaftem Login die passende Fehlerantwort zurück."""
    is_htmx = request.headers.get("HX-Request") == "true"
    accepts_json = "application/json" in request.headers.get("accept", "")

    if accepts_json:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=message)

    next_param = f"&next={next_url}" if next_url else ""

    if is_htmx:
        return templates.TemplateResponse(
            "auth/login.html",
            {
                "request": request,
                "error": message,
                "prefill_email": email,
                "next_url": _validate_next_url(next_url),
            },
            status_code=200,
        )

    # Browser-Form: Redirect zurück zur Login-Seite mit Fehlermeldung
    from urllib.parse import quote
    return RedirectResponse(
        url=f"/auth/login?error={quote(message)}&prefill_email={quote(email)}{next_param}",
        status_code=303,
    )


@router.post("/refresh")
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Erneuert den Access-Token anhand des Refresh-Tokens (httpOnly-Cookie)."""
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Kein Refresh-Token")

    try:
        payload = decode_token(refresh_token, settings)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh-Token abgelaufen")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Ungültiger Refresh-Token")

    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Falscher Token-Typ")

    user = session.exec(
        select(WebUser)
        .where(WebUser.id == payload["sub"])
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()
    if not user or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Benutzer nicht gefunden oder inaktiv",
        )

    role_values = [r.value for r in user.roles]
    access = create_access_token(str(user.id), user.email, role_values, settings)
    new_refresh = create_refresh_token(str(user.id), settings)
    _set_auth_cookies(response, access, new_refresh, settings)

    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, _: CurrentUser):
    """Löscht Auth-Cookies (Client-seitige Token-Invalidierung)."""
    response.delete_cookie(_ACCESS_COOKIE)
    response.delete_cookie(_REFRESH_COOKIE, path="/auth/refresh")


@router.get("/me")
def me(current_user: CurrentUser):
    """Gibt den aktuellen Benutzer zurück."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "roles": [r.value for r in current_user.roles],
        "person_id": str(current_user.person_id) if current_user.person_id else None,
    }
