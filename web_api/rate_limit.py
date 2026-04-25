"""Geteilter slowapi-Limiter, importierbar aus Routern und main.py.

Eigenes Modul, damit Router den Limiter dekorieren können, ohne main.py
zu importieren (vermeidet zirkuläre Imports).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)