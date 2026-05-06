"""Auth-Cookie-Helper: gemeinsam genutzt von /auth/login und /account/credentials."""

from fastapi import Response

from web_api.config import Settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

# Pfad-Migrationsschuld: bis 2026-05-07 war REFRESH_COOKIE auf path="/auth/refresh"
# beschränkt. Für Server-Side-Silent-Refresh in `require_login` muss der Cookie auf
# jedem Request verfügbar sein → Path "/". Beim nächsten Schreib-/Löschvorgang
# räumen wir den alten Pfad mit auf, damit es keine Cookie-Doubletten gibt.
_LEGACY_REFRESH_COOKIE_PATH = "/auth/refresh"


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.delete_cookie(REFRESH_COOKIE, path=_LEGACY_REFRESH_COOKIE_PATH)
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE)
    response.delete_cookie(REFRESH_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=_LEGACY_REFRESH_COOKIE_PATH)