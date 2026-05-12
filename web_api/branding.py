"""Zentrale Definition des Rollen-Brandings.

Single Source of Truth für Label, Akzentfarben und Tailwind-Klassen pro Rolle.
Wird genutzt:

- vom Dashboard-Router, um die Tile-Sektionen zu rendern
- vom `role_kicker`-Macro in `templates/_macros/branding.html`, das die
  Sidebar-Kicker (`● MITARBEITER`, `● DISPOSITION`, ...) konsistent rendert

Hex-Werte und Tailwind-Klassen sind direkt gespiegelt: `color` = Hex-String,
`dot_class` = Tailwind-Background-Utility derselben Farbe, `text_class` =
abgeschwächte Variante (`-300/80` oder `-400/80`) für den Kicker-Text.
"""

from web_api.models.web_models import WebUserRole

ROLE_BRANDING: dict[WebUserRole, dict[str, str]] = {
    WebUserRole.employee: {
        "label": "Mitarbeiter",
        "color": "#F97316",          # orange-500
        "color_light": "#FFF7ED",
        "dot_class": "bg-orange-500",
        "text_class": "text-orange-400/80",
    },
    WebUserRole.dispatcher: {
        "label": "Disposition",
        "color": "#38BDF8",          # sky-400
        "color_light": "#F0F9FF",
        "dot_class": "bg-sky-400",
        "text_class": "text-sky-300/80",
    },
    WebUserRole.admin: {
        "label": "Administration",
        "color": "#F43F5E",          # rose-500
        "color_light": "#FFF1F2",
        "dot_class": "bg-rose-500",
        "text_class": "text-rose-400/80",
    },
    WebUserRole.accountant: {
        "label": "Buchhaltung",
        "color": "#2DD4BF",          # teal-400
        "color_light": "#F0FDFA",
        "dot_class": "bg-teal-400",
        "text_class": "text-teal-300/80",
    },
}


PERSONAL_BRANDING: dict[str, str] = {
    "label": "Persönlich",
    "color": "#64748B",              # slate-500 — bewusst neutral gegenueber Rollen
    "color_light": "#F1F5F9",
    "dot_class": "bg-slate-500",
    "text_class": "text-slate-400/80",
}


def role_branding(role_key: str) -> dict[str, str]:
    """Liefert Branding-Daten fuer eine Rolle (string-key).

    Akzeptiert: 'employee', 'dispatcher', 'admin', 'accountant'.
    Fallback bei unbekanntem Key: Employee-Branding (defensiv, damit Templates
    nicht crashen, falls jemand einen falschen Key uebergibt).
    """
    try:
        role = WebUserRole(role_key)
    except ValueError:
        return ROLE_BRANDING[WebUserRole.employee]
    return ROLE_BRANDING.get(role, ROLE_BRANDING[WebUserRole.employee])
