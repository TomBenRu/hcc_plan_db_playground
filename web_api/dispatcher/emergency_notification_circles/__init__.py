"""Dispatcher-UI: Notfall-Benachrichtigungs-Kreis pro Arbeitsort.

Eigene Whitelist parallel zum regulären `location_notification_circle`.
Aktivierung implicit: leere Whitelist ⇒ Auto-Mode (alle berechtigten
Personen werden benachrichtigt); Whitelist mit Members ⇒ Filter aktiv.
Kein Boolean-Toggle auf LocationOfWork.
"""
