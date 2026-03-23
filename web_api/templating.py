"""Zentraler Jinja2Templates-Singleton für die gesamte Web-API."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
