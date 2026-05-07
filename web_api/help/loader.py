"""Loader fuer Hilfe-Topics: liest Markdown+YAML-Frontmatter aus dem Dateisystem.

Lade-Zeitpunkt:
- Standard: Lazy beim ersten Zugriff, dann gecached (Modul-globaler `dict`).
- Dev-Mode: Wenn `HCC_HELP_HOT_RELOAD=1` gesetzt ist, wird auf jeden Aufruf
  frisch von Disk gelesen — so muss der Server nicht neugestartet werden,
  wenn man an Markdown-Inhalten arbeitet.

Pfad-Konvention:
- ``web_api/help_content/<lang>/<category>/<topic>.md``
- Slug = Pfad nach `<lang>/`, ohne `.md` (z.B. ``employee/calendar``).
- Bilder sollen unter ``web_api/static/help_images/<slug>/<datei>.png``
  liegen (Static-Mount kommt mit dem ersten Bild — siehe `__init__.py`).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import frontmatter
import mistune

from web_api.help.models import HelpTopic

logger = logging.getLogger(__name__)


CONTENT_ROOT = Path(__file__).parent.parent / "help_content"
DEFAULT_LANG = "de"


_markdown_renderer = mistune.create_markdown(
    escape=False,                       # Inline-HTML in Topics ist erlaubt
    plugins=["strikethrough", "table", "url"],
)


def _is_hot_reload() -> bool:
    return os.environ.get("HCC_HELP_HOT_RELOAD") == "1"


def _slug_from_path(md_path: Path, lang_root: Path) -> str:
    """``help_content/de/employee/calendar.md`` → ``employee/calendar``."""
    rel = md_path.relative_to(lang_root).with_suffix("")
    return rel.as_posix()


def _normalize_roles(raw) -> tuple[str, ...]:
    if not raw:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(r) for r in raw)


def _strip_to_text(html: str) -> str:
    """Sehr einfache Plaintext-Extraktion fuer FTS in Phase 3.

    Wir koennten BeautifulSoup nehmen, aber das ist hier zu schwer fuer
    den Use-Case. Solange die Topics keine ``<script>``-Tags enthalten
    (tun sie nicht), reicht ein primitiver Tag-Stripper.
    """
    import re
    return re.sub(r"<[^>]+>", " ", html)


def _load_single(md_path: Path, lang_root: Path) -> HelpTopic | None:
    """Liest eine einzelne Markdown-Datei und rendert sie zu HelpTopic.

    Bei Parse-Fehlern wird geloggt und ``None`` zurueckgegeben — eine
    fehlerhafte Datei darf den Rest des Hilfesystems nicht killen.
    """
    try:
        post = frontmatter.load(md_path)
    except Exception as exc:
        logger.warning("Help-Topic %s konnte nicht geladen werden: %s", md_path, exc)
        return None

    slug = _slug_from_path(md_path, lang_root)
    body_html = _markdown_renderer(post.content) or ""
    body_text = _strip_to_text(body_html)

    title = post.metadata.get("title")
    if not title:
        logger.warning("Help-Topic %s ohne `title` im Frontmatter — uebersprungen", slug)
        return None

    return HelpTopic(
        slug=slug,
        title=str(title),
        roles=_normalize_roles(post.metadata.get("roles")),
        category=str(post.metadata.get("category") or "Allgemein"),
        body_html=body_html,
        body_text=body_text,
        anchors=tuple(str(a) for a in (post.metadata.get("anchors") or [])),
        order=int(post.metadata.get("order", 100)),
        updated=post.metadata.get("updated"),
        related=tuple(str(r) for r in (post.metadata.get("related") or [])),
    )


def _load_all(lang: str = DEFAULT_LANG) -> dict[str, HelpTopic]:
    lang_root = CONTENT_ROOT / lang
    if not lang_root.exists():
        logger.info("Help-Content-Verzeichnis %s existiert nicht — keine Topics geladen", lang_root)
        return {}

    topics: dict[str, HelpTopic] = {}
    for md_path in lang_root.rglob("*.md"):
        topic = _load_single(md_path, lang_root)
        if topic is not None:
            topics[topic.slug] = topic
    return topics


# ── oeffentliche API ─────────────────────────────────────────────────────────

_cache: dict[str, HelpTopic] | None = None


def get_all_topics() -> dict[str, HelpTopic]:
    """Liefert alle bekannten Topics, gecached (oder frisch im Dev-Mode)."""
    global _cache
    if _is_hot_reload():
        return _load_all()
    if _cache is None:
        _cache = _load_all()
    return _cache


def get_topic(slug: str) -> HelpTopic | None:
    return get_all_topics().get(slug)


def get_topics_for_role(role: str) -> list[HelpTopic]:
    """Topics, die fuer eine Rolle sichtbar sind, sortiert nach (category, order, title)."""
    topics = [t for t in get_all_topics().values() if not t.roles or role in t.roles]
    topics.sort(key=lambda t: (t.category, t.order, t.title))
    return topics