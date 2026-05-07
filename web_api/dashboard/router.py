"""Dashboard-Router: rollenbasierte Kachelübersicht nach dem Login."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import Person
from web_api.auth.dependencies import LoggedInUser
from web_api.dashboard.service import resolve_tile_count
from web_api.dependencies import get_db_session
from web_api.models.web_models import WebUser, WebUserRole
from web_api.templating import templates

router = APIRouter(tags=["dashboard"])

# ── Tile-Definitionen je Rolle ────────────────────────────────────────────────
# icon_path: Heroicons outline, viewBox="0 0 24 24"

_ROLE_SECTIONS = {
    WebUserRole.employee: {
        "label": "Mitarbeiter",
        "color": "#F97316",
        "color_light": "#FFF7ED",
        "tiles": [
            {
                "title": "Mein Kalender",
                "desc": "Eigene Termine und Schichten einsehen",
                "url": "/employees/calendar",
                "icon": "M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z",
            },
            {
                "title": "Verfügbarkeit",
                "desc": "Verfügbarkeiten und Anmerkungen eintragen",
                "url": "/availability/",
                "icon": "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
            },
            {
                "title": "Absagen",
                "desc": "Termin absagen oder Ersatz finden",
                "url": "/cancellations/",
                "icon": "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z",
            },
            {
                "title": "Tauschbörse",
                "desc": "Termine tauschen oder Tausch-Anfragen verwalten",
                "url": "/swap-requests",
                "icon": "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
            },
            {
                "title": "Meine Angebote",
                "desc": "Eigene Einsprung-Angebote für unterbesetzte Termine einsehen",
                "url": "/offers/mine",
                "icon": "M7 11l5-5m0 0l5 5m-5-5v12",
            },
        ],
    },
    WebUserRole.dispatcher: {
        "label": "Disposition",
        "color": "#38BDF8",
        "color_light": "#F0F9FF",
        "tiles": [
            {
                "title": "Team-Pläne",
                "desc": "Pläne aller Teams einsehen und bearbeiten",
                "url": "/dispatcher/plan",
                "icon": "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
            },
            {
                "title": "Dienstplanung",
                "desc": "Planungsperioden anlegen und verwalten",
                "url": "/dispatcher/periods",
                "icon": "M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z",
            },
            {
                "title": "Reminder",
                "desc": "Erinnerungs-Gruppen verwalten",
                "url": "/dispatcher/notification-groups",
                "icon": "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
            },
            {
                "title": "Benachrichtigungskreise",
                "desc": "Empfängerkreis pro Arbeitsort eingrenzen",
                "url": "/dispatcher/notification-circles",
                "icon": "M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z",
            },
            {
                "title": "Vertretungen",
                "desc": "Absagen verwalten und Übernahmen genehmigen",
                "url": "/dispatcher/cancellations",
                "icon": "M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z",
            },
            {
                "title": "Tauschanfragen",
                "desc": "Tausch-Anfragen prüfen und bestätigen",
                "url": "/dispatcher/swap-requests",
                "icon": "M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4",
            },
            {
                "title": "Angebote",
                "desc": "Einsprung-Angebote für unterbesetzte Termine annehmen oder ablehnen",
                "url": "/offers/dispatcher",
                "icon": "M9 11l3 3L22 4M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11",
            },
        ],
    },
    WebUserRole.admin: {
        "label": "Administration",
        "color": "#F43F5E",
        "color_light": "#FFF1F2",
        "tiles": [
            {
                "title": "Benutzerverwaltung",
                "desc": "Zugänge anlegen, Rollen und Passwörter verwalten",
                "url": "/admin/users",
                "icon": "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
            },
            {
                "title": "Teams & Standorte",
                "desc": "Organisationsstruktur und Zuweisungen pflegen",
                "url": "/admin/teams",
                "icon": "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4",
            },
            {
                "title": "Projekt-Einstellungen",
                "desc": "Projektweite Konfiguration (z. B. Tageszeiten-Modus)",
                "url": "/admin/project-settings",
                "icon": "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
            },
            {
                "title": "E-Mail-Einstellungen",
                "desc": "SMTP-Server für den serverseitigen Mail-Versand",
                "url": "/admin/email-settings",
                "icon": "M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
            },
        ],
    },
    WebUserRole.accountant: {
        "label": "Buchhaltung",
        "color": "#2DD4BF",
        "color_light": "#F0FDFA",
        "tiles": [
            {
                "title": "Abrechnungsexport",
                "desc": "Daten filtern und als CSV oder Excel exportieren",
                "url": "/accounting/export",
                "icon": "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4",
            },
        ],
    },
}

# ── Persönliche Sektion (rollen-unabhängig, für alle eingeloggten User) ─────

_PERSONAL_SECTION = {
    "label": "Persönlich",
    "color": "#64748B",        # slate-500 — bewusst neutraler Ton gegenüber Rollen-Farben
    "color_light": "#F1F5F9",  # slate-100
    "tiles": [
        {
            "title": "Einstellungen",
            "desc": "Eigene Farben für Einsatzorte und weitere Präferenzen",
            "url": "/user/settings",
            "icon": "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
        },
    ],
}


# ── Hilfe-Sektion (rollen-unabhängig, Onboarding-Anker für neue User) ───────

_HELP_SECTION = {
    "label": "Hilfe & Support",
    "color": "#8B5CF6",        # violet-500 — bewusst eigenständig, kein Konflikt mit Rollen-Farben
    "color_light": "#F5F3FF",  # violet-50
    "tiles": [
        {
            "title": "Hilfe & Anleitungen",
            "desc": "Schritt-für-Schritt-Erklärungen zu allen Funktionen",
            "url": "/help",
            "icon": "M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093M12 17h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
        },
    ],
}


_MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
_DAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _today_formatted() -> str:
    today = datetime.now(timezone.utc)
    return f"{_DAYS_DE[today.weekday()]}, {today.day}. {_MONTHS_DE[today.month - 1]} {today.year}"


# ── Route ─────────────────────────────────────────────────────────────────────


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, user: LoggedInUser, session: Session = Depends(get_db_session)):
    sections = []
    for role, section in _ROLE_SECTIONS.items():
        if role not in user.roles:
            continue
        tiles = [
            {
                **tile,
                "color": section["color"],
                "color_light": section["color_light"],
                "count": resolve_tile_count(tile["url"], session, user),
            }
            for tile in section["tiles"]
        ]
        sections.append({**section, "tiles": tiles})

    # Persönliche Sektion für jeden eingeloggten User ans Ende hängen —
    # rollen-unabhängig, keine Badge-Counts.
    personal_tiles = [
        {
            **tile,
            "color": _PERSONAL_SECTION["color"],
            "color_light": _PERSONAL_SECTION["color_light"],
            "count": None,
        }
        for tile in _PERSONAL_SECTION["tiles"]
    ]
    sections.append({**_PERSONAL_SECTION, "tiles": personal_tiles})

    # Hilfe-Sektion ganz am Ende — Onboarding-Anker für neue User.
    help_tiles = [
        {
            **tile,
            "color": _HELP_SECTION["color"],
            "color_light": _HELP_SECTION["color_light"],
            "count": None,
        }
        for tile in _HELP_SECTION["tiles"]
    ]
    sections.append({**_HELP_SECTION, "tiles": help_tiles})

    # Anzeigename: Vor- und Zuname aus Person-Eintrag, Fallback auf E-Mail-Prefix
    display_name = user.email.split("@")[0].replace(".", " ").replace("_", " ").title()
    if user.person_id:
        person = session.get(Person, user.person_id)
        if person:
            display_name = f"{person.f_name} {person.l_name}"

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "sections": sections,
            "display_name": display_name,
            "today": _today_formatted(),
        },
    )


def _user_can_see_tile_url(user: WebUser, tile_url: str) -> bool:
    """True, wenn die URL in einer fuer diesen User aktiven Rolle als Tile registriert ist.

    Schutz gegen Information-Leak via `/dashboard/tile-badge?url=…`: ein
    Employee soll nicht den Dispatcher-Counter abfragen koennen.
    """
    for role, section in _ROLE_SECTIONS.items():
        if role not in user.roles:
            continue
        for tile in section["tiles"]:
            if tile["url"] == tile_url:
                return True
    return False


@router.get("/dashboard/tile-badge", response_class=HTMLResponse)
def tile_badge(
    request: Request,
    user: LoggedInUser,
    url: str = Query(..., min_length=1),
    session: Session = Depends(get_db_session),
):
    """HTMX-Polling-Endpoint fuer Tile-Counts. Liefert nur das Badge-Span-Wrapper.

    Wenn der User die URL nicht sehen darf (nicht in seinen Rollen-Tiles) oder
    wenn die URL gar nicht registriert ist, wird ein leerer Wrapper geliefert
    — HTMX-Polling laeuft trotzdem weiter, weil der Wrapper die hx-Attribute
    behaelt.
    """
    if _user_can_see_tile_url(user, url):
        count = resolve_tile_count(url, session, user)
    else:
        count = None
    return templates.TemplateResponse(
        "dashboard/partials/tile_badge.html",
        {"request": request, "tile_url": url, "count": count},
    )
