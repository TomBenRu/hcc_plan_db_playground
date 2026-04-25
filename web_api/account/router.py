"""Account-Router: /account/profile (Person-Stammdaten) und /account/credentials (Passwort)."""

from fastapi import APIRouter, Depends, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from web_api.account.service import change_password, load_profile, update_profile
from web_api.auth.cookies import set_auth_cookies
from web_api.auth.dependencies import LoggedInUser
from web_api.auth.service import create_access_token, create_refresh_token
from web_api.config import Settings, get_settings
from web_api.dependencies import get_db_session
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


@router.get("/credentials", response_class=HTMLResponse)
def credentials_page(request: Request, user: LoggedInUser):
    return templates.TemplateResponse(
        "account/credentials.html",
        {
            "request": request,
            "user": user,
            "active_tab": "credentials",
            "saved": False,
            "errors": [],
        },
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
            {
                "request": request,
                "user": user,
                "active_tab": "credentials",
                "saved": False,
                "errors": errors,
            },
        )

    session.commit()

    # Frische Tokens fuer die laufende Session ausstellen — der iat-Stempel
    # uebersteigt das gerade gesetzte password_changed_at.
    role_values = [r.value for r in user.roles]
    access_tok = create_access_token(str(user.id), user.email, role_values, settings)
    refresh_tok = create_refresh_token(str(user.id), settings)

    response = templates.TemplateResponse(
        "account/credentials.html",
        {
            "request": request,
            "user": user,
            "active_tab": "credentials",
            "saved": True,
            "errors": [],
        },
    )
    set_auth_cookies(response, access_tok, refresh_tok, settings)
    return response