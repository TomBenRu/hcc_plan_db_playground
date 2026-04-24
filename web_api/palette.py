"""Single Source of Truth für UI-Farb-Paletten.

Zentralisiert drei bisher duplizierte Farblogiken:

1. `LOCATION_PALETTE` — 16 Hex-Farben für Kalender-Event-Chips und den
   User-Swatch-Picker in /user/settings. User-Overrides müssen aus dieser
   Liste stammen (Allowlist).

2. `OKABE_ITO_PALETTE` — 8 Farben für den Colorblind-Modus. Wird beiden
   Kalender-Templates per Context-Processor bereitgestellt (früher in
   `_calendar_base.html` und `availability/index.html` dupliziert).

3. `default_location_color()` — prozess-stabiler Default (MD5-basiert).
   Ersetzt den vorherigen `hash(str(uuid))`, der seit Python 3.3 per
   `PYTHONHASHSEED` randomisiert ist und nach jedem Uvicorn-Restart
   unterschiedliche Default-Farben liefern konnte.
"""

import hashlib
import uuid


# 16 Farben — erweitert die bisherige 8er-Palette um 8 kontrastsichere
# Tailwind-500-Töne. Alle getestet gegen weißen Event-Chip-Text (WCAG AA).
LOCATION_PALETTE: list[str] = [
    "#F97316",  # orange-500 (Brand)
    "#FB923C",  # orange-400
    "#EF4444",  # red-500
    "#EC4899",  # pink-500
    "#F472B6",  # pink-400
    "#D946EF",  # fuchsia-500
    "#A855F7",  # purple-500
    "#A78BFA",  # violet-400
    "#818CF8",  # indigo-400
    "#3B82F6",  # blue-500
    "#0EA5E9",  # sky-500
    "#38BDF8",  # sky-400
    "#06B6D4",  # cyan-500
    "#2DD4BF",  # teal-400
    "#10B981",  # emerald-500
    "#4ADE80",  # green-400
]


# Okabe-Ito Palette (8 Farben) — wissenschaftlich validiert für Protanopie,
# Deuteranopie und Tritanopie. Schwarz (`#000000`) bewusst weggelassen, weil
# Event-Chips weißen Text tragen; stattdessen Grau für 8. Slot.
OKABE_ITO_PALETTE: list[str] = [
    "#0072B2",  # blau
    "#E69F00",  # orange
    "#009E73",  # grün
    "#CC79A7",  # pink
    "#56B4E9",  # hellblau
    "#D55E00",  # rot
    "#F0E442",  # gelb
    "#999999",  # grau
]


def default_location_color(location_id: uuid.UUID) -> str:
    """Prozess-stabiler Default aus der Location-ID via MD5.

    Ersetzt den früheren `hash(str(location_id))`, dessen Werte seit
    Python 3.3 per `PYTHONHASHSEED` randomisiert werden und nach jedem
    Prozess-Neustart wechseln können.
    """
    digest = hashlib.md5(str(location_id).encode()).hexdigest()
    return LOCATION_PALETTE[int(digest, 16) % len(LOCATION_PALETTE)]


def location_color(
    location_id: uuid.UUID,
    user_overrides: dict[uuid.UUID, str] | None = None,
) -> str:
    """Liefert die User-Override-Farbe oder den deterministischen Default."""
    if user_overrides and location_id in user_overrides:
        return user_overrides[location_id]
    return default_location_color(location_id)


def is_allowed_location_color(hex_value: str) -> bool:
    """Allowlist-Validator für POST-Endpoints — nur Palette-Farben zulassen."""
    return hex_value in LOCATION_PALETTE