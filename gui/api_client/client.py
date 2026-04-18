"""Desktop-API-Client: requests-basierte Anbindung an die Web-API.

Konfiguration via Umgebungsvariable:
    DESKTOP_API_URL  (Standard: http://localhost:8000)

Login-Flow:
    client = get_api_client()
    client.login("dispatcher@example.com", "password", remember=True)
    # ab jetzt senden alle Requests Authorization: Bearer <token>

Silent-Login beim App-Start (wenn Refresh-Token im Keyring liegt):
    client = get_api_client()
    if client.try_silent_login():
        # Eingeloggt ohne Dialog
    else:
        # Login-Dialog zeigen

Refresh-Interceptor: Bei HTTP 401 wird einmalig /auth/refresh versucht;
klappt das, wird der urspruengliche Request wiederholt. Scheitert der
Refresh, wird die Authentifizierung (einschl. Keyring-Token) geloescht
und die Auth-Exception normal geworfen.
"""

from __future__ import annotations

import os
from typing import Any

import requests
from requests import Response

from gui.auth.token_store import (
    TokenStoreError,
    clear_refresh_token,
    load_refresh_token,
    save_refresh_token,
)


# ── Exceptions ────────────────────────────────────────────────────────────────


class ApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API {status_code}: {detail}")


class ApiAuthError(ApiError):
    """HTTP 401 oder 403 — Token fehlt, abgelaufen oder keine Berechtigung."""


class ApiNotFoundError(ApiError):
    """HTTP 404 — Ressource nicht gefunden."""


class ApiValidationError(ApiError):
    """HTTP 422 — Validierungsfehler (Eingabedaten)."""


class ApiServerError(ApiError):
    """HTTP 5xx — Serverfehler."""


# ── Client ────────────────────────────────────────────────────────────────────


_LOGIN_PATH = "/auth/login"
_REFRESH_PATH = "/auth/refresh"
_REFRESH_COOKIE = "refresh_token"


