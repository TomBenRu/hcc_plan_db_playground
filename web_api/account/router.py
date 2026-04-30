"""Account-Router: /account/profile (Person-Stammdaten), /account/credentials (Passwort + Email)."""

import jwt
from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from web_api.account.service import change_password, load_profile, update_profile
from web_api.auth.cookies import set_auth_cookies
from web_api.auth.dependencies import LoggedInUser
from web_api.auth.email_change import (
    build_notice_email,
    build_verify_email,
    cancel_pending_change,
    consume_token,
    create_email_change_token,
    has_recent_token,
    is_email_taken_by_other,
    normalize_email,
    verify_token,
)
from web_api.auth.service import create_access_token, create_refresh_token, decode_token
from web_api.config import Settings, get_settings
from web_api.dependencies import get_db_session
from web_api.email.service import schedule_emails
from web_api.rate_limit import limiter
from web_api.templating import templates

router = APIRouter(prefix="/account", tags=["account"])


@router.get("", include_in_schema=False)
def account_index():
    return RedirectResponse(url="/account/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile", response_class=HTMLResponse)
def profile_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    profile = load_profile(session, user)
    return templates.TemplateResponse(
        "account/profile.html",
        {
            "request": request,
            "user": user,
            "profile": profile,
            "active_tab": "profile",
            "saved": False,
            "errors": [],
        },
    )


@router.post("/profile", response_class=HTMLResponse)
def profile_update(
    request: Request,
    user: LoggedInUser,
    email: str = Form(...),
    phone_nr: str = Form(""),
    street: str = Form(""),
    postal_code: str = Form(""),
    city: str = Form(""),
    session: Session = Depends(get_db_session),
):
    errors: list[str] = []

    if user.person_id is None:
        errors.append("Mit diesem Konto ist kein Personenprofil verknüpft.")

    email_clean = email.strip()
    if not email_clean or "@" not in email_clean:
        errors.append("Bitte gib eine gültige E-Mail-Adresse an.")
    if len(email_clean) > 50:
        errors.append("Die E-Mail-Adresse darf höchstens 50 Zeichen haben.")
    if len(phone_nr.strip()) > 50:
        errors.append("Die Telefonnummer darf höchstens 50 Zeichen haben.")

    if errors:
        return templates.TemplateResponse(
            "account/profile.html",
            {
                "request": request,
                "user": user,
                "profile": load_profile(session, user),
                "active_tab": "profile",
                "saved": False,
                "errors": errors,
                "form_email": email_clean,
                "form_phone": phone_nr,
                "form_street": street,
                "form_postal_code": postal_code,
                "form_city": city,
            },
        )

    updated = update_profile(
        session,
        user,
        email=email_clean,
        phone_nr=phone_nr,
        street=street,
        postal_code=postal_code,
        city=city,
    )
    session.commit()

    return templates.TemplateResponse(
        "account/profile.html",
        {
            "request": request,
            "user": user,
            "profile": updated,
            "active_tab": "profile",
            "saved": True,
            "errors": [],
        },
    )


def _credentials_context(request: Request, user, **extra) -> dict:
    """Gemeinsamer Render-Context für die Credentials-Seite."""
    base = {
        "request": request,
        "user": user,
        "active_tab": "credentials",
        "password_saved": False,
        "password_errors": [],
        "email_info": None,
        "email_errors": [],
        "pending_email": user.pending_email,
    }
    base.update(extra)
    return base


@router.get("/credentials", response_class=HTMLResponse)
def credentials_page(request: Request, user: LoggedInUser):
    return templates.TemplateResponse(
        "account/credentials.html",
        _credentials_context(request, user),
    )


