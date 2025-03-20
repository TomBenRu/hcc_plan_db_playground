"""This module provides a function to open Google Calendar in the default web browser."""
import webbrowser
from typing import Optional

def open_google_calendar_in_browser(calendar_id: Optional[str] = None) -> None:
    """Opens Google Calendar in the default web browser.

    Args:
        calendar_id: Optional calendar ID to open a specific calendar.
                    If None, opens the main Google Calendar view.
    """
    base_url = "https://calendar.google.com/"

    if calendar_id:
        url = f"{base_url}calendar/u/0?cid={calendar_id}"
    else:
        url = f"{base_url}calendar/u/0/"

    webbrowser.open(url)