class DesktopApiClient:
    _instance: DesktopApiClient | None = None

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token: str | None = None
        self._session = requests.Session()

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> DesktopApiClient:
        if cls._instance is None:
            url = os.environ.get("DESKTOP_API_URL", "http://localhost:8000")
            cls._instance = cls(url)
        return cls._instance

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self, email: str, password: str, *, remember: bool = False) -> None:
        """Authentifiziert den Desktop-Client und speichert den JWT.

        remember=True: das Refresh-Token wird im OS-Keyring persistiert,
        damit beim naechsten App-Start ohne Dialog eingeloggt werden kann.
        remember=False: ein evtl. zuvor gespeicherter Refresh-Token wird
        geloescht (neuer User / Logout-Semantik).
        """
        response = self._session.post(
            f"{self._base_url}{_LOGIN_PATH}",
            data={"username": email, "password": password},
            headers={"Accept": "application/json"},
        )
        _raise_for_status(response)
        self._access_token = response.json()["access_token"]

        refresh_value = self._session.cookies.get(_REFRESH_COOKIE)
        if remember and refresh_value:
            try:
                save_refresh_token(refresh_value)
            except TokenStoreError:
                # Keyring nicht verfuegbar — still weiterlaufen; der User ist
                # in dieser Sitzung eingeloggt, muss beim naechsten Start nur
                # frisch Passwort eingeben.
                pass
        else:
            clear_refresh_token()

    def try_silent_login(self) -> bool:
        """Versucht, mit einem im Keyring gespeicherten Refresh-Token einen
        frischen Access-Token zu holen — ohne User-Interaktion.

        Returns True, wenn erfolgreich (Client ist danach eingeloggt).
        Returns False, wenn kein Token gespeichert war, der Refresh
        fehlschlug oder der Server nicht erreichbar ist.
        """
        stored = load_refresh_token()
        if not stored:
            return False
        # Cookie mit passendem Pfad injizieren — /auth/refresh erwartet
        # den Refresh-Token als httpOnly-Cookie.
        self._session.cookies.set(_REFRESH_COOKIE, stored, path=_REFRESH_PATH)
        try:
            response = self._session.post(
                f"{self._base_url}{_REFRESH_PATH}",
                headers={"Accept": "application/json"},
            )
        except requests.RequestException:
            return False
        if not response.ok:
            # Token abgelaufen oder invalidiert — aufraeumen.
            clear_refresh_token()
            self._session.cookies.clear()
            return False
        self._access_token = response.json()["access_token"]
        # Der Server hat via Set-Cookie ein rotiertes Refresh-Token geliefert;
        # aktualisiere den Keyring-Eintrag entsprechend.
        new_refresh = self._session.cookies.get(_REFRESH_COOKIE)
        if new_refresh and new_refresh != stored:
            try:
                save_refresh_token(new_refresh)
            except TokenStoreError:
                pass
        return True

    def _try_refresh_on_401(self) -> bool:
        """Interner Refresh-Versuch nach einem 401 in einem normalen Request.

        Unterschied zu try_silent_login: Wir starten nicht vom Keyring, sondern
        vom bereits in der Session-Cookie stehenden Refresh-Token. Schlaegt
        der Refresh fehl, wird alles aufgeraeumt (Keyring + Session-Cookies).
        """
        if not self._session.cookies.get(_REFRESH_COOKIE):
            return False
        try:
            response = self._session.post(
                f"{self._base_url}{_REFRESH_PATH}",
                headers={"Accept": "application/json"},
            )
        except requests.RequestException:
            return False
        if not response.ok:
            self._access_token = None
            clear_refresh_token()
            self._session.cookies.clear()
            return False
        self._access_token = response.json()["access_token"]
        new_refresh = self._session.cookies.get(_REFRESH_COOKIE)
        if new_refresh:
            try:
                save_refresh_token(new_refresh)
            except TokenStoreError:
                pass
        return True

    def logout(self) -> None:
        """Loescht Access-Token, Refresh-Cookie und Keyring-Eintrag."""
        self._access_token = None
        self._session.cookies.clear()
        clear_refresh_token()

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    @property
    def base_url(self) -> str:
        return self._base_url

    # ── HTTP-Basis ────────────────────────────────────────────────────────────

    def _headers(self, *, json_body: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if json_body:
            headers["Content-Type"] = "application/json"
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self._request("POST", path, json=json, **kwargs)

    def put(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self._request("PUT", path, json=json, **kwargs)

    def patch(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self._request("PATCH", path, json=json, **kwargs)

    def delete(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        return self._request("DELETE", path, json=json, **kwargs)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        has_body = "json" in kwargs and kwargs["json"] is not None
        url = f"{self._base_url}{path}"
        response = self._session.request(
            method, url, headers=self._headers(json_body=has_body), **kwargs,
        )
        # 401-Interceptor: einmaliger Refresh-Versuch + Retry. Schluss, wenn
        # es erneut 401 wird oder kein Refresh-Token im Zugriff ist. Auf dem
        # Refresh-Pfad selbst interveniert der Client nicht (Endlosschleife-Schutz).
        if (
            response.status_code == 401
            and path != _REFRESH_PATH
            and self._access_token is not None
            and self._try_refresh_on_401()
        ):
            response = self._session.request(
                method, url, headers=self._headers(json_body=has_body), **kwargs,
            )
        _raise_for_status(response)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()


# ── Hilfsfunktion ─────────────────────────────────────────────────────────────


def _raise_for_status(response: Response) -> None:
    if response.ok:
        return
    try:
        detail = response.json().get("detail", response.text)
    except Exception:
        detail = response.text
    sc = response.status_code
    if sc in (401, 403):
        raise ApiAuthError(sc, detail)
    elif sc == 404:
        raise ApiNotFoundError(sc, detail)
    elif sc == 422:
        raise ApiValidationError(sc, detail)
    elif sc >= 500:
        raise ApiServerError(sc, detail)
    else:
        raise ApiError(sc, detail)


# ── Modul-Level-Zugriff ───────────────────────────────────────────────────────


def get_api_client() -> DesktopApiClient:
    """Gibt die Singleton-Instanz des Desktop-API-Clients zurück."""
    return DesktopApiClient.get_instance()