@router.post("/credentials/password", response_class=HTMLResponse)
@limiter.limit("10/hour")
def change_password_endpoint(
    request: Request,
    user: LoggedInUser,
    current_password: str = Form(...),
    new_password: str = Form(...),
    new_password_confirm: str = Form(...),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Ändert das Passwort des eingeloggten Users.

    Bei Erfolg wird password_changed_at aktualisiert (revoziert alte Refresh-Tokens),
    und die aktuelle Session bekommt frische Tokens — sonst würde der nächste
    Refresh den User ausloggen.
    """
    errors = change_password(
        session,
        user,
        current_password=current_password,
        new_password=new_password,
        new_password_confirm=new_password_confirm,
    )

    if errors:
        return templates.TemplateResponse(
            "account/credentials.html",
            _credentials_context(request, user, password_errors=errors),
        )

    session.commit()

    # Frische Tokens fuer die laufende Session ausstellen — der iat-Stempel
    # uebersteigt das gerade gesetzte password_changed_at.
    role_values = [r.value for r in user.roles]
    access_tok = create_access_token(str(user.id), user.email, role_values, settings)
    refresh_tok = create_refresh_token(str(user.id), settings)

    response = templates.TemplateResponse(
        "account/credentials.html",
        _credentials_context(request, user, password_saved=True),
    )
    set_auth_cookies(response, access_tok, refresh_tok, settings)
    return response


# ── Email-Change-Flow ─────────────────────────────────────────────────────────


@router.post("/credentials/email", response_class=HTMLResponse)
@limiter.limit("3/hour")
def request_email_change(
    request: Request,
    user: LoggedInUser,
    background_tasks: BackgroundTasks,
    new_email: str = Form(...),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
):
    """Startet eine Email-Wechsel-Anfrage. Zwei Mails: Verify (an neu) + Hinweis (an alt).

    Antwort ist immer dieselbe info-Meldung — verhindert User-Enumeration und
    Spam, wenn target == current oder target schon belegt ist.
    """
    target = normalize_email(new_email)
    errors: list[str] = []

    if not target or "@" not in target:
        errors.append("Bitte gib eine gültige E-Mail-Adresse an.")
    elif len(target) > 254:
        errors.append("Die E-Mail-Adresse ist zu lang (max. 254 Zeichen).")

    if errors:
        return templates.TemplateResponse(
            "account/credentials.html",
            _credentials_context(request, user, email_errors=errors),
        )

    # Anfragen ueber 5min-Throttle hinaus stillschweigend ignorieren.
    can_send = (
        target != normalize_email(user.email)
        and not is_email_taken_by_other(session, target, user.id)
        and not has_recent_token(session, user.id)
    )

    if can_send:
        old_email = user.email
        token = create_email_change_token(session, user, target)
        session.commit()
        schedule_emails(
            background_tasks,
            [
                build_verify_email(target, token, settings),
                build_notice_email(old_email, target, settings),
            ],
            session,
        )

    info = (
        f"Wenn die Adresse {target} verfügbar ist, ist gerade eine "
        "Bestätigungs-Mail unterwegs. Erst nach dem Klick auf den Link "
        "wird die Login-Adresse umgestellt."
    )
    return templates.TemplateResponse(
        "account/credentials.html",
        _credentials_context(request, user, email_info=info, pending_email=target if can_send else user.pending_email),
    )


@router.post("/credentials/email/cancel", response_class=HTMLResponse)
def cancel_email_change(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    """Bricht eine offene Email-Wechsel-Anfrage ab."""
    cancel_pending_change(session, user)
    session.commit()
    return templates.TemplateResponse(
        "account/credentials.html",
        _credentials_context(
            request, user,
            email_info="Anfrage zur Adressänderung wurde zurückgezogen.",
            pending_email=None,
        ),
    )


@router.get("/email-change/confirm", response_class=HTMLResponse)
def confirm_email_change_page(
    request: Request,
    token: str = Query(...),
    session: Session = Depends(get_db_session),
):
    """Zeigt die Bestätigungs-Seite. Verifiziert OHNE Verbrauch — die
    eigentliche Mutation passiert erst beim POST.

    Login ist hier NICHT vorausgesetzt: der User hat den Link evtl. auf einem
    anderen Gerät als sein Browser-Login geöffnet.
    """
    result = verify_token(session, token)
    if result is None:
        return templates.TemplateResponse(
            "account/email_change_confirm.html",
            {"request": request, "invalid_token": True},
        )
    user, target_email = result
    return templates.TemplateResponse(
        "account/email_change_confirm.html",
        {
            "request": request,
            "invalid_token": False,
            "email_taken": False,
            "success": False,
            "token": token,
            "target_email": target_email,
        },
    )


@router.post("/email-change/confirm", response_class=HTMLResponse)
@limiter.limit("5/hour")
def confirm_email_change(
    request: Request,
    token: str = Form(...),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    access_token: str | None = Cookie(default=None),
):
    """Verbraucht den Token und schaltet die Login-Email um."""
    pre = verify_token(session, token)
    if pre is None:
        return templates.TemplateResponse(
            "account/email_change_confirm.html",
            {"request": request, "invalid_token": True},
        )

    pre_user, target_email = pre
    if is_email_taken_by_other(session, target_email, pre_user.id):
        return templates.TemplateResponse(
            "account/email_change_confirm.html",
            {
                "request": request,
                "invalid_token": False,
                "email_taken": True,
                "target_email": target_email,
            },
        )

    consumed = consume_token(session, token)
    if consumed is None:
        return templates.TemplateResponse(
            "account/email_change_confirm.html",
            {"request": request, "invalid_token": True},
        )
    user, _old_email, new_email = consumed
    session.commit()

    # Best-Effort: Wenn der Confirm-Request mit aktivem Auth-Cookie desselben
    # Users kommt, refreshen wir die Tokens, damit der email-Claim aktuell ist.
    # Andernfalls (anderes Gerät) zeigen wir einen Hinweis auf neue Anmeldung.
    refresh_for_current_session = False
    if access_token:
        try:
            payload = decode_token(access_token, settings)
            if payload.get("type") == "access" and payload.get("sub") == str(user.id):
                refresh_for_current_session = True
        except jwt.PyJWTError:
            pass

    response = templates.TemplateResponse(
        "account/email_change_confirm.html",
        {
            "request": request,
            "invalid_token": False,
            "email_taken": False,
            "success": True,
            "new_email": new_email,
            "still_logged_in": refresh_for_current_session,
        },
    )

    if refresh_for_current_session:
        role_values = [r.value for r in user.roles]
        access_tok = create_access_token(str(user.id), user.email, role_values, settings)
        refresh_tok = create_refresh_token(str(user.id), settings)
        set_auth_cookies(response, access_tok, refresh_tok, settings)

    return response