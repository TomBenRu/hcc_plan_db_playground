"""Admin-Router: projektweite Einstellungen."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import Person, Project
from web_api.admin.email_settings_service import (
    get_settings_or_none,
    upsert_settings,
)
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.dependencies import get_db_session
from web_api.email.config_loader import (
    EmailNotConfiguredError,
    SmtpConfig,
    load_smtp_config,
)
from web_api.email.crypto import (
    EmailDecryptionError,
    EmailEncryptionKeyMissingError,
)
from web_api.email.service import send_test_email
from web_api.models.web_models import WebUser
from web_api.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_admin_project(session: Session, user: WebUser) -> Project:
    """Lädt das vom Admin-User verwaltete Projekt.

    Vertrag: Genau ein Projekt pro Admin, erreichbar über
    `user.person_id → Person.admin_of_project_id`. Wirft 403, wenn der
    User keine Person-Verknüpfung oder keine Admin-Projekt-Zuordnung
    hat.
    """
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )
    person = session.get(Person, user.person_id)
    if person is None or person.admin_of_project_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Diesem Konto ist kein Projekt als Administrator zugeordnet",
        )
    project = session.get(Project, person.admin_of_project_id)
    if project is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Projekt nicht gefunden",
        )
    return project


# ── Projekt-Einstellungen ────────────────────────────────────────────────────


@router.get("/project-settings", response_class=HTMLResponse)
def admin_project_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Vollständige Einstellungs-Seite (erste Navigation)."""
    project = _get_admin_project(session, user)
    return templates.TemplateResponse(
        "admin/project_settings.html",
        {"request": request, "user": user, "project": project, "saved": False},
    )


@router.post("/project-settings", response_class=HTMLResponse)
def admin_update_project_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    use_simple_time_slots: str | None = Form(default=None),
):
    """HTMX-Swap-Ziel: speichert Toggle-Zustand und liefert Settings-Card zurück."""
    project = _get_admin_project(session, user)
    project.use_simple_time_slots = use_simple_time_slots is not None
    session.commit()
    session.refresh(project)
    return templates.TemplateResponse(
        "admin/partials/settings_card.html",
        {"request": request, "project": project, "saved": True},
    )


# ── E-Mail-Einstellungen (SMTP) ──────────────────────────────────────────────


def _email_form_context(request: Request, settings_row, *, saved: bool, error: str | None):
    """Gemeinsamer Kontext für die Form-Card und ihre Partial-Variante."""
    return {
        "request": request,
        "settings": settings_row,
        "has_settings": settings_row is not None,
        "saved": saved,
        "error": error,
    }


@router.get("/email-settings", response_class=HTMLResponse)
def admin_email_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Vollständige Einstellungs-Seite für SMTP-Konfiguration."""
    settings_row = get_settings_or_none(session)
    return templates.TemplateResponse(
        "admin/email_settings.html",
        {**_email_form_context(request, settings_row, saved=False, error=None), "user": user},
    )


@router.post("/email-settings", response_class=HTMLResponse)
def admin_save_email_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
    smtp_host: str = Form(...),
    smtp_port: int = Form(...),
    smtp_username: str = Form(default=""),
    smtp_password: str = Form(default=""),
    use_tls: str | None = Form(default=None),
    use_ssl: str | None = Form(default=None),
    email_from: str = Form(...),
    email_from_name: str = Form(default=""),
):
    """HTMX-Swap-Ziel: persistiert SMTP-Settings, liefert Form-Card zurück.

    Leeres Passwort-Feld behält den bestehenden Ciphertext — Standard-Pattern,
    damit der Admin nicht jedes Mal das Passwort neu eintippen muss.
    """
    try:
        settings_row = upsert_settings(
            session,
            smtp_host=smtp_host.strip(),
            smtp_port=smtp_port,
            smtp_username=smtp_username.strip(),
            smtp_password=smtp_password if smtp_password else None,
            use_tls=use_tls is not None,
            use_ssl=use_ssl is not None,
            email_from=email_from.strip(),
            email_from_name=email_from_name.strip() or None,
            updated_by_id=user.id,
        )
        error = None
    except EmailEncryptionKeyMissingError as exc:
        settings_row = get_settings_or_none(session)
        error = str(exc)

    return templates.TemplateResponse(
        "admin/partials/email_settings_form.html",
        _email_form_context(request, settings_row, saved=error is None, error=error),
    )


@router.post("/email-settings/test", response_class=HTMLResponse)
def admin_test_email_settings(
    request: Request,
    user: WebUser = require_role(WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Schickt eine Test-Mail an die Email-Adresse des eingeloggten Admins.

    Nutzt die aktuell in der DB persistierten Settings — der Admin sollte
    also vor dem Test einmal speichern. Wirft den SMTP-Fehler als Banner
    zurück, falls der Versand fehlschlägt.
    """
    try:
        smtp_config: SmtpConfig = load_smtp_config(session)
    except EmailNotConfiguredError as exc:
        return templates.TemplateResponse(
            "admin/partials/email_settings_test_result.html",
            {"request": request, "ok": False, "message": str(exc)},
        )
    except (EmailEncryptionKeyMissingError, EmailDecryptionError) as exc:
        return templates.TemplateResponse(
            "admin/partials/email_settings_test_result.html",
            {"request": request, "ok": False, "message": str(exc)},
        )

    try:
        send_test_email(smtp_config, user.email)
    except Exception as exc:
        return templates.TemplateResponse(
            "admin/partials/email_settings_test_result.html",
            {
                "request": request,
                "ok": False,
                "message": f"SMTP-Versand fehlgeschlagen: {exc}",
            },
        )

    return templates.TemplateResponse(
        "admin/partials/email_settings_test_result.html",
        {
            "request": request,
            "ok": True,
            "message": f"Test-Mail wurde an {user.email} versendet.",
        },
    )