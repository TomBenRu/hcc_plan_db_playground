"""Auth-Router: /auth/login, /auth/refresh, /auth/logout, /auth/me."""

from datetime import datetime, timezone

import jwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Cookie,
    Depends,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.auth.cookies import ACCESS_COOKIE, REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from web_api.auth.dependencies import CurrentUser
from web_api.auth.password_policy import validate_password
from web_api.auth.password_reset import (
    build_reset_email,
    consume_token_and_set_password,
    create_reset_token,
    has_recent_token,
    verify_token,
)
from web_api.auth.service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from web_api.config import Settings, get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import schedule_emails
from web_api.models.web_models import WebUser
from web_api.rate_limit import limiter
from web_api.templating import templates

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _load_user_with_roles(session: Session, email: str) -> WebUser | None:
    return session.exec(
        select(WebUser)
        .where(WebUser.email == _normalize_email(email))
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
    session: Session = Depends(get_db_session),
):
    """Zeigt die Login-Seite an. Leitet direkt zum Dashboard weiter, wenn bereits eingeloggt."""
    stale_cookie = False
    if access_token:
        try:
            payload = decode_token(access_token, settings)
            if payload.get("type") == "access":
                # Signatur valide ist nicht genug: der User aus dem sub-Claim muss
                # noch in der DB existieren und aktiv sein. Sonst Redirect-Loop
                # mit /dashboard's require_login (z. B. nach DB-Wipe / User-Delete).
                user_id = payload.get("sub")
                user = session.get(WebUser, user_id) if user_id else None
                if user and user.is_active:
                    redirect_url = _validate_next_url(next_url) or "/dashboard"
                    return RedirectResponse(url=redirect_url, status_code=303)
                stale_cookie = True
        except jwt.PyJWTError:
            stale_cookie = True

    response = templates.TemplateResponse(
        "auth/login.html",
        {
            "request": request,
            "error": error,
            "prefill_email": prefill_email,
            "next_url": _validate_next_url(next_url),
        },
    )
    if stale_cookie:
        clear_auth_cookies(response)
    return response


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
        set_auth_cookies(response, access_tok, refresh_tok, settings)
        return {"access_token": access_tok, "token_type": "bearer"}

    if is_htmx:
        htmx_response = Response(status_code=200)
        htmx_response.headers["HX-Redirect"] = redirect_url
        set_auth_cookies(htmx_response, access_tok, refresh_tok, settings)
        return htmx_response

    # Regulärer Browser-Submit: POST-Redirect-GET (303)
    redirect_response = RedirectResponse(url=redirect_url, status_code=303)
    set_auth_cookies(redirect_response, access_tok, refresh_tok, settings)
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

    # Refresh-Tokens, die VOR der letzten Passwort-Änderung ausgestellt wurden,
    # sind ungültig (Reset oder Self-Change hat alle Sessions revoziert).
    token_iat = payload.get("iat")
    if token_iat is not None:
        pwd_changed = user.password_changed_at
        if pwd_changed.tzinfo is None:
            pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
        # 5s Toleranz gegen Uhren-Drift beim Ausstellen direkt nach einer Änderung
        if token_iat + 5 < int(pwd_changed.timestamp()):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                detail="Sitzung durch Passwort-Änderung beendet — bitte neu anmelden",
            )

    role_values = [r.value for r in user.roles]
    access = create_access_token(str(user.id), user.email, role_values, settings)
    new_refresh = create_refresh_token(str(user.id), settings)
    set_auth_cookies(response, access, new_refresh, settings)

    return {"access_token": access, "token_type": "bearer"}


@router.post("/logout")
def logout(_: CurrentUser):
    """Löscht Auth-Cookies und leitet zur Login-Seite weiter."""
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookies(response)
    return response


@router.get("/me")
def me(current_user: CurrentUser):
    """Gibt den aktuellen Benutzer zurück."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "roles": [r.value for r in current_user.roles],
        "person_id": str(current_user.person_id) if current_user.person_id else None,
    }


# ── Passwort vergessen / zurücksetzen ─────────────────────────────────────────


@router.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "error": None, "info": None, "prefill_email": None},
    )


@router.post("/forgot-password", response_class=HTMLResponse)
@limiter.limit("3/hour")
def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Sendet einen Reset-Link, falls die Email einem aktiven User zugeordnet ist.

    Antwort ist immer dieselbe (Erfolgs-Template), unabhängig davon, ob die Email
    existiert oder nicht — verhindert User-Enumeration.
    Pro User höchstens alle EMAIL_THROTTLE_MINUTES eine neue Mail.
    """
    user = _load_user_with_roles(session, email)

    if user is not None and user.is_active and not has_recent_token(session, user.id):
        token = create_reset_token(session, user)
        session.commit()
        payload = build_reset_email(user, token, settings)
        schedule_emails(background_tasks, [payload], session)

    info = (
        "Falls für diese Adresse ein Konto existiert, ist gerade eine E-Mail mit "
        "einem Reset-Link unterwegs. Prüfe ggf. den Spam-Ordner."
    )
    return templates.TemplateResponse(
        "auth/forgot_password.html",
        {"request": request, "error": None, "info": info, "prefill_email": None},
    )


@router.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(
    request: Request,
    token: str = Query(...),
    session: Session = Depends(get_db_session),
):
    user = verify_token(session, token)
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {
            "request": request,
            "token": token,
            "invalid_token": user is None,
            "errors": [],
        },
    )


@router.post("/reset-password", response_class=HTMLResponse)
@limiter.limit("5/hour")
def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    session: Session = Depends(get_db_session),
):
    """Verbraucht den Reset-Token und setzt das neue Passwort."""
    pre_user = verify_token(session, token)
    if pre_user is None:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "invalid_token": True, "errors": []},
        )

    errors: list[str] = []
    if password != password_confirm:
        errors.append("Die beiden Passwort-Eingaben stimmen nicht überein.")
    errors.extend(validate_password(password, pre_user.email))

    if errors:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "invalid_token": False, "errors": errors},
        )

    user = consume_token_and_set_password(session, token, password)
    if user is None:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "invalid_token": True, "errors": []},
        )

    session.commit()
    return RedirectResponse(
        url="/auth/login?prefill_email=" + user.email,
        status_code=status.HTTP_303_SEE_OTHER,
    )
