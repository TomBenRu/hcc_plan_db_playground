"""Desktop-API-Client: httpx-basierte Anbindung an die Web-API.

Konfiguration via Umgebungsvariable:
    DESKTOP_API_URL  (Standard: http://localhost:8000)

Login-Flow:
    client = get_api_client()
    client.login("dispatcher@example.com", "password")
    # ab jetzt senden alle Requests Authorization: Bearer <token>
"""

from __future__ import annotations

import os
from typing import Any

import requests
from requests import Response


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

    def login(self, email: str, password: str) -> None:
        """Authentifiziert den Desktop-Client und speichert den JWT."""
        response = self._session.post(
            f"{self._base_url}/auth/login",
            data={"username": email, "password": password},
            headers={"Accept": "application/json"},
        )
        _raise_for_status(response)
        self._access_token = response.json()["access_token"]

    def logout(self) -> None:
        self._access_token = None

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

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
        response = self._session.request(
            method,
            f"{self._base_url}{path}",
            headers=self._headers(json_body=has_body),
            **kwargs,
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
