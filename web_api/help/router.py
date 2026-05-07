"""Help-Router: Hilfeseiten-Uebersicht und Volltext-View einzelner Topics.

Sicherheits-Hinweis: Der Slug wird **nicht** als Filesystem-Pfad verwendet,
sondern als Dict-Key ueber das vorab geladene Topic-Dict. Damit ist Path-
Traversal definitionsgemaess ausgeschlossen — ``../etc/passwd`` ist einfach
kein registriertes Topic und liefert 404.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, HTTPException, status
from fastapi.requests import Request
from fastapi.responses import HTMLResponse

from web_api.auth.dependencies import LoggedInUser
from web_api.help import get_topic, get_topics_for_role
from web_api.help.models import HelpTopic
from web_api.templating import templates

router = APIRouter(prefix="/help", tags=["help"])


def _topics_visible_to_user(user) -> list[HelpTopic]:
    """Vereinigung aller Topics ueber die Rollen des Users.

    Ein Topic mit leerer Rollen-Liste (``roles: []`` oder weggelassen) ist
    fuer alle eingeloggten User sichtbar — z.B. fuer reine Allgemein-Topics.
    """
    seen: dict[str, HelpTopic] = {}
    for role in user.roles:
        for topic in get_topics_for_role(role.value):
            seen.setdefault(topic.slug, topic)
    return sorted(seen.values(), key=lambda t: (t.category, t.order, t.title))


def _group_by_category(topics: list[HelpTopic]) -> list[tuple[str, list[HelpTopic]]]:
    grouped: dict[str, list[HelpTopic]] = defaultdict(list)
    for t in topics:
        grouped[t.category].append(t)
    return sorted(grouped.items(), key=lambda kv: kv[0])


@router.get("", response_class=HTMLResponse)
def help_index(request: Request, user: LoggedInUser):
    """Hilfe-Uebersicht mit nach Kategorie gruppiertem TOC."""
    topics = _topics_visible_to_user(user)
    categories = _group_by_category(topics)
    return templates.TemplateResponse(
        "help/index.html",
        {
            "request": request,
            "user": user,
            "categories": categories,
            "total": len(topics),
        },
    )


@router.get("/popover/{slug:path}", response_class=HTMLResponse)
def help_popover(
    request: Request,
    user: LoggedInUser,
    slug: str,
    anchor: str | None = None,
):
    """HTMX-Popover-Endpoint: liefert ein Modal-Shell-Fragment fuer ``#modal-root``.

    Muss VOR der ``/{slug:path}``-Catch-All-Route stehen — sonst wuerde FastAPI
    ``popover/employee/availability`` als Topic-Slug interpretieren und 404
    liefern, weil ``popover/employee/availability`` kein registriertes Topic
    ist.
    """
    topic = get_topic(slug)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hilfe-Thema nicht gefunden")
    if topic.roles:
        user_roles = {r.value for r in user.roles}
        if not user_roles.intersection(topic.roles):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hilfe-Thema nicht gefunden")
    return templates.TemplateResponse(
        "help/_popover.html",
        {
            "request": request,
            "user": user,
            "topic": topic,
            "anchor": anchor or None,
        },
    )


@router.get("/{slug:path}", response_class=HTMLResponse)
def help_topic(request: Request, user: LoggedInUser, slug: str):
    """Volltext-View eines einzelnen Topics.

    ``{slug:path}`` erlaubt Slashes im Slug (z.B. ``employee/calendar``),
    ohne dass FastAPI den Pfad an `/` bricht.
    """
    topic = get_topic(slug)
    if topic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hilfe-Thema nicht gefunden")

    # Rollenfilter: leere roles-Liste = oeffentlich; sonst muss eine Rolle des Users matchen.
    if topic.roles:
        user_roles = {r.value for r in user.roles}
        if not user_roles.intersection(topic.roles):
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Hilfe-Thema nicht gefunden")

    related_topics = [t for t in (get_topic(s) for s in topic.related) if t is not None]

    return templates.TemplateResponse(
        "help/topic.html",
        {
            "request": request,
            "user": user,
            "topic": topic,
            "related": related_topics,
        },
    )