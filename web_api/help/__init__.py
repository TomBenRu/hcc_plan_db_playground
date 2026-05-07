"""Hilfesystem fuer das Web-UI.

Topics liegen als Markdown-Dateien mit YAML-Frontmatter unter::

    web_api/help_content/<lang>/<category>/<topic>.md

Bilder gehoeren unter::

    web_api/static/help_images/<slug>/<datei>.png

(Der Static-Mount wird erst dann angelegt, wenn das erste Bild eingecheckt
wird — bis dahin haben Topics nur Text + Code-Bloecke.)

Der Modul-Import ist nebenwirkungsfrei: Topics werden erst beim ersten
Aufruf von ``get_all_topics()`` von Disk gelesen (PEP 562 Lazy-Pattern).
Im Dev-Modus (Env-Var ``HCC_HELP_HOT_RELOAD=1``) wird der Cache
umgangen — Content-Aenderungen werden ohne Server-Neustart sichtbar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from web_api.help.models import HelpTopic

__all__ = ["HelpTopic", "get_topic", "get_all_topics", "get_topics_for_role"]


def __getattr__(name: str):
    """PEP 562 Lazy-Import: keine Disk-I/O beim Import des Pakets."""
    if name in ("get_topic", "get_all_topics", "get_topics_for_role"):
        from web_api.help import loader
        return getattr(loader, name)
    if name == "HelpTopic":
        from web_api.help.models import HelpTopic
        return HelpTopic
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")