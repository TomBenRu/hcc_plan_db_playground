import sys

from pydantic import BaseModel


def total_size(obj, seen=None):
    """Berechnet die Gesamtspeichergröße eines Objekts und seiner Inhalte."""
    if seen is None:
        seen = set()

    obj_id = id(obj)
    if obj_id in seen:
        return 0
    seen.add(obj_id)

    size = sys.getsizeof(obj)

    # Wenn es sich um eine Pydantic-Klasse handelt
    if isinstance(obj, BaseModel):
        # Iteriere über die Felder
        for field in obj.__dict__.values():
            size += total_size(field, seen)
    elif isinstance(obj, dict):
        size += sum(total_size(k, seen) + total_size(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, frozenset)):
        size += sum(total_size(i, seen) for i in obj)

    return size