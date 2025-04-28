from enum import Enum


class FlagCategories(Enum):
    PERSON = 'person'
    EVENT = 'event'


class Gender(Enum):
    female = 'f'
    male = 'm'
    divers = 'd'


class Role(Enum):
    SUPERVISOR = 'supervisor'
    ADMIN = 'admin'
    DISPATCHER = 'dispatcher'
    EMPLOYEE = 'employee'
    APPRENTICE = 'apprentice'
    GUEST = 'guest'

    @classmethod
    def has_permission(cls, required_role: 'Role', user_role: 'Role') -> bool:
        """
        Überprüft, ob der Benutzer die erforderlichen Berechtigungen hat.
        Höhere Rollen habe automatisch die Berechtigungen niedrigerer Rollen.
        """
        role_hierarchy = {
            cls.GUEST: 1,
            cls.APPRENTICE: 2,
            cls.EMPLOYEE: 3,
            cls.DISPATCHER: 4,
            cls.ADMIN: 5,
            cls.SUPERVISOR: 6
        }
        return role_hierarchy.get(user_role, 0) >= role_hierarchy.get(required_role, 0)


# Enum für plan-api-remote access:
class TimeOfDay(Enum):
    morning = 'v'
    afternoon = 'n'
    whole_day = 'g'
