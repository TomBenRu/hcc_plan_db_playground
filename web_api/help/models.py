"""Datenklassen fuer das Hilfesystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True, slots=True)
class HelpTopic:
    """Ein Hilfe-Topic, geladen aus einer Markdown-Datei mit YAML-Frontmatter.

    Der Slug ist die kanonische Adresse (Pfad ohne Sprache und ohne `.md`),
    z.B. ``employee/calendar`` fuer ``help_content/de/employee/calendar.md``.
    """

    slug: str
    title: str
    roles: tuple[str, ...]              # z.B. ("employee",) oder ("employee", "dispatcher")
    category: str                       # Gruppierung im TOC, z.B. "Mitarbeiter"
    body_html: str                      # bereits gerenderter HTML-Body
    body_text: str                      # Plain-Text fuer spaetere FTS (Phase 3)
    anchors: tuple[str, ...] = ()       # optionale Section-Anker, z.B. ("absage-frist",)
    order: int = 100                    # Sortier-Hint im TOC; kleinere Werte zuerst
    updated: date | None = None         # zuletzt aktualisiert (optional)
    related: tuple[str, ...] = field(default_factory=tuple)  # weitere Topic-Slugs
